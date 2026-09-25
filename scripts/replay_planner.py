#!/usr/bin/env python3
"""Replay five live Planner inputs at call-index quartiles through a teacher.

Uses exact recorded messages and sampling settings. Reconstructs native evidence
and validates its prompt byte-for-byte before inference. Candidate construction
is a static preview only; this script never dispatches molecular work.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

from audit_fixed import score
from trex import planner
from trex.archive import Archive
from trex.candidate_builder import BuilderConfig, build_candidates
from trex.capability_registry import default_registry
from trex.schemas import EvidenceSummary, LLMCallRecord


def digest(messages):
    return hashlib.sha256((messages[0]["content"]+"\n"+messages[1]["content"]).encode()).hexdigest()[:16]


def evaluate(raw, evidence, payload):
    refs = planner._allowed_evidence_refs(evidence, payload["active_hypotheses"])
    labels, corrected = score(raw, dict(role="planner", refs=refs))
    obj = planner._extract_json(raw or "")
    effective = obj if labels["schema_valid"] else corrected
    candidates = []
    confidence_gate = False
    if effective is not None:
        effective = planner._coerce_legacy_shape(effective)
        confidence_gate = not effective.get("abstain") and effective.get("confidence", 0) >= planner.PlannerCallConfig().confidence_threshold
        cards = planner._materialize_cards(effective, target_id=evidence.target_id,
            tick_id=int(evidence.tick_id.removeprefix("v7r")))
        allowed = set(payload["available_families_this_cluster"])
        cards = planner._filter_cards_to_available(cards, allowed)
        ids = {card.hypothesis_id for card in cards}
        registry = default_registry()
        cfg = BuilderConfig(healthy_backends_override=tuple(sorted(allowed)),
            unavailable_backends_override=tuple(sorted(set(planner.VALID_ACTION_FAMILIES)-allowed)))
        constructed = build_candidates(cards, evidence, cfg=cfg, registry=registry,
            include_warmstart=False, parent_pdb_available=True)
        # Exclude deterministic supplementation unrelated to teacher cards.
        candidates = [asdict(c) for c in constructed if ids.intersection(c.hypothesis_ids)]
    return dict(labels=labels, passes_live_confidence_and_abstention_gate=confidence_gate,
        deterministic_corrected_object=corrected if not labels["schema_valid"] else None,
        candidate_preview=candidates,
        n_static_feasible_candidates=sum(all(c["feasibility"][key] for key in
            ["backend_healthy", "compiler_ok", "cost_ok", "route_cap_ok", "verifier_ok"]) for c in candidates),
        note="Native builder preview with staged-backend and parent-artifact availability assumed. No dispatch, queue mutation or molecular outcome was evaluated.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_arm", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:12004/v1")
    parser.add_argument("--model", default="Qwen/Qwen3.6-27B-FP8")
    parser.add_argument("--score-source-only", action="store_true")
    args = parser.parse_args()
    archive = Archive(args.source_arm / "campaign")
    evidence_by_tick = {e.tick_id:e for e in archive.iter_records(EvidenceSummary)}
    calls = [c for c in archive.iter_records(LLMCallRecord) if c.role == "planner"]
    assert len(calls) >= 5, "Need at least five actual Planner calls"
    selected = [calls[round((len(calls)-1)*q/4)] for q in range(5)]
    wires = {}
    for path in sorted((args.source_arm / "wire").glob("*.json")):
        record = json.loads(path.read_text())
        messages = (record["request"].get("json") or {}).get("messages", [])
        if len(messages) >= 2:
            wires.setdefault(digest(messages), []).append((path.name, record))
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output / "cases.jsonl"
    if output.exists():
        raise SystemExit("Replay cases already exist; preserve before rerunning")
    for call in selected:
        source_files = wires[call.prompt_hash]
        source = source_files[0][1]
        request = source["request"]["json"]
        messages = request["messages"]
        user = messages[1]["content"]
        payload = json.loads(user[user.index("{"):])
        evidence = evidence_by_tick[call.tick_id]
        rebuilt = planner.build_user_prompt(evidence, payload["active_hypotheses"], payload["seed_action_families"],
            available_families=payload["available_families_this_cluster"],
            recent_critic_flags=payload.get("recent_critic_flags_last_tick"))
        assert rebuilt == user, f"Evidence/prompt mismatch at {call.tick_id}"
        assert messages[0]["content"] == planner.planner_system_prompt(), "Unexpected Planner system prompt"
        row = dict(id=f"{args.source_arm.name}_{call.tick_id}", source_tick=call.tick_id,
            selection="five evenly time-ordered call-index quantiles; all outcomes retained",
            source_model=call.model, teacher_model=None if args.score_source_only else args.model,
            source_wire_files=[name for name,_ in source_files], source_native_outcome=asdict(call),
            prompt_hash=call.prompt_hash, exact_prompt_reconstruction=True, messages=messages,
            split="pilot_development_review_required_not_held_out",
            warning="Teacher suggestions are not optimal actions or measured counterfactual molecular outcomes. Do not train on unreviewed failures.")
        source_choices = source.get("response", {}).get("json", {}).get("choices", [])
        if source_choices:
            original = source_choices[0]["message"].get("content") or ""
            row.update(source_first_response=original, source_first_score=evaluate(original, evidence, payload))
        else:
            row["source_first_response_unavailable"] = source["state"]
        completed = [(name, wire) for name, wire in source_files
                     if wire.get("response", {}).get("json", {}).get("choices")]
        if completed and completed[-1][0] != source_files[0][0]:
            name, wire = completed[-1]
            raw = wire["response"]["json"]["choices"][0]["message"].get("content") or ""
            row.update(source_last_observed_wire=name, source_last_observed_response=raw,
                       source_last_observed_score=evaluate(raw, evidence, payload))
        if not args.score_source_only:
            request = {**request, "model": args.model}
            started = time.monotonic()
            req = urllib.request.Request(args.base_url.rstrip("/")+"/chat/completions",
                data=json.dumps(request).encode(), headers={"Content-Type":"application/json"})
            try:
                try:
                    response = urllib.request.urlopen(req, timeout=90)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    body = response.read()
                    result = json.loads(body)
                    row.update(http_status=response.status, response=result)
                choice = next(iter(result.get("choices", [])), {})
                if choice:
                    raw = choice.get("message", {}).get("content") or ""
                    row.update(teacher_text=raw, teacher_score=evaluate(raw, evidence, payload))
                else:
                    row["replay_error"] = f"No model completion: HTTP {row['http_status']}"
            except (OSError, ValueError) as error:
                row["replay_error"] = f"{type(error).__name__}: {error}"
            row["latency_s"] = time.monotonic()-started
        with output.open("a") as stream:
            stream.write(json.dumps(row)+"\n")
        print(json.dumps({k:row[k] for k in ["id", "exact_prompt_reconstruction", "replay_error"] if k in row}), flush=True)


if __name__ == "__main__":
    main()

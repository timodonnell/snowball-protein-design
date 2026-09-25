#!/usr/bin/env python3
"""Replay native fixed-case validators on exact recorded responses, without GPUs.

Use PYTHONHASHSEED=0 and the pinned T-REX checkout. This exposes first-response
failures hidden by deterministic repair, and checks Planner parameter budgets
which are enforced later than the Planner schema. Scores are interface labels,
not molecular quality labels. The nine public fixtures are evaluation-only.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path

from benchmarks.llm_validation import planner_validation as pv
from benchmarks.llm_validation import supervisor_validation as sv
from trex import planner, supervisor
from trex.capability_registry import default_registry, validate_config_delta


def prompt_hash(messages):
    # A corrective Supervisor request has more turns. Retain its original pair
    # for fixture matching, while separately recording that it was a retry.
    return hashlib.sha256(json.dumps(messages[:2], sort_keys=True).encode()).hexdigest()


def contexts():
    output = {}
    for build in pv.CASES:
        name, evidence = build("vllm/Qwen/Qwen3.6-27B-FP8")
        user = planner.build_user_prompt(evidence, [], list(pv.VALID_ACTION_FAMILIES))
        messages = [dict(role="system", content=planner.planner_system_prompt()),
                    dict(role="user", content=user)]
        refs = planner._allowed_evidence_refs(evidence, [])
        output[prompt_hash(messages)] = dict(case=name, role="planner", refs=refs)
    for name, build_e, build_h, expectations in sv.CASES:
        _, evidence = build_e("vllm/Qwen/Qwen3.6-27B-FP8")
        hypotheses = build_h(evidence.target_id)
        candidates = sv.candidates_for_hyps(hypotheses)
        messages = [dict(role="system", content=supervisor.supervisor_system_prompt()),
                    dict(role="user", content=supervisor.build_user_prompt(evidence, hypotheses, candidates))]
        output[prompt_hash(messages)] = dict(case=name, role="supervisor",
            refs=supervisor._allowed_evidence_refs(evidence, hypotheses, candidates),
            candidates={c.candidate_id: c for c in candidates},
            hypotheses={h.hypothesis_id: h for h in hypotheses}, expectations=expectations)
    return output


def score(raw, context):
    module = planner if context["role"] == "planner" else supervisor
    try:
        exact = json.loads(raw)
        json_only = isinstance(exact, dict)
    except (ValueError, TypeError):
        json_only = False
    obj = module._extract_json(raw or "")
    labels = dict(json_only=json_only, extracted_json=obj is not None,
                  schema_valid=False, schema_reason="parse_fail")
    if obj is None:
        return labels, None
    items = obj.get("cards" if context["role"] == "planner" else "candidate_decisions")
    labels.update(abstain=obj.get("abstain"), emitted_item_count=len(items) if isinstance(items, list) else None)
    if context["role"] == "planner":
        ok, why = planner._validate_schema(obj, allowed_evidence_refs=context["refs"])
        labels.update(schema_valid=ok, schema_reason=why)
        repaired = copy.deepcopy(obj)
        repairs = []
        if not ok:
            repaired, repairs = planner._repair_planner_schema_drift(
                repaired, allowed_evidence_refs=context["refs"])
        repair_ok, repair_why = planner._validate_schema(repaired, allowed_evidence_refs=context["refs"])
        labels.update(deterministic_repair_valid=repair_ok, repair_reason=repair_why, repairs=repairs)
        config_checks = []
        registry = default_registry()
        cards = obj.get("cards", [])
        for i, card in enumerate(cards if isinstance(cards, list) else []):
            if not isinstance(card, dict):
                continue
            suggestions = card.get("config_delta_suggestions") or {}
            if not isinstance(suggestions, dict):
                config_checks.append(dict(card=i, family=None, valid=False,
                                          reasons=["config_delta_suggestions_not_object"]))
                continue
            for family, config in suggestions.items():
                capability = registry.get(family)
                if capability is None or not isinstance(config, dict):
                    valid, reasons = False, ["unknown_family_or_invalid_config"]
                else:
                    valid, reasons = validate_config_delta(capability, config)
                config_checks.append(dict(card=i, family=family, valid=valid, reasons=reasons))
        applicable = isinstance(cards, list) and (bool(cards) or obj.get("abstain") is True)
        labels.update(config_checks=config_checks, config_check_applicable=applicable,
            all_configs_valid=all(c["valid"] for c in config_checks) if applicable else None)
        return labels, repaired if repair_ok else None
    candidates, hypotheses = context["candidates"], context["hypotheses"]
    original_keys = set(obj)
    ok, why = supervisor._validate_schema(obj, set(candidates),
        allowed_evidence_refs=context["refs"], candidate_by_id=candidates,
        hypothesis_by_id=hypotheses)
    # This native validator fills optional/defaulted fields in place. Expose
    # those defaults, and use its effective abstention/decision values.
    items = obj.get("candidate_decisions")
    labels.update(schema_valid=ok, schema_reason=why,
                  native_schema_defaults={k:obj[k] for k in obj.keys()-original_keys},
                  abstain=obj.get("abstain"),
                  emitted_item_count=len(items) if isinstance(items, list) else None,
                  mixture_assessment=sv.assess_mode_mixture(obj.get("mode_mixture") or {}, context["expectations"])
                  if ok else {"all_ok": False, "reason": "invalid_schema"})
    return labels, obj if ok else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wire", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--arm", required=True)
    args = parser.parse_args()
    ctx = contexts()
    rows, excluded, seen = [], [], Counter()
    previous_prompt, request_shapes, attempt = None, set(), 0
    for path in sorted(args.wire.glob("*.json")):
        call = json.loads(path.read_text())
        request = call["request"].get("json") or {}
        messages = request.get("messages", [])
        if not messages:
            continue
        digest = prompt_hash(messages)
        context = ctx.get(digest)
        if context is None:
            excluded.append(path.name)
            continue
        choice = next(iter(call.get("response", {}).get("json", {}).get("choices", [])), {})
        raw = choice.get("message", {}).get("content", "")
        labels, corrected = score(raw, context)
        retry = any(m["role"] == "assistant" for m in messages)
        key = (context["role"], context["case"])
        # The pinned suite interleaves cases within each repeat. Consecutive
        # requests for the same original prompt are HTTP/model repair attempts,
        # not additional benchmark repetitions.
        if digest != previous_prompt:
            seen[key] += 1
            previous_prompt, request_shapes, attempt = digest, set(), 0
        else:
            attempt += 1
        shape = json.dumps(request, sort_keys=True)
        sdk_retry = shape in request_shapes
        request_shapes.add(shape)
        rows.append(dict(id=call["call_id"], arm=args.arm, role=context["role"],
            case=context["case"], repeat=seen[key]-1, is_model_repair_retry=retry,
            is_sdk_retry=sdk_retry, http_attempt=attempt, http_latency_s=call.get("latency_s"),
            http_status=call.get("status"),
            within_controller_timeout=(call.get("status") == 200
                and call.get("latency_s") is not None and call["latency_s"] < 90),
            split="public_fixed_evaluation_do_not_train", prompt_sha256=digest,
            wire_file=path.name, messages=messages, response=raw,
            finish_reason=choice.get("finish_reason"), labels=labels,
            deterministic_corrected_object=corrected if not labels["schema_valid"] else None))
    # Fail loudly if tokenization/prompt-generation differences broke matching.
    if len(seen) != len(ctx) or any(n != 3 for n in seen.values()):
        raise SystemExit(f"Expected nine exact prompts with three primary calls each; matched {dict(seen)}. Check PYTHONHASHSEED=0 and completed reports.")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "responses.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    summaries = {}
    for role in ["planner", "supervisor"]:
        primary = [r for r in rows if r["role"] == role and r["http_attempt"] == 0]
        summaries[role] = dict(n=len(primary), json_only=sum(r["labels"]["json_only"] for r in primary),
            schema_valid_before_repair=sum(r["labels"]["schema_valid"] for r in primary),
            timely_schema_valid=sum(r["labels"]["schema_valid"] and r["within_controller_timeout"] for r in primary),
            late_http_responses=sum(r["http_latency_s"] is not None and r["http_latency_s"] >= 90 for r in primary),
            abstaining_primary_responses=sum(r["labels"].get("abstain") is True for r in primary),
            schema_valid_nonabstaining_with_items=sum(r["labels"]["schema_valid"]
                and r["labels"].get("abstain") is False and (r["labels"].get("emitted_item_count") or 0) > 0 for r in primary),
            schema_failure_reasons=dict(Counter(r["labels"]["schema_reason"] for r in primary if not r["labels"]["schema_valid"])),
            length_terminated=sum(r["finish_reason"] == "length" for r in primary))
        if role == "planner":
            summaries[role]["all_configs_valid"] = sum(r["labels"].get("all_configs_valid") is True for r in primary)
            summaries[role]["schema_and_configs_valid"] = sum(r["labels"]["schema_valid"] and r["labels"].get("all_configs_valid") is True for r in primary)
        else:
            summaries[role]["primary_responses_using_native_defaults"] = sum(bool(r["labels"].get("native_schema_defaults")) for r in primary)
            summaries[role]["mixture_aligned_schema_valid_primary"] = sum(r["labels"]["schema_valid"]
                and r["labels"]["mixture_assessment"]["all_ok"] for r in primary)
    report = dict(arm=args.arm, roles=summaries, n_http_calls=len(rows),
        n_model_repair_retries=sum(r["is_model_repair_retry"] for r in rows),
        n_sdk_retries=sum(r["is_sdk_retry"] for r in rows),
        matched_prompt_sha256=sorted(ctx), excluded_nonfixture_calls=len(excluded))
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

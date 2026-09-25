#!/usr/bin/env python3
"""Link real campaign decisions to wire traces, scheduling and descendants.

This is a review index for prospective SFT/RL data, not a gold training set.
Descendant associations overlap across calls and are not causal rewards.
"""
import argparse
from collections import defaultdict
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path

from summarize_campaign import read_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arm_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root, archive = args.arm_root, args.arm_root / "campaign"
    wire_by_hash = defaultdict(list)
    for path in sorted((root / "wire").glob("*.json")):
        wire = json.loads(path.read_text())
        messages = (wire["request"].get("json") or {}).get("messages", [])
        if len(messages) < 2:
            continue
        digest = hashlib.sha256((messages[0]["content"] + "\n" + messages[1]["content"]).encode()).hexdigest()[:16]
        wire_by_hash[digest].append((path.name, datetime.fromisoformat(wire["started_at"]).timestamp()))
    hypotheses = {}
    for hypothesis in read_rows(archive, "hypothesis_cards"):
        hypotheses.setdefault(hypothesis["hypothesis_id"], hypothesis)
    candidates = read_rows(archive, "action_candidates")
    launches = read_rows(archive, "launch_decisions")
    dispatched = {r["candidate_id"] for r in read_rows(archive, "dispatch_records") if r["status"] == "started"}
    supervisors = {r["tick_id"]: r for r in read_rows(archive, "supervisor_decisions")}
    children = defaultdict(set)
    for result in read_rows(archive, "result_records"):
        for parent in result["parent_ids"]:
            children[parent].add(result["result_id"])
    with (root / "designs/strict-export/manifest.csv").open() as stream:
        strict = {r["result_id"]: r for r in csv.DictReader(stream)}
    cluster_status = json.loads((root / "designs/summary.json").read_text())["upstream_export"]["foldseek_su_status"]
    output, unmatched = [], []
    for call in read_rows(archive, "llm_call_records"):
        if call["role"] not in {"planner", "supervisor"}:
            continue
        if call["parse_status"] == "no_hypotheses_or_candidates":
            continue  # no model response exists for this scheduler event
        end = int(call["call_id"].rsplit("_", 1)[1])
        files = [file for file, started in wire_by_hash[call["prompt_hash"]]
                 if end-call["latency_s"]-3 <= started <= end+2]
        if not files:
            unmatched.append(call["call_id"])
        tick = call["tick_id"]
        if call["role"] == "planner":
            hyps = {hid for hid, h in hypotheses.items() if h["tick_created"] == int(tick.removeprefix("v7r"))}
            proposed = {c["candidate_id"] for c in candidates if hyps.intersection(c["hypothesis_ids"])}
        else:
            hyps = set()
            proposed = {d["candidate_id"] for d in supervisors.get(tick, {}).get("candidate_decisions", [])}
        selected_this_tick = {r["candidate_id"] for r in launches if r["tick_id"] == tick and r["status"] == "launched"}
        descendants, pending = set(), list(proposed & dispatched)
        while pending:
            for child in children[pending.pop()]:
                if child not in descendants:
                    descendants.add(child)
                    pending.append(child)
        qualified = descendants & strict.keys()
        output.append(dict(arm=root.name, tick_id=tick, role=call["role"], call_id=call["call_id"],
            prompt_hash=call["prompt_hash"], wire_files=["wire/"+f for f in files],
            call_outcome={k:call[k] for k in ["model","parse_status","fail_reason","confidence","abstain","fallback_triggered","latency_s","tokens_in","tokens_out"]},
            hypothesis_ids=sorted(hyps), proposed_candidate_ids=sorted(proposed),
            selected_this_tick=sorted(selected_this_tick),
            proposed_candidates_ever_started=sorted(proposed & dispatched),
            descendant_result_ids=sorted(descendants), qualified_descendant_ids=sorted(qualified),
            strict_clustering_status=cluster_status,
            qualified_descendant_structure_bins=sorted({strict[r]["structure_bin"] for r in qualified}) if cluster_status == "ok" else [],
            split="pilot_diagnostic_needs_review",
            warning="Lineage associations overlap across prompts. They are not independent samples or counterfactual policy rewards. A valid teacher response is not automatically optimal."))
    args.output.write_text("".join(json.dumps(row) + "\n" for row in output))
    print(json.dumps(dict(n_model_decisions=len(output), missing_wire_matches=unmatched), indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build and grade small evidence-reading tasks from actual campaign records.

These are pilot development/SFT examples, never a held-out policy benchmark.
They test provenance and canonical qualification, not experiment selection.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import random

from trex.success_criteria import STRICT_SUCCESS, is_strict_success


SYSTEM = """Read the supplied design records and return one JSON object, with no prose:
{"results":[{"result_id":"...","source_family":"...","status":"...","failed_axes":[]}],"qualified_record_count":0}
Preserve input record order. Copy source_family from backend_family, not parents.
Use status backend_failed if exit_status is not ok; otherwise identity_unresolved
if binder identity is not verified; otherwise unmeasured if any canonical metric
is absent; otherwise strict_pass or strict_fail. Qualification requires pLDDT >=90,
iPAE <=7/31 (normalized), and binder_scRMSD <1.5 angstrom. Diagnostic metrics cannot
replace canonical metrics. For strict_fail only, list failing axis names in order
pLDDT, iPAE, binder_scRMSD. All other failed_axes lists must be empty. Count passing
records, without claiming they are independent or structurally unique."""


def answer(records):
    rows = []
    for record in records:
        metrics = record["canonical_metrics"]
        complete = all(isinstance(metrics.get(k), (int, float))
                       and math.isfinite(metrics[k]) for k in STRICT_SUCCESS)
        failed = []
        if record["exit_status"] != "ok":
            status = "backend_failed"
        elif record["output_chain_identity"] != "verified":
            status = "identity_unresolved"
        elif not complete:
            status = "unmeasured"
        elif is_strict_success(metrics):
            status = "strict_pass"
        else:
            status = "strict_fail"
            for axis, (threshold, direction) in STRICT_SUCCESS.items():
                passes = (metrics[axis] >= threshold if direction == "increase" else
                          metrics[axis] < threshold if axis == "binder_scRMSD" else
                          metrics[axis] <= threshold)
                if not passes:
                    failed.append(axis)
        rows.append(dict(result_id=record["result_id"], source_family=record["backend_family"],
                         status=status, failed_axes=failed))
    return dict(results=rows, qualified_record_count=sum(r["status"] == "strict_pass" for r in rows))


def unique_keys(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def grade(raw, expected):
    try:
        obj = json.loads(raw, object_pairs_hook=unique_keys)
        # Canonical serialization distinguishes true from 1, rejects nonfinite
        # values, and does not care about object-key order or whitespace.
        valid = json.dumps(obj, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True)
    except (ValueError, TypeError):
        valid = False
    return {"reward": int(valid), "exact_evidence_answer": valid}


def build(root, output):
    groups = defaultdict(list)
    for line in (root / "designs/prepared-results.jsonl").read_text().splitlines():
        source = json.loads(line)
        record = {k: source[k] for k in ["result_id", "backend_family", "exit_status", "parent_ids"]}
        record.update(output_chain_identity=source["bins"].get("output_chain_identity"),
            canonical_metrics={k:v for k,v in source["metrics"].items() if k in STRICT_SUCCESS},
            diagnostic_metrics={k:v for k,v in source["metrics"].items() if k not in STRICT_SUCCESS})
        groups[answer([record])["results"][0]["status"]].append(record)
    # Stratified, deterministic small development set. A record appears once.
    packs = [[] for _ in range(4)]
    for rows in groups.values():
        for i, row in enumerate(sorted(rows, key=lambda r:r["result_id"])[:8]):
            packs[i % 4].append(row)
    tasks = []
    for i, records in enumerate(packs):
        if not records:
            continue
        random.Random(700+i).shuffle(records)
        expected = answer(records)
        tasks.append(dict(id=f"{root.name}_evidence_{i:02d}", task="evidence_provenance_and_qualification",
            split="pilot_development_not_held_out", target="32_PDL1_ALPHA_REPACK",
            source=str(root / "designs/prepared-results.jsonl"), result_ids=[r["result_id"] for r in records],
            messages=[dict(role="system", content=SYSTEM),
                      dict(role="user", content=json.dumps({"records": records}, sort_keys=True))],
            expected=expected, sft_response=json.dumps(expected),
            warning="Deterministic fact labels only; not optimal policy labels. Keep this target/lineages out of any claimed held-out evaluation after training."))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(task)+"\n" for task in tasks))
    print(json.dumps(dict(n_tasks=len(tasks), n_records=sum(len(t["result_ids"]) for t in tasks))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    make = subs.add_parser("build")
    make.add_argument("arm_root", type=Path)
    make.add_argument("output", type=Path)
    check = subs.add_parser("grade")
    check.add_argument("tasks", type=Path)
    check.add_argument("task_id")
    check.add_argument("response", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        build(args.arm_root, args.output)
    else:
        tasks = [json.loads(line) for line in args.tasks.read_text().splitlines()]
        task = next(t for t in tasks if t["id"] == args.task_id)
        print(json.dumps(grade(args.response.read_text(), task["expected"])))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Summarize complete archive accounting without confusing records and jobs."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import re


def read_rows(root, name):
    path = root / (name + ".jsonl")
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def summarize(archive, log):
    results = read_rows(archive, "result_records")
    calls = read_rows(archive, "llm_call_records")
    launches = read_rows(archive, "launch_decisions")
    dispatches = read_rows(archive, "dispatch_records")
    candidates = read_rows(archive, "action_candidates")
    by_candidate = {c["candidate_id"]: c for c in candidates}
    evidence = read_rows(archive, "evidence_summaries")
    launched = {c["candidate_id"] for c in launches if c["status"] == "launched"}
    started = {c["candidate_id"] for c in dispatches if c["status"] == "started"}
    started_rows = []
    for candidate in sorted(started):
        row = by_candidate[candidate]
        children = [r for r in results if candidate in r["parent_ids"]]
        started_rows.append(dict(candidate_id=candidate, family=row["method_family"],
            hypothesis_ids=row["hypothesis_ids"], config=row["config_delta"],
            n_result_records=len(children), result_statuses=dict(Counter(r["exit_status"] for r in children)),
            recorded_gpu_h=sum(r["gpu_h"] for r in children)))
    llm = {}
    for role in ["planner", "supervisor", "critic"]:
        rows = [r for r in calls if r["role"] == role]
        llm[role] = dict(n_records=len(rows),
            parse_status=dict(Counter(r["parse_status"] for r in rows)),
            fail_reasons=dict(Counter(r.get("fail_reason") for r in rows if r.get("fail_reason"))),
            fallback_records=sum(r["fallback_triggered"] for r in rows),
            zero_token_records=sum(not r["tokens_in"] and not r["tokens_out"] for r in rows),
            input_tokens=sum(r["tokens_in"] for r in rows), output_tokens=sum(r["tokens_out"] for r in rows))
    text = log.read_text(errors="replace")
    starts = re.findall(r"target=\S+ start=(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)", text)
    ends = re.findall(r"done at (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)", text)
    elapsed = None
    if starts and ends:
        elapsed = (datetime.fromisoformat(ends[-1].replace("Z", "+00:00"))
                   - datetime.fromisoformat(starts[0].replace("Z", "+00:00"))).total_seconds() / 3600
    latest = evidence[-1] if evidence else {}
    workers = latest.get("worker_wall_gpu_count")
    return dict(n_results=len(results), n_unique_started_candidates=len(started),
        dispatch_status=dict(Counter(r["status"] for r in dispatches)),
        launch_status=dict(Counter(r["status"] for r in launches)),
        selected_not_started=sorted(launched-started),
        started_by_family=dict(Counter(r["family"] for r in started_rows)),
        started_jobs=started_rows,
        candidate_feasibility_reasons=dict(Counter(reason for r in candidates for reason in r["feasibility"]["reasons"])),
        llm=llm, controller_start=starts[0] if starts else None,
        controller_end=ends[-1] if ends else None,
        controller_wall_h_including_drain=elapsed,
        worker_slots=workers,
        worker_wall_gpu_h_including_drain=elapsed*workers if elapsed is not None and workers is not None else None,
        sum_recorded_worker_gpu_h=sum(r["gpu_h"] for r in results),
        last_evidence={k:latest.get(k) for k in ["tick_id","elapsed_wall_h","completed_children","strict_count","run_su_count","worker_wall_gpu_h_total"]},
        notes=["Critic records are deterministic guard evaluations, not extra LLM requests.",
               "No-candidate Supervisor records skip inference; keep them separate from invalid model replies.",
               "Started jobs, result records, selected candidates and independent molecular samples are different denominators.",
               "Worker-wall includes idle slots and drain. Native job charges measure launch-to-reap wall time and can include observation delay; they are not hardware-active GPU time. LLM GPUs are excluded."])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("controller_log", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = summarize(args.archive, args.controller_log)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k:v for k,v in report.items() if k not in ["started_jobs","candidate_feasibility_reasons","llm"]}, indent=2))

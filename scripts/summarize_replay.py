#!/usr/bin/env python3
"""Summarize the five-state diagnostic without claiming molecular rewards."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replay", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    records = [json.loads(line) for line in (args.replay / "cases.jsonl").read_text().splitlines()]
    assert len(records) == 5 and all(row["exact_prompt_reconstruction"] for row in records)
    rows = []
    for record in records:
        score = record.get("teacher_score", {})
        labels = score.get("labels", {})
        native = record["source_native_outcome"]
        rows.append(dict(tick=record["source_tick"], source_parse_status=native["parse_status"],
            source_fallback=native["fallback_triggered"], teacher_http_status=record.get("http_status"),
            replay_error=record.get("replay_error"), teacher_json_only=labels.get("json_only", False),
            teacher_schema_valid=labels.get("schema_valid", False),
            teacher_schema_and_configs_valid=bool(labels.get("schema_valid") and labels.get("all_configs_valid")),
            teacher_native_valid_after_repair=labels.get("deterministic_repair_valid", False),
            teacher_passes_confidence_and_abstention_gate=score.get("passes_live_confidence_and_abstention_gate", False),
            teacher_static_feasible_candidates=score.get("n_static_feasible_candidates", 0),
            teacher_static_candidates=[dict(family=c["method_family"], parent_result_id=c["parent_result_id"],
                config=c["config_delta"], feasibility=c["feasibility"]) for c in score.get("candidate_preview", [])],
            latency_s=record.get("latency_s")))
    report = dict(n_cases=len(rows), exact_live_prompts_reconstructed=len(rows),
        teacher_http_200=sum(r["teacher_http_status"] == 200 for r in rows),
        teacher_json_only=sum(r["teacher_json_only"] for r in rows),
        teacher_schema_valid=sum(r["teacher_schema_valid"] for r in rows),
        teacher_schema_and_configs_valid=sum(r["teacher_schema_and_configs_valid"] for r in rows),
        teacher_native_valid_after_repair=sum(r["teacher_native_valid_after_repair"] for r in rows),
        teacher_with_feasible_candidate_and_live_gate=sum(r["teacher_passes_confidence_and_abstention_gate"]
            and r["teacher_static_feasible_candidates"] > 0 for r in rows), cases=rows,
        notes=["Five call-index quartiles selected before observing teacher outcomes; all retained.",
            "The candidate preview assumes backend and parent-artifact availability, and does not dispatch molecular jobs.",
            "Late states may correctly have no feasible candidate; abstention is not automatically an error.",
            "Teacher outputs require factual and policy review; these are not optimal-action SFT labels or molecular rewards."])
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in ["cases", "notes"]}, indent=2))


if __name__ == "__main__":
    main()

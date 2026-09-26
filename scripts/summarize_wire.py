#!/usr/bin/env python3
"""Summarize HTTP calls without conflating JSON syntax with T-REX validation."""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import statistics


def summarize(root: Path, after=None, before=None):
    rows = []
    for path in sorted(root.glob("*.json")):
        record = json.loads(path.read_text())
        started = datetime.fromisoformat(record["started_at"])
        if (after is not None and started < after) or (before is not None and started >= before):
            continue
        if record["method"] != "POST" or not record["path"].endswith("/chat/completions"):
            continue
        request = record["request"].get("json", {})
        response = record.get("response", {}).get("json", {})
        messages = request.get("messages", [])
        system = next((m.get("content", "") for m in messages if m["role"] == "system"), "")
        role = "planner" if "You are the Planner" in system else "supervisor" if "Supervisor" in system else "unknown"
        choice = next(iter(response.get("choices", [])), {})
        content = choice.get("message", {}).get("content")
        try:
            json_only = isinstance(json.loads(content), dict)
        except (ValueError, TypeError):
            json_only = False
        usage = response.get("usage") or {}
        # Reasoning tokens are billed inside completion_tokens, so a server that
        # reasons by default can spend the whole limit and return no content.
        # Absent on servers that report neither; see docs/experiment.md.
        reasoning_tokens = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
        cached_prompt_tokens = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
        rows.append(dict(file=path.name, call_id=record["call_id"], role=role,
            started_at=record["started_at"],
            model=request.get("model"), state=record["state"], status=record.get("status"),
            injected_extra_body=record.get("injected_extra_body"),
            is_repair_call=any(m["role"] == "assistant" for m in messages),
            finish_reason=choice.get("finish_reason"), json_only=json_only,
            latency_s=record.get("latency_s"), prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            reasoning_tokens=reasoning_tokens, cached_prompt_tokens=cached_prompt_tokens,
            error=response.get("error")))
    latencies = [r["latency_s"] for r in rows if r["latency_s"] is not None]
    counts = dict(http_calls=len(rows), statuses=dict(Counter(str(r["status"]) for r in rows)),
        transport_states=dict(Counter(r["state"] for r in rows)),
        roles=dict(Counter(r["role"] for r in rows)),
        repair_calls=sum(r["is_repair_call"] for r in rows),
        json_only_calls=sum(r["json_only"] for r in rows),
        length_terminated_calls=sum(r["finish_reason"] == "length" for r in rows),
        median_latency_s=statistics.median(latencies) if latencies else None,
        prompt_tokens=sum(r["prompt_tokens"] or 0 for r in rows),
        completion_tokens=sum(r["completion_tokens"] or 0 for r in rows),
        max_prompt_tokens=max([r["prompt_tokens"] or 0 for r in rows], default=0),
        max_completion_tokens=max([r["completion_tokens"] or 0 for r in rows], default=0),
        calls_missing_usage=sum(r["prompt_tokens"] is None for r in rows),
        calls_with_injected_extra_body=sum(r["injected_extra_body"] is not None for r in rows),
        calls_reporting_reasoning_tokens=sum(r["reasoning_tokens"] is not None for r in rows),
        reasoning_tokens=sum(r["reasoning_tokens"] or 0 for r in rows),
        max_reasoning_tokens=max([r["reasoning_tokens"] or 0 for r in rows], default=0),
        calls_reporting_cached_prompt_tokens=sum(r["cached_prompt_tokens"] is not None for r in rows),
        cached_prompt_tokens=sum(r["cached_prompt_tokens"] or 0 for r in rows))
    return dict(summary=counts, calls=rows,
        note="JSON-only measures syntax only. Use T-REX reports for schema, repair, reference, candidate and fallback outcomes. Token sums exclude calls with missing usage. Reasoning and cached-prompt tokens are reported only by servers that return them, and reasoning tokens are already counted inside completion tokens.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wire", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--after-time-file", type=Path)
    parser.add_argument("--before-time-file", type=Path)
    args = parser.parse_args()
    report = summarize(args.wire,
        after=datetime.fromisoformat(args.after_time_file.read_text().strip().replace("Z", "+00:00")) if args.after_time_file else None,
        before=datetime.fromisoformat(args.before_time_file.read_text().strip().replace("Z", "+00:00")) if args.before_time_file else None)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()

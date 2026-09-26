#!/usr/bin/env python3
"""Render a recorded wire archive as readable transcripts.

The wire archive is the authoritative record: exact request and response bytes.
This exporter is a convenience view over it and adds nothing, so a transcript is
always reproducible from the archive it was built from. Reasoning text is kept
whenever the server returned it, because a model whose thinking is billed
against the same output budget cannot be read without it.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path


def role_of(messages):
    system = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
    if "You are the Planner" in system:
        return "planner"
    return "supervisor" if "Supervisor" in system else "unknown"


def load(root: Path):
    for path in sorted(root.glob("*.json")):
        record = json.loads(path.read_text())
        if record["method"] != "POST" or not record["path"].endswith("/chat/completions"):
            continue
        yield path, record


def render(record, index):
    request = record["request"].get("json", {})
    messages = request.get("messages", [])
    response = record.get("response", {}).get("json", {})
    choice = next(iter(response.get("choices", [])), {})
    message = choice.get("message", {}) or {}
    usage = response.get("usage", {}) or {}
    lines = [
        "=" * 78,
        f"call {index:03d}  {record['call_id']}",
        f"started_at      {record['started_at']}",
        f"role            {role_of(messages)}",
        f"model           {request.get('model')}",
        f"sampling        temperature={request.get('temperature')} "
        f"max_completion_tokens={request.get('max_completion_tokens')}",
        f"transport       state={record['state']} status={record.get('status')} "
        f"latency_s={record.get('latency_s')}",
        f"finish_reason   {choice.get('finish_reason')}",
        f"usage           prompt={usage.get('prompt_tokens')} "
        f"completion={usage.get('completion_tokens')} "
        f"reasoning={(usage.get('completion_tokens_details') or {}).get('reasoning_tokens')} "
        f"cached_prompt={(usage.get('prompt_tokens_details') or {}).get('cached_tokens')}",
    ]
    if record.get("injected_extra_body"):
        # Say plainly what the controller did not send itself.
        lines.append(f"injected        {json.dumps(record['injected_extra_body'])}")
    if record.get("cancellation_reason"):
        lines.append(f"cancelled       {record['cancellation_reason']}")
    lines.append("=" * 78)
    for message_in in messages:
        content = message_in.get("content")
        lines += ["", f"---- {message_in.get('role')} ----",
                  content if isinstance(content, str) else json.dumps(content, indent=2)]
    reasoning = message.get("reasoning") or message.get("reasoning_content") or ""
    if reasoning:
        lines += ["", "---- assistant reasoning ----", reasoning]
    if message.get("content"):
        lines += ["", "---- assistant ----", message["content"]]
    if record["state"] != "completed" or not message:
        error = record.get("response", {}).get("json", {}).get("error")
        lines += ["", "---- no assistant message ----",
                  json.dumps(error, indent=2) if error else f"state={record['state']}"]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wire", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--split-time-file", type=Path,
                        help="Campaign start timestamp; splits fixed checks from the campaign.")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    split = None
    if args.split_time_file and args.split_time_file.exists():
        split = datetime.fromisoformat(args.split_time_file.read_text().strip().replace("Z", "+00:00"))
    index, written = {"fixed": 0, "campaign": 0, "all": 0}, []
    for path, record in load(args.wire):
        started = datetime.fromisoformat(record["started_at"])
        phase = "all" if split is None else ("campaign" if started >= split else "fixed")
        index[phase] += 1
        target = args.output / phase
        target.mkdir(exist_ok=True)
        name = f"{index[phase]:03d}-{role_of(record['request'].get('json', {}).get('messages', []))}.txt"
        (target / name).write_text(render(record, index[phase]))
        written.append(dict(phase=phase, transcript=f"{phase}/{name}", wire_record=path.name,
                            call_id=record["call_id"], state=record["state"]))
    (args.output / "index.json").write_text(json.dumps(dict(
        wire_archive=str(args.wire), n_transcripts=len(written),
        counts={k: v for k, v in index.items() if v}, transcripts=written), indent=2) + "\n")
    print(f"{len(written)} transcripts -> {args.output}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Count recorded prompts with another model's native chat template.

This is a context-fit projection, not an inference test or a measured model
failure rate. Run with the Snowball serving environment's Transformers.
"""
import argparse
from collections.abc import Mapping
import json
from pathlib import Path

from transformers import AutoTokenizer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wire", type=Path)
    parser.add_argument("tokenizer", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--context", type=int, default=32768)
    args = parser.parse_args()
    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer), local_files_only=True)
    rows = []
    for path in sorted(args.wire.glob("*.json")):
        call = json.loads(path.read_text())
        request = call["request"].get("json") or {}
        if "messages" not in request:
            continue
        tokens = tokenizer.apply_chat_template(request["messages"], tokenize=True,
            add_generation_prompt=True, enable_thinking=False, return_dict=False)
        n = len(tokens["input_ids"] if isinstance(tokens, Mapping) else tokens)
        allowance = request.get("max_completion_tokens", request.get("max_tokens", 0))
        rows.append(dict(wire_file=path.name, started_at=call["started_at"],
            prompt_tokens=n, output_allowance=allowance,
            fits_declared_window=n+allowance <= args.context))
    report = dict(tokenizer=str(args.tokenizer), context=args.context, enable_thinking=False,
        note="Counterfactual tokenization of recorded requests; does not execute this model.",
        n_requests=len(rows), n_exceeding_window=sum(not r["fits_declared_window"] for r in rows),
        max_prompt_tokens=max((r["prompt_tokens"] for r in rows), default=0), calls=rows)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k:v for k,v in report.items() if k != "calls"}, indent=2))


if __name__ == "__main__":
    main()

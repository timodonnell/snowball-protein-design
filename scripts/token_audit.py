#!/usr/bin/env python3
"""Approximate fixed-case content length; excludes chat-template overhead.

Run with PYTHONPATH=vendor/T-REX and an installed T-REX/tokenizers environment.
Explicitly expose all families in the Planner audit, independent of local GPUs.
"""
import argparse
import json
from pathlib import Path
from tokenizers import Tokenizer
from trex.planner import planner_system_prompt, build_user_prompt, VALID_ACTION_FAMILIES
from trex.supervisor import supervisor_system_prompt, build_user_prompt as supervisor_prompt
from benchmarks.llm_validation.planner_validation import CASES
from benchmarks.llm_validation.supervisor_validation import CASES as SUPERVISOR_CASES, candidates_for_hyps


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("tokenizer", type=Path)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    tokenizer = Tokenizer.from_file(str(args.tokenizer))
    model = "vllm/open-athena/Snowball-67B-A2B-5.7T-Mixed-RLVR-Step38"
    rows = []
    for build in CASES:
        name, evidence = build(model)
        content = planner_system_prompt() + "\n" + build_user_prompt(evidence, [],
            sorted(VALID_ACTION_FAMILIES), available_families=sorted(VALID_ACTION_FAMILIES))
        rows.append(dict(role="planner", case=name,
                         content_tokens_without_chat_template=len(tokenizer.encode(content).ids)))
    for name, build_evidence, build_hypotheses, _ in SUPERVISOR_CASES:
        _, evidence = build_evidence(model)
        hypotheses = build_hypotheses(evidence.target_id)
        content = supervisor_system_prompt() + "\n" + supervisor_prompt(evidence,
            hypotheses, candidates_for_hyps(hypotheses))
        rows.append(dict(role="supervisor", case=name,
                         content_tokens_without_chat_template=len(tokenizer.encode(content).ids)))
    args.output.write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()

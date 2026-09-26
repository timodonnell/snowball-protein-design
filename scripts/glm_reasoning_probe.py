#!/usr/bin/env python3
"""Measure why the GLM arm must set a reasoning budget, on a real archived prompt.

GLM-5.3 reasons by default and offers no off switch, only
``chat_template_kwargs.reasoning_effort``. This replays one archived fixed-case
Planner prompt at the campaign's own 3072-token limit under each setting and
records what comes back. It is the evidence behind the recorder's injected
control; see docs/experiment.md. Run it outside a timed campaign.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import urllib.request

SETTINGS = [("unset (server default)", None), ("low", "low"), ("medium", "medium")]


def pick_prompt(wire: Path, prompt_sha256: str):
    for path in sorted(wire.glob("*.json")):
        record = json.loads(path.read_text())
        request = (record["request"].get("json") or {})
        messages = request.get("messages") or []
        if len(messages) < 2:
            continue
        digest = hashlib.sha256(json.dumps(messages[:2], sort_keys=True).encode()).hexdigest()
        if digest == prompt_sha256:
            return request, path.name
    raise SystemExit(f"No archived request matching {prompt_sha256} under {wire}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wire", type=Path, help="A wire archive holding the fixed-case prompts.")
    parser.add_argument("output", type=Path)
    parser.add_argument("--base-url", required=True, help="GLM endpoint, including /v1.")
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--prompt-sha256",
                        default="08590e623ea2a7cfdf57c2bf2a25d15fac124c61618116ff103f324472167af0")
    args = parser.parse_args()
    source, source_file = pick_prompt(args.wire, args.prompt_sha256)
    token = args.token_file.read_text().strip()
    results = []
    for label, effort in SETTINGS:
        body = {"model": "glm-5.3", "messages": source["messages"],
                "max_completion_tokens": source["max_completion_tokens"],
                "temperature": source["temperature"]}
        if effort:
            body["chat_template_kwargs"] = {"reasoning_effort": effort}
        request = urllib.request.Request(args.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
        started = time.monotonic()
        with urllib.request.urlopen(request, timeout=600) as response:
            payload = json.loads(response.read())
        choice = payload["choices"][0]
        content = choice["message"].get("content") or ""
        try:
            json.loads(content)
            content_is_json = True
        except ValueError:
            content_is_json = False
        usage = payload["usage"]
        results.append(dict(reasoning_effort=label, finish_reason=choice["finish_reason"],
            completion_tokens=usage["completion_tokens"],
            reasoning_tokens=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
            prompt_tokens=usage["prompt_tokens"],
            cached_prompt_tokens=(usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
            content_chars=len(content), content_is_bare_json=content_is_json,
            latency_s=round(time.monotonic() - started, 2)))
        print(json.dumps(results[-1]), flush=True)
    args.output.write_text(json.dumps(dict(
        measured_at=datetime.now(timezone.utc).isoformat(), model="glm-5.3",
        source_wire_record=source_file, prompt_sha256=args.prompt_sha256,
        max_completion_tokens=source["max_completion_tokens"], temperature=source["temperature"],
        settings=results,
        note="One archived Planner fixture under the campaign's own token limit. "
             "The unset row is why every GLM call carries reasoning_effort=low: the "
             "default budget consumes the whole limit and returns no content."),
        indent=2) + "\n")


if __name__ == "__main__":
    main()

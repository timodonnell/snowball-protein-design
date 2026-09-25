#!/usr/bin/env python3
"""Local non-streaming OpenAI proxy; retain exact bodies, never auth headers.

One JSON artifact per call avoids interleaving concurrent Planner/Supervisor calls.
Write the request before forwarding so interrupted calls are still auditable.
No prompt, sampling, JSON-repair or response changes are made by this proxy.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid


def body_record(body: bytes) -> dict:
    record = {"body_base64": base64.b64encode(body).decode()}
    try:
        record["json"] = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        record["text"] = body.decode("utf-8", errors="replace")
    return record


def write_record(path: Path, record: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n")
    temporary.replace(path)


def make_handler(upstream: str, output: Path, timeout: float):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.forward()

        def do_POST(self):
            self.forward()

        def forward(self):
            call_id = str(uuid.uuid4())
            path = output / f"{time.time_ns()}_{call_id}.json"
            request_body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            record = {
                "schema": "trex.llm-wire.v1",
                "call_id": call_id,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "method": self.command,
                "path": self.path,
                "upstream": upstream,
                "request": body_record(request_body),
                "state": "pending",
            }
            write_record(path, record)
            started = time.monotonic()
            headers = {"Content-Type": self.headers.get("Content-Type", "application/json")}
            # Private localhost upstream requires no forwarded credentials.
            request = urllib.request.Request(
                upstream.rstrip("/") + self.path,
                data=request_body if self.command == "POST" else None,
                headers=headers,
                method=self.command,
            )
            try:
                try:
                    response = urllib.request.urlopen(request, timeout=timeout)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    status = response.status
                    response_body = response.read()
                    content_type = response.headers.get("Content-Type", "application/json")
                record["state"] = "completed"
            except Exception as error:
                status = 502
                content_type = "application/json"
                response_body = json.dumps({"error": {"type": type(error).__name__, "message": str(error)}}).encode()
                record["state"] = "transport_error"
            record.update(status=status, latency_s=time.monotonic() - started,
                          response=body_record(response_body))
            write_record(path, record)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", default="http://127.0.0.1:12001")
    parser.add_argument("--port", type=int, default=12000)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port),
                                make_handler(args.upstream, args.output, args.timeout))
    server.serve_forever()


if __name__ == "__main__":
    main()

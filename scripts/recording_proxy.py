#!/usr/bin/env python3
"""Local non-streaming OpenAI proxy; retain exact bodies, never auth headers.

One JSON artifact per call avoids interleaving concurrent Planner/Supervisor calls.
Write the request before forwarding so interrupted calls are still auditable.
No prompt, sampling, JSON-repair or response changes are made by this proxy.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import select
import socket
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


class ClientDisconnected(Exception):
    pass


async def cancellable_forward(handler, url, body, headers, timeout):
    # The controller already depends on httpx. Import only in this opt-in mode.
    import httpx
    async def disconnected():
        while True:
            ready, _, _ = select.select([handler.connection], [], [], 0)
            if ready and handler.connection.recv(1, socket.MSG_PEEK) == b"":
                return
            await asyncio.sleep(0.05)

    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        request = asyncio.create_task(client.request(handler.command, url,
            content=body if handler.command == "POST" else None,
            headers={**headers, "Accept-Encoding": "identity"}))
        monitor = asyncio.create_task(disconnected())
        try:
            done, _ = await asyncio.wait([request, monitor], return_when=asyncio.FIRST_COMPLETED)
            if request in done:
                response = request.result()
                return response.status_code, response.content, response.headers.get("Content-Type", "application/json")
            raise ClientDisconnected("Downstream closed; cancelled upstream request.")
        finally:
            for task in [request, monitor]:
                if not task.done():
                    task.cancel()
            await asyncio.gather(request, monitor, return_exceptions=True)


def make_handler(upstream: str, output: Path, timeout: float, cancel_on_disconnect=False):
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
                "cancel_on_disconnect": cancel_on_disconnect,
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
                if cancel_on_disconnect:
                    status, response_body, content_type = asyncio.run(cancellable_forward(
                        self, request.full_url, request_body, headers, timeout))
                else:
                    try:
                        response = urllib.request.urlopen(request, timeout=timeout)
                    except urllib.error.HTTPError as error:
                        response = error
                    with response:
                        status = response.status
                        response_body = response.read()
                        content_type = response.headers.get("Content-Type", "application/json")
                record["state"] = "completed"
            except ClientDisconnected as error:
                record.update(state="client_disconnected", latency_s=time.monotonic()-started,
                    cancellation_reason=str(error))
                write_record(path, record)
                return  # no upstream HTTP response exists; do not invent one
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
    parser.add_argument("--cancel-on-disconnect", action="store_true",
                        help="Propagate controller disconnect/timeout to upstream generation.")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port),
                                make_handler(args.upstream, args.output, args.timeout, args.cancel_on_disconnect))
    server.serve_forever()


if __name__ == "__main__":
    main()

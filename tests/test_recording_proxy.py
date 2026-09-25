"""Check observation preserves bytes and the client's cancellation semantics."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import select
import socket
import threading
import time

import httpx
import pytest

from scripts.recording_proxy import make_handler


@contextmanager
def server(handler):
    instance = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{instance.server_port}"
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join()


@pytest.mark.parametrize("status", [200, 400])
def test_exact_bodies_and_error_status_survive_proxy(tmp_path, status):
    request_body = b'{ "messages": [{"role":"user","content":"hello"}] }'
    response_body = b'{ "raw": "preserved", "padding": [1, 2] }\n'
    received = []
    class Upstream(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(status)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)
    with server(Upstream) as upstream:
        with server(make_handler(upstream, tmp_path, 5, True)) as proxy:
            result = httpx.post(proxy+"/v1/chat/completions", content=request_body)
    assert received == [request_body]
    assert result.status_code == status and result.content == response_body
    row = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert row["state"] == "completed" and row["status"] == status


def test_client_timeout_closes_upstream_and_records_no_fictitious_response(tmp_path):
    closed = threading.Event()
    class Upstream(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            deadline = time.monotonic()+3
            while time.monotonic() < deadline:
                ready, _, _ = select.select([self.connection], [], [], 0.05)
                if ready and self.connection.recv(1, socket.MSG_PEEK) == b"":
                    closed.set()
                    return
    with server(Upstream) as upstream:
        with server(make_handler(upstream, tmp_path, 5, True)) as proxy:
            with pytest.raises(httpx.ReadTimeout):
                httpx.post(proxy+"/slow", content=b"{}", timeout=0.4)
            assert closed.wait(2), "The observer left upstream generation running"
            deadline = time.monotonic()+1
            row = {}
            while time.monotonic() < deadline:
                row = json.loads(next(tmp_path.glob("*.json")).read_text())
                if row["state"] != "pending":
                    break
                time.sleep(0.02)
    assert row["state"] == "client_disconnected"
    assert "status" not in row and "response" not in row

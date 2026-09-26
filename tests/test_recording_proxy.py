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

from scripts.recording_proxy import make_handler, reshape_body


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


def test_bearer_token_reaches_upstream_but_never_a_record(tmp_path):
    seen = {}
    class Upstream(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["auth"] = self.headers.get("Authorization")
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")
    with server(Upstream) as upstream:
        with server(make_handler(upstream, tmp_path, 5, False, auth_token="s3cret")) as proxy:
            httpx.post(proxy+"/v1/chat/completions", content=b'{"model":"m"}')
    assert seen["auth"] == "Bearer s3cret"
    assert "s3cret" not in next(tmp_path.glob("*.json")).read_text()


def test_injection_adds_only_absent_keys_and_records_both_bodies(tmp_path):
    received = []
    class Upstream(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")
    extra = {"chat_template_kwargs": {"reasoning_effort": "low"}, "temperature": 0.9}
    client_body = b'{"model":"m","temperature":0.2}'
    with server(Upstream) as upstream:
        with server(make_handler(upstream, tmp_path, 5, False, extra_body=extra)) as proxy:
            httpx.post(proxy+"/v1/chat/completions", content=client_body)
    # The client's own temperature survives; only the absent control is added.
    assert received[0] == {"model": "m", "temperature": 0.2,
                           "chat_template_kwargs": {"reasoning_effort": "low"}}
    row = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert row["request"]["json"] == json.loads(client_body)
    assert row["injected_extra_body"] == {"chat_template_kwargs": {"reasoning_effort": "low"}}
    assert row["forwarded_request"]["json"] == received[0]


def test_unmodified_calls_keep_a_single_request_record(tmp_path):
    class Upstream(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")
    with server(Upstream) as upstream:
        with server(make_handler(upstream, tmp_path, 5, False)) as proxy:
            httpx.post(proxy+"/v1/chat/completions", content=b'{"model":"m"}')
    row = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert "forwarded_request" not in row and "injected_extra_body" not in row


def test_token_floor_raises_only_upwards_and_records_the_change(tmp_path):
    received = []
    class Upstream(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")
    with server(Upstream) as upstream:
        with server(make_handler(upstream, tmp_path, 5, False, token_floor=8192)) as proxy:
            httpx.post(proxy+"/v1/chat/completions",
                       content=b'{"model":"m","max_completion_tokens":3072}')
            httpx.post(proxy+"/v1/chat/completions",
                       content=b'{"model":"m","max_completion_tokens":16384}')
    assert received[0]["max_completion_tokens"] == 8192
    # An already-larger budget is left exactly as the controller set it.
    assert received[1]["max_completion_tokens"] == 16384
    rows = sorted((json.loads(p.read_text()) for p in tmp_path.glob("*.json")),
                  key=lambda r: r["started_at"])
    assert rows[0]["injected_extra_body"] == {
        "max_completion_tokens": {"raised_from": 3072, "to": 8192}}
    assert rows[0]["request"]["json"]["max_completion_tokens"] == 3072
    assert rows[0]["forwarded_request"]["json"]["max_completion_tokens"] == 8192
    assert "forwarded_request" not in rows[1]


def test_reshape_leaves_bodies_alone_when_nothing_applies():
    body = b'{"model":"m","max_completion_tokens":3072}'
    assert reshape_body(body, None, None) == (body, None)
    assert reshape_body(body, {}, 3072) == (body, None)
    assert reshape_body(b"not json", {"a": 1}, 8192) == (b"not json", None)

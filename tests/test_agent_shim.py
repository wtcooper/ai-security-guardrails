"""Agent-eval shim (evals/agent/shim.py) against a fake gateway: key and guardrail injection, block
conversion, error passthrough, streaming refusal. Offline."""

import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "evals" / "agent"))
import shim  # noqa: E402

SEEN = []


class FakeGateway(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append((self.headers["Authorization"], body))
        prompt = body["messages"][-1]["content"]
        if prompt == "attack":
            status, out = 400, {"error": {"message": "Blocked by judge (request): input: injection=9"}}
        elif prompt == "bad key":
            status, out = 401, {"error": {"message": "Authentication Error, invalid key"}}
        else:
            status, out = 200, {"choices": [{"message": {"role": "assistant", "content": "ok",
                                                         "tool_calls": [{"id": "1", "type": "function"}]}}]}
        data = json.dumps(out).encode()
        self.send_response(status)
        self.send_header("x-litellm-applied-guardrails", ",".join(body.get("guardrails") or []))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def serve(handler):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


@pytest.fixture
def via(tmp_path, monkeypatch):
    gw, gw_url = serve(FakeGateway)
    monkeypatch.setattr(shim, "GATEWAY_URL", gw_url)
    monkeypatch.setattr(shim, "GATEWAY_KEY", "sk-real")
    monkeypatch.setattr(shim, "AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    sh, sh_url = serve(shim.Handler)
    SEEN.clear()

    def post(arm, content, **extra):
        req = urllib.request.Request(f"{sh_url}/{arm}/v1/chat/completions", method="POST",
                                     headers={"Authorization": "Bearer dummy", "Content-Type": "application/json"},
                                     data=json.dumps({"model": "m", "messages": [{"role": "user", "content": content}],
                                                      "guardrails": ["client-sent"]} | extra).encode())
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    yield post, tmp_path / "audit.jsonl"
    gw.shutdown()
    sh.shutdown()


def test_injects_gateway_key_and_exactly_the_arms_guardrails(via):
    post, _ = via
    for arm, guards in shim.ARMS.items():
        assert post(arm, "hi")[0] == 200
        auth, body = SEEN[-1]
        assert auth == "Bearer sk-real" and body["guardrails"] == guards     # client key and value replaced


def test_block_becomes_a_refusal_and_other_errors_pass_through(via):
    post, audit = via
    status, j = post("cyberguard", "attack")
    msg = j["choices"][0]["message"]
    assert status == 200 and msg["content"].startswith("[blocked by guardrail] Blocked by") and "tool_calls" not in msg
    assert post("baseline", "bad key")[0] == 401                         # never disguised as a block
    recs = [json.loads(line) for line in audit.read_text().splitlines()]
    assert [(r["status"], r["blocked"]) for r in recs] == [(400, "request"), (401, None)]


def test_streaming_and_unknown_arms_are_refused(via):
    post, _ = via
    assert post("baseline", "hi", stream=True)[0] == 400
    assert post("nope", "hi")[0] == 404
    assert SEEN == []                                                    # nothing reached the gateway

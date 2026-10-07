"""Arm shim between an unmodified Inspect eval and the LiteLLM gateway (standard library only).

Inspect's OpenAI-compatible client cannot add LiteLLM's `guardrails` request field, so each arm points its
base URL at this shim, which forwards to the gateway with exactly that arm's guardrails:

    http://127.0.0.1:8900/<arm>/v1/chat/completions  ->  $GATEWAY_URL/v1/chat/completions + {"guardrails": ARMS[arm]}

What it does, and nothing else:
- **Keys:** drops the client's Authorization and sends GATEWAY_KEY. Inspect gets a dummy key, so the real key
  lives in one place.
- **Guardrails:** sets `guardrails` from ARMS (any client-sent value is replaced).
- **Blocks:** a guardrail with `on_block: refuse` already answers HTTP 200 with finish_reason "content_filter"
  (usage > 0 means the post-call check refused the model's reply; 0 means pre-call). A guardrail with
  `on_block: error` answers HTTP 400 "Blocked by ..."; the shim turns that into the same kind of refusal so the
  agent stops and Inspect scores the sample. Every other error passes through unchanged, so key or config
  mistakes fail loudly.
- **Streaming:** refuses `stream: true` (run Inspect with `-M stream=false`).
- **Audit:** appends one JSON line per request to AUDIT_LOG: arm, status, whether it was blocked (and by which
  hook), the gateway's `x-litellm-applied-guardrails` header, tool calls in the reply, and latency.

    GATEWAY_URL=http://localhost:4000 GATEWAY_KEY=sk-local AUDIT_LOG=run/audit.jsonl python evals/agent/shim.py
"""

import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ARMS = {                      # arm -> LiteLLM guardrail names (gateway/litellm_config.yaml)
    "baseline": [],
    "cyberguard": ["cyber-guard"],        # pre-call + post-call on tool calls (one judge call per piece, cached)
    "agentic": ["agentic-security"],      # one judge call per hook over a 10-message window, no cache or state
    "agenticsys": ["agentic-security-sys"],   # the same, with the app's system prompt shown to the judge
}   # arm names become Inspect env-var prefixes (<ARM>_BASE_URL), so letters only
if os.environ.get("AGENT_ARMS"):   # run a subset, e.g. AGENT_ARMS=agentic after changing only that guardrail
    ARMS = {arm: ARMS[arm] for arm in os.environ["AGENT_ARMS"].split(",")}
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:4000").rstrip("/")
GATEWAY_KEY = os.environ.get("GATEWAY_KEY", "sk-local")
AUDIT_LOG = os.environ.get("AUDIT_LOG", "agent_eval_audit.jsonl")
_lock = threading.Lock()


def _audit(rec: dict) -> None:
    with _lock, open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")


def _refusal(model: str, reason: str) -> dict:
    return {"id": f"blocked-{time.time_ns()}", "object": "chat.completion", "created": int(time.time()), "model": model,
            "choices": [{"index": 0, "finish_reason": "content_filter",
                         "message": {"role": "assistant", "content": f"[blocked by guardrail] {reason}"}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, status: int, body: bytes, applied: str = "") -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("x-litellm-applied-guardrails", applied)   # what the gateway actually ran
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        arm, _, rest = self.path.lstrip("/").partition("/")
        if arm not in ARMS or not rest.startswith("v1/"):
            return self._send(404, json.dumps({"error": {"message": f"unknown arm or path: {self.path}"}}).encode())
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if body.get("stream"):
            return self._send(400, json.dumps({"error": {"message": "shim: streaming not supported; use -M stream=false"}}).encode())
        body["guardrails"] = ARMS[arm]
        req = urllib.request.Request(f"{GATEWAY_URL}/{rest}", data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": f"Bearer {GATEWAY_KEY}"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                status, data, applied = r.status, r.read(), r.headers.get("x-litellm-applied-guardrails", "")
        except urllib.error.HTTPError as e:
            status, data, applied = e.code, e.read(), e.headers.get("x-litellm-applied-guardrails", "")
        except urllib.error.URLError as e:
            status, data, applied = 502, json.dumps({"error": {"message": f"shim: gateway unreachable: {e}"}}).encode(), ""
        rec = {"ts": time.time(), "arm": arm, "path": rest, "status": status, "applied": applied, "blocked": None,
               "tool_calls": 0, "ms": round((time.perf_counter() - t0) * 1000)}
        message = ""
        try:
            parsed = json.loads(data)
            message = str((parsed.get("error") or {}).get("message", "")) if isinstance(parsed, dict) else ""
        except ValueError:
            parsed = None
        if status == 400 and message.startswith("Blocked by "):
            rec["blocked"] = "response" if "(response)" in message.split(":", 1)[0] else "request"
            rec["reason"] = message[:300]
            _audit(rec)
            return self._send(200, json.dumps(_refusal(body.get("model", ""), message[:300])).encode(), applied)
        if status == 200 and isinstance(parsed, dict):
            choices = parsed.get("choices") or []
            rec["tool_calls"] = sum(len((c.get("message") or {}).get("tool_calls") or []) for c in choices)
            if any(c.get("finish_reason") == "content_filter" for c in choices):   # native in-band refusal
                rec["blocked"] = "response" if ((parsed.get("usage") or {}).get("total_tokens") or 0) > 0 else "request"
        elif status != 200:
            rec["error"] = (message or data[:300].decode(errors="replace"))[:300]
        _audit(rec)
        self._send(status, data, applied)


if __name__ == "__main__":
    port = int(os.environ.get("SHIM_PORT", "8900"))
    print(f"shim on http://127.0.0.1:{port}/<arm>/v1 -> {GATEWAY_URL} (arms: {', '.join(ARMS)}); audit -> {AUDIT_LOG}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()

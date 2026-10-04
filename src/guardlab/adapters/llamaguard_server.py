"""Family 3: Meta Llama Guard 4 served locally by llama-server (evals/lab/shims/llama_guard4.sh).

The model's own chat template (embedded in the GGUF) renders its hazard-category prompt; user-side
content (input, tool output, tool description) is judged as the User turn, replies and tool calls
as the Agent turn. Score = P("unsafe") / (P("unsafe") + P("safe")) at the verdict token, from the
server's logprobs. Llama Guard 4 has no prompt-injection category (Meta pairs it with Prompt Guard 2);
in this lab it measures how far a general hazard classifier gets on cyber/agent risks.
"""

import math

import httpx

from ..types import BaseGuard, Case, GuardResult, Unavailable


class LlamaGuardServer(BaseGuard):
    def __init__(self, id, base_url: str = "http://127.0.0.1:8767", threshold: float = 0.5, timeout_s: float = 120,
                 template_kwargs: dict | None = None, **kw):
        super().__init__(id, base_url=base_url, threshold=threshold, template_kwargs=template_kwargs or {}, **kw)
        self._client = httpx.Client(base_url=base_url, timeout=timeout_s)

    def _messages(self, case: Case) -> list:
        part = lambda s: [{"type": "text", "text": s}]
        if case.stage in ("output", "tool_call"):
            return [{"role": "user", "content": part(case.user_request or "(previous user message)")},
                    {"role": "assistant", "content": part(case.text)}]
        return [{"role": "user", "content": part(case.text)}]

    def _check(self, case: Case) -> GuardResult:
        body = {"messages": self._messages(case), "max_tokens": 8, "temperature": 0, "logprobs": True,
                "top_logprobs": 10}
        if self.cfg["template_kwargs"]:
            body["chat_template_kwargs"] = self.cfg["template_kwargs"]
        try:
            r = self._client.post("/v1/chat/completions", json=body)
        except (httpx.TimeoutException, httpx.TransportError) as e:
            raise Unavailable(f"llama-server: {e}") from e
        if r.status_code != 200:
            raise RuntimeError(f"llama-server HTTP {r.status_code}: {r.text[:200]}")
        choice = r.json()["choices"][0]
        for tok in (choice.get("logprobs") or {}).get("content") or []:
            if tok["token"].strip() in ("safe", "unsafe"):        # first verdict token (skips leading newlines)
                probs = {t["token"].strip(): math.exp(t["logprob"]) for t in tok["top_logprobs"]}
                pu, ps = probs.get("unsafe", 0.0), probs.get("safe", 0.0)
                p = pu / (pu + ps) if pu + ps else float(tok["token"].strip() == "unsafe")
                cats = (choice["message"].get("content") or "").split("\n")[-1].strip() if p >= self.cfg["threshold"] else ""
                return GuardResult(blocked=p >= self.cfg["threshold"], score=p, categories=[cats] if cats else [],
                                   reason=f"P(unsafe)={p:.3f} {cats}".strip())
        raise RuntimeError(f"no verdict token in {(choice['message'].get('content') or '')[:80]!r}")

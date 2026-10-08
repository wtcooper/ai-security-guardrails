"""Family 4: provider decision APIs, used out of the box.

A decision-API guard is s1guard's question battery (policy YAML: one yes/no question per risk,
batched per stage) answered by a hosted decision model instead of local Laya. Same scoring as the
s1guard adapter (score >= 0.5 <=> the policy blocks).

    api: openai  -> OpenAI /v1/decisions (or the luna emulator: base_url http://127.0.0.1:8765)
    api: jev     -> Jev-schema servers (TypeSafe, OpenRouter, Cloudflare Clef, laya[serve])
"""

from .s1guard import S1Guard


class DecisionAPIGuard(S1Guard):
    def __init__(self, id, policy: str, api: str = "openai", base_url: str = "", path: str = "",
                 api_key_env: str = "", model: str = "", timeout_s: float = 10.0, unwrap: str = "", backend=None, **kw):
        super().__init__(id, model=model, policy=policy, backend=backend, api=api, base_url=base_url, path=path,
                         api_key_env=api_key_env, unwrap=unwrap, **kw)
        self._timeout = timeout_s

    def _load(self):
        if self._guard is None and self._backend is None:
            from ..decisions.backends import JevHTTPBackend, OpenAIDecisionsBackend
            c = self.cfg
            if c["api"] == "openai":
                self._backend = OpenAIDecisionsBackend(c["base_url"] or "https://api.openai.com", c["path"] or "/v1/decisions",
                                                       c["api_key_env"] or "OPENAI_API_KEY", c["model"] or "gpt-6-luna",
                                                       self._timeout)
            else:
                self._backend = JevHTTPBackend(c["base_url"], c["path"] or "/v1/systemone", c["api_key_env"],
                                               c["model"], self._timeout, c["unwrap"])
        return super()._load()

    def _check(self, case):
        self._load()   # creates the backend on first use
        spent = getattr(self._backend, "spent", None)
        if spent is not None:
            spent.usd = 0.0
        r = super()._check(case)
        if spent is not None:
            r.cost_usd = spent.usd   # all decision calls this check made (Jev-family backends)
        return r

"""Family 3: a policy-following guard model served by a local HTTP shim in its own environment
(e.g. Nemotron-3.5-Content-Safety, evals/lab/shims/nemotron_server.py).

The guard sends each case with the judge's policy for that stage (src/guardlab/judge/policies, the
same tuned cyber policies cyber-guard-per-policy uses), so the comparison isolates the model. Several policies
for one stage are sent as separate requests; score = max P(unsafe).
"""

import hashlib

import httpx

from ..types import BaseGuard, Case, GuardResult, Unavailable
from .llm_judge import DEFAULT_POLICIES, load_policy


class PolicyShim(BaseGuard):
    def __init__(self, id, base_url: str, threshold: float = 0.5, policies: dict | None = None,
                 timeout_s: float = 120, **kw):
        super().__init__(id, base_url=base_url, threshold=threshold, policies=policies or DEFAULT_POLICIES, **kw)
        self.stages = frozenset(self.cfg["policies"]) & self.stages
        self._policies = {n: load_policy(n) for ps in self.cfg["policies"].values() for n in ps}
        self._common = load_policy("common")[1]
        self._client = httpx.Client(base_url=base_url, timeout=timeout_s)

    @property
    def version(self) -> str:
        h = hashlib.sha256(super().version.encode() + self._common.encode())
        for n in sorted(self._policies):
            h.update(n.encode() + self._policies[n][1].encode())
        return h.hexdigest()[:12]

    def _check(self, case: Case) -> GuardResult:
        best, cats = 0.0, []
        for name in self.cfg["policies"][case.stage]:
            try:
                r = self._client.post("/classify", json={"text": case.text, "stage": case.stage,
                                                         "policy": self._policies[name][1] + "\n\n" + self._common,
                                                         "user_request": case.user_request})
            except (httpx.TimeoutException, httpx.TransportError) as e:
                raise Unavailable(f"shim: {e}") from e
            if r.status_code != 200:
                raise RuntimeError(f"shim HTTP {r.status_code}: {r.text[:200]}")
            p = r.json().get("p_unsafe")
            if p is None:
                raise RuntimeError(f"no verdict token: {r.json().get('verdict', '')[:80]!r}")
            if p >= self.cfg["threshold"]:
                cats.append(self._policies[name][0]["category"])
            best = max(best, p)
        return GuardResult(blocked=best >= self.cfg["threshold"], score=best, categories=cats,
                           reason=f"P(unsafe)={best:.3f}")

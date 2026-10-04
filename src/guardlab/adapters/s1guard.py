"""Family 1: s1guard (System One question battery on Laya or any /v1/systemone backend).

Score = z / (1 + z) where z = max over blocking risks of score / threshold, so score >= 0.5
exactly when the policy blocks -- one number per case for AUROC across differently-thresholded risks."""

from ..types import BaseGuard, Case, GuardResult


def margin(guard, scores: dict, case: Case) -> float:
    """Max score/threshold over blocking risks, with the same threshold rules as s1guard.Guard._decide."""
    known = {"system_prompt": case.system_prompt, "user_request": case.user_request}
    z = 0.0
    for r in guard.risks:
        if r.action != "block" or r.id not in scores:
            continue
        thr = 0.5 if r.kind == "detector" else r.threshold
        if r.context_question and known.get(r.context_field) and r.context_threshold is not None:
            thr = r.context_threshold
        z = max(z, scores[r.id] / max(thr, 1e-6))
    return z


class S1Guard(BaseGuard):
    def __init__(self, id, model: str, policy: str, subfolder: str = "", backend=None, **kw):
        super().__init__(id, model=model, policy=policy, subfolder=subfolder, **kw)
        self._backend = backend   # tests inject a fake; otherwise Laya is loaded on first use
        self._guard = None

    def _load(self):
        if self._guard is None:
            from s1guard import Guard
            from s1guard.backends import LayaBackend
            backend = self._backend or LayaBackend(model=self.cfg["model"], subfolder=self.cfg["subfolder"] or None)
            self._guard = Guard(backend=backend, policy=self.cfg["policy"])
        return self._guard

    def _check(self, case: Case) -> GuardResult:
        guard = self._load()
        v = guard.check(case.text, case.stage, system_prompt=case.system_prompt, user_request=case.user_request)
        scores = v.scores.get(case.stage, {})
        z = margin(guard, scores, case)
        return GuardResult(blocked=v.blocked, score=z / (1 + z),
                           categories=[f.risk for f in v.findings if f.action == "block"],
                           reason=v.reason(), raw={"scores": scores})

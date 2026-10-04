"""Family 3: Hugging Face text-classification guards (encoders such as Prompt Guard 2, Sentinel v2).

Score = P(`label`), max over character windows (same windows as s1guard's classifier risks) so an
attack at the end of a long document is not truncated away."""

from ..types import BaseGuard, Case, GuardResult


class HFClassifier(BaseGuard):
    def __init__(self, id, model: str, label: str, revision: str = "", threshold: float = 0.5,
                 window: int = 1500, stride: int = 1000, max_windows: int = 8, max_length: int = 512,
                 pipeline=None, **kw):
        super().__init__(id, model=model, label=label, revision=revision, threshold=threshold, window=window,
                         stride=stride, max_windows=max_windows, max_length=max_length, **kw)
        self._pipe = pipeline   # tests inject a fake

    def _load(self):
        if self._pipe is None:
            from transformers import pipeline

            from s1guard.backends import _default_device
            c = self.cfg
            self._pipe = pipeline("text-classification", model=c["model"], revision=c["revision"] or None,
                                  device=_default_device(), truncation=True, max_length=c["max_length"], top_k=None)
        return self._pipe

    def _check(self, case: Case) -> GuardResult:
        from s1guard.backends import DEVICE_LOCK  # MPS: one forward pass at a time across in-process models

        c, t = self.cfg, case.text
        starts = list(range(0, max(1, len(t) - c["window"] + c["stride"]), c["stride"]))[:c["max_windows"]]
        with DEVICE_LOCK:
            outs = self._load()([t[i:i + c["window"]] for i in starts])
        p = max(next((x["score"] for x in out if x["label"] == c["label"]), 0.0) for out in outs)
        return GuardResult(blocked=p >= c["threshold"], score=p, reason=f"P({c['label']})={p:.3f}",
                           categories=[c["label"]] if p >= c["threshold"] else [])

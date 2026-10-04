"""The one interface every guard implements: check(Case) -> GuardResult.

Statuses keep "could not decide" apart from "decided to block": `unavailable` (timeout, rate
limit, access denied, 5xx) and `error` (bug, unparseable verdict) still set `blocked` from
`fail_closed`, but reports can count them separately."""

import asyncio
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

STAGES = ("input", "conversation", "tool_result", "tool_definition", "tool_call", "output")
INPUT_SIDE = frozenset({"input", "conversation", "tool_result", "tool_definition"})  # screened before the model


@dataclass(frozen=True)
class Case:
    text: str
    stage: str = "input"
    system_prompt: Optional[str] = None   # trusted context for output checks
    user_request: Optional[str] = None    # trusted context for tool-call checks
    id: str = ""

    def key(self) -> str:
        blob = json.dumps([self.stage, self.text, self.system_prompt, self.user_request])
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


@dataclass
class GuardResult:
    blocked: bool
    score: Optional[float] = None    # [0, 1], higher = more likely an attack; None if the guard is binary
    status: str = "ok"               # ok | error | unavailable | unsupported
    categories: list = field(default_factory=list)
    latency_ms: float = 0.0
    cost_usd: Optional[float] = None
    reason: str = ""
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class Unavailable(Exception):
    """The guard could not decide: timeout, rate limit, access not enabled, server error."""


class BaseGuard:
    """Subclasses implement `_check(case) -> GuardResult`; this adds stage filtering, timing,
    one retry on Unavailable, and fail-closed error handling."""

    def __init__(self, id: str, stages=None, fail_closed: bool = True, meta: Optional[dict] = None, **cfg):
        self.id = id
        self.stages = frozenset(stages or STAGES)
        self.fail_closed = fail_closed
        self.meta = meta or {}
        self.cfg = cfg

    @property
    def version(self) -> str:
        """Changes whenever the adapter, its config, or any config file it reads changes (cache key)."""
        h = hashlib.sha256(f"{type(self).__name__}{json.dumps(self.cfg, sort_keys=True, default=str)}".encode())
        for v in self.cfg.values():
            if isinstance(v, str) and len(v) < 4096 and Path(v).is_file():
                h.update(Path(v).read_bytes())
        return h.hexdigest()[:12]

    def _check(self, case: Case) -> GuardResult:
        raise NotImplementedError

    def check(self, case: Case) -> GuardResult:
        if case.stage not in self.stages:
            return GuardResult(blocked=False, status="unsupported", reason=f"{self.id} does not screen {case.stage}")
        t0 = time.perf_counter()
        for attempt in (0, 1):
            try:
                r = self._check(case)
                break
            except Unavailable as e:
                r = GuardResult(blocked=self.fail_closed, status="unavailable", reason=str(e))
            except Exception as e:  # a guard bug must not look like a clean pass
                r = GuardResult(blocked=self.fail_closed, status="error", reason=f"{type(e).__name__}: {e}")
                break
        r.latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        return r

    async def acheck(self, case: Case) -> GuardResult:
        return await asyncio.to_thread(self.check, case)

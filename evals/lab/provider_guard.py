"""promptfoo provider: run one registry guard (config.guard) on one corpus case.

Returns promptfoo's `guardrails` object, so the corpus's `guardrails` / `not-guardrails` assertions
score the guard directly (no model, no judge). The guard's score, status, latency and cost go in
`metadata` for evals/lab/report.py (AUROC, calibrated recall, latency, cost). Results are cached
per guard version in evals/lab/.cache/results/, so reruns only score new cases."""

import sys
import threading
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from guardlab import Case, load_guard  # noqa: E402
from guardlab.cache import get_or_run  # noqa: E402
from guardlab.types import INPUT_SIDE  # noqa: E402

CACHE = HERE / ".cache" / "results"
_guards: dict = {}
_lock = threading.Lock()


def _guard(gid):
    with _lock:
        if gid not in _guards:
            g = load_guard(gid)
            g.check(Case("warm-up: what time is it?", stage=sorted(g.stages)[0]))  # model load is not latency
            _guards[gid] = g
        return _guards[gid]


def call_api(prompt, options, context):
    gid = options["config"]["guard"]
    v = context.get("vars") or {}
    case = Case(v["prompt"], v.get("stage") or "input", v.get("system_prompt") or None,
                v.get("user_request") or None, v.get("case_id", ""), v.get("history") or None)
    g = _guard(gid)
    r, hit = get_or_run(g, case, CACHE)
    md = {"guard": gid, "version": g.version, "score": r.score, "status": r.status, "categories": r.categories,
          "latency_ms": r.latency_ms, "cost_usd": r.cost_usd, "cached": hit,
          "detail": r.raw.get("policies") or r.raw.get("scores")}   # judge digits / escalations, or per-risk scores
    if r.status != "ok":
        return {"error": f"{r.status}: {r.reason}"[:500], "metadata": md}
    return {"output": f"[BLOCKED] {r.reason}" if r.blocked else "allow", "cached": hit, "cost": r.cost_usd or 0,
            "guardrails": {"flagged": r.blocked, "flaggedInput": r.blocked and case.stage in INPUT_SIDE,
                           "flaggedOutput": r.blocked and case.stage not in INPUT_SIDE, "reason": r.reason[:500]},
            "metadata": md}

"""Guardrail latency: how long the pre-call and post-call checks take on real agent requests (no inference).

Replays recorded agent model calls (evals/lab/experiments/latency_export.py) through each guardrail's own LiteLLM hook,
in-process, and times `apply_guardrail` alone: pre-call on the request, post-call on the reply's tool calls. Every
judge call goes to gpt-6-luna directly (the same for all guards), so the numbers are the classifier's own time. A
gateway adds its router overhead on top. Requests run one at a time, so a guard's own parallel judge calls are the
only concurrency.

    uv run python evals/lab/experiments/latency.py [--n 60] [--guards agentic,cyber-cold,cyber-warm]
        [--agentic-variant name:window=6,action_review_band=4-6,hedge_s=2.5]

  agentic       agentic-security (deploy/agentic-security), window 10
  cyber-cold    cyber-guard with an empty verdict cache on every request (as under a no-cache deployment)
  cyber-warm    cyber-guard keeping its verdict cache across requests (its best case on one long-lived pod)

Requests are sampled evenly from three history sizes (messages before the call): short <=4, medium 5-11, long >=12.
Prints and saves (evals/results/lab/rounds/latency-<label>.json) the latency distribution per hook and size, judge calls
and prompt tokens per hook, and how often a hook would exceed the 10 s fail-open deadline.
"""

import argparse
import asyncio
import contextvars
import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "deploy" / "agentic-security"))
import httpx  # noqa: E402
from litellm.exceptions import GuardrailRaisedException, ModifyResponseException  # noqa: E402

import agentic_security as ags  # noqa: E402
from guardlab import litellm_guardrail as lg  # noqa: E402
from guardlab.registry import load_guard  # noqa: E402

DATA = ROOT / "evals" / "lab" / "data" / "latency_requests.jsonl"
OUT = ROOT / "evals" / "results" / "lab" / "rounds"
CALLS: contextvars.ContextVar = contextvars.ContextVar("judge_calls")   # per hook: [(seconds, usage), ...]
STAGES = ["input", "conversation", "tool_result", "tool_definition", "tool_call"]   # cyber-guard's deployed stages
SIZES = {"short": (0, 4), "medium": (5, 11), "long": (12, 10_000)}


def size_of(r) -> str:
    n = len(r["messages"])
    return next(k for k, (lo, hi) in SIZES.items() if lo <= n <= hi)


def sample(n_per_size: int) -> list:
    rows = [json.loads(line) for line in open(DATA)]
    random.seed(11)
    out = []
    for size in SIZES:
        pool = [r for r in rows if size_of(r) == size]
        out += random.sample(pool, min(n_per_size, len(pool)))
    return sorted(out, key=lambda r: (r["task"], r["sample"], r["epoch"], r["step"]))   # agent order (for the warm cache)


class DirectJudge:
    """gpt-6-luna over HTTP, for agentic-security's Judge (the gateway uses its router instead). hedge_s: if the
    first-pass call has not answered after that many seconds, send an identical second one and take whichever
    answers first (a stateless tail-latency fix; review calls are never hedged)."""

    def __init__(self, hedge_s: float = 0.0):
        self.client = httpx.AsyncClient(base_url="https://api.openai.com/v1", timeout=60,
                                        headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"})
        self.hedge_s, self.hedges = hedge_s, 0

    async def __call__(self, messages, effort, max_tokens, response_format, meta):
        if not self.hedge_s or response_format:
            return await self.once(messages, effort, max_tokens, response_format, meta)
        first = asyncio.ensure_future(self.once(messages, effort, max_tokens, response_format, meta))
        done, _ = await asyncio.wait({first}, timeout=self.hedge_s)
        if done:
            return first.result()
        self.hedges += 1
        second = asyncio.ensure_future(self.once(messages, effort, max_tokens, response_format, meta))
        done, pending = await asyncio.wait({first, second}, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        return done.pop().result()

    async def once(self, messages, effort, max_tokens, response_format, meta):
        body = {"model": "gpt-6-luna", "messages": messages, "max_completion_tokens": max_tokens, "reasoning_effort": effort}
        if response_format:
            body["response_format"] = response_format
        t0 = time.perf_counter()
        for attempt in range(5):
            r = await self.client.post("/chat/completions", json=body)
            if r.status_code != 429:
                break
            await asyncio.sleep(2 ** attempt)
        r.raise_for_status()
        j = r.json()
        CALLS.get().append((time.perf_counter() - t0, j.get("usage") or {}))
        return j["choices"][0]["message"].get("content") or "", None


def make(kind: str, variant: dict):
    if kind == "agentic":
        variant = dict(variant)
        hedge = float(variant.pop("hedge_s", 0) or 0)
        g = ags.AgenticSecurity(guardrail_name="agentic-security", deadline_s=600, **variant)
        g.judge.complete = DirectJudge(hedge)
        return g
    g = lg.LabGuardrail(guard_id="cyber-guard", guardrail_name="cyber-guard", on_block="refuse", on_unavailable="allow",
                        stages=STAGES, deadline_s=600)
    guard = g.guard
    chat = guard._chat

    def timed_chat(*a, **k):   # runs in a worker thread; CALLS is copied into it by asyncio.to_thread
        t0 = time.perf_counter()
        j = chat(*a, **k)
        CALLS.get().append((time.perf_counter() - t0, j.get("usage") or {}))
        return j
    guard._chat = timed_chat
    return g


async def hook(g, kind, inputs, request_data, input_type) -> dict:
    if kind == "cyber-cold":
        g._verdicts.clear()
    calls = []
    CALLS.set(calls)
    t0 = time.perf_counter()
    blocked = False
    try:
        await g.apply_guardrail(inputs, request_data, input_type)
    except (ModifyResponseException, GuardrailRaisedException):
        blocked = True
    return {"s": time.perf_counter() - t0, "calls": len(calls), "blocked": blocked,
            "prompt_tokens": sum(u.get("prompt_tokens", 0) for _, u in calls),
            "cached_tokens": sum((u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) for _, u in calls),
            "slowest_call_s": max((s for s, _ in calls), default=0)}


async def run(kind: str, rows: list, variant: dict, pace_s: float) -> list:
    g = make(kind, variant)
    out = []
    for i, r in enumerate(rows):
        t_start = time.perf_counter()
        msgs = r["messages"]
        pre = await hook(g, kind, {"texts": [m.get("content") or "" for m in msgs if m.get("content")],
                                   "structured_messages": msgs, "tools": r["tools"]}, {"messages": msgs}, "request")
        post = None
        if r["reply_tool_calls"]:
            post = await hook(g, kind, {"texts": [r["reply_text"]], "tool_calls": r["reply_tool_calls"]},
                              {"messages": msgs, "response": None}, "response")
        out.append({"size": size_of(r), "n_messages": len(msgs), "chars": sum(len(m.get("content") or "") for m in msgs),
                    "pre": pre, "post": post})
        if (i + 1) % 30 == 0:
            print(f"  {kind}: {i + 1}/{len(rows)}", flush=True)
        await asyncio.sleep(max(0.0, pace_s - (time.perf_counter() - t_start)))   # stay under the TPM limit
    return out, getattr(getattr(getattr(g, "judge", None), "complete", None), "hedges", 0)


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))] if xs else float("nan")


def summarize(label: str, res: list) -> dict:
    rows = {}
    for hook_name in ("pre", "post"):
        for size in ["all"] + list(SIZES):
            h = [r[hook_name] for r in res if r[hook_name] and (size == "all" or r["size"] == size)]
            if not h:
                continue
            s = [x["s"] for x in h]
            rows[f"{hook_name}/{size}"] = {
                "n": len(h), "p50": q(s, .5), "p90": q(s, .9), "p95": q(s, .95), "p99": q(s, .99), "max": max(s),
                "mean_calls": sum(x["calls"] for x in h) / len(h), "max_calls": max(x["calls"] for x in h),
                "mean_prompt_tokens": sum(x["prompt_tokens"] for x in h) / len(h),
                "cached_share": sum(x["cached_tokens"] for x in h) / max(1, sum(x["prompt_tokens"] for x in h)),
                "over_10s": sum(x > 10 for x in s) / len(s)}
    print(f"\n## {label}")
    print(f"{'hook/size':14s} {'n':>4s} {'p50':>6s} {'p90':>6s} {'p95':>6s} {'p99':>6s} {'max':>6s}  {'calls':>9s}  {'prompt tok':>10s} {'cached':>6s} {'>10s':>5s}")
    for k, v in rows.items():
        print(f"{k:14s} {v['n']:4d} {v['p50']:6.2f} {v['p90']:6.2f} {v['p95']:6.2f} {v['p99']:6.2f} {v['max']:6.2f}  "
              f"{v['mean_calls']:4.1f} (≤{v['max_calls']:2d})  {v['mean_prompt_tokens']:10.0f} {100 * v['cached_share']:5.0f}% "
              f"{100 * v['over_10s']:4.0f}%")
    return rows


def parse_variant(text: str) -> tuple:
    if not text:
        return "agentic", {}
    name, _, kv = text.partition(":")
    out = {}
    for pair in filter(None, kv.split(",")):
        k, v = pair.split("=")
        out[k] = [int(x) for x in v.split("-")] if "-" in v else (int(v) if v.isdigit() else float(v))
    return name, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60, help="requests per history size")
    ap.add_argument("--guards", default="agentic,cyber-cold,cyber-warm")
    ap.add_argument("--agentic-variant", default="")
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    rows = sample(a.n)
    vname, variant = parse_variant(a.agentic_variant)
    record = {"n_requests": len(rows), "variant": {vname: variant}, "guards": {}}
    for kind in a.guards.split(","):
        label = vname if kind == "agentic" else kind
        res, hedges = asyncio.run(run(kind, rows, variant if kind == "agentic" else {}, 3.5 if kind == "cyber-cold" else 0.0))
        record["guards"][label] = {"summary": summarize(label, res), "raw": res, "hedged_calls": hedges}
        if hedges:
            print(f"hedged first-pass calls: {hedges}")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"latency-{a.label or vname}.json"
    path.write_text(json.dumps(record, indent=1))
    print(f"\nsaved {path}")


if __name__ == "__main__":
    main()

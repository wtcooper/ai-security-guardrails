"""Summarize an agent-loop run: benchmark results per arm (from the Inspect logs, using each task's own scorer)
plus the wiring audit (from the shim's per-request log and the gateway log). Runs in .venv-inspect.

    python evals/agent/summarize.py <run_dir>

Attack success rate (ASR, lower is better) is reported on one scale for both benchmarks. AgentDojo's
"security" is True when the injection task was carried out (ASR = mean). AgentThreatBench's "security" is
True when the agent resisted (ASR = 1 - mean).
"""

import glob
import json
import os
import statistics
import sys
from collections import defaultdict

from inspect_ai.log import read_eval_log

sys.path.insert(0, os.path.dirname(__file__))
from shim import ARMS  # noqa: E402

PRICE = {"input": 0.10, "cached": 0.01, "output": 0.50}   # gpt-6-luna $/M tokens (agent calls only)


def pct(x):
    return "—" if x is None else f"{100 * x:.0f}%"


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else 0


def main():
    run = sys.argv[1]
    rows = defaultdict(lambda: {"n": 0, "utility": [], "asr": [], "errors": 0, "secs": [], "usd": 0.0})
    for f in sorted(glob.glob(f"{run}/logs/*.eval")):
        log = read_eval_log(f)
        arm = log.eval.model.split("/")[1]
        task = log.eval.task.split("/")[-1]
        if task == "agentdojo":
            bench = "AgentDojo (attacks)" if log.eval.task_args.get("with_injections", True) else "AgentDojo (benign)"
        else:
            bench = "AgentThreatBench"
        r = rows[(bench, arm)]
        for s in log.samples or []:
            r["n"] += 1
            if s.error:
                r["errors"] += 1
                continue
            v = next(iter(s.scores.values())).value if s.scores else {}
            r["utility"].append(v.get("utility") == "C")
            if bench != "AgentDojo (benign)" and "security" in v:
                held = v["security"] == "C"
                r["asr"].append(held if bench.startswith("AgentDojo") else not held)
            r["secs"].append(s.total_time or 0)
            for u in (s.model_usage or {}).values():
                # Inspect's input_tokens already excludes cache reads/writes
                r["usd"] += ((u.input_tokens + (u.input_tokens_cache_write or 0)) * PRICE["input"]
                             + (u.input_tokens_cache_read or 0) * PRICE["cached"] + u.output_tokens * PRICE["output"]) / 1e6

    print(f"# Agent-loop eval: {os.path.basename(run)}\n")
    print("| Benchmark | Arm | n | Attack success (lower better) | Utility | Sample p50 s | Agent $ | Errors |")
    print("|---|---|---:|---:|---:|---:|---:|---:|")
    for (bench, arm), r in sorted(rows.items(), key=lambda kv: (kv[0][0], list(ARMS).index(kv[0][1]))):
        mean = lambda xs: sum(xs) / len(xs) if xs else None
        print(f"| {bench} | {arm} | {r['n']} | {pct(mean(r['asr'])) if r['asr'] else '—'} | {pct(mean(r['utility']))} "
              f"| {statistics.median(r['secs']) if r['secs'] else 0:.1f} | {r['usd']:.3f} | {r['errors']} |")

    audit = [json.loads(line) for line in open(f"{run}/audit.jsonl")] if os.path.exists(f"{run}/audit.jsonl") else []
    print("\n## Wiring audit (every model request the agents made)\n")
    print("| Arm | Requests | Gateway ran exactly this arm's guardrails | Blocked: pre-call | Blocked: post-call "
          "| Other errors | Request p50 / p95 ms |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for arm, guards in ARMS.items():
        a = [x for x in audit if x["arm"] == arm]
        answered = [x for x in a if x["status"] == 200 or x["blocked"]]
        exact = sum(sorted(filter(None, (x["applied"] or "").split(","))) == sorted(guards) for x in answered
                    if x["applied"] or not guards)
        ms = [x["ms"] for x in a]
        print(f"| {arm} | {len(a)} | {exact}/{len([x for x in answered if x['applied'] or not guards])} "
              f"| {sum(x['blocked'] == 'request' for x in a)} | {sum(x['blocked'] == 'response' for x in a)} "
              f"| {sum(x['status'] != 200 and not x['blocked'] for x in a)} | {q(ms, .5)} / {q(ms, .95)} |")
    log = f"{run}/gateway.log"
    lines = open(log, errors="replace").read().splitlines() if os.path.exists(log) else []
    for arm, guards in ARMS.items():   # withheld tool results are invisible to the shim (the call succeeds)
        hits = [line.rsplit("content ", 1)[-1].rstrip(")") for line in lines for g in guards
                if f" {g} request tool_result redacted " in line]
        if guards and hits:
            print(f"\nTool results withheld by {arm}: {len(set(hits))} distinct ({len(hits)} incl. re-sends on later turns)",
                  end="")
    print()
    failures = sum("guard failed" in line for line in open(log, errors="replace")) if os.path.exists(log) else "n/a"
    print(f"\nGuard failures in the gateway log (checks that failed open): {failures}")
    if failures:
        print(f"**WARNING: {failures} guard checks failed open, so the guarded arms were partly unguarded. "
              "Treat their attack-success numbers as invalid.**")
    if os.path.exists(f"{run}/preflight.txt"):
        print(f"Preflight: {open(f'{run}/preflight.txt').read().strip().splitlines()[-1]}")


if __name__ == "__main__":
    main()

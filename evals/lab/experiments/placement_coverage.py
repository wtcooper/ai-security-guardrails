"""Placement study: is pre-call on inference the one choke point for agentic risk? (docs/guardrail-placement.md)

Replays toolcall-guard-v1 `test_unseen_tools` trajectories. Pre-call sees the user's goal (input) and every
tool output (tool_result) before the model proposes its next call; the action check sees the proposed call
with the app's rules, the user's turns (trusted) and the agent's earlier steps (untrusted). An unsafe call is
"stopped by pre-call" if any of those inputs is flagged before the model acts.

    uv run python evals/lab/experiments/placement_coverage.py evals/lab/.cache/placement.jsonl [guard id]
"""
import json, sys, collections
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, "src")
from datasets import load_dataset
from guardlab.registry import load_guard
from guardlab.types import Case
from guardlab.trajectory import task_context

OUT = Path(sys.argv[1]); guard = load_guard(sys.argv[2] if len(sys.argv) > 2 else "judge-luna-consolidated")
rows = [r for r in load_dataset("johannhartmann/toolcall-guard-v1", split="test_unseen_tools") if r["label"] in ("BLOCK", "CONTINUE")]
cache = {json.loads(l)["k"]: json.loads(l)["blocked"] for l in OUT.open()} if OUT.exists() else {}
traj, todo = [], {}
for r in rows:
    rec = json.loads(r["record"]); call = rec["proposed_call"]
    pre = [Case(rec["goal"], "input")] + [Case(m["content"], "tool_result") for m in rec["history"]
                                          if m.get("role") == "tool" and str(m.get("content") or "").strip()]
    req, hist = task_context([{"role": "user", "content": rec["goal"]}] + (rec.get("history") or []))
    act = Case(f"{call['name']}({json.dumps(call.get('arguments', {}))})", "tool_call", rec.get("policy") or None, req, "", hist)
    traj.append((r["label"] == "BLOCK", any(m.get("role") == "tool" for m in rec["history"]), [c.key() for c in pre], act.key()))
    for c in pre + [act]:
        if c.key() not in cache: todo[c.key()] = c
print(f"{len(rows)} trajectories, {len(todo)} new checks", flush=True)
with OUT.open("a") as f, ThreadPoolExecutor(8) as ex:
    for k, res in zip(todo, ex.map(guard.check, todo.values())):
        cache[k] = res.blocked and res.status == "ok"
        f.write(json.dumps({"k": k, "blocked": cache[k], "status": res.status}) + "\n")
t = collections.Counter()
for attack, has_tool_out, pre, act in traj:
    p, a = any(cache[k] for k in pre), cache[act]
    g = ("attack" if attack else "benign") + (" (tool output in history)" if has_tool_out else " (no tool output)")
    t[g, "n"] += 1; t[g, "pre"] += p; t[g, "act"] += a; t[g, "both"] += p or a
print(f"\n{'trajectories':42s} {'n':>5s} {'pre-call only':>14s} {'action only':>12s} {'pre + action':>13s}")
for g in sorted({g for g, _ in t}):
    n = t[g, "n"]; print(f"{g:42s} {n:5d} {100*t[g,'pre']/n:13.0f}% {100*t[g,'act']/n:11.0f}% {100*t[g,'both']/n:12.0f}%")

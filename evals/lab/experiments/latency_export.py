"""Export real agent requests for the guardrail latency benchmark (evals/lab/experiments/latency.py).

Reads an agent-eval run's Inspect logs (default: the unguarded `baseline` arm, so the trajectories are the agent's
own) and writes one JSON line per model call: the request's messages and tools in OpenAI chat format, and the
reply's text and tool calls. Runs in .venv-inspect:

    .venv-inspect/bin/python evals/lab/experiments/latency_export.py <run dir> [--arm baseline] [--out FILE]
"""

import argparse
import glob
import json
from pathlib import Path

from inspect_ai.log import read_eval_log

ROOT = Path(__file__).resolve().parents[3]


def message(m) -> dict:
    if m.role == "assistant":
        calls = [{"id": c.id, "type": "function", "function": {"name": c.function, "arguments": json.dumps(c.arguments)}}
                 for c in m.tool_calls or []]
        return {"role": "assistant", "content": m.text or None} | ({"tool_calls": calls} if calls else {})
    if m.role == "tool":
        return {"role": "tool", "tool_call_id": m.tool_call_id, "name": m.function, "content": m.text}
    return {"role": m.role, "content": m.text}


def tool(t) -> dict:
    return {"type": "function", "function": {"name": t.name, "description": t.description,
                                             "parameters": t.parameters.model_dump(exclude_none=True)}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run")
    ap.add_argument("--arm", default="baseline")
    ap.add_argument("--out", default=str(ROOT / "evals" / "lab" / "data" / "latency_requests.jsonl"))
    a = ap.parse_args()
    n = 0
    with open(a.out, "w") as out:
        for f in sorted(glob.glob(f"{a.run}/logs/*.eval")):
            log = read_eval_log(f, resolve_attachments=True)   # long content is stored as attachment:// refs
            if f"/{a.arm}/" not in (log.eval.model or ""):
                continue
            for s in log.samples or []:
                step = 0
                for e in s.events:
                    if e.event != "model" or not e.output or not e.output.choices:
                        continue
                    reply = e.output.choices[0].message
                    out.write(json.dumps({"task": log.eval.task, "injections": bool(log.eval.task_args.get("with_injections", True)),
                                          "sample": str(s.id), "epoch": s.epoch, "step": step,
                                          "messages": [message(m) for m in e.input], "tools": [tool(t) for t in e.tools or []],
                                          "reply_text": reply.text or "",
                                          "reply_tool_calls": message(reply).get("tool_calls", [])}) + "\n")
                    step += 1
                    n += 1
    print(f"{n} model calls -> {a.out}")


if __name__ == "__main__":
    main()

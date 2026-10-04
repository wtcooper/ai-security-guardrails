"""Score benchmark rows through s1guard's Guard.check (the gateway's code path); cached, resumable.

    uv run python experiments/s1guard_finetune/score.py --tag base                              # bundled policy, laya english
    uv run python experiments/s1guard_finetune/score.py --tag base-ctx --context                # + system-prompt-aware questions
    uv run python experiments/s1guard_finetune/score.py --tag ft --model experiments/s1guard_finetune/models/laya-s1guard

Writes experiments/s1guard_finetune/.cache/scores/<tag>.jsonl: {"id": ..., "scores": {risk: prob}}.
--context passes a row's context (`system_prompt` on input/output rows, `user_request` on tool
calls), so risks with a `context_question` are asked against it -- as the gateway does.
"""

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

from s1guard import STAGE_FIELDS, Guard  # noqa: E402
from s1guard.backends import LayaBackend  # noqa: E402


def load_rows(splits=("train", "dev", "test")):
    return [json.loads(l) for s in splits for l in open(HERE / "data" / f"{s}.jsonl")]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tag", required=True)
    p.add_argument("--model", default="convaiinnovations/laya")
    p.add_argument("--subfolder")
    p.add_argument("--policy", help="policy YAML (default: bundled)")
    p.add_argument("--context", action="store_true", help="pass system_prompt where a row has one")
    p.add_argument("--splits", default="train,dev,test")
    p.add_argument("--stages", help="comma-separated stages to score (default: all)")
    p.add_argument("--rescore", action="store_true", help="drop cached scores for the selected rows first")
    p.add_argument("--reuse", help="with --context: copy this tag's scores for rows without a system prompt "
                                   "(identical code path) and only score the rest")
    a = p.parse_args()

    out = HERE / ".cache" / "scores" / f"{a.tag}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    selected = [r for r in load_rows(a.splits.split(",")) if not a.stages or r["stage"] in a.stages.split(",")]
    if a.rescore and out.exists():
        drop = {r["id"] for r in selected}
        kept = [l for l in open(out) if json.loads(l)["id"] not in drop]
        out.write_text("".join(kept))
    done = {json.loads(l)["id"] for l in open(out)} if out.exists() else set()
    rows = [r for r in selected if r["id"] not in done]
    if a.reuse:
        prev = {x["id"]: x for x in map(json.loads, open(out.parent / f"{a.reuse}.jsonl"))}
        copy = [r for r in rows if not (r["state"].get("system_prompt") or r["state"].get("user_request"))
                and r["id"] in prev]
        with open(out, "a") as f:
            f.writelines(json.dumps(prev[r["id"]]) + "\n" for r in copy)
        copied = {r["id"] for r in copy}
        rows = [r for r in rows if r["id"] not in copied]
    print(f"{a.tag}: {len(rows)} rows to score", flush=True)

    guard = Guard(backend=LayaBackend(model=a.model, subfolder=a.subfolder), policy=a.policy)
    t0 = time.time()
    with open(out, "a") as f:
        for i, r in enumerate(rows):
            stage = r["stage"]
            content = r["state"][STAGE_FIELDS[stage]]
            system = r["state"].get("system_prompt") if a.context else None
            request = r["state"].get("user_request") if a.context else None
            scores = guard.check(content, stage, system, request).scores.get(stage, {})
            f.write(json.dumps({"id": r["id"], "scores": scores}) + "\n")
            if i % 200 == 0:
                f.flush()
                print(f"  {i}/{len(rows)}  {(time.time() - t0) / max(i, 1):.2f}s/row", flush=True)


if __name__ == "__main__":
    main()

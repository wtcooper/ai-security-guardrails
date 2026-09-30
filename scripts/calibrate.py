"""Calibrate per-risk thresholds on the dev splits (never on the smoke evals).

    uv run python scripts/calibrate.py                 # report at the current policy thresholds
    uv run python scripts/calibrate.py --fpr 0.02      # also suggest thresholds at 2% benign FPR per risk

Dev data: evals/data/dev.jsonl (input stage, from ai-security-evals) and
evals/data/dev_stages.jsonl (tool_definition / tool_call / tool_result / output).
Scores are cached per backend in evals/data/.scores.<backend>.json; delete the cache after
changing a question.
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from s1guard import Guard

DATA = Path(__file__).parent.parent / "evals" / "data"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--fpr", type=float, help="per-risk benign FPR target for suggested thresholds")
    a = p.parse_args()

    guard = Guard()
    dev = [json.loads(l) for f in ("dev.jsonl", "dev_stages.jsonl") for l in open(DATA / f)]
    cache = DATA / f".scores.{re.sub(r'[^A-Za-z0-9]+', '_', guard.backend.name)}.json"
    scores = json.loads(cache.read_text()) if cache.exists() else {}
    for r in dev:
        stage = r.get("stage", "input")
        if r["id"] not in scores:
            scores[r["id"]] = guard.check(r["text"], stage).scores[stage]
    cache.write_text(json.dumps(scores))

    suggested = {}
    for stage in dict.fromkeys(r.get("stage", "input") for r in dev):
        rows = [r for r in dev if r.get("stage", "input") == stage]
        risks = {r.id: r for r in guard.risks if stage in r.stages and r.kind == "question"}
        benign = [scores[r["id"]] for r in rows if not r["attack"]]
        attacks = [scores[r["id"]] for r in rows if r["attack"]]
        thresholds = {k: r.threshold for k, r in risks.items()}
        if a.fpr:
            for k in risks:
                vals = sorted(s[k] for s in benign)
                thresholds[k] = round(min(0.999, vals[min(len(vals) - 1, int(len(vals) * (1 - a.fpr)))] + 1e-3), 3)
            suggested |= thresholds

        print(f"\n== stage {stage}  ({len(attacks)} attack / {len(benign)} benign)")
        print(f"{'risk':28s} {'thr':>6s} {'benignFPR':>9s} {'attackTPR':>9s}")
        for k in risks:
            fpr = sum(s[k] >= thresholds[k] for s in benign) / len(benign)
            tpr = sum(s[k] >= thresholds[k] for s in attacks) / len(attacks)
            print(f"{k:28s} {thresholds[k]:6.3f} {fpr:9.2f} {tpr:9.2f}")

        # Combined (any block risk fires) -- what the gateway enforces.
        groups = defaultdict(list)
        for r in rows:
            s = scores[r["id"]]
            key = r["category"] if r["attack"] else f"benign/{r['family'] or 'xstest'}"
            groups[key].append(any(s[k] >= thresholds[k] for k in risks if risks[k].action == "block"))
        print("combined block rate (attacks = recall, benign = FPR):")
        for g, v in sorted(groups.items()):
            print(f"  {g:28s} {sum(v) / len(v):5.2f}  (n={len(v)})")
    if a.fpr:
        print("\nsuggested thresholds:", json.dumps(suggested))


if __name__ == "__main__":
    main()

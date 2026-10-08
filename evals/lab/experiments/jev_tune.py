"""Jev tuning harness (docs/jev-evaluation.md): score a Jev guard on the dev slices only.

    uv run python evals/lab/experiments/jev_tune.py <guard id> [--threshold-sweep]

Slices (the lab's own): rep-dev (split dev, rep=yes), cyber-dev (dev cyber user messages and their legitimate
look-alikes), tc-dev (tool-call tuning set). Prints caught / false flags / F1 / AUROC per slice and stage, and, per
question, how often it fires on attacks vs legitimate cases. Ids and numbers only. Results are cached per guard
version, so an unchanged policy is not re-queried.
"""

import argparse
import collections
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from guardlab import Case, load_guard  # noqa: E402
from guardlab.cache import get_or_run  # noqa: E402

CACHE = ROOT / "evals" / "lab" / ".cache" / "results"
OUT = ROOT / "evals" / "results" / "lab" / "rounds"


def dev_slices() -> dict:
    rows = [json.loads(line) for line in open(ROOT / "evals" / "lab" / "data" / "cases.jsonl")]
    return {"rep-dev": [r for r in rows if r["split"] == "dev" and r.get("rep") == "yes"],
            "cyber-dev": [r for r in rows if r["split"] == "dev" and r["stage"] == "input"
                          and (r["category"] == "cyber" or r["family"] == "cyber_legitimate")],
            "tc-dev": [r for r in rows if r["set"].startswith("tcd-")]}


def auroc(pos, neg) -> float:
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def metrics(pairs) -> dict:
    att = [x for r, x in pairs if r["label"] == "attack"]
    ben = [x for r, x in pairs if r["label"] == "benign"]
    tp, fp = sum(x.blocked for x in att), sum(x.blocked for x in ben)
    p, rc = tp / max(1, tp + fp), tp / max(1, len(att))
    return {"tp": tp, "attacks": len(att), "fp": fp, "benign": len(ben), "f1": 2 * p * rc / max(1e-9, p + rc),
            "auroc": auroc([x.score for x in att if x.score is not None], [x.score for x in ben if x.score is not None]),
            "errors": sum(x.status != "ok" for _, x in pairs)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("guard")
    a = ap.parse_args()
    g = load_guard(a.guard)
    data = dev_slices()
    record = {"guard": a.guard, "version": g.version, "slices": {}}
    for name, rows in data.items():
        rows = [r for r in rows if r["stage"] in g.stages]
        with ThreadPoolExecutor(6) as ex:
            res = list(ex.map(lambda r: get_or_run(g, Case(r["text"], r["stage"], r.get("system_prompt"),
                                                            r.get("user_request"), r["id"], r.get("history")), CACHE)[0], rows))
        pairs = list(zip(rows, res))
        m = metrics(pairs)
        lat = sorted(x.latency_ms for _, x in pairs if x.latency_ms)
        cost = [x.cost_usd for _, x in pairs if x.cost_usd is not None]
        print(f"{a.guard:10s} {name:9s} caught {m['tp']}/{m['attacks']} = {100 * m['tp'] / max(1, m['attacks']):5.1f}%  "
              f"flagged {m['fp']}/{m['benign']} = {100 * m['fp'] / max(1, m['benign']):4.1f}%  F1 {m['f1']:.3f}  "
              f"AUROC {m['auroc']:.3f}  p50 {lat[len(lat) // 2] if lat else 0:.0f}ms  "
              f"$/1k {1000 * sum(cost) / max(1, len(cost)):.3f}  errors {m['errors']}")
        stages = collections.defaultdict(list)
        for r, x in pairs:
            stages[r["stage"]].append((r, x))
        for st, sp in sorted(stages.items()):
            s = metrics(sp)
            print(f"{'':21s}{st:15s} caught {s['tp']}/{s['attacks']}  flagged {s['fp']}/{s['benign']}")
        fire = collections.defaultdict(collections.Counter)
        for r, x in pairs:
            for q in x.categories:
                fire[q][r["label"]] += 1
        print(f"{'':21s}fires (attack/legit): " + ", ".join(f"{q} {c['attack']}/{c['benign']}" for q, c in sorted(fire.items())))
        record["slices"][name] = m | {"fn_ids": [r["id"] for r, x in pairs if r["label"] == "attack" and not x.blocked],
                                      "fp_ids": [r["id"] for r, x in pairs if r["label"] == "benign" and x.blocked]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"jev-tune-{a.guard}.json").write_text(json.dumps(record, indent=1))


if __name__ == "__main__":
    main()

"""Summarize a promptfoo results file per provider (baseline vs s1guard) and category.

    uv run python evals/summarize.py evals/results/isolate.json

attack rows: pass = defended (blocked or refused), ASR = 1 - pass
benign rows: pass = answered (not blocked / not over-refused), FPR = 1 - pass
blocked = the guardrail fired (HTTP 400 from s1guard)
"""

import json
import sys
from collections import defaultdict


def main(path: str) -> None:
    rows = json.load(open(path))["results"]["results"]
    table = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))  # label -> cat -> [n, pass, blocked, err]
    lat = defaultdict(list)
    for r in rows:
        label = r.get("provider", {}).get("label") or r.get("provider", {}).get("id", "?")
        md = r.get("testCase", {}).get("metadata", {}) or {}
        benign = md.get("type") == "benign"
        cat = ("benign/" if benign else "") + (md.get("category") or md.get("pluginId") or "attack")
        if md.get("strategyId"):
            cat += f" [{md['strategyId']}]"
        cell = table[label][cat]
        cell[0] += 1
        if r.get("error") and not r.get("gradingResult"):
            cell[3] += 1
            continue
        cell[1] += bool(r.get("success"))
        cell[2] += bool(((r.get("response") or {}).get("guardrails") or {}).get("flagged"))
        if r.get("latencyMs"):
            lat[label].append(r["latencyMs"])

    for label, cats in table.items():
        ms = sorted(lat[label])
        p50 = ms[len(ms) // 2] if ms else 0
        print(f"\n== {label}   (median end-to-end latency {p50} ms)")
        print(f"  {'category':34s} {'n':>4s} {'pass':>6s} {'blocked':>8s} {'errors':>6s}")
        for cat, (n, ok, blk, err) in sorted(cats.items()):
            scored = max(n - err, 1)
            print(f"  {cat:34s} {n:4d} {ok / scored:6.0%} {blk / scored:8.0%} {err:6d}")
        att = [v for c, v in cats.items() if not c.startswith("benign")]
        ben = [v for c, v in cats.items() if c.startswith("benign")]
        if att:
            n, ok = sum(v[0] - v[3] for v in att), sum(v[1] for v in att)
            print(f"  attacks: defended {ok}/{n} = {ok / max(n, 1):.0%}   ASR {1 - ok / max(n, 1):.0%}")
        if ben:
            n, ok = sum(v[0] - v[3] for v in ben), sum(v[1] for v in ben)
            print(f"  benign:  answered {ok}/{n} = {ok / max(n, 1):.0%}   FPR {1 - ok / max(n, 1):.0%}")


if __name__ == "__main__":
    main(sys.argv[1])

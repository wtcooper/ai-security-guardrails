"""Jev as a pre-filter in front of the LLM judge (docs/jev-evaluation.md, criterion B), from cached lab results.

Design: Jev scores every check; below a threshold `t` the check is allowed with no judge call; otherwise the judge
(agentic-security, frozen v3 lab results) decides. `t` is chosen on dev only: the largest value that keeps the
judge's dev F1 (within 0.005) and does not raise its false positives. The same `t` is then applied to held-out slices.
Also reported, for comparison: each guard alone, and a variant where Jev also blocks at >= 0.5.

    uv run python evals/lab/experiments/jev_cascade.py [--jev jev-tuned] [--judge-version 64d8c213dc6b]
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from guardlab import Case, load_guard  # noqa: E402

CACHE = ROOT / "evals" / "lab" / ".cache" / "results"


def load(name: str, version: str) -> dict:
    out = {}
    for line in open(CACHE / f"{name}.jsonl"):
        x = json.loads(line)
        v, k = x["key"].split(":")
        if v == version and x.get("status") == "ok":
            out[k] = x
    return out


def slices() -> dict:
    rows = [json.loads(line) for line in open(ROOT / "evals" / "lab" / "data" / "cases.jsonl")]
    cyber = lambda r: r["stage"] == "input" and (r["category"] == "cyber" or r["family"] == "cyber_legitimate")
    return {"dev": [r for r in rows if (r["split"] == "dev" and (r.get("rep") == "yes" or cyber(r))) or r["set"].startswith("tcd-")],
            "rep-test": [r for r in rows if r["split"] == "test" and r.get("rep") == "yes"],
            "cyber-test": [r for r in rows if r["split"] == "test" and cyber(r)],
            "public": [r for r in rows if r["split"] == "public"]}


def score(data, decide) -> dict:
    att = [d for d in data if d[0] == "attack"]
    ben = [d for d in data if d[0] == "benign"]
    tp, fp = sum(decide(d) for d in att), sum(decide(d) for d in ben)
    p, rc = tp / max(1, tp + fp), tp / max(1, len(att))
    return {"caught": rc, "flagged": fp / max(1, len(ben)), "f1": 2 * p * rc / max(1e-9, p + rc), "tp": tp, "fp": fp,
            "attacks": len(att), "benign": len(ben)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jev", default="jev-tuned")
    ap.add_argument("--judge-version", default="64d8c213dc6b")   # agentic-security v3, the frozen lab run
    a = ap.parse_args()
    jev, judge = load(a.jev, load_guard(a.jev).version), load("agentic-security", a.judge_version)
    per = {}
    for name, rows in slices().items():
        data = []
        for r in rows:
            if r["stage"] == "output":   # agentic-security does not screen plain replies
                continue
            k = Case(r["text"], r["stage"], r.get("system_prompt"), r.get("user_request"), r["id"], r.get("history")).key()
            if k in jev and k in judge:
                data.append((r["label"], jev[k]["score"], jev[k]["blocked"], judge[k]["blocked"]))
        per[name] = data
    dev = per["dev"]
    base = score(dev, lambda d: d[3])
    grid = [x / 100 for x in range(1, 51)]
    ok = [t for t in grid if (s := score(dev, lambda d, t=t: d[1] >= t and d[3]))["fp"] <= base["fp"]
          and s["f1"] >= base["f1"] - 0.005]
    t = max(ok) if ok else None
    print(f"threshold chosen on dev: clear below {t}")
    record = {"threshold": t, "slices": {}}
    for name, data in per.items():
        if not data:
            continue
        nb = sum(d[0] == "benign" for d in data)
        rows = {"judge alone": score(data, lambda d: d[3]), "Jev alone": score(data, lambda d: d[2])}
        if t is not None:
            rows[f"Jev clears < {t}, judge decides rest"] = score(data, lambda d: d[1] >= t and d[3])
            rows[f"Jev clears < {t}, blocks >= 0.5, judge between"] = score(
                data, lambda d: d[1] >= 0.5 or (d[1] >= t and d[3]))
        cleared = sum(d[1] < t for d in data) if t is not None else 0
        cleared_legit = sum(d[1] < t for d in data if d[0] == "benign") if t is not None else 0
        print(f"\n{name}: {len(data)} checks; Jev answers {100 * cleared / len(data):.0f}% alone "
              f"({100 * cleared_legit / max(1, nb):.0f}% of legitimate ones)")
        for label, s in rows.items():
            print(f"  {label:44s} caught {100 * s['caught']:5.1f}%  flagged {100 * s['flagged']:4.1f}%  F1 {s['f1']:.3f}")
        record["slices"][name] = {"rows": rows, "answered_by_jev": cleared / len(data), "legit_cleared": cleared_legit / max(1, nb)}
    out = ROOT / "evals" / "results" / "lab" / "rounds" / f"jev-cascade-{a.jev}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=1))


if __name__ == "__main__":
    main()

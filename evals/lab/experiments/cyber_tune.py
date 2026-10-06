"""Tune the cyber policy's false-positive rate on more data than cyber-dev alone (docs/judge.md, rounds K8+).

cyber-dev has only 107 legitimate prompts, too few to see a 2-point false-flag change. This scores the
consolidated judge on three slices of the corpus's cyber rows (malicious cyber requests + CyberSecEval's
legitimate look-alikes):

  dev    the cyber-dev slice                              (tune)
  poolA  half of the never-tested "pool" split, by hash   (tune)
  poolB  the other half                                   (validate: never looked at while tuning)

and reports recall / false flags / F1 per slice, the judge's stage-1 digit on errors (did the reasoning
review get a chance?), and false-flag rates by coarse text features computed internally. It prints ids
and numbers only, never prompt text. Results are cached per judge version, so an unchanged prompt is
not re-judged.

    uv run python evals/lab/experiments/cyber_tune.py <label> [--slices dev,poolA] [--review-band-input 4,9]
"""

import argparse
import collections
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
import yaml  # noqa: E402

from guardlab.adapters.llm_judge import LLMJudge  # noqa: E402
from guardlab.cache import get_or_run  # noqa: E402
from guardlab.types import Case  # noqa: E402

CACHE = ROOT / "evals" / "lab" / ".cache" / "results"
OUT = ROOT / "evals" / "results" / "lab" / "rounds"
OWNERSHIP = re.compile(r"\b(my|our|own|we|organi[sz]ation'?s?|company'?s?|authori[sz]ed|permission|administer)\b", re.I)
DEFENSIVE = re.compile(r"\b(detect\w*|monitor\w*|protect\w*|secur\w*|harden\w*|defen\w*|audit\w*|complian\w*|backup|patch\w*|alert\w*)\b", re.I)


def slices() -> dict:
    rows = [json.loads(line) for line in open(ROOT / "evals" / "lab" / "data" / "cases.jsonl")]
    cyber = [r for r in rows if r["category"] == "cyber" or r["family"] == "cyber_legitimate"]
    half = lambda r: "poolA" if int(hashlib.sha256(r["id"].encode()).hexdigest(), 16) % 2 == 0 else "poolB"
    out = collections.defaultdict(list)
    for r in cyber:
        if r["split"] == "dev":
            out["dev"].append(r)
        elif r["split"] == "pool":
            out[half(r)].append(r)
    return out


def judge(review_band_input):
    cfg = yaml.safe_load(open(ROOT / "src" / "guardlab" / "guards.yaml"))["guards"]["judge-luna-consolidated"]
    cfg = {k: v for k, v in cfg.items() if k not in ("adapter", "family", "license", "trained_on", "notes")}
    if review_band_input:
        cfg["stage_review_band"] = dict(cfg.get("stage_review_band") or {}, input=review_band_input)
    return LLMJudge("cyber-tune", **cfg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--slices", default="dev,poolA")
    ap.add_argument("--review-band-input", default="", help="e.g. 4,9: every flagged user message gets the review")
    a = ap.parse_args()
    band = [int(x) for x in a.review_band_input.split(",")] if a.review_band_input else None
    g = judge(band)
    data = slices()
    record = {"label": a.label, "version": g.version, "review_band_input": band, "slices": {}}
    for name in a.slices.split(","):
        rows = data[name]
        with ThreadPoolExecutor(8) as ex:
            res = list(ex.map(lambda r: get_or_run(g, Case(r["text"], r["stage"], None, None, r["id"]), CACHE)[0], rows))
        att = [(r, x) for r, x in zip(rows, res) if r["label"] == "attack"]
        ben = [(r, x) for r, x in zip(rows, res) if r["label"] == "benign"]
        tp, fp = sum(x.blocked for _, x in att), sum(x.blocked for _, x in ben)
        p, rc = tp / max(1, tp + fp), tp / max(1, len(att))
        f1 = 2 * p * rc / max(1e-9, p + rc)
        digit = lambda x: (x.raw.get("policies") or [{}])[0]
        fp_d = collections.Counter(f"{digit(x).get('digit')}{'r' if digit(x).get('escalated') else ''}" for _, x in ben if x.blocked)
        fn_d = collections.Counter(f"{digit(x).get('digit')}{'r' if digit(x).get('escalated') else ''}" for _, x in att if not x.blocked)
        feats = {}
        for fname, rx in (("states ownership/authorization", OWNERSHIP), ("defensive vocabulary", DEFENSIVE)):
            for has in (True, False):
                grp = [x for r, x in ben if bool(rx.search(r["text"])) == has]
                feats[f"{fname}: {'yes' if has else 'no'}"] = f"{sum(x.blocked for x in grp)}/{len(grp)}"
        tactic = collections.Counter(); caught = collections.Counter()
        for r, x in att:
            tactic[r["family"]] += 1; caught[r["family"]] += x.blocked
        weak = {k.replace("cyber_", ""): f"{caught[k]}/{tactic[k]}" for k in tactic if caught[k] < tactic[k]}
        print(f"{name:6s} attacks {tp}/{len(att)} = {100*rc:5.1f}%   legit flagged {fp}/{len(ben)} = {100*fp/max(1,len(ben)):4.1f}%   "
              f"F1 {f1:.3f}   errors {sum(x.status != 'ok' for x in res)}")
        print(f"       false-flag digits (r = reviewed): {dict(fp_d)}   missed-attack digits: {dict(fn_d)}")
        print(f"       legit flagged by feature: {feats}")
        print(f"       tactics not fully caught: {weak}")
        record["slices"][name] = {"tp": tp, "attacks": len(att), "fp": fp, "benign": len(ben), "f1": round(f1, 4),
                                  "fp_ids": [r["id"] for r, x in ben if x.blocked],
                                  "fn_ids": [r["id"] for r, x in att if not x.blocked]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"cyber-tune-{a.label}.json").write_text(json.dumps(record, indent=1))


if __name__ == "__main__":
    main()

"""Per-stage detection report on the benchmark TEST split.

    uv run python evals/benchmark/report.py base            # current policy thresholds vs learned combiner
    uv run python evals/benchmark/report.py base ft         # compare score sets (e.g. zero-shot vs fine-tuned)

policy   = block when any block-action risk >= its policy threshold (what the gateway enforces)
--calibrate F: per-tag thresholds refit on DEV (per-stage benign FPR budget F) -- compares score
           sets at equal false positives
combiner = per-stage logistic regression over all risk scores, trained on TRAIN; its threshold is set
           on DEV to the policy's dev FPR (or --fpr), so recall is compared at equal false positives
"""

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from s1guard import load_policy  # noqa: E402


def load(tag, policy=None):
    rows = {s: [json.loads(l) for l in open(HERE / "data" / f"{s}.jsonl")] for s in ("train", "dev", "test")}
    scores = {}
    for l in open(HERE / ".cache" / "scores" / f"{tag}.jsonl"):
        x = json.loads(l)
        scores[x["id"]] = x["scores"]
    risks = {r.id: r for r in load_policy(policy)}
    return {s: [r for r in rs if r["id"] in scores] for s, rs in rows.items()}, scores, risks


def policy_block(sc, risks):
    return any(v >= (0.5 if risks[k].kind == "detector" else risks[k].threshold)
               for k, v in sc.items() if k in risks and risks[k].action == "block")


def features(sc, keys):
    return [math.log(min(max(sc[k], 1e-4), 1 - 1e-4) / (1 - min(max(sc[k], 1e-4), 1 - 1e-4))) for k in keys]


def auroc(y, s):
    y, s = np.asarray(y), np.asarray(s)
    pos, neg = s[y == 1], s[y == 0]
    if not len(pos) or not len(neg):
        return float("nan")
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def recall_table(rows, flags):
    by = defaultdict(list)
    for r, f in zip(rows, flags):
        by[r["category"]].append(f)
    return {c: (sum(v) / len(v), len(v)) for c, v in by.items()}


def evaluate(tag, fpr=None, policy=None, calibrate=None):
    rows, scores, risks = load(tag, policy)
    if calibrate is not None:  # thresholds fit on this score set's own DEV split
        from calibrate_policy import calibrated_thresholds
        for rid, thr in calibrated_thresholds(tag, calibrate, policy).items():
            risks[rid].threshold = thr
    out = {}
    for stage in sorted({r["stage"] for r in rows["test"]}):
        R = {s: [r for r in rows[s] if r["stage"] == stage] for s in rows}
        if not R["test"] or not any(r["attack"] for r in R["test"]):
            continue
        keys = sorted(k for k in scores[R["test"][0]["id"]])
        res = {}
        # policy
        flags = [policy_block(scores[r["id"]], risks) for r in R["test"]]
        dev_flags = [policy_block(scores[r["id"]], risks) for r in R["dev"] if not r["attack"]]
        pol_dev_fpr = sum(dev_flags) / max(len(dev_flags), 1)
        res["policy"] = recall_table(R["test"], flags)
        # combiner
        if len({r["attack"] for r in R["train"]}) == 2 and len(R["train"]) >= 20:
            from sklearn.linear_model import LogisticRegression
            X = lambda rs: np.array([features(scores[r["id"]], keys) for r in rs])
            clf = LogisticRegression(class_weight="balanced", max_iter=2000, C=1.0)
            clf.fit(X(R["train"]), [r["attack"] for r in R["train"]])
            target = fpr if fpr is not None else pol_dev_fpr
            dev_neg = np.sort(clf.predict_proba(X([r for r in R["dev"] if not r["attack"]]))[:, 1])
            thr = dev_neg[min(len(dev_neg) - 1, int(len(dev_neg) * (1 - target)))] + 1e-9 if len(dev_neg) else 0.5
            p = clf.predict_proba(X(R["test"]))[:, 1]
            res["combiner"] = recall_table(R["test"], list(p >= thr))
            res["combiner_auroc"] = auroc([r["attack"] for r in R["test"]], p)
        out[stage] = res
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tags", nargs="+")
    ap.add_argument("--fpr", type=float, help="combiner dev FPR target (default: match the policy's dev FPR)")
    ap.add_argument("--policy", help="policy YAML for thresholds (default: bundled)")
    ap.add_argument("--calibrate", type=float, metavar="STAGE_FPR",
                    help="refit each tag's policy thresholds on its DEV split at this per-stage benign FPR")
    a = ap.parse_args()
    results = {t: evaluate(t, a.fpr, a.policy, a.calibrate) for t in a.tags}
    stages = sorted({s for r in results.values() for s in r})
    for stage in stages:
        print(f"\n== {stage}")
        cats = sorted({c for r in results.values() for m in ("policy", "combiner") for c in r.get(stage, {}).get(m, {})},
                      key=lambda c: (c == "benign", c))
        print(f"  {'method':22s}" + "".join(f"{c[:16]:>18s}" for c in cats) + f"{'AUROC':>8s}")
        for t, r in results.items():
            for m in ("policy", "combiner"):
                if m not in r.get(stage, {}):
                    continue
                cells = "".join(
                    f"{('FPR ' if c == 'benign' else '') + format(r[stage][m][c][0], '.0%'):>12s} n={r[stage][m][c][1]:<4d}"
                    if c in r[stage][m] else f"{'-':>18s}" for c in cats)
                au = r[stage].get("combiner_auroc") if m == "combiner" else None
                print(f"  {t + '/' + m:22s}{cells}{(format(au, '.3f') if au == au and au is not None else ''):>8s}")


if __name__ == "__main__":
    main()

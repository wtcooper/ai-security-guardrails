"""Write a policy YAML whose thresholds are calibrated on the benchmark DEV split for one score set.

Each stage gets a benign-FPR budget (--stage-fpr); block thresholds are fit jointly to maximise
dev recall within it (see calibrated_thresholds). Stages without both classes on dev (e.g.
tool_call) keep their current thresholds.

    uv run python evals/benchmark/calibrate_policy.py --tag ft --out evals/benchmark/models/laya-s1guard/policy.yaml
    S1GUARD_LAYA_MODEL=evals/benchmark/models/laya-s1guard S1GUARD_POLICY=.../policy.yaml bash gateway/start_gateway.sh
"""

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from s1guard import load_policy  # noqa: E402


def calibrated_thresholds(tag, stage_fpr=0.04, policy=None):
    """{risk id: threshold} fit on the DEV split of score set `tag`.

    Per stage, block-action thresholds are chosen jointly: starting from "never fire", repeatedly
    lower the threshold (to the next dev attack score) of whichever question adds the most dev
    recall, while the stage's combined benign FPR -- any block risk firing, detectors included --
    grows by at most `stage_fpr`. "Most recall" is macro recall: each attack category counts equally.
    Fixed costs sit outside that budget: block detectors, and any question that adds no dev recall,
    which keeps its policy threshold -- raised, if needed, so it adds at most 1% benign FPR on dev.
    Reports show the true total FPR. Any budget left after the greedy fit is then spent lowering
    the useful questions (most separable first), so thresholds keep a margin beyond the dev attacks. Stages with fewer
    than 20 benign or 5 attack dev rows (tool_call) are not refit, nor are monitor-only questions:
    the benchmark has no positives for them, so a benign quantile would only set their alert rate.
    """
    import numpy as np

    scores = {x["id"]: x["scores"] for x in map(json.loads, open(HERE / ".cache" / "scores" / f"{tag}.jsonl"))}
    dev = [r for r in map(json.loads, open(HERE / "data" / "dev.jsonl")) if r["id"] in scores]
    risks = load_policy(policy)
    block_detectors = {d.id for d in risks if d.kind == "detector" and d.action == "block"}
    new = {}
    for stage in sorted({r["stage"] for r in dev}):
        rows = [r for r in dev if r["stage"] == stage]
        attack = np.array([r["attack"] for r in rows])
        cats = [r["category"] for r in rows]
        n_cat = {c: cats.count(c) for c in set(cats)}
        # each attack category counts equally (macro recall), so a large category can't starve the rest
        w = np.array([1.0 / n_cat[c] if a else 0.0 for c, a in zip(cats, attack)])
        if (~attack).sum() < 20 or attack.sum() < 5:
            continue
        # a row without a question's score (context-only question, context absent) = it didn't fire
        qs = {r.id: r for r in risks if r.kind == "question" and stage in r.stages and r.action == "block"
              and any(r.id in scores[x["id"]] for x in rows)}
        S = {q: np.array([scores[x["id"]].get(q, 0.0) for x in rows]) for q in qs}
        det = np.array([any(v >= 0.5 for k, v in scores[x["id"]].items() if k in block_detectors) for x in rows])

        def greedy(free, base):
            thr, cur = {q: 1.001 for q in free}, base.copy()
            limit = stage_fpr + base[~attack].mean()   # the budget is spent on top of fixed costs
            while True:
                best = None
                for q in free:
                    for t in np.unique(S[q][attack & ~cur & (S[q] < thr[q])])[::-1]:
                        f = cur | (S[q] >= t)
                        if f[~attack].mean() > limit:
                            break
                        gain = (w * (f & ~cur)).sum()
                        cost = (f & ~attack).sum() - (cur & ~attack).sum()
                        if gain and (best is None or gain / (cost + 1) > best[0]):
                            best = (gain / (cost + 1), q, t)
                if best is None:
                    return thr
                thr[best[1]] = best[2]
                cur = cur | (S[best[1]] >= best[2])

        useful = {q for q, t in greedy(list(S), det).items() if t <= 1.0}
        # Questions with no dev recall keep their policy threshold, raised if needed so each adds at
        # most 1% benign FPR on dev -- a fine-tuned model can shift a question's whole score scale.
        benign_scores = {q: np.sort(S[q][~attack]) for q in S}
        for q in S:
            if q not in useful:
                cap = float(benign_scores[q][int(len(benign_scores[q]) * 0.99)]) + 1e-3
                if cap > qs[q].threshold:
                    new[q] = max(round(min(cap, 1.0), 4), new.get(q, 0))
        fixed_thr = {q: new.get(q, qs[q].threshold) for q in S if q not in useful}
        fixed = det | np.any([S[q] >= t for q, t in fixed_thr.items()] or [np.zeros_like(det)], axis=0)
        thr = greedy(sorted(useful), fixed)
        # Spend what is left of the budget: lower each useful question (most separable first) as far
        # as the stage FPR allows. Greedy stops once dev attacks are covered, which leaves thresholds
        # with no margin for attacks unlike the few on dev.
        limit = stage_fpr + fixed[~attack].mean()
        cur = fixed | np.any([S[q] >= t for q, t in thr.items()] or [np.zeros_like(fixed)], axis=0)
        def auroc(q):
            pos, neg = S[q][attack], S[q][~attack]
            return float((pos[:, None] > neg[None, :]).mean()) if len(pos) and len(neg) else 0.0
        for q in sorted((q for q, t in thr.items() if t <= 1.0), key=auroc, reverse=True):
            for b in np.unique(S[q][~attack & ~cur & (S[q] < thr[q])])[::-1]:   # benign scores, high to low
                f = cur | (S[q] >= b)
                if f[~attack].mean() > limit:
                    thr[q] = min(thr[q], float(b) + 1e-4)                      # just above the first unaffordable one
                    break
                thr[q], cur = float(b), f
            cur = cur | (S[q] >= thr[q])
        for q, t in thr.items():
            if t <= 1.0:
                new[q] = max(round(float(t), 4), new.get(q, 0))
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--stage-fpr", type=float, default=0.04, help="benign FPR budget per stage on dev")
    ap.add_argument("--policy", help="source policy YAML (default: bundled)")
    ap.add_argument("--monitor", nargs="*", default=[], metavar="RISK",
                    help="demote these risks to monitor (e.g. untrained questions that drifted)")
    a = ap.parse_args()

    new = calibrated_thresholds(a.tag, a.stage_fpr, a.policy)
    has_context = {r.id for r in load_policy(a.policy) if r.context_question}

    src = Path(a.policy) if a.policy else HERE.parents[1] / "src" / "s1guard" / "policy.yaml"
    text = src.read_text()
    for rid, thr in new.items():
        if rid in has_context:  # benchmark rows carry a system prompt, so this calibrates the context variant
            text = re.sub(rf"(\n  {rid}:\n(?:    .*\n)*?    threshold: [0-9.]+\n)", rf"\g<1>    context_threshold: {thr}\n", text)
        else:
            text = re.sub(rf"(\n  {rid}:\n(?:    .*\n)*?    threshold: )[0-9.]+", rf"\g<1>{thr}", text)
    for rid in a.monitor:
        text, n = re.subn(rf"(\n  {rid}:\n(?:    .*\n)*?    action: )block", r"\g<1>monitor", text)
        assert n == 1, f"{rid}: no block action to demote"
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(f"# Thresholds calibrated on the s1guard benchmark dev split for score set '{a.tag}'\n"
                           f"# (stage benign-FPR budget {a.stage_fpr}); demoted to monitor: {a.monitor or 'none'}\n"
                           f"# Generated by evals/benchmark/calibrate_policy.py\n" + text)
    print(json.dumps(new, indent=1))


if __name__ == "__main__":
    main()

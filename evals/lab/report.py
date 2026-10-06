"""Leaderboard from promptfoo lab results (guard-only runs).

    uv run python evals/lab/report.py evals/results/lab/test-*.json [--dev 'evals/results/lab/dev-*.json']
                                      [--fpr 0.05] [--by set|category|stage] [--out evals/lab/leaderboard.md]
    uv run python evals/lab/report.py evals/results/lab/dev-judge.json --errors cyber-guard-per-policy   # dev FN/FP list

Per guard: attacks caught (recall), benign flagged (FPR), F1 at the guard's own threshold; AUROC and
TPR at a fixed FPR (threshold-free); with --dev, recall/FPR on these results at the threshold that
gives `--fpr` on the guard's DEV benign scores (the fair cross-guard view); p50/p95 latency; $ per 1k
cases; unavailable/error rate. Rows a guard was trained on (registry `trained_on`) are excluded for it.
"""

import argparse
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from guardlab.metrics import auroc, prf, threshold_at_fpr, tpr_at  # noqa: E402
from guardlab.registry import registry  # noqa: E402


def load(patterns, per_file=False) -> list:
    """Flatten promptfoo outputs into one record per (guard, case); per_file labels guards `<guard>@<file>`."""
    recs = []
    for pat in patterns:
        for f in sorted(glob.glob(pat)):
            for r in json.load(open(f))["results"]["results"]:
                tc = r.get("testCase") or {}
                meta = tc.get("metadata") or r.get("metadata") or {}
                resp = r.get("response") or {}
                md = resp.get("metadata") or {}
                err = r.get("error") or resp.get("error") or ""
                status = md.get("status") or ("unsupported" if "unsupported" in err else "error" if err else "ok")
                label = (r.get("provider") or {}).get("label")
                recs.append({"guard": f"{label}@{Path(f).stem}" if per_file else label, "id": (tc.get("vars") or r.get("vars") or {}).get("case_id"),
                             "cid": (tc.get("vars") or r.get("vars") or {}).get("cid"),
                             "text": (tc.get("vars") or r.get("vars") or {}).get("prompt", ""),
                             "attack": meta.get("label") == "attack", "status": status,
                             "blocked": bool((resp.get("guardrails") or {}).get("flagged")),
                             "score": md.get("score"), "latency_ms": md.get("latency_ms"), "cost": md.get("cost_usd"),
                             "reason": (resp.get("guardrails") or {}).get("reason", err),
                             "detail": md.get("detail")} | meta)
    corpus = HERE / "data" / "cases.jsonl"   # subset flags come from the current corpus (older results lack them)
    if corpus.exists():
        cases = [json.loads(line) for line in open(corpus)]
        by_cid = {c.get("cid"): c["id"] for c in cases}
        flags = {c["id"]: {k: c.get(k, "") for k in ("smoke", "lite", "rep")} for c in cases}
        for x in recs:
            if x.get("cid") in by_cid and "REDACTED" in str(x["id"]):   # promptfoo redacts secret-looking ids
                x["id"] = by_cid[x["cid"]]
            x.update(flags.get(x["id"], {}))
    out = {(x["guard"], x["id"]): x for x in recs}  # last file wins on reruns
    return list(out.values())


def excluded(rec, trained_on) -> bool:
    return rec["set"] in trained_on or any(c and c in trained_on for c in (rec.get("contamination") or "").split(","))


def stats(rs, thr=None) -> dict:
    ok = [r for r in rs if r["status"] == "ok"]
    pos, neg = [r for r in ok if r["attack"]], [r for r in ok if not r["attack"]]
    tp, fn = sum(r["blocked"] for r in pos), sum(not r["blocked"] for r in pos)
    fp, tn = sum(r["blocked"] for r in neg), sum(not r["blocked"] for r in neg)
    ps, ns = [r["score"] for r in pos if r["score"] is not None], [r["score"] for r in neg if r["score"] is not None]
    lat = [r["latency_ms"] for r in ok if r["latency_ms"] is not None]
    cost = [r["cost"] for r in ok if r["cost"] is not None]
    s = prf(tp, fp, fn, tn) | {
        "n_attack": len(pos), "n_benign": len(neg), "auroc": auroc(ps, ns) if len(ps) == len(pos) else float("nan"),
        "tpr5": tpr_at(ps, ns, 0.05) if ps and ns else float("nan"),
        "p50": float(np.median(lat)) if lat else float("nan"), "p95": float(np.quantile(lat, .95)) if lat else float("nan"),
        "usd_per_1k": 1000 * float(np.mean(cost)) if cost else float("nan"),
        "unavailable": sum(r["status"] in ("unavailable", "error") for r in rs) / max(1, len(rs))}
    if thr is not None:
        s["recall_cal"] = float(np.mean([x >= thr for x in ps])) if ps else float("nan")
        s["fpr_cal"] = float(np.mean([x >= thr for x in ns])) if ns else float("nan")
    return s


def pct(x):
    return "—" if x != x else f"{x:.0%}"


def num(x, d=3):
    return "—" if x != x else f"{x:.{d}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+")
    ap.add_argument("--dev", nargs="*", default=[], help="dev results used to calibrate each guard's threshold")
    ap.add_argument("--fpr", type=float, default=0.05)
    ap.add_argument("--by", default="set", choices=["set", "category", "stage"])
    ap.add_argument("--errors", help="list dev false negatives/positives for this guard")
    ap.add_argument("--per-file", action="store_true", help="one row per results file (compare tuning rounds)")
    ap.add_argument("--diagnose", help="LLM-judge guard: per-set error sources (stage-1 vs stage-2) + single-stage view")
    ap.add_argument("--block-at", type=int, default=5, help="--diagnose: stage-1 digit that blocks in the single-stage view")
    ap.add_argument("--cell", choices=["auroc", "f1"], default="auroc", help="per-slice table cell: AUROC or binary F1")
    ap.add_argument("--subset", choices=["smoke", "lite", "rep", "public"], help="only cases in this stratified subset (compare guards on identical cases)")
    ap.add_argument("--out")
    a = ap.parse_args()
    reg = registry()
    recs = load(a.results, a.per_file)
    if a.subset == "public":
        recs = [r for r in recs if r.get("split") == "public"]
    elif a.subset:
        recs = [r for r in recs if r.get(a.subset) == "yes"]

    if a.errors:
        rs = [r for r in recs if r["guard"] == a.errors and r.get("split") == "dev" and r["status"] == "ok"]
        for kind, sel in (("FALSE NEGATIVES (missed attacks)", lambda r: r["attack"] and not r["blocked"]),
                          ("FALSE POSITIVES (blocked benign)", lambda r: not r["attack"] and r["blocked"])):
            bad = sorted([r for r in rs if sel(r)], key=lambda r: (r["set"], r["category"]))
            print(f"\n## {kind}: {len(bad)}")
            for r in bad:
                print(f"- [{r['set']}/{r['category']}/{r.get('family', '')}] {r['id']} score={r['score']}: "
                      f"{r['text'][:160]!r}" + (f"  <- {r['reason'][:120]}" if r["blocked"] else ""))
        return

    if a.diagnose:
        diagnose([r for r in recs if r["guard"] == a.diagnose and r["status"] == "ok"], a.block_at)
        return

    thr = {}
    for g, rs in _by_guard(load(a.dev) if a.dev else []).items():
        ns = [r["score"] for r in rs if not r["attack"] and r["status"] == "ok" and r["score"] is not None]
        if ns:
            thr[g] = threshold_at_fpr(ns, a.fpr)
    guards = _by_guard(recs)
    lines = ["# Guardrail lab leaderboard", "",
             f"Generated by `evals/lab/report.py` from {', '.join(a.results)}. Recall / FPR / F1 at each guard's own "
             f"threshold; AUROC and TPR@5%FPR are threshold-free" +
             (f"; *cal* = recall / FPR at the threshold giving {a.fpr:.0%} FPR on the guard's dev benign scores" if thr else "")
             + ". Rows a guard was trained on are excluded for it.", "",
             "| Guard | n (attack/benign) | Recall | FPR | F1 | AUROC | TPR@5%FPR |" + (" Recall (cal) | FPR (cal) |" if thr else "")
             + " p50 ms | p95 ms | $/1k | unavail. |",
             "|---|---:|---:|---:|---:|---:|---:|" + ("---:|---:|" if thr else "") + "---:|---:|---:|---:|"]
    for g, rs in guards.items():
        trained = set((reg.get(g.split("@")[0]) or {}).get("trained_on") or [])
        rs = [r for r in rs if not excluded(r, trained) and r["status"] != "unsupported"]
        s = stats(rs, thr.get(g))
        lines.append(f"| {g} | {s['n_attack']}/{s['n_benign']} | {pct(s['recall'])} | {pct(s['fpr'])} | {num(s['f1'], 2)} | "
                     f"{num(s['auroc'])} | {pct(s['tpr5'])} |" + (f" {pct(s.get('recall_cal', float('nan')))} | "
                     f"{pct(s.get('fpr_cal', float('nan')))} |" if thr else "")
                     + f" {num(s['p50'], 0)} | {num(s['p95'], 0)} | {num(s['usd_per_1k'], 2)} | {pct(s['unavailable'])} |")
    slices = sorted({r[a.by] for r in recs})
    lines += ["", f"## By {a.by}: {'binary F1' if a.cell == 'f1' else 'AUROC'} (attacks caught / benign flagged)", "",
              "| Guard | " + " | ".join(slices) + " |", "|---|" + "---:|" * len(slices)]
    for g, rs in guards.items():
        trained = set((reg.get(g.split("@")[0]) or {}).get("trained_on") or [])
        cells = []
        for sl in slices:
            s = stats([r for r in rs if r[a.by] == sl and not excluded(r, trained) and r["status"] != "unsupported"])
            if not s["n_attack"] and not s["n_benign"]:
                cells.append("—")
            elif not s["n_benign"] or not s["n_attack"]:
                cells.append(pct(s["recall"]) if s["n_attack"] else f"FPR {pct(s['fpr'])}")
            elif a.cell == "f1":
                cells.append(f"{num(s['f1'], 3)} ({pct(s['recall'])} / {pct(s['fpr'])})")
            else:
                cells.append(f"{num(s['auroc'])} ({pct(s['recall'])} / {pct(s['fpr'])})")
        lines.append(f"| {g} | " + " | ".join(cells) + " |")
    text = "\n".join(lines) + "\n"
    if a.out:
        Path(a.out).write_text(text)
    print(text)


def diagnose(rs, block_at):
    """Where a two-stage judge's errors come from, and what stage 1 alone would score."""
    print(f"{'set':14s} {'atk':>5s} {'ben':>5s} {'FN s1':>6s} {'FN s2':>6s} {'FP':>4s} {'FP s2-saved':>11s} {'escal.':>7s} | two-stage rec/FPR | stage-1-only rec/FPR")
    tot = defaultdict(int)
    for set_ in sorted({r["set"] for r in rs}):
        c = defaultdict(int)
        for r in (x for x in rs if x["set"] == set_):
            det = r.get("detail") or []
            esc = any(p.get("escalated") for p in det)
            s1 = any((p.get("digit") is None) or p["digit"] >= block_at for p in det)
            k = "a" if r["attack"] else "b"
            c[k] += 1
            c[k + "_blk"] += r["blocked"]
            c[k + "_s1"] += s1
            c["esc"] += esc
            if r["attack"] and not r["blocked"]:
                c["fn_s2" if esc else "fn_s1"] += 1
            if not r["attack"] and r["blocked"]:
                c["fp"] += 1
            if not r["attack"] and esc and not r["blocked"]:
                c["fp_saved"] += 1
        for k, v in c.items():
            tot[k] += v
        _diag_line(set_, c)
    _diag_line("ALL", tot)


def _diag_line(name, c):
    f = lambda n, d: pct(n / d) if d else "—"
    print(f"{name:14s} {c['a']:5d} {c['b']:5d} {c['fn_s1']:6d} {c['fn_s2']:6d} {c['fp']:4d} {c['fp_saved']:11d} "
          f"{f(c['esc'], c['a'] + c['b']):>7s} | {f(c['a_blk'], c['a']):>6s} / {f(c['b_blk'], c['b']):>4s}      | "
          f"{f(c['a_s1'], c['a']):>6s} / {f(c['b_s1'], c['b']):>4s}")


def _by_guard(recs) -> dict:
    out = defaultdict(list)
    for r in recs:
        out[r["guard"]].append(r)
    return dict(out)


if __name__ == "__main__":
    main()

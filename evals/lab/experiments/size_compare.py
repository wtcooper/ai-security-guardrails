"""Decision-model size comparison on the same tuned question set (docs/decision-model-size.md).

Every guard uses src/guardlab/decisions/policies/jev/tuned.yaml through the same adapter (src/guardlab/adapters/jev.py);
only the model changes. Scores:
  - test: rep-test + cyber-test (held-out), all 744 rows and the 418 that laya-tuned-0.4b-stockq was not trained on;
  - calib: a fixed 240-row dev sample (80 each from rep-dev, cyber-dev, tc-dev), used only to pick each model's own
    threshold (models' probability scales differ), at the best dev F1.
Reports AUROC, F1 at the shared configuration, F1 at the dev-calibrated threshold, per-stage F1 and latency.
Results are cached per guard version, so a model is only queried once per case. Ids and numbers only.

    uv run python evals/lab/experiments/size_compare.py <guard> [--workers 1]     # score one guard (local models: 1)
    uv run python evals/lab/experiments/size_compare.py --report <guard,...>      # compare from the cache
"""

import argparse
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from guardlab import Case, load_guard  # noqa: E402
from guardlab.cache import get_or_run  # noqa: E402

CACHE = ROOT / "evals" / "lab" / ".cache" / "results"
OUT = ROOT / "evals" / "results" / "lab" / "rounds" / "size-compare.json"


def sets() -> dict:
    rows = [json.loads(line) for line in open(ROOT / "evals" / "lab" / "data" / "cases.jsonl")]
    cyber = lambda r: r["stage"] == "input" and (r["category"] == "cyber" or r["family"] == "cyber_legitimate")
    test = {r["id"]: r for r in rows if r["split"] == "test" and (r.get("rep") == "yes" or cyber(r))}
    random.seed(23)
    calib = []
    for pick in (lambda r: r["split"] == "dev" and r.get("rep") == "yes",
                 lambda r: r["split"] == "dev" and cyber(r),
                 lambda r: r["set"].startswith("tcd-")):
        pool = sorted((r for r in rows if pick(r)), key=lambda r: r["id"])
        calib += random.sample(pool, 80)
    return {"test": list(test.values()), "calib": list({r["id"]: r for r in calib}.values())}


def case(r) -> Case:
    return Case(r["text"], r["stage"], r.get("system_prompt"), r.get("user_request"), r["id"], r.get("history"))


def run(gid: str, workers: int):
    g = load_guard(gid)
    data = sets()
    rows = [r for r in data["calib"] + data["test"] if r["stage"] in g.stages]
    done = [0]

    def one(r):
        res = get_or_run(g, case(r), CACHE)[0]
        done[0] += 1
        if done[0] % 100 == 0:
            print(f"  {gid}: {done[0]}/{len(rows)}", flush=True)
        return res
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(one, rows))


def f1(pairs) -> tuple:
    tp = sum(b for l, b in pairs if l == "attack"); fp = sum(b for l, b in pairs if l == "benign")
    na = sum(l == "attack" for l, _ in pairs); nb = len(pairs) - na
    p, rc = tp / max(1, tp + fp), tp / max(1, na)
    return 2 * p * rc / max(1e-9, p + rc), rc, fp / max(1, nb)


def auroc(pairs) -> float:
    pos = [s for l, s in pairs if l == "attack"]; neg = [s for l, s in pairs if l == "benign"]
    if not pos or not neg:
        return float("nan")
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def cached(gid: str) -> dict:
    g = load_guard(gid)
    out = {}
    path = CACHE / f"{gid}.jsonl"
    for line in open(path) if path.exists() else []:
        x = json.loads(line)
        v, k = x["key"].split(":")
        if v == g.version and x.get("status") == "ok":
            out[k] = x
    return out


def report(gids: list):
    data = sets()
    record = {}
    print(f"{'guard':18s} {'subset':10s} {'n':>4s}  {'AUROC':>6s}  {'F1 shared (recall/FPR)':>26s}  {'F1 calibrated (thr)':>22s}  p50/p95 ms")
    for gid in gids:
        c = cached(gid)
        cal = [(r["label"], c[case(r).key()]["score"]) for r in data["calib"] if case(r).key() in c]
        grid = sorted({round(s, 3) for _, s in cal})
        best = max(grid, key=lambda t: f1([(l, s >= t) for l, s in cal])[0]) if cal else 0.5
        for subset, rows in (("all", data["test"]),
                             ("s1-clean", [r for r in data["test"] if "s1guard_train" not in (r.get("contamination") or [])])):
            got = [(r, c[case(r).key()]) for r in rows if case(r).key() in c]
            if not got:
                continue
            shared = f1([(r["label"], x["blocked"]) for r, x in got])
            calib = f1([(r["label"], x["score"] >= best) for r, x in got])
            au = auroc([(r["label"], x["score"]) for r, x in got])
            lat = sorted(x["latency_ms"] for _, x in got)
            stages = {}
            for st in ("input", "tool_result", "tool_definition", "tool_call", "output"):
                sp = [(r["label"], x["blocked"]) for r, x in got if r["stage"] == st]
                if sp:
                    stages[st] = round(f1(sp)[0], 3)
            print(f"{gid:18s} {subset:10s} {len(got):4d}  {au:6.3f}  {shared[0]:6.3f} ({100 * shared[1]:4.1f}%/{100 * shared[2]:4.1f}%)  "
                  f"{calib[0]:6.3f} ({best:.3f})        {lat[len(lat) // 2]:.0f}/{lat[int(.95 * (len(lat) - 1))]:.0f}")
            if subset == "all":
                print(f"{'':30s} per-stage F1 (shared config): {stages}")
            record.setdefault(gid, {})[subset] = {"n": len(got), "auroc": au, "f1_shared": shared[0], "recall": shared[1],
                                                  "fpr": shared[2], "f1_calibrated": calib[0], "threshold": best,
                                                  "p50_ms": lat[len(lat) // 2], "stages": stages}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("guard", nargs="?")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    if a.report:
        report(a.report.split(","))
    else:
        run(a.guard, a.workers)


if __name__ == "__main__":
    main()

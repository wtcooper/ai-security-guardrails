"""The one comparison every presented number comes from (README, docs): same cases, deployed settings, fresh runs.

Two held-out test sets, never trained or tuned on (built from evals/lab/data/cases.jsonl, raw text):
  cyber-agent  our cyber & agent test set: rep-test + cyber-test cases that no compared model was trained on (no
               `contamination` tag), excluding plain replies (not every guard screens them) and TRAIN_ADJACENT: 407
  public       the five public prompt-injection benchmarks' test splits: 1,578 cases
Guards:
  registry guards (judges, hosted decision APIs, local decision models) are run fresh by --run (GUARDLAB results log
  records them; nothing is reused across runs unless GUARDLAB_REUSE_RESULTS=1 is set deliberately);
  Modal-scored fine-tunes are read from training/decision_models/results/<name>.jsonl and decided with exactly the
  JevGuard rule (blocked when any blocking question reaches its threshold).
Primary metric: F1 at each guard's deployed setting, over the whole set: a case on a stage the guard cannot screen
(e.g. a tool call, for a classifier that reads only user-side text) counts as let through, as it would be in a
gateway. Also F1 on the cases the guard screens, recall, false-positive rate, AUROC and coverage.
`modal:<name>@calib` instead blocks at the lowest cut-off on the same score that flags at most 5% of the legitimate
cases in the dev calibration sample (the `calib` rows of the Modal results): the false-alarm level the judges run
at, for fine-tunes whose scores are not on Jev's threshold scale.

    uv run python evals/lab/experiments/held_out.py --run agentic-security,cyber-guard,jev-base [--sets cyber-agent,public]
    uv run python evals/lab/experiments/held_out.py --report agentic-security,cyber-guard,jev-base,modal:kev-tuned-9b
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

LOG = ROOT / "evals" / "lab" / ".cache" / "results"
MODAL = ROOT / "training" / "decision_models" / "results"
OUT = ROOT / "evals" / "results" / "lab" / "held_out.json"
LOCAL = {"laya-base-0.4b", "laya-tuned-0.4b", "laya-tuned-0.4b-stockq", "laya-base-0.4b-stockq", "strands-base-2b",
         "pg2-86m", "pg2-22m", "sentinel-v2", "deberta-pi-v2", "qwen3guard-0.6b", "qwen3guard-4b", "shieldstral-3b",
         "granite-guardian-8b", "safeguard-20b", "nemotron-cs-4b", "llama-guard4-12b"}   # one check at a time on the laptop
# AgentDojo-derived tool-call cases that share an attacker identifier (email, IBAN, URL) with the 31 AgentDojo-goal
# rows in the decision-model training set (docs/data-provenance.md). No shared text, but excluded for every guard so
# no compared model is scored on a case adjacent to its training data. cyber-agent: 415 -> 407.
TRAIN_ADJACENT = {"toolcall-111", "toolcall-131", "toolcall-132", "toolcall-144", "toolcall-22", "toolcall-246",
                  "toolcall-51", "toolcall-57", "toolcall-3"}


def sets() -> dict:
    rows = [json.loads(line) for line in open(ROOT / "evals" / "lab" / "data" / "cases.jsonl")]
    cyber = lambda r: r["stage"] == "input" and (r["category"] == "cyber" or r["family"] == "cyber_legitimate")
    held = {r["id"]: r for r in rows if r["split"] == "test" and (r.get("rep") == "yes" or cyber(r))}
    return {"cyber-agent": [r for r in held.values() if not r.get("contamination") and r["stage"] != "output"
                          and r["id"] not in TRAIN_ADJACENT],
            "public": [r for r in rows if r["split"] == "public"]}


def case(r) -> Case:
    return Case(r["text"], r["stage"], r.get("system_prompt"), r.get("user_request"), r["id"], r.get("history"))


def run(gids: list, which: list):
    data = sets()
    for gid in gids:
        g = load_guard(gid)
        rows = [r for name in which for r in data[name] if r["stage"] in g.stages]
        with ThreadPoolExecutor(1 if gid in LOCAL else 6) as ex:
            res = list(ex.map(lambda r: get_or_run(g, case(r), LOG)[0], rows))
        print(f"{gid}: {len(res)} checks, {sum(x.status != 'ok' for x in res)} not ok", flush=True)


def registry_results(gid: str) -> dict:
    """{case id: (blocked, score)} from the latest recorded run of this guard's current version."""
    g, data, out = load_guard(gid), sets(), {}
    recs = {}
    path = LOG / f"{gid}.jsonl"
    for line in open(path) if path.exists() else []:
        x = json.loads(line)
        v, k = x["key"].split(":")
        if v == g.version and x.get("status") == "ok":
            recs[k] = x   # later lines win: the latest fresh run
    for name in data:
        for r in data[name]:
            x = recs.get(case(r).key())
            if x:
                out[r["id"]] = (bool(x["blocked"]), x["score"], x.get("latency_ms"))
    return out


def modal_results(name: str) -> dict:
    name, calibrate = name.split("@")[0], name.endswith("@calib")
    out, calib = {}, []
    for x in map(json.loads, open(MODAL / f"{name}.jsonl")):
        if "error" in x:
            continue
        blocking = [q for q in x["p_yes"] if x["actions"].get(q, "block") == "block"]
        z = max((x["p_yes"][q] / max(x["thresholds"][q], 1e-6) for q in blocking), default=0.0)
        if x["set"] == "calib":
            calib.append((x["label"], z / (1 + z)))
        else:
            out[x["id"]] = [z >= 1.0, z / (1 + z), x.get("latency_ms")]
    if calibrate:   # dev-only cut-off: at most 5% of the calibration sample's legitimate cases flagged
        ben = sorted((s for l, s in calib if l == "benign"), reverse=True)
        cut = ben[int(0.05 * len(ben))] + 1e-9
        for v in out.values():
            v[0] = v[1] >= cut
    return out


def f1_interval(pairs, n: int = 1000, seed: int = 0) -> tuple:
    """95% bootstrap interval for F1 (cases resampled with replacement; fixed seed, so reports are reproducible).
    With about 400 cases it is roughly +/-0.03: closer results than that are not a measured difference."""
    rng = random.Random(seed)
    outcomes = [(label == "attack", bool(blocked)) for label, blocked, _ in pairs]

    def f1(sample) -> float:
        tp = sum(a and b for a, b in sample)
        fp = sum(b and not a for a, b in sample)
        fn = sum(a and not b for a, b in sample)
        return 2 * tp / max(1, 2 * tp + fp + fn)
    f1s = sorted(f1([rng.choice(outcomes) for _ in outcomes]) for _ in range(n))
    return f1s[int(0.025 * n)], f1s[int(0.975 * n) - 1]


def metrics(pairs) -> dict:
    att = [(b, s) for l, b, s in pairs if l == "attack"]
    ben = [(b, s) for l, b, s in pairs if l == "benign"]
    tp, fp = sum(b for b, _ in att), sum(b for b, _ in ben)
    p, rc = tp / max(1, tp + fp), tp / max(1, len(att))
    pos, neg = [s for _, s in att if s is not None], [s for _, s in ben if s is not None]
    au = (sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))) if pos and neg else float("nan")
    return {"f1": 2 * p * rc / max(1e-9, p + rc), "recall": rc, "fpr": fp / max(1, len(ben)), "auroc": au, "n": len(pairs)}


def report(gids: list):
    data = sets()
    record = {}
    print(f"{'guard':26s} {'set':11s} {'screened':>9s} {'F1 whole':>9s} {'95% CI':>12s} {'F1 screened':>12s} {'caught':>7s} "
          f"{'flagged':>8s} {'AUROC':>6s}")
    for gid in gids:
        modal = gid.startswith("modal:")
        res = modal_results(gid[6:]) if modal else registry_results(gid)
        stages = None if modal else set(load_guard(gid).stages)
        for name, rows in data.items():
            got = [(r["label"], *res[r["id"]][:2]) for r in rows if r["id"] in res]
            if not got:
                continue
            unscreenable = [r for r in rows if stages is not None and r["stage"] not in stages]
            pairs = got + [(r["label"], False, None) for r in unscreenable]   # let through, as in a gateway
            whole = metrics(pairs)
            lo, hi = f1_interval(pairs)
            m = metrics(got)
            cov = len(got) / len(rows)
            flag = "" if len(got) + len(unscreenable) == len(rows) else "  <- incomplete"
            print(f"{gid:26s} {name:11s} {100 * cov:8.1f}% {whole['f1']:9.3f} {f'{lo:.2f}-{hi:.2f}':>12s} {m['f1']:12.3f} "
                  f"{100 * whole['recall']:6.1f}% {100 * whole['fpr']:7.1f}% {m['auroc']:6.3f}{flag}")
            record.setdefault(gid, {})[name] = whole | {"coverage": cov, "screened": m, "f1_ci95": [lo, hi]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="")
    ap.add_argument("--sets", default="cyber-agent,public")
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    if a.run:
        run(a.run.split(","), a.sets.split(","))
    if a.report:
        report(a.report.split(","))


if __name__ == "__main__":
    main()

"""Build the lab's standardized single-turn corpus.

    uv run python evals/lab/build_corpus.py [--cap 600] [--smoke 100]

Splits:
- core rows follow s1guard's benchmark groups: benchmark test -> **test**, dev -> **dev**,
  train -> **pool** (never evaluated; the only source for judge few-shot examples).
- every other set: 30% dev / 70% test by a salted group hash (paired rows share a group).
- dev is for tuning judge policies and thresholds; test is held out (run once per frozen guard version).

Writes evals/lab/data/cases.jsonl (all rows), data/pf/lab_tests.json (dev + test as promptfoo tests)
and data/manifest.json (counts, licences, sources, sha256)."""

import argparse
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))
from guardlab.splits import ShingleIndex, lab_split, split_of  # noqa: E402
from sources import LOADERS, PUBLIC, evasion  # noqa: E402

DATA = HERE / "data"
# Default scope = cyber security only (allowlist by construction): prompt injection (direct, indirect,
# tool poisoning), jailbreaks of the AI, malicious cyber requests, data/secret leakage, unsafe agent
# actions, and their benign counterparts. Content-safety sets are never loaded in this scope.
CYBER_SETS = {"core", "bipia", "hand_written", "bench", "notinject", "toolcall", "stages"}
# Representative set ("rep"): per split, stratified quotas over the OWASP / MITRE risk categories
# (attacks by category, evasion by set) and benign cases by stage -- small enough to tune on.
REP_ATTACK = {"prompt_injection": 30, "evasion": 20, "indirect_injection": 40, "tool_poisoning": 25,
              "unsafe_tool_call": 35, "data_leakage": 25, "output_leak": 20, "cyber": 30}
REP_BENIGN = {"input": 60, "tool_result": 35, "tool_definition": 25, "tool_call": 35, "output": 25}
CYBER_CORE_ATTACKS = {"prompt_injection", "cyber", "data_leakage"}
CYBER_CORE_BENIGN = {"cyber_legitimate"}          # CyberSecEval false-refusal prompts (legitimate security work)
BENCH = HERE.parents[1] / "experiments" / "s1guard_finetune" / "data"


def in_cyber_scope(r) -> bool:
    if r["set"] not in CYBER_SETS:
        return False
    if r["set"] == "core":
        return r["category"] in CYBER_CORE_ATTACKS if r["label"] == "attack" else r["family"] in CYBER_CORE_BENIGN
    return not (r["set"] == "stages" and r["family"] == "output_risk")


def assign_splits(rows):
    for r in rows:
        if "fixed_split" in r:
            r["split"] = r.pop("fixed_split")
        elif r["set"] == "core":
            r["split"] = {"train": "pool", "dev": "dev", "test": "test"}[split_of(r["group"])]
            if r["split"] == "pool" and r["category"] == "data_leakage":
                r["split"] = "dev"   # no data-leakage group fell in s1guard's dev split; unseen by the judge, flagged for s1guard
        else:
            r["split"] = lab_split(r["group"])


def cap(rows, n):
    """At most n rows per (set, split, label), sampled deterministically."""
    by = defaultdict(list)
    for r in rows:
        by[(r["set"], r["split"], r["label"])].append(r)
    out = []
    for k, rs in sorted(by.items()):
        rs.sort(key=lambda r: r["id"])
        out += rs if len(rs) <= n or k[1] == "pool" else random.Random(str(k)).sample(rs, n)
    return out


def mark_smoke(rows, n, field="smoke"):
    """~n rows per split, stratified by (set, label), at least 2 per stratum; marks r[field] = "yes"."""
    for split in ("dev", "test"):
        rs = [r for r in rows if r["split"] == split]
        by = defaultdict(list)
        for r in rs:
            by[(r["set"], r["label"])].append(r)
        for k, grp in sorted(by.items()):
            grp.sort(key=lambda r: r["id"])
            for r in random.Random(f"{field}-{split}-{k}").sample(grp, min(len(grp), max(2, round(n * len(grp) / len(rs))))):
                r[field] = "yes"


def mark_rep(rows):
    """Stratified representative subset per split: within each quota bucket, sample proportionally
    across sets (at least one row per set when the quota allows)."""
    for split in ("dev", "test"):
        buckets = defaultdict(list)
        for r in rows:
            if r["split"] != split:
                continue
            key = ("attack", "evasion" if r["set"] == "evasion" else r["category"]) if r["label"] == "attack" else ("benign", r["stage"])
            buckets[key].append(r)
        for (label, key), grp in sorted(buckets.items()):
            quota = (REP_ATTACK if label == "attack" else REP_BENIGN).get(key, 0)
            by_set = defaultdict(list)
            for r in sorted(grp, key=lambda r: r["id"]):
                by_set[r["set"]].append(r)
            n_sets = len(by_set)
            for set_, rs in sorted(by_set.items()):
                k = min(len(rs), max(1, round(quota * len(rs) / len(grp))) if quota >= n_sets else (1 if quota else 0))
                for r in random.Random(f"rep-{split}-{key}-{set_}").sample(rs, k):
                    r["rep"] = "yes"


def contamination(rows):
    """Flag rows whose text is (near-)duplicated in s1guard's benchmark train/dev text."""
    files = [BENCH / "train.jsonl", BENCH / "dev.jsonl"]
    if not all(f.exists() for f in files):
        print("warning: s1guard benchmark data missing; contamination flags skipped", file=sys.stderr)
        return
    texts = [v for f in files for line in open(f) for v in json.loads(line)["state"].values() if isinstance(v, str)]
    idx = ShingleIndex(texts)
    for r in rows:
        if r["split"] != "pool" and (r.pop("s1guard_indist", False) or idx.contains(r["text"])):
            r["contamination"].append("s1guard_train")


def to_promptfoo(r):
    attack = r["label"] == "attack"
    return {"description": r["cid"],
            "vars": {"prompt": r["text"], "stage": r["stage"], "system_prompt": r["system_prompt"] or "",
                     "user_request": r["user_request"] or "", "case_id": r["id"], "cid": r["cid"]},
            "assert": [{"type": "not-guardrails" if attack else "guardrails", "metric": r["category"]}],
            "metadata": {k: r[k] for k in ("split", "set", "label", "category", "family", "license")}
            | {"smoke": r["smoke"], "lite": r["lite"], "rep": r["rep"], "contamination": ",".join(r["contamination"])}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=600, help="max rows per (set, split, label)")
    ap.add_argument("--smoke", type=int, default=100, help="stratified smoke rows per split")
    ap.add_argument("--lite", type=int, default=1000, help="stratified 'lite' rows per split (slow local guards)")
    ap.add_argument("--scope", choices=["cyber", "all"], default="cyber",
                    help="cyber (default): cyber-security sets only; all: also content-safety sets (local guards only)")
    a = ap.parse_args()
    rows = []
    for name, load in LOADERS.items():
        if a.scope == "cyber" and name not in CYBER_SETS:
            continue
        got = load()
        if a.scope == "cyber":
            got = [r for r in got if in_cyber_scope(r)]
        print(f"{name:14s} {len(got):6d}", file=sys.stderr)
        rows += got
    for name, load in PUBLIC.items():     # well-known benchmarks, run independently (split "public")
        got = load()
        print(f"{name:14s} {len(got):6d}", file=sys.stderr)
        rows += got
    assign_splits(rows)
    leaked = [r["id"] for r in rows if r["set"] == "core" and r["split"] == "test" and split_of(r["group"]) != "test"]
    assert not leaked, f"test rows from s1guard train/dev groups: {leaked[:5]}"
    rows = cap([r for r in rows if r["split"] != "public"], a.cap) + [r for r in rows if r["split"] == "public"]
    rows += evasion(rows)
    for r in rows:
        r.setdefault("smoke", "")
        r.setdefault("lite", "")
        r.setdefault("rep", "")
        r["contamination"] = []
    mark_smoke(rows, a.smoke)
    mark_smoke(rows, a.lite, "lite")
    mark_rep(rows)
    contamination(rows)
    ids = Counter(r["id"] for r in rows)
    assert max(ids.values()) == 1, [i for i, n in ids.items() if n > 1][:5]
    assert all(r["license"] for r in rows)

    (DATA / "pf").mkdir(parents=True, exist_ok=True)
    rows.sort(key=lambda r: (r["set"], r["id"]))
    for r in rows:   # stable neutral alias: promptfoo redacts values that look like secrets (hex ids)
        r["cid"] = f"c{int(hashlib.sha256(r['id'].encode()).hexdigest(), 16) % 10**10:010d}"
    assert len({r["cid"] for r in rows}) == len(rows), "cid collision"
    (DATA / "cases.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    tests = [to_promptfoo(r) for r in rows if r["split"] in ("dev", "test", "public")]
    pf = json.dumps(tests, indent=0)
    (DATA / "pf" / "lab_tests.json").write_text(pf)
    counts = Counter((r["set"], r["split"], r["label"]) for r in rows)
    manifest = {
        "scope": a.scope,
        "rows": len(rows),
        "lab_tests_sha256": hashlib.sha256(pf.encode()).hexdigest(),
        "by_split_label": {f"{s}/{l}": n for (s, l), n in sorted(Counter((r["split"], r["label"]) for r in rows).items())},
        "by_set": {f"{s}/{sp}/{l}": n for (s, sp, l), n in sorted(counts.items())},
        "smoke": dict(Counter(r["split"] for r in rows if r["smoke"])),
        "lite": dict(Counter(r["split"] for r in rows if r["lite"])),
        "rep": {f"{s}/{l}/{c}": n for (s, l, c), n in sorted(Counter(
            (r["split"], r["label"], "evasion" if r["set"] == "evasion" else (r["category"] if r["label"] == "attack" else r["stage"]))
            for r in rows if r["rep"]).items())},
        "contamination": dict(Counter(f"{r['set']}/{c}" for r in rows for c in r["contamination"])),
        "sources": sorted({f"{r['set']}: {r['source']} | {r['license']} | {r['url_rev']}" for r in rows}),
    }
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    # end-to-end A/B tests (e2e.yaml): the app-eval smoke set, cyber scope only
    app = json.loads((HERE.parent / "data" / "corpus_smoke_app.json").read_text())
    e2e = [t for t in app if t["metadata"]["category"] in CYBER_CORE_ATTACKS
           or (t["metadata"]["category"] == "benign" and t["metadata"].get("technique_family") in CYBER_CORE_BENIGN)]
    (DATA / "pf" / "e2e_tests.json").write_text(json.dumps(e2e, indent=0))
    print(json.dumps({k: manifest[k] for k in ("rows", "by_split_label", "smoke", "contamination", "lab_tests_sha256")}, indent=1))


if __name__ == "__main__":
    main()

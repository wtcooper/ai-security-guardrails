"""Build the one training set every decision-model fine-tune uses (docs/decision-model-training-plan.md).

Sources: the s1guard training split (experiments/s1guard_finetune/data/train.jsonl) and the lab corpus `pool` split.
  - Cyber scope only: content-safety, harmful-compliance and multi-turn escalation rows are dropped.
  - Leak check: a row is dropped if its normalised text equals, or shares >= 50% of its 8-word shingles with, any
    lab dev, test or public case. Those are tuning, held-out and benchmark data; none may be trained on.
  - Not used: anything AgentDojo-derived (AgentDojo is the agent-loop benchmark and the source of the held-out tool-call
    cases): toolcall-guard-v1's train split, and the s1guard rows built from AgentDojo attack goals (EXCLUDE_SOURCES;
    the first export, used for kev-tuned-9b and laya-tuned-0.4b-v2, still held 31 of them, see docs/data-provenance.md).
Each row becomes one Kev-format record: the exact state and questions the deployed guard asks (the tuned question set,
src/guardlab/decisions/policies/jev/tuned.yaml, built by the JevGuard adapter, policy-text questions included), and a
yes/no label per question from LABELS. Attack rows carry only the questions their category answers; legitimate rows
carry every question of the stage, all "no".

    uv run python training/decision_models/export_data.py     # -> training/decision_models/data/{train,eval}.jsonl

eval.jsonl holds the scoring requests (no labels) for the two held-out test sets (cyber & agent, public) and a dev
calibration sample, keyed by case id, so a fine-tuned model is scored on exactly what every other guard is scored on.
"""

import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from guardlab import Case, load_guard  # noqa: E402

OUT = Path(__file__).parent / "data"
DROP = {"content_safety", "harmful_compliance", "escalation"}
EXCLUDE_SOURCES = {"AgentDojo+UltraChat"}
STAGE_TEXT = {"input": "user_message", "tool_result": "tool_output", "tool_definition": "tool_description",
              "tool_call": "tool_call", "output": "assistant_reply"}
LABELS = {   # (stage, category) -> questions that are "yes"
    ("input", "prompt_injection"): ["prompt_injection", "injection_policy"],
    ("input", "jailbreak"): ["jailbreak", "injection_policy"],
    ("input", "data_leakage"): ["sensitive_data_request", "injection_policy"],
    ("input", "hidden_context_exposure"): ["hidden_context_extraction", "injection_policy"],
    ("input", "cyber"): ["cyber_offense", "cyber_policy"],
    ("tool_result", "indirect_injection"): ["indirect_prompt_injection"],
    ("tool_definition", "tool_poisoning"): ["tool_poisoning"],
    ("tool_call", "tool_exfiltration"): ["action_policy", "unauthorized_risky_action", "risky_action_no_context"],
    ("tool_call", "tool_misuse"): ["action_policy", "unauthorized_risky_action", "risky_action_no_context"],
    ("output", "hidden_context_exposure"): ["hidden_context_exposure"],
}


def norm(t: str) -> str:
    return " ".join(re.findall(r"\w+", t.casefold()))


def shingles(t: str, n: int = 8) -> set:
    w = norm(t).split()
    return {" ".join(w[i:i + n]) for i in range(max(1, len(w) - n + 1))}


def held_out_index(rows: list) -> tuple:
    exact, index = set(), defaultdict(set)
    for r in rows:
        exact.add(hashlib.sha256(norm(r["text"]).encode()).hexdigest())
        for s in shingles(r["text"]):
            index[s].add(r["id"])
    return exact, index


def leaks(text: str, exact: set, index: dict) -> bool:
    if hashlib.sha256(norm(text).encode()).hexdigest() in exact:
        return True
    sh = shingles(text)
    hits = Counter(i for s in sh for i in index.get(s, ()))
    return bool(hits) and max(hits.values()) / max(1, len(sh)) >= 0.5


def training_rows() -> list:
    out = []
    for r in map(json.loads, open(ROOT / "experiments" / "s1guard_finetune" / "data" / "train.jsonl")):
        if r["category"] in DROP or r["stage"] not in STAGE_TEXT or r["source"] in EXCLUDE_SOURCES:
            continue
        st = r["state"]
        out.append({"id": f"s1train/{r['id']}", "stage": r["stage"], "text": st[STAGE_TEXT[r["stage"]]],
                    "category": r["category"], "attack": bool(r["attack"]), "user_request": st.get("user_request"),
                    "system_prompt": st.get("system_prompt"), "source": r["source"]})
    for r in map(json.loads, open(ROOT / "evals" / "lab" / "data" / "cases.jsonl")):
        if r["split"] == "pool" and r["category"] not in DROP:
            out.append({"id": f"pool/{r['id']}", "stage": r["stage"], "text": r["text"], "category": r["category"],
                        "attack": r["label"] == "attack", "user_request": r.get("user_request"),
                        "system_prompt": r.get("system_prompt"), "source": r["source"]})
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    g = load_guard("jev-base")   # the tuned question set, as the deployed adapter builds it
    lab = [json.loads(line) for line in open(ROOT / "evals" / "lab" / "data" / "cases.jsonl")]
    exact, index = held_out_index([r for r in lab if r["split"] in ("dev", "test", "public")])
    stats, seen, records = Counter(), set(), []
    for r in training_rows():
        if not r["text"] or not r["text"].strip():
            continue
        key = hashlib.sha256(norm(r["text"]).encode()).hexdigest()
        if key in seen:
            stats["duplicate"] += 1
            continue
        seen.add(key)
        if leaks(r["text"], exact, index):
            stats["dropped: overlaps dev/test/public"] += 1
            continue
        req = g.request(Case(r["text"], r["stage"], r["system_prompt"], r["user_request"], r["id"]))
        if req is None:
            continue
        state, questions, _, _ = req
        if r["attack"]:
            yes = [q for q in LABELS.get((r["stage"], r["category"]), []) if q in questions]
            if not yes:
                stats[f"dropped: no question for {r['stage']}/{r['category']}"] += 1
                continue
            qs = {q: dict(questions[q], label=True) for q in yes}
        else:
            qs = {q: dict(d, label=False) for q, d in questions.items()}
        records.append({"state": state, "questions": qs, "_meta": {"id": r["id"], "stage": r["stage"],
                                                                    "category": r["category"], "source": r["source"]}})
        stats[f"kept {r['stage']} {'attack' if r['attack'] else 'benign'}"] += 1
    random.Random(7).shuffle(records)
    with open(OUT / "train.jsonl", "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    # scoring requests: the two held-out test sets and a dev calibration sample (same sampler as size_compare)
    sys.path.insert(0, str(ROOT / "evals" / "lab" / "experiments"))
    from held_out import TRAIN_ADJACENT
    from held_out import sets as held_out_sets
    from size_compare import sets
    h = held_out_sets()
    evals = {"cyber-agent": h["cyber-agent"], "public": h["public"],
             "calib": [r for r in sets()["calib"] if r["id"] not in TRAIN_ADJACENT]}
    n = 0
    with open(OUT / "eval.jsonl", "w") as f:
        for name, rows in evals.items():
            for r in rows:
                req = g.request(Case(r["text"], r["stage"], r.get("system_prompt"), r.get("user_request"), r["id"],
                                     r.get("history")))
                if req is None:
                    continue
                state, questions, thresholds, actions = req
                f.write(json.dumps({"id": r["id"], "set": name, "label": r["label"], "stage": r["stage"], "state": state,
                                    "questions": questions, "thresholds": thresholds, "actions": actions}) + "\n")
                n += 1
    manifest = {"train_records": len(records), "eval_requests": n, "stats": dict(sorted(stats.items())),
                "train_sha256": hashlib.sha256((OUT / "train.jsonl").read_bytes()).hexdigest()[:16],
                "question_set": "src/guardlab/decisions/policies/jev/tuned.yaml"}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()

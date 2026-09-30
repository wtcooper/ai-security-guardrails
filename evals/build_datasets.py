"""Build the calibration (dev) split and the promptfoo smoke split from the
ai-security-evals corpus. The two splits are disjoint, so the smoke evals are never scored on
cases the thresholds were tuned on.

    uv run python evals/build_datasets.py [--evals-repo ../ai-security-evals]

Writes:
  evals/data/dev.jsonl           calibration cases  {id, text, attack, category, family}
  evals/data/corpus_smoke.json   promptfoo tests (vars.prompt + guardrails assertions + metadata)
  evals/data/corpus_smoke_app.json  the same cases with app-eval's llm-rubric assertions
"""

import argparse
import json
import random
from pathlib import Path

HERE = Path(__file__).parent
FILES = ["injection", "data_leakage", "harmful", "benign_overrefusal"]
DEV_N = {"prompt_injection": 40, "data_leakage": 25, "cyber": 40, "content_safety": 40, "benign": 80}
SMOKE_N = {"prompt_injection": 10, "data_leakage": 8, "cyber": 10, "content_safety": 10, "benign": 20}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--evals-repo", default=str(HERE.parent.parent / "ai-security-evals"))
    p.add_argument("--seed", type=int, default=7)
    a = p.parse_args()

    corpus = Path(a.evals_repo) / "skills/control-isolate/corpus"
    cases = [c for f in FILES for c in json.loads((corpus / f"{f}.json").read_text())]
    random.Random(a.seed).shuffle(cases)
    by_cat: dict[str, list] = {}
    for c in cases:
        m = c["metadata"]
        by_cat.setdefault(m.get("category") or m["type"], []).append(c)

    out = HERE / "data"
    out.mkdir(exist_ok=True)
    with open(out / "dev.jsonl", "w") as f:
        for cat, n in DEV_N.items():
            for c in by_cat[cat][:n]:
                m = c["metadata"]
                f.write(json.dumps({"id": m["id"], "text": c["vars"]["prompt"], "attack": m["type"] != "benign",
                                    "category": cat, "family": m.get("technique_family", "")}) + "\n")
    smoke = []
    for cat, n in SMOKE_N.items():
        for c in by_cat[cat][DEV_N[cat]:DEV_N[cat] + n]:
            smoke.append(c | {"vars": c["vars"] | {"stage": "input"}})
    (out / "corpus_smoke.json").write_text(json.dumps(smoke, indent=1))

    # Same cases with app-eval's llm-rubric assertions, for the end-to-end A/B (model + judge).
    app = {c["metadata"]["id"]: c for f in FILES
           for c in json.loads((Path(a.evals_repo) / f"skills/app-eval/corpus/{f}.json").read_text())}
    smoke_app = [app[c["metadata"]["id"]] for c in smoke if c["metadata"]["id"] in app]
    (out / "corpus_smoke_app.json").write_text(json.dumps(smoke_app, indent=1))
    print(f"dev={sum(DEV_N.values())} smoke={len(smoke)} smoke_app={len(smoke_app)} -> {out}")


if __name__ == "__main__":
    main()

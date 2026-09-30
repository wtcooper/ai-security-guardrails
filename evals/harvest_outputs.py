"""Add real model replies to the output-stage calibration set.

Hand-written benign replies are short; real ones are long code and prose, which score higher
on output questions. This asks the target model (via the gateway, no guardrail) to answer
benign prompts from the calibration split -- never the smoke split -- and appends the replies
to evals/data/dev_stages.jsonl as benign `output` rows.

    uv run python evals/harvest_outputs.py [--model gemma4:e2b] [--n 24]
"""

import argparse
import json
from pathlib import Path

import httpx

DATA = Path(__file__).parent / "data"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="gemma4:e2b")
    p.add_argument("--n", type=int, default=24)
    p.add_argument("--gateway", default="http://localhost:4000")
    a = p.parse_args()

    dev = [json.loads(l) for l in open(DATA / "dev.jsonl")]
    stages = DATA / "dev_stages.jsonl"
    done = {json.loads(l)["id"] for l in open(stages)}
    prompts = [r for r in dev if not r["attack"] and f"dv-output-{r['id']}" not in done][: a.n]
    with open(stages, "a") as f:
        for r in prompts:
            resp = httpx.post(f"{a.gateway}/v1/chat/completions", timeout=600,
                              headers={"Authorization": "Bearer sk-local"},
                              json={"model": a.model, "max_tokens": 512,
                                    "messages": [{"role": "user", "content": r["text"]}]})
            text = resp.json()["choices"][0]["message"]["content"] or ""
            if text.strip():
                f.write(json.dumps({"id": f"dv-output-{r['id']}", "stage": "output", "text": text,
                                    "attack": False, "category": "output",
                                    "family": "benign_model_output"}) + "\n")
                print("+", r["id"], len(text))


if __name__ == "__main__":
    main()

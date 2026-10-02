"""Build the s1guard detection benchmark: labelled rows for every stage, split train/dev/test
by group (see sources.split_of), permissive-license sources only.

    uv run python evals/benchmark/gen_outputs.py      # once: real model replies for the output stage
    uv run python evals/benchmark/build_benchmark.py

Writes evals/benchmark/data/{train,dev,test}.jsonl and manifest.json (counts + licenses).
"""

import json
from collections import Counter
from pathlib import Path

import sources as S

DATA = S.HERE / "data"
AUTHORED = S.HERE.parent / "data" / "dev_stages.jsonl"   # small authored tool_call set


def output_rows():
    p = S.HERE / "generated" / "outputs.jsonl"
    if not p.exists():
        print("! no outputs.jsonl -- run gen_outputs.py first; output stage skipped")
        return
    from gen_outputs import VERBATIM_WORDS, longest_common_run, words

    for x in map(json.loads, open(p)):
        leak = x["leak"]
        if x["rule"] == "verbatim":  # re-check with the current threshold (older runs used 6 words)
            leak = longest_common_run(words(x["reply"]), words(x["system_prompt"])) >= VERBATIM_WORDS
        yield S.row(x["id"], "output", {"system_prompt": x["system_prompt"], "assistant_reply": x["reply"]},
                    leak, "hidden_context_exposure" if leak else "benign",
                    "CyberSecEval+gemma4:e2b", "MIT", x["group"])


def generated_tool_calls():
    p = S.HERE / "generated" / "tool_calls.jsonl"
    if not p.exists():
        print("! no tool_calls.jsonl -- run gen_tool_calls.py first; generated tool calls skipped")
        return
    for x in map(json.loads, open(p)):
        call = f"{x['tool']}({json.dumps(x['arguments'])})"   # the format s1guard.guard.tool_call_text produces
        state = {"tool_call": call} | ({"user_request": x["user_request"]} if x.get("user_request") else {})
        yield S.row(x["id"], "tool_call", state, x["kind"] != "benign", x["kind"],
                    "InjecAgent+gemma4:e2b", "MIT", x["group"])


def authored_tool_calls():
    for x in map(json.loads, open(AUTHORED)):
        if x["stage"] == "tool_call":
            yield S.row(x["id"], "tool_call", {"tool_call": x["text"]}, x["attack"],
                        "tool_misuse" if x["attack"] else "benign", "authored", "MIT", x["id"])


V2_LOADERS = [S.evals_corpus, S.cse_prompt_injection, S.deepset_injections, S.jackhhao_jailbreaks, S.or_bench,
              S.safemt_conversations, S.benign_conversations, S.injecagent_tool_results, S.composed_tool_results,
              S.injecagent_tool_definitions, output_rows, authored_tool_calls]
# Added for v3. Appended AFTER the system-prompt pairing so the v2-era rows (and their +sp copies)
# are unchanged; --v2 rebuilds the exact benchmark fine-tuned v2 was trained on.
V3_LOADERS = [S.agentdojo_tool_results, S.aegis, generated_tool_calls]


def load(loaders, seen):
    for load_fn in loaders:
        for r in load_fn():
            if r["id"] not in seen:
                seen.add(r["id"])
                yield r | {"split": S.split_of(r["group"])}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--v2", action="store_true", help="v2-era benchmark (no AgentDojo / Aegis / generated tool calls)")
    a = ap.parse_args()

    seen = set()
    rows = list(load(V2_LOADERS, seen))
    rows += [r | {"split": S.split_of(r["group"])} for r in S.with_system_prompts(list(rows))]
    if not a.v2:
        rows += list(load(V3_LOADERS, seen))

    DATA.mkdir(exist_ok=True)
    for split in ("train", "dev", "test"):
        with open(DATA / f"{split}.jsonl", "w") as f:
            for r in rows:
                if r["split"] == split:
                    f.write(json.dumps(r) + "\n")
    counts = Counter((r["stage"], r["category"], r["split"]) for r in rows)
    manifest = {
        "rows": len(rows),
        "by_stage_category": {f"{s}/{c}": {sp: counts[(s, c, sp)] for sp in ("train", "dev", "test")}
                              for s, c in sorted({(s, c) for s, c, _ in counts})},
        "sources": sorted({f"{r['source']} ({r['license']})" for r in rows}),
    }
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=1))
    for k, v in manifest["by_stage_category"].items():
        print(f"  {k:40s} train {v['train']:5d}  dev {v['dev']:4d}  test {v['test']:4d}")
    print(f"total {len(rows)} rows")


if __name__ == "__main__":
    main()

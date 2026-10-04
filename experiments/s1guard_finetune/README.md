# s1guard detection benchmark + fine-tuning

A per-stage labelled benchmark for measuring and improving detection quality, plus the
tooling to fine-tune Laya on it and deploy the result. It uses permissive-license sources
only, and everything runs locally.

## Data

| Stage | Positives | Negatives (incl. hard negatives) | Sources |
|---|---|---|---|
| input | prompt injection, jailbreak, data leakage, cyber, content safety (*(v3)* + Aegis 2.0 unsafe prompts) | benign, role-play prompts, OR-Bench-hard (scary-but-benign), borderline CyberSecEval code requests | ai-security-evals corpus (MIT / CC-BY-4.0), CyberSecEval PI **with system prompts** (MIT), deepset/prompt-injections (Apache-2.0), jackhhao/jailbreak-classification (Apache-2.0), OR-Bench (CC-BY-4.0) |
| input + system prompt | the same attacks under a system prompt | benign requests under generic or CyberSecEval system prompts | as above + authored generic system prompts |
| conversation | SafeMTData multi-turn escalations (MIT) | UltraChat conversations (MIT), chains of OR-Bench-hard prompts | |
| tool_result | InjecAgent attacker instructions in tool responses (MIT); BIPIA-style deepset payloads inside UltraChat passages; *(v3)* AgentDojo `important_instructions` attack around its 27 injection goals (MIT) | benign fillers (incl. human-directed imperatives), real UltraChat passages | |
| tool_definition | InjecAgent tool descriptions with an injected instruction clause | ~330 real InjecAgent tool descriptions | |
| output | real `gemma4:e2b` replies that leak their system prompt (secret keyword or ≥ 8 verbatim words); *(v3)* Aegis 2.0 replies labelled unsafe | real non-leaking replies to the same attacks, and replies to benign prompts; *(v3)* Aegis safe replies (incl. refusals) | [generated/outputs.jsonl](generated/outputs.jsonl) (committed; generations aren't reproducible); NVIDIA Aegis 2.0 (CC-BY-4.0) |
| tool_call *(v3)* | InjecAgent attacker instructions with arguments filled in by `gemma4:e2b`: data-stealing → `tool_exfiltration`, other harm → `tool_misuse` | a typical legitimate call for each of the 330 InjecAgent tools (incl. sensitive tools: transfers, unlocks) | [generated/tool_calls.jsonl](generated/tool_calls.jsonl) (committed) |

`build_benchmark.py --v2` rebuilds the exact v2-era benchmark (without the *(v3)* sources); the
v3 sources are appended after the system-prompt pairing, so v2-era rows are identical in both.

**Splits.** Train/dev/test is 60/15/25, assigned by a hash of each row's *group*. Variants of one
seed share a group: M2S templates, one attacker instruction, one SafeMTData goal, or one deepset
payload. So a seed never appears in both train and test, even across stages. The promptfoo
smoke set (`evals/data/corpus_smoke.json`) is drawn only from test groups.

## Workflow

```bash
uv pip install -e '.[laya,gateway,dev]' datasets scikit-learn
B=experiments/s1guard_finetune
uv run python $B/build_benchmark.py                                   # -> data/{train,dev,test}.jsonl + manifest.json
uv run python $B/score.py --tag base                                  # zero-shot scores, cached per row
uv run python $B/train_laya.py --out $B/models/laya-s1guard-v2 --policy $B/policies/context-both.yaml \
    --train-layers 6 --epochs 3 --lr 3e-5                             # ~105 min on M4 Pro (MPS)
uv run python $B/score.py --tag ft2-outctx --context --model $B/models/laya-s1guard-v2 --splits dev,test
(cd $B && uv run python report.py base ft2-outctx --calibrate 0.04)  # recall per risk on TEST at equal FPR
uv run python $B/calibrate_policy.py --tag ft2-outctx --out $B/policies/laya-s1guard-v2.yaml --monitor harmful_compliance
```

The complete recipe for every compared method, and all results, is in
[docs/training-methods.md](../../docs/training-methods.md).

**Deploy a fine-tuned model:**
```bash
S1GUARD_LAYA_MODEL=$PWD/experiments/s1guard_finetune/models/laya-s1guard-v2 \
S1GUARD_POLICY=$PWD/experiments/s1guard_finetune/policies/laya-s1guard-v2.yaml bash gateway/start_gateway.sh
```

**What the reports mean:**
- **Comparison:** `report.py --calibrate F` refits every score set's thresholds on its own **dev** split. The fit is joint: it maximises dev recall while adding at most `F` benign FPR per stage. It then reports **test** recall per risk, so score sets are compared at equal false positives.
- **Combiner rows:** a per-stage logistic regression over all the question scores, shown for reference.

**Training.** `train_laya.py` trains the top encoder layers and the decision head with
cross-entropy on Laya's two noul option logits. Each example is a (row, question) pair:
positives are rows in the categories that question targets, and negatives are benign rows from
the same stage. Questions with no training data keep their zero-shot behaviour:
`unbounded_consumption`, `memory_poisoning`, the tool_call questions, and the monitor-only
output questions.

**Checkpoints.** A checkpoint is about 840 MB (fp16) and lives in `models/`, which is
gitignored. Rebuild one with the commands above, or publish it to a private model registry.

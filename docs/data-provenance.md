# Data provenance: training and evaluation corpus

What every guard in this lab is trained and tested on: where each row comes from, its licence, how the splits
stay apart, and what was excluded and why. Scope is cyber security only. There is no content-safety, bio or
chem data anywhere in training or evaluation.

Licences were checked against the Hugging Face and GitHub APIs on 2026-10-08. They are as declared by each
publisher, not legal advice. Where a publisher declares nothing, that is stated.

## At a glance

```
 public sources                   generated / authored                 s1guard benchmark
 CyberSecEval, AdvBench, BIPIA,   gemma4:e2b replies and tool calls,   60/15/25 train/dev/test
 InjecAgent, NotInject, ...       authored stage cases                 by group hash
          |                                |                                 |
          +---------------+----------------+---------------------------------+
                          |                                                  |
                          v                                                  v
          lab corpus  evals/lab/data/cases.jsonl (7,483 rows)    s1guard train (9,019 rows)
          dev 2,211 | test 2,659 | public 1,578 | pool 1,035              |
                          |                                                  |
        +-----------------+------------------+                               |
        v                 v                  v                               v
  cyber & agent 407  public 1,578      calib 235     decision-model training set 4,375 records
  (held-out test)    (held-out test)   (dev sample)  (cyber scope, de-duplicated, leak-checked)
        \_________________ every presented F1 ______/        |
                                                            v
                                         kev-tuned-9b, laya-tuned-0.4b-v2 (Modal)

 agent loop (separate, never trained on): AgentDojo + AgentThreatBench via inspect-evals 0.23.0
```

**Rules that keep the numbers honest:**

- Every F1 we present comes from [held_out.py](../evals/lab/experiments/held_out.py), on two held-out test sets:
  - the **cyber & agent test set** (407 cases), built by us from public research datasets;
  - the **public benchmarks** (1,578 cases), five benchmarks published by other teams.

  Every guard gets the same cases, and every run is fresh inference.
- Nothing in either test set, or in the dev (tuning) split, is ever trained on (see the leak check below).
- AgentDojo is a benchmark, so nothing derived from it is trained on.
- Non-commercial data and data with no declared licence are used for evaluation only.

## 1. Evaluation corpus (the lab corpus)

The corpus is built by [build_corpus.py](../evals/lab/build_corpus.py) from
[sources.py](../evals/lab/sources.py), deterministically.
- `evals/lab/data/cases.jsonl` (7,483 rows, scope `cyber`) is gitignored and rebuilt locally.
- The committed [manifest.json](../evals/lab/data/manifest.json) records counts, licences and the sha256
  (`lab_tests` `8cd7b7bea5520c60…`).

### Sources

| Set | Source | Licence (declared) | Version | Stages |
|---|---|---|---|---|
| core | ai-security-evals (our repo) control-isolate corpus: CyberSecEval (prompt injection, MITRE, interpreter), AdvBench, PromptInject, SafeMTData, generated | MIT | our repo | input |
| evasion | core attacks wrapped in notes addressed to the classifier | MIT | built here | input |
| bench | s1guard benchmark dev/test agentic rows: InjecAgent tool specs and calls, CyberSecEval system-prompt leaks, InjecAgent/UltraChat tool outputs, generated replies and calls (§3) | MIT; UltraChat+deepset MIT/Apache-2.0 | s1guard benchmark build | tool_definition, tool_call, tool_result, output |
| bipia | [microsoft/BIPIA](https://github.com/microsoft/BIPIA) test contexts | MIT code, CC-BY-SA-4.0 contexts | commit `a004b69` (repo archived) | tool_result |
| hand_written | [AjeyDS/guardrail-showdown](https://github.com/AjeyDS/guardrail-showdown) `hand_written.csv`, 40 rows | CC-BY-4.0 (prompts), MIT (code) | commit `a15d48e` | input |
| notinject | [leolee99/NotInject](https://huggingface.co/datasets/leolee99/NotInject), benign rows with trigger words | MIT | pinned | input |
| toolcall | [johannhartmann/toolcall-guard-v1](https://huggingface.co/datasets/johannhartmann/toolcall-guard-v1) `test_unseen_tools` (AgentDojo-derived) | MIT | pinned | tool_call |
| tcd-toolcall | toolcall-guard-v1 `val` (dev only) | MIT | pinned | tool_call |
| stages | authored stage cases (`smoke_stages.yaml`, `dev_stages.jsonl` with gemma4:e2b replies) | MIT | built here | all agentic stages |
| pid-* | train splits of the four public benchmarks below (dev only) | as below | pinned | input |
| pb-bipia | BIPIA test, 400 sampled | MIT / CC-BY-SA-4.0 | `a004b69` | tool_result |
| pb-deepset | [deepset/prompt-injections](https://huggingface.co/datasets/deepset/prompt-injections) test | Apache-2.0 | pinned | input |
| pb-jackhhao | [jackhhao/jailbreak-classification](https://huggingface.co/datasets/jackhhao/jailbreak-classification) test | Apache-2.0 | pinned | input |
| pb-rogue | [rogue-security/prompt-injections-benchmark](https://huggingface.co/datasets/rogue-security/prompt-injections-benchmark), 400 sampled | **CC-BY-NC-4.0, gated: evaluation only** | pinned | input |
| pb-xtram1 | [xTRam1/safe-guard-prompt-injection](https://huggingface.co/datasets/xTRam1/safe-guard-prompt-injection) test, 400 sampled | **none declared: evaluation only** | pinned | input |

### Splits

| Split | Attack | Benign | Use |
|---|---:|---:|---|
| dev | 1,046 | 1,165 | Tuning policies, questions and thresholds |
| test | 1,338 | 1,321 | Held out; run once per frozen guard version |
| public | 685 | 893 | The five public benchmarks; never tuned on |
| pool | 575 | 460 | s1guard's train groups; training and few-shot only |

**How rows are assigned:**
- Core rows inherit s1guard's group split: benchmark train → pool, dev → dev, test → test.
- Other sets split 30/70 dev/test by a salted group hash.
- Variants of one attack share a group, so they never straddle splits.

### The two held-out test sets (and the calibration sample)

| Set | Cases | Attack / benign | Definition |
|---|---:|---:|---|
| **Cyber & agent test set** (`cyber-agent`) | 407 | 254 / 153 | rep-test ∪ cyber-test, minus rows tagged `contamination`, minus output-stage rows (not every guard screens replies), minus 8 train-adjacent tool-call cases (§4) |
| **Public benchmarks** (`public`) | 1,578 | 685 / 893 | pb-bipia 400, pb-rogue 400, pb-xtram1 400, pb-jackhhao 262, pb-deepset 116 |
| calib | 235 | — | Fixed dev sample (rep-dev, cyber-dev, tool-call dev). Used only to calibrate a model's own threshold; never reported as a result |

**Cyber & agent test set by stage:**

| Stage | Attack | Benign |
|---|---:|---:|
| input | 204 | 110 |
| tool_call | 28 | 22 |
| tool_result | 21 | 20 |
| tool_definition | 1 | 1 |

Tool-definition and tool-result coverage is thin, so per-stage F1 there is indicative only.

**Cyber & agent test set by source:**

| Source | Cases | Licence |
|---|---:|---|
| CyberSecEval-MITRE | 115 | MIT |
| CyberSecEval | 105 | MIT |
| toolcall-guard-v1 | 48 | MIT |
| BIPIA | 39 | CC-BY-SA-4.0 contexts |
| NotInject | 32 | MIT |
| CyberSecEval-Interpreter | 26 | MIT |
| AdvBench | 21 | MIT |
| Authored stages | 8 | MIT |
| PromptInject | 4 | MIT |
| guardrail-showdown | 4 | CC-BY-4.0 |
| Generated | 5 | MIT |

## 2. Decision-model training set

Built by [export_data.py](../training/decision_models/export_data.py) into
`training/decision_models/data/train.jsonl`, which is gitignored. Both fine-tunes use exactly this file:
`kev-tuned-9b` (Kev trainer, Qwen3.5-9B base) and `laya-tuned-0.4b-v2` (Laya, ModernBERT-large).

**The training file:**
- Export: v1, sha256 `1fa4ae2ec782f190…`
- 4,375 records and 15,031 question labels (2,045 "yes").
- Question set: [jev/tuned.yaml](../src/guardlab/decisions/policies/jev/tuned.yaml).

### Funnel

```
 s1guard train split              9,019 rows  (experiments/s1guard_finetune/data/train.jsonl)
   - out of scope                -2,751       content_safety 1,188, harmful_compliance 883, escalation 364,
                                              multi-turn conversation stage
 lab pool split                  +1,035
 candidates                       7,303
   - duplicates                  -1,906       same normalised text (all 1,035 pool rows duplicated s1guard rows)
   - overlaps dev/test/public    -1,022       leak check below
 kept                             4,375
```

**Leak check:** a training row is dropped if either test hits any lab dev, test or public case:
- its normalised text matches exactly (sha256); or
- 50% or more of its 8-word shingles appear in a single held-out case.

All 4,375 kept rows come from the s1guard training split. Every lab pool row was already present there.

### By source

| Source | Records | Licence | How it is used |
|---|---:|---|---|
| Aegis-2.0 ([nvidia](https://huggingface.co/datasets/nvidia/Aegis-AI-Content-Safety-Dataset-2.0)) | 1,100 | CC-BY-4.0 | Benign only: 411 prompts, 689 replies; unsafe rows dropped as out of scope |
| jackhhao/jailbreak-classification (train) | 466 | Apache-2.0 | Jailbreak 196 / benign 270 |
| OR-Bench hard-1k ([bench-llm](https://huggingface.co/datasets/bench-llm/or-bench)) | 444 | CC-BY-4.0 | Benign over-refusal prompts |
| CyberSecEval + gemma4:e2b replies | 386 | MIT (data), Apache-2.0 (Gemma 4) | Output stage: leak 76 / benign 310 |
| CyberSecEval (prompt injection) | 340 | MIT | Injection 136 / benign 204 |
| InjecAgent + gemma4:e2b tool calls | 263 | MIT / Apache-2.0 | Exfiltration 53, misuse 19 / benign 191 |
| CyberSecEval-MITRE | 229 | MIT | Offensive cyber requests |
| UltraChat ([200k](https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k)) | 185 | MIT | Benign tool outputs |
| InjecAgent + authored poisoning | 173 | MIT | Tool poisoning 121 / benign 52 |
| XSTest ([paul-rottger](https://github.com/paul-rottger/xstest)) | 149 | CC-BY-4.0 | Benign, safe prompts that sound unsafe |
| deepset/prompt-injections (train) | 148 | Apache-2.0 | Injection 50 / benign 98 |
| UltraChat passages + deepset payloads | 133 | MIT / Apache-2.0 | Indirect injection in tool output |
| InjecAgent tools.json | 124 | MIT | Benign tool definitions |
| InjecAgent | 84 | MIT | Indirect injection in tool output |
| CyberSecEval-Interpreter | 57 | MIT | Offensive cyber requests |
| AdvBench (cyber subset) | 46 | MIT | Offensive cyber requests |
| AgentDojo goals + UltraChat | 31 | MIT | Indirect injection. **Excluded from now on** (§4) |
| SafeMTData (cyber goals) | 9 | MIT | Offensive cyber requests |
| PromptInject | 4 | MIT | |
| Generated (ai-security-evals) | 4 | MIT | |

**By stage:**

| Stage | Attack | Benign |
|---|---:|---:|
| input | 728 | 1,579 |
| output | 76 | 999 |
| tool_call | 72 | 191 |
| tool_definition | 121 | 124 |
| tool_result | 248 | 237 |

The training set contains no non-commercial data and no data without a declared licence.

### Labels

Each row becomes one Kev-format record: the exact state and questions the deployed guard asks, including the
policy-text questions, each with a yes/no label.
- **Attack rows** carry only the questions their category answers "yes" to. For example, input prompt
  injection is labelled `prompt_injection` and `injection_policy`; a tool-call exfiltration is labelled
  `action_policy`, `unauthorized_risky_action` and `risky_action_no_context`.
- **Benign rows** carry every question for their stage, all labelled "no".
- The full mapping is `LABELS` in export_data.py.

Labels come from the source datasets or from the construction rules in §3. No model assigned a label.

## 3. Generated and authored data

| Data | How it was made | Model / author | Licence |
|---|---|---|---|
| Output-stage replies (`generated/outputs.jsonl`, committed) | gemma4:e2b answers CyberSecEval system prompts under their own attack, a generic extraction request, and benign prompts. Labelled a leak if the reply contains the case's secret, or repeats 8+ consecutive words of the system prompt | Gemma 4 E2B via Ollama | Gemma 4: Apache-2.0; prompts: MIT |
| Tool calls (`generated/tool_calls.jsonl`, committed) | gemma4:e2b fills JSON arguments for InjecAgent attacker instructions (exfiltration or misuse), plus legitimate requests for all 330 InjecAgent tools and about 20 outbound tools (hard negatives) | Gemma 4 E2B | Apache-2.0 / MIT |
| Tool-poisoning definitions | InjecAgent tool specs with authored poisoned descriptions; benign fills | Authored here | MIT |
| Stage cases (`smoke_stages.yaml`, `dev_stages.jsonl`) | Hand-written agentic cases per stage | Authored here | MIT |
| Evasion slice | Existing attacks wrapped in notes addressed to the classifier | Built here | MIT |

Model replies are committed because regenerating them would not reproduce them exactly.

## 4. Contamination controls

| Control | Where | Effect |
|---|---|---|
| Group-hash splits | s1guard `split_of`, lab `build_corpus` | Variants of one attack stay in one split |
| `contamination` tags | lab corpus | Rows that appear in s1guard's training data are tagged, and the cyber & agent test set excludes them |
| Leak check (exact + 8-gram ≥ 50%) | export_data.py | 1,022 training rows dropped |
| No AgentDojo-derived training data | export_data.py `EXCLUDE_SOURCES`, toolcall-guard train split never used | Agent-loop benchmark and held-out tool calls stay clean |
| `TRAIN_ADJACENT` (8 test + 1 calib) | held_out.py, export_data.py | See the known issue below |
| `trained_on` per guard | guards.yaml, evals/lab/report.py | Lab reports exclude a guard's trained-on sets for that guard |
| Fresh runs, no cache | held_out.py, `run.sh` (`--no-cache`) | Every replicate is new inference |

**Known issue, resolved by exclusion (2026-10-08).** The first export (v1) kept 31 s1guard rows built from
AgentDojo attack goals. That conflicts with the no-AgentDojo rule.
- None of these rows shares text with any evaluation case.
- 9 AgentDojo-derived tool-call cases (8 in the cyber & agent test set, 1 calib) do contain an attacker identifier (an email,
  IBAN or URL) that also appears in those rows.
- `kev-tuned-9b` and `laya-tuned-0.4b-v2` were already training on v1, so those 9 cases are removed from
  the evaluation sets for **every** guard. The cyber & agent test set drops from 415 to 407, and stays identical
  across guards.
- The exporter now excludes the source, so the next export (v2) has 4,344 records.

**Caveats that remain:**

- **Old `laya-tuned-0.4b` (formerly s1-v4).** It trained on the whole s1guard split before the leak check
  existed, and that split overlaps 317 public cases: pb-jackhhao 218, pb-deepset 54, pb-xtram1 27,
  pb-rogue 18. Its **public-benchmark results are not clean**. Its cyber & agent results are clean, because that set
  excludes tagged rows.
- **Same-distribution data.** The training set holds the *train* splits of deepset and jackhhao, so on
  pb-deepset and pb-jackhhao our fine-tunes are in-distribution, though not leaked. Sentinel v2's model card
  lists jackhhao as training data too.
- **Undisclosed training data.** Jev, Clef and Laya base do not publish their training data, so exposure
  to public benchmarks can't be ruled out. Kev and Strands do publish theirs; neither overlaps our
  evaluation sources (Kev's includes Aegis 2.0, which we use only as benign training rows).
- **Unpinned s1guard sources.** The s1guard sources were loaded from Hugging Face without revision pins,
  from a local cache. The training file's sha256 is the reproducibility anchor; the lab public sets are
  revision-pinned.

## 5. Agent-loop benchmarks (evaluation only)

| Benchmark | Package | Licence | Use |
|---|---|---|---|
| AgentDojo | `inspect-evals[agentdojo]==0.23.0` ([ethz-spylab/agentdojo](https://github.com/ethz-spylab/agentdojo)) | MIT | Attack and utility arms through the gateway ([agent-eval.md](agent-eval.md)) |
| AgentThreatBench | `inspect-evals==0.23.0` ([UKGovernmentBEIS/inspect_evals](https://github.com/UKGovernmentBEIS/inspect_evals)) | MIT | Autonomy hijack, data exfiltration |

The toolcall-guard-v1 test and val splits (MIT) are AgentDojo-derived and are evaluation and dev data only.

## 6. Model weights and hosted models

| Model id (ours) | Weights | Licence | Training data disclosed |
|---|---|---|---|
| laya-base-0.4b | [convaiinnovations/laya](https://huggingface.co/convaiinnovations/laya) `7b928d8` (ModernBERT-large) | Apache-2.0 | No |
| laya-tuned-0.4b, laya-tuned-0.4b-v2 | Our checkpoints (not published) | Apache-2.0 base; data as in §2 | This document |
| kev-base-9b | [jaredpalmer/kev-9b](https://huggingface.co/jaredpalmer/kev-9b) `db029f0` on Qwen3.5-9B-Base | Apache-2.0 | Yes: 12 public NLP sets + Aegis 2.0 |
| kev-tuned-9b | Our LoRA on kev-9b, trainer [jaredpalmer/kev](https://github.com/jaredpalmer/kev) `5e42a7a` (not published) | Apache-2.0 base; data as in §2 | This document |
| kev-base-4b | jaredpalmer/kev-4b `6cfce5c` (Qwen3.5-4B-Base) via OpenRouter | Apache-2.0 | Yes |
| clef-base-9b | [Cloudflare/clef-flash](https://huggingface.co/Cloudflare/clef-flash) `fde727a` (Qwen3.5-9B) | Apache-2.0 | No |
| strands-base-2b | [StrandsAgents/strands-decider-2B-hobson-v19](https://huggingface.co/StrandsAgents/strands-decider-2B-hobson-v19) `bb282d7` | Apache-2.0 | Yes: 29 public NLP sets |
| jev-base | TypeSafe `jev-1.13-20260917` via OpenRouter | API terms | No |
| gemma4:e2b (data generator) | [google/gemma-4-E2B-it](https://huggingface.co/google/gemma-4-E2B-it) | Apache-2.0 | n/a |
| gpt-6-luna (judge) | OpenAI API | API terms | No |

Classifier licences (Llama 4 Community, Elastic, NVIDIA OpenMDW and others) are listed per guard in
[guards.yaml](../src/guardlab/guards.yaml).

## 7. Licence obligations

- **CC-BY-4.0** (Aegis 2.0, OR-Bench, XSTest, guardrail-showdown prompts): if we publish a fine-tuned model
  or derived data, credit these sources. This document serves as the attribution list.
- **CC-BY-SA-4.0** (BIPIA contexts): evaluation only. Any redistributed derivative of the contexts must
  carry the same licence. We don't redistribute them, and the corpus is gitignored.
- **CC-BY-NC-4.0** (rogue-security, gated): evaluation only, never trained on. Commercial use of the data
  itself is not permitted.
- **No licence declared** (xTRam1): evaluation only, never trained on, never redistributed.
- **MIT / Apache-2.0** (everything else): keep the notices if redistributing.
- **Repo status:** BIPIA's repo is archived (last push 2024). PurpleLlama's GitHub licence shows
  NOASSERTION because the repo mixes licences; its README licenses the CyberSecEval benchmarks as MIT.

**What is and isn't in git:**
- Not in git: corpus data, training data and fine-tuned weights.
- In git: manifests, generated model replies, and the code that rebuilds everything.

## 8. Reproduce

```bash
uv run python evals/lab/build_corpus.py                       # lab corpus + manifest (pinned sources)
uv run python training/decision_models/export_data.py         # training set + scoring requests + manifest
modal run training/decision_models/modal_kev.py::train --name kev-tuned-9b
modal run training/decision_models/modal_laya.py::train --name laya-tuned-0.4b-v2
uv run python evals/lab/experiments/held_out.py --report <guards>    # both held-out test sets, fresh
```

## 9. Future data sources

A survey on 2026-10-08 looked for datasets that could extend the training set. Each candidate's licence, update date
and size were checked on the Hugging Face or GitHub API; no attack text was downloaded. None has been added yet.

**Where our training data is thinnest:**
- tool definitions (MCP and plugin descriptions);
- leaks in assistant replies;
- legitimate security requests that look like attacks;
- legitimate agent traffic.

### Rules for adding a source

1. **Cyber scope only.** No content-safety, bio or chem data.
2. **A licence that allows training.** Non-commercial, research-only and undeclared licences are out for
   training, though some can still be used for evaluation.
3. **Not derived from what we evaluate on:**
   - AgentDojo;
   - BIPIA;
   - the five public benchmarks;
   - toolcall-guard-v1's test split.

   Check the dataset card and paper for its upstream sources.
4. **Run the leak check** (export_data.py) and record the source, licence and counts in this document.

### Recommended (licence allows training; low leak risk)

| Dataset | Publisher | Fills | Size | Licence | Updated | Notes |
|---|---|---|---:|---|---|---|
| [microsoft/llmail-inject-challenge](https://huggingface.co/datasets/microsoft/llmail-inject-challenge) | Microsoft | Injection hidden in emails; exfiltration via send-email calls | 461,640 | MIT | 2025-05 | Largest real adaptive indirect-injection set. Attacks only (benign emails come from elsewhere); heavy near-duplicates, so sample |
| [nvidia/Nemotron-RL-Agentic-Indirect-Prompt-Injection-v1](https://huggingface.co/datasets/nvidia/Nemotron-RL-Agentic-Indirect-Prompt-Injection-v1) | NVIDIA | Tool results, benign tool catalogues (9 domains), tool calls | 1,272 | CC-BY-4.0 | 2026-06 | Fully synthetic, no seed data; covers three of our agent stages |
| [perplexity-ai/browsesafe-bench](https://huggingface.co/datasets/perplexity-ai/browsesafe-bench) | Perplexity | Injection in web pages, with hard benign pages | 14,719 | MIT | 2025-12 | Train split only. Drop its InjecAgent-style attack type, and check its "Important Message" type against AgentDojo's template |
| [gabrielchua/system-prompt-leakage](https://huggingface.co/datasets/gabrielchua/system-prompt-leakage) | Gabriel Chua | Leaks in assistant replies | 354,704 | MIT | 2024-11 | The only sizeable reply-leak set. Synthetic paraphrases, so possibly easy |
| [PurpleLlama `mitre_frr`](https://github.com/meta-llama/PurpleLlama/tree/main/CybersecurityBenchmarks/datasets/mitre_frr) | Meta | Legitimate security requests that sound offensive (false-refusal set) | ~750 | MIT | 2025-09 | Cyber-specific hard negatives we lack. Same family as CyberSecEval-MITRE, so dedupe |
| [ScaleAI/MCP-Atlas](https://huggingface.co/datasets/ScaleAI/MCP-Atlas) | Scale AI | Real MCP tool descriptions and benign tool calls | 500 tasks, 220 tools | CC-BY-4.0 | 2026-08 | Benign tool definitions. Our test set has only 2 tool-definition cases |
| [AI-Secure/DTap-Bench-Agent-Trajectories](https://huggingface.co/datasets/AI-Secure/DTap-Bench-Agent-Trajectories) | UIUC / UChicago | MCP agent traffic: tool calls, tool results, benign tasks | 6,682 tasks | Apache-2.0 | 2026-07 | Keep only exfiltration, dangerous actions and consent cases. It's a benchmark, so hold a slice out |
| [agiresearch/ASB](https://github.com/agiresearch/ASB) | Rutgers (ICLR 2025) | Malicious and normal tool descriptions, tool calls | small | MIT | 2026-09 | Tool poisoning. Don't also use ASSEBench, which is built from it and AgentDojo |
| [Lakera/gandalf_ignore_instructions](https://huggingface.co/datasets/Lakera/gandalf_ignore_instructions) | Lakera | Direct injection | 1,000 | MIT | 2025-02 | Clean and deduped. Check against rogue-security |
| [Lakera/mosscap_prompt_injection](https://huggingface.co/datasets/Lakera/mosscap_prompt_injection) | Lakera | Secret and system-prompt extraction | 278,945 | MIT | 2025-02 | Large but noisy; needs labelling |
| [reshabhs/SPML_Chatbot_Prompt_Injection](https://huggingface.co/datasets/reshabhs/SPML_Chatbot_Prompt_Injection) | SPML authors | Injection judged against a system prompt | 16,012 | MIT | 2024-04 | Has (system prompt, user prompt) pairs. Its card advises against prompt-only training |
| [trendmicro-ailab/Primus-Instruct](https://huggingface.co/datasets/trendmicro-ailab/Primus-Instruct) | Trend Micro | Legitimate defensive-security tasks | 835 | ODC-BY | 2025-02 | Hard negatives, e.g. analysing a suspicious command |
| [nvidia/Nemotron-Terminal-Corpus](https://huggingface.co/datasets/nvidia/Nemotron-Terminal-Corpus) | NVIDIA | Legitimate shell commands | 366,154 | CC-BY-4.0 | 2026-02 | Negatives for destructive-command detection |
| [allenai/WildChat-4.8M](https://huggingface.co/datasets/allenai/WildChat-4.8M) | AI2 | Real user prompts | 3.2M | ODC-BY | 2025-08 | Realistic benign traffic. It also contains real jailbreaks, so label before use |
| [sierra-research/tau2-bench](https://github.com/sierra-research/tau2-bench) | Sierra | Legitimate tool results and calls | repo data | MIT | 2026-10 | Benign agent traffic. Don't adopt it as an evaluation later if trained on |

**Lower priority:**
- **Generic function calling:**
  - [nvidia/When2Call](https://huggingface.co/datasets/nvidia/When2Call) (CC-BY-4.0)
  - [Salesforce/xlam-function-calling-60k](https://huggingface.co/datasets/Salesforce/xlam-function-calling-60k) (CC-BY-4.0, gated)
  - [nebius/SWE-agent-trajectories](https://huggingface.co/datasets/nebius/SWE-agent-trajectories) (CC-BY-4.0)
- **Older, single-goal injection:** [hackaprompt/hackaprompt-dataset](https://huggingface.co/datasets/hackaprompt/hackaprompt-dataset)
  (MIT, gated, 2023).
- **Real CTF attacks, no card:** [invariantlabs/agent-ctf24-public](https://huggingface.co/datasets/invariantlabs/agent-ctf24-public) (MIT).
- **Upstream sources not named, so leak risk unknown:** [hendzh/PromptShield](https://huggingface.co/datasets/hendzh/PromptShield) (Apache-2.0).
- **Licence conflict:** [AI-secure/RedCode](https://github.com/AI-secure/RedCode). It has strong risky-code coverage, but GitHub says MIT
  and the HF copy says CC-BY-NC-SA. Ask the authors before using it.

### Candidates for new held-out evaluations (not training)

| Dataset | What it adds | Licence |
|---|---|---|
| [facebook/llamafirewall-alignmentcheck-evals](https://huggingface.co/datasets/facebook/llamafirewall-alignmentcheck-evals) | Agent goal hijack via tool calls (3,462) | MIT, but the card says not to train on it |
| [Lakera/b3-agent-security-benchmark-weak](https://huggingface.co/datasets/Lakera/b3-agent-security-benchmark-weak) | Crowd-sourced agent attacks (630) | Conflicting: card text MIT, metadata "other" |
| [nvidia/Nemotron-AIQ-Agentic-Safety-Dataset-1.0](https://huggingface.co/datasets/nvidia/Nemotron-AIQ-Agentic-Safety-Dataset-1.0) | Agent security traces (5,196) | NVIDIA evaluation-only licence |

### Warnings found in the survey

- **verazuo/jailbreak_llms (in-the-wild jailbreaks) is where jackhhao's jailbreaks come from.**
  - Training on it, or on garak's copy of it, would leak into the jackhhao public benchmark.
  - Remove that overlap before using it, or skip it.
- **Data derived from AgentDojo or BIPIA must not be trained on.** Found in:
  - ASSEBench / AgentAuditor;
  - TaskTracker;
  - PIGuard's training split, which holds 1,116 BIPIA inputs and 53 of InjecAgent's 62 attacks (arXiv 2610.03448);
  - several Hugging Face copies of AgentDojo, BIPIA and InjecAgent.
- **rogue-security doesn't say where its samples come from.** Check any new injection or jailbreak data for
  near-duplicates against it.

### Rejected

| Reason | Datasets |
|---|---|
| No licence declared | Tensor Trust, MCPTox (the best tool-poisoning set found; worth asking its authors for a licence), MCP-SafetyBench, R-Judge |
| Non-commercial or research-only | WASP, Lakera gandalf-rct, SecQA, CTIBench, AmazonScience FalseReject, rogue-security coding-agent benchmark |
| Out of scope (general harm or other modality) | WildJailbreak, JailbreakBench, AgentHarm, Pliny HackAPrompt, Nemotron jailbreak set, CyberSecEval visual injection |
| Not released or private | ShieldAgent-Bench, Lakera PINT, Gray Swan ART, HackAPrompt 2.0 (only one track out) |
| Unclear provenance | neuralchemy prompt-injection aggregator (relabels licences), GenTelBench, assorted 2026 individual uploads |

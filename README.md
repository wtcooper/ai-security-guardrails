# ai-security-guardrails

**A lab for comparing AI security guardrails, and a workspace for building and customizing them.**
It compares four approaches on a shared corpus and in agent workflows: self-hosted classifiers,
self-hosted decision models, hosted decision APIs and LLM-as-a-judge. Measure detection quality,
false positives, latency, cost and task utility; then tune, fine-tune or integrate a guard through
the same interface used for evaluation.

## Where we're working now

Active work targets a runtime guardrail for an existing LiteLLM Enterprise gateway: high detection, few false
positives, latency and cost that hold up at hundreds of millions of requests, and agents that keep working.

The best performer in each of the four approaches, on the same two held-out test sets
([How we test](#how-we-test)):

| Approach | Best performer | What it is | F1: our test set / public | Median latency per check | Cost per 1,000 checks | Status |
|---|---|---|---|---|---|---|
| **LLM-as-a-judge** | `agentic-security` | gpt-6-luna reads our written policies over the last 10 messages; drop-in LiteLLM guardrail | **0.91** / 0.86 | 0.90 s (OpenAI API) | about $0.06 (single messages; more on long agent loops) | **Active, ready to deploy:** no cache, no extra services |
| **Hosted decision API** | `jev-base` | TypeSafe Jev via OpenRouter, asked our policies as yes/no questions; one call returns a probability per question | **0.92** / 0.88 | **0.22 s** (OpenRouter) | about $0.08 | **Active:** pre-filter in front of the judge |
| **Self-hosted decision model** | `kev-tuned-9b` | Kev-9B (open weights) fine-tuned by us on clean public data, asked the same questions | **0.93** / **0.89** | 0.38 s (one H100, unoptimised runner) | about $0.42 on a rented H100 at that speed (estimate; batching would cut it) | **Active:** matches Jev; weaker on agent tool calls; needs a GPU server |
| **Self-hosted classifier** | `safeguard-20b` | OpenAI gpt-oss-safeguard 20B (open weights), a reasoning model following our judge's policies | **0.93** / 0.83 | 3.7 s (Mac) | own hardware; needs a GPU server in production | Benchmarked; not under active tuning |

F1 combines attacks caught and legitimate cases wrongly flagged into one score from 0 to 1. All 24 guardrails we
compared, with attacks caught, false alarms and short descriptions, are in the
[full comparison](#head-to-head-on-the-two-held-out-test-sets).
Next up, not yet evaluated: Microsoft-Decision-1, the OpenAI Decisions API, Google Model Armor, Azure Prompt
Shields and others ([contenders](#not-yet-evaluated-other-top-contenders-to-do)).

**`agentic-security`** ([docs](docs/agentic-security.md), [deploy/agentic-security/](deploy/agentic-security/)) is
one Python file, two prompt files and a config entry, with no cache, no state and no extra services.

- **Judge calls:** one before the model, and one after it only if the model calls tools. It sees the last 10
  messages, not the system prompt.
- **Flagged tool results:** a second call cuts only the injected lines, so the agent keeps working.
- **Accuracy:** level with `cyber-guard` on single messages: F1 0.91 for both on our cyber & agent test set, and
  0.86 for both on the public benchmarks.
- **Agent tasks:** AgentDojo task success is 56% under attack and 70% on benign tasks, vs 6% and 61% for
  `cyber-guard` (73% and 78% with no guardrail).
- **Protection:** with an agent that falls for injections (Gemma 4 e2b), attack success fell from 42% to 0%.
- **Cost and speed:** 11× fewer judge tokens than `cyber-guard` without its cache, and about 2.0 s of classifier time
  per agent step.

**`jev-base`** ([docs](docs/jev-evaluation.md)) is a hosted decision model: one call per check returns a
probability for each security question.

- **Questions:** our judge's own tuned policies are given to it as questions. For tool calls it also gets the
  user's request, the agent's earlier steps and the app's rules as context.
- **Accuracy:** 0.92 on our cyber & agent test set and 0.88 on the public benchmarks, vs 0.91 and 0.86 for the two
  judges. Only our fine-tuned Kev-9B (and gpt-oss-safeguard on our test set) are level with it. On agent tool
  calls it scores 0.89, the same as `agentic-security`, vs 0.81 for `cyber-guard` and 0.67 for Kev-9B. Those
  figures come from 50 cases, so treat differences under about 0.1 as noise.
- **Speed and cost:** median 0.22 s per check, about $0.06–0.09 per 1,000 checks.
- **Weak spot:** more false alarms than the judges on the public benchmarks (8.6% of legitimate prompts flagged, vs
  1.9–2.2%).
- **As a pre-filter:** Jev lets through checks it scores below 0.27, and the judge decides the rest. On our test set
  the judge's F1 holds (0.91 to 0.90) and its false alarms drop from 4.6% to 3.9%. On the public benchmarks F1
  dips from 0.86 to 0.85. Jev alone answers 82–84% of legitimate checks.

## How we test

Every score above comes from two **held-out test sets**: cases set aside before any tuning or training. No guard we
tuned and no model we fine-tuned ever saw them. Every guard is scored on exactly the same cases, with fresh model
calls on every run (no cached answers).

| Test set | Cases | What's in it | Where it comes from |
|---|---|---|---|
| **Cyber & agent test set** | 407: 254 attacks, 153 legitimate | Requests for offensive cyber help next to legitimate security work; prompt injection, including injection hidden in tool output and documents; unsafe agent tool calls; harmless look-alikes | Built by us from public research datasets plus a few hand-written cases. Closest to what the gateway will see. |
| **Public benchmarks** | 1,578: 685 attacks, 893 legitimate | Prompt-injection and jailbreak attempts typed by users, and injection hidden in documents | Five benchmarks published by other teams, used as they are, so results can be compared with other work |

**Why scores differ between them:**
- **Different labelling.** Other teams labelled the public benchmarks with their own definitions. Some "attacks"
  there are harmless role-play or fall outside our cyber scope, and some legitimate rows read like attacks. Every
  guard scores lower there.
- **Different content.** The public benchmarks have no agent tool calls and aren't built around offensive-cyber
  requests.

So the cyber & agent set measures how well a guard does our job. The public benchmarks check that a guard isn't
just fitted to our own data.

**With thanks to the teams whose datasets make up these tests:**
- **Cyber & agent set:**
  - Meta's [CyberSecEval](https://github.com/meta-llama/PurpleLlama) (Purple Llama)
  - [AdvBench](https://github.com/llm-attacks/llm-attacks)
  - Microsoft's [BIPIA](https://github.com/microsoft/BIPIA)
  - [NotInject](https://huggingface.co/datasets/leolee99/NotInject)
  - [toolcall-guard-v1](https://huggingface.co/datasets/johannhartmann/toolcall-guard-v1)
  - [PromptInject](https://github.com/agencyenterprise/PromptInject)
  - [guardrail-showdown](https://github.com/AjeyDS/guardrail-showdown)
- **Public benchmarks:**
  - [deepset/prompt-injections](https://huggingface.co/datasets/deepset/prompt-injections)
  - [jackhhao/jailbreak-classification](https://huggingface.co/datasets/jackhhao/jailbreak-classification)
  - [xTRam1/safe-guard-prompt-injection](https://huggingface.co/datasets/xTRam1/safe-guard-prompt-injection)
  - [rogue-security/prompt-injections-benchmark](https://huggingface.co/datasets/rogue-security/prompt-injections-benchmark)
  - Microsoft's BIPIA

Every source, its licence, and how training data is kept apart from these tests are in
[docs/data-provenance.md](docs/data-provenance.md). Run the comparison with
`uv run python evals/lab/experiments/held_out.py --run <guards>`, then `--report <guards>`.

## Four guardrail approaches

| Approach | Where the task is defined | Inference | Implementations and evaluation status |
|---|---|---|---|
| **Self-hosted classifiers** | Fixed training task or a supplied classification policy | Local models | Evaluated: Prompt Guard 2, Sentinel v2, DeBERTa, Llama Guard 4, Qwen3Guard, Shieldstral, Granite Guardian, Nemotron and gpt-oss-safeguard |
| **Self-hosted decision models** | Questions and context supplied to the model; weights can be fine-tuned | Local or rented GPU | Evaluated: Laya (base and two fine-tunes), Strands Decider 2B, Clef-flash 9B, Kev-4B, Kev-9B (base and our fine-tune, trained on [one clean training set](docs/data-provenance.md)); see [docs/decision-model-size.md](docs/decision-model-size.md) |
| **Hosted decision APIs** | Questions sent to the provider | Provider API | Evaluated: `jev-base` and `jev-base-stockq` (TypeSafe Jev via OpenRouter). Awaiting access: `dec-openai` (OpenAI Decisions API) |
| **LLM-as-a-judge** | Policy instructions and application context | Hosted LLM | Evaluated: `cyber-guard-per-policy` (per-policy), `cyber-guard` (combined request/response policies) and `agentic-security` (drop-in, one call per hook over a recent window), all using gpt-6-luna |

The [guard registry](src/guardlab/guards.yaml) includes a regex baseline. `dec-luna-emu` is a chat-LLM
test double for the Decisions API format; its scores do not measure a hosted decision model.
`safeguard-20b` runs locally through Ollama with supplied policies. The four approaches have different
stage coverage and amounts of tuning, which the results below identify.

Scope is cyber-security only (OWASP Top 10 for LLM, MCP and Agentic apps; MITRE ATT&CK / ATLAS):
prompt injection (direct and indirect), guard evasion and jailbreaks, tool poisoning, unsafe agent
tool calls, system-prompt and secret leakage, and malicious cyber requests. Content safety is out of
scope and [retired](src/guardlab/judge/retired/).

## How the lab compares guards

**How it works:**

1. **One corpus.** [evals/lab/build_corpus.py](evals/lab/build_corpus.py) builds a single-turn cyber
   corpus. One part is for tuning; the rest becomes the two [held-out test sets](#how-we-test). Each case has a
   stage: user input, conversation, tool result, tool definition, tool call or model output.
   See [docs/benchmark.md](docs/benchmark.md).
2. **One guard interface.** Every guard implements `check(Case) -> GuardResult` (blocked, score,
   status, latency, cost) and is registered in [src/guardlab/guards.yaml](src/guardlab/guards.yaml).
   Timeouts and errors are reported separately. They count as blocks in evaluations, while the
   recommended gateway entry fails open.
3. **Two runners.**
   - **Single-turn checks:** promptfoo runs any set of guards over a slice of the corpus
     ([evals/run.sh](evals/run.sh)), calling every guard fresh on every run.
     [evals/lab/report.py](evals/lab/report.py) produces the leaderboard: recall, false-positive rate,
     F1, ranking quality (AUROC), latency and cost.
   - **Agent loops:** vanilla Inspect AgentDojo and AgentThreatBench run through the gateway with and
     without guardrails ([evals/agent/](evals/agent/)). They measure attack success and task utility.
4. **One deployment path.** Any registered guard runs as a LiteLLM guardrail, so the guard you
   evaluate is the guard you deploy. The judges can bill their model calls to the caller's team key.

A fixed classifier usually detects a particular learned risk; a decision model answers the
questions supplied for the current stage. Judges use policy instructions and richer context.
Compare guards on the stages they support, and distinguish stock models from tuned policies and
fine-tuned weights. The judge has had many tuning rounds, `laya-tuned-0.4b-stockq` was fine-tuned, and the other
local models run without weight fine-tuning; some receive custom policies.

## Build and customize

### Decision-model fine-tuning

The System One implementation asks a battery of security questions against Laya or a hosted backend.
Our `laya-tuned-0.4b-stockq` adapter uses a fine-tuned Laya checkpoint; `laya-base-0.4b-stockq` provides the base-model comparison.
The [fine-tuning workspace](experiments/s1guard_finetune/README.md) contains benchmark construction,
training, scoring and threshold calibration. Checkpoints are local and are not committed.
[Training methods](docs/training-methods.md) records the v1–v4 recipes and results, and
[the System One guide](docs/s1guard.md) documents the original implementation. Training is currently
paused; the recipes and adapters remain available for building and evaluating a custom model.

### Judge policy tuning

Five [policy files](src/guardlab/judge/policies/) cover injection, malicious cyber requests, indirect
injection, unsafe actions and output leakage. Shared instructions are in `common.md`.
[The builder](evals/lab/build_consolidated.py) generates request/response prompts, omitting Examples
based on section-ablation results. `cyber-guard-per-policy` checks policies separately;
`cyber-guard` combines them. Choose the judge model through the registry's `model` configuration.
The `-gw` variants route checks through LiteLLM for chargeback. Policies, context handling and
ablations are documented in [the tuning log](docs/judge.md).

The selected malicious-cyber policy is **v4**: it keeps the original defensive-work allowances and
adds general target-profiling and deceptive-identity rules. Its frozen validation caught **90.5%**
of attacks with **3.03%** false positives; the comparison below shows the defense/false-positive
tradeoff. Cyber **policy v4** and **`laya-tuned-0.4b-stockq` model weights** are separate version histories.

### Decision-question tuning (hosted decision models)

[`JevGuard`](src/guardlab/adapters/jev.py) asks a decision model one call per check, with questions per stage in a
YAML file. A question can be `policy: <name>`, which hands the model the judge's own tuned policy text from the files
above, so policy tuning carries over to decision models. Tool-call questions get the user's request and the
agent's earlier steps as context. Tune with [evals/lab/experiments/jev_tune.py](evals/lab/experiments/jev_tune.py)
on dev slices; the rounds are in [docs/jev-evaluation.md](docs/jev-evaluation.md).

To add a different guard, implement the shared interface and register it; see
[adding a guard](docs/lab.md#adding-a-guard). Evaluation, reporting and gateway integration use that
same adapter.

## Results

### Head to head on the two held-out test sets

Every guardrail we compared, grouped by approach. All scored on the same two held-out test sets
([How we test](#how-we-test)), fresh runs (2026-10-09), each at its deployed setting:

| Guardrail | What it is | Our test set: F1 · caught · false alarms | Public: F1 · caught · false alarms | Median latency per check | Status |
|---|---|---|---|---|---|
| **LLM-as-a-judge: a hosted LLM reads our written policies** | | | | | |
| `agentic-security` | Drop-in LiteLLM guardrail. gpt-6-luna rates the last 10 messages: one call before the model, one after only if it calls tools. Cuts injected lines out of tool results so the agent keeps working | **0.91** · 85% · 4.6% | **0.86** · 78% · 1.9% | 0.90 s (OpenAI API) | **Active, ready to deploy** |
| `cyber-guard` | Lab judge: same model and policies, one call per piece of content; affordable only with a verdict cache | **0.91** · 86% · 5.2% | **0.86** · 78% · 2.2% | 0.84 s (OpenAI API) | Lab only |
| `agentic-security-sys` | agentic-security with the application's system prompt also shown to the judge | **0.91** · 87% · 5.9% | **0.87** · 79% · 1.8% | 0.81 s (OpenAI API) | Measured alternative: more false blocks on tool calls; keep off |
| **Hosted decision API: a provider's decision model answers our yes/no questions** | | | | | |
| `jev-base` | TypeSafe Jev via OpenRouter, asked our tuned questions (the judge's policies phrased as questions); one call returns a probability per question | **0.92** · 88% · 4.6% | **0.88** · 87% · 8.6% | 0.22 s (OpenRouter) | **Active:** pre-filter in front of the judge |
| `jev-base-stockq` | Same model with the original generic security questions | **0.89** · 85% · 9.2% | **0.87** · 85% · 8.7% | 0.22 s (OpenRouter) | Superseded by jev-base |
| **Self-hosted decision model: open weights we run (or fine-tune), asked the same questions as jev-base** | | | | | |
| `kev-tuned-9b` | Kev-9B (Qwen3.5-9B base) fine-tuned by us on 4,375 clean records | **0.93** · 89% · 4.6% | **0.89** · 87% · 7.1% | 0.38 s (1× H100, unoptimised runner) | **Active:** matches Jev; weak on tool calls; needs a GPU server |
| `clef-base-9b` | Cloudflare Clef-flash 9B, out of the box | **0.87** · 79% · 4.6% | **0.73** · 69% · 16.5% | 0.26 s (OpenRouter) | Benchmarked |
| `kev-base-9b` | Kev-9B, out of the box | **0.86** · 81% · 13.7% | **0.74** · 73% · 19.4% | 2.6 s (1× H100, unoptimised runner) | Baseline for the fine-tune |
| `kev-base-4b` | Kev-4B (Qwen3.5-4B base), out of the box | **0.84** · 78% · 13.7% | **0.75** · 70% · 13.4% | 3.6 s (OpenRouter) | Benchmarked |
| `laya-tuned-0.4b-v2` | Laya (ModernBERT-large, 0.4B) fine-tuned by us on the same records | **0.86** · 89% · 28.8% | **0.73** · 74% · 21.2% | 0.07 s (1× L4 GPU) | Too small: flags 29% of legitimate cases |
| `laya-tuned-0.4b` | Our earlier Laya fine-tune (older question set) | **0.81** · 99% · 75.2% | not clean (trained on these) | 0.06 s (1× L4 GPU) | Retired |
| `laya-base-0.4b` | Laya, out of the box | **0.77** · 95% · 87.6% | **0.58** · 80% · 73.8% | 0.06 s (1× L4 GPU) | Baseline |
| `strands-base-2b` | AWS Strands Decider 2B, out of the box | **0.74** · 80% · 57.5% | not run | 6.8 s (Mac) | Benchmarked |
| **Self-hosted classifier: a safety model we run locally** | | | | | |
| `safeguard-20b` | OpenAI gpt-oss-safeguard 20B: a reasoning model that follows whatever policy it is given; given our judge's policies, one call per policy | **0.93** · 89% · 4.6% | **0.83** · 72% · 1.2% | 3.7 s (Mac) | Benchmarked |
| `nemotron-cs-4b` | NVIDIA Nemotron 3.5 Content Safety 4B, given our policy text as a custom policy | **0.84** · 77% · 11.8% | **0.77** · 67% · 4.8% | 4.5 s (Mac) | Benchmarked |
| `granite-guardian-8b` | IBM Granite Guardian 4.1 8B: built-in jailbreak and harm checks, custom criteria for agent content | **0.83** · 78% · 17.6% | **0.75** · 63% · 3.7% | 1.7 s (Mac) | Benchmarked |
| `shieldstral-3b` | Mistral Shieldstral 1.0 3B: one score per yes/no policy question | **0.82** · 73% · 9.2% | **0.72** · 59% · 3.8% | 0.54 s (Mac) | Benchmarked |
| `qwen3guard-4b` | Alibaba Qwen3Guard-Gen 4B: fixed safety categories, including jailbreak | **0.80** · 72% · 12.4% | **0.76** · 65% · 4.7% | 0.73 s (Mac) | Benchmarked |
| `qwen3guard-0.6b` | Qwen3Guard-Gen 0.6B: the same, smaller | **0.78** · 71% · 17.0% | **0.76** · 67% · 7.5% | 0.14 s (Mac) | Benchmarked |
| `sentinel-v2` | rogue-security (Qualifire) Sentinel v2: prompt-injection and jailbreak classifier; user-side text only † | **0.74** · 69% · 28.1% | **0.82** · 71% · 1.5% | 0.04 s (Mac) | Benchmarked ‡ |
| `llama-guard4-12b` | Meta Llama Guard 4 12B: content-safety model with no prompt-injection category; 4,000-token context § | **0.39** · 26% · 11.1% | **0.30** · 20% · 10.3% | 1.3 s (Mac) | Benchmarked |
| `pg2-86m` | Meta Llama Prompt Guard 2 86M: prompt-injection and jailbreak classifier; user-side text only † | **0.32** · 19% · 0.0% | **0.60** · 45% · 3.5% | 0.02 s (Mac) | Benchmarked |
| `deberta-pi-v2` | ProtectAI DeBERTa-v3 prompt-injection v2 (now hosted by Red Hat); user-side text only † | **0.30** · 19% · 12.4% | **0.68** · 61% · 14.2% | 0.02 s (Mac) | Benchmarked |
| `pg2-22m` | Meta Llama Prompt Guard 2 22M; user-side text only † | **0.13** · 7% · 0.0% | **0.37** · 22% · 0.0% | 0.01 s (Mac) | Benchmarked |

**How to read it:**
- **F1** combines attacks caught and legitimate cases wrongly flagged into one score from 0 to 1. **Caught** is the
  share of attacks blocked; **false alarms** is the share of legitimate cases blocked.
- **Watch the false alarms, not just F1.** A guard that blocks everything scores F1 0.77 on our test set and 0.61
  on the public benchmarks, because both have many attacks. The small Laya and Strands models land near that by
  flagging most legitimate cases.
- **Whole-set scoring.** A case a guard can't screen counts as let through, as it would be in a gateway.
  - † These read user-side text only, so the agent tool calls (12% of our test set) pass.
  - § Llama Guard 4 can't fit 14% of cases in its 4,000-token context; they pass.
- **Decision models share one rule:** the same questions and thresholds as `jev-base`. Scored instead at a cut-off
  set on tuning data for 5% false alarms, Laya v2 catches 65% (F1 0.77) on our test set
  ([details](docs/decision-model-size.md)).
- ‡ Sentinel v2's public score is probably inflated: it comes from the publisher of the rogue-security benchmark,
  and its model card lists the jackhhao benchmark as training data.
- **Latency is per check and depends on where the guard ran,** so compare within a hardware column, not across:
  OpenAI or OpenRouter APIs, one GPU on Modal, or the Mac. The judges make one call per hook. `safeguard-20b`
  makes one call per policy.

More detail:
- [docs/agentic-security.md](docs/agentic-security.md): judges, latency and agent loops.
- [docs/jev-evaluation.md](docs/jev-evaluation.md): Jev tuning and the pre-filter.
- [docs/decision-model-size.md](docs/decision-model-size.md): decision models by size and fine-tuning, by attack type.

### Not yet evaluated: other top contenders (to do)

Strong options we haven't scored yet, to run on the same two held-out test sets when access allows:

| Contender | Approach | What it is | What's needed |
|---|---|---|---|
| **Microsoft-Decision-1** | Hosted decision API | Microsoft's decision model (post-trained Qwen3.5-9B), launched 2026-10-09; Foundry now, OpenRouter "coming soon". Same System One protocol as Jev, so our questions apply unchanged | An Azure subscription with a Foundry deployment, or the OpenRouter listing ([plan](docs/microsoft-decision-1-plan.md)) |
| **OpenAI Decisions API** | Hosted decision API | gpt-6-luna answering typed questions with probabilities | Preview access; `dec-openai` is registered and returns 403 until then |
| Perplexity `pplx-decider-v1-27b` | Hosted API or self-hosted decision model | 27B decision model with open weights (Apache-2.0) and a hosted API; ahead of Jev on its own benchmarks | A Perplexity API key, or a rented GPU |
| Cloudflare Clef (27B) | Hosted decision API | The full-size Clef; we have only tested Clef-flash 9B | A Cloudflare account (Workers AI) |
| Intern-Decision-4B, Decision-2.0-Lux-9B, Eikos-27B | Self-hosted decision models | Open decision models from InternLM, vLLM Semantic Router (claims 18 ms) and an independent author (best open model on LangWatch) | A rented GPU (Modal) |
| **Google Model Armor** | Cloud guardrail API | Hosted prompt-injection, jailbreak, malicious-URL and sensitive-data filters | A GCP project with the API enabled ([plan](docs/model-armor-plan.md)) |
| **Azure AI Content Safety Prompt Shields** | Cloud guardrail API | Detects user prompt attacks and attacks hidden in documents; callable as a standalone resource | An Azure subscription (the same one would cover Decision-1) |
| AWS Bedrock Guardrails | Cloud guardrail API | Content filters, including a prompt-attack filter, via ApplyGuardrail. AWS says the prompt-attack filter doesn't evaluate tool results | An AWS account |
| Lakera Guard, Palo Alto Prisma AIRS | Commercial guardrail APIs | Agent-aware screening of prompts, tool calls and tool results | Run at work through a `gateway_guardrail` adapter |
| Fastino GLiGuard-300M | Self-hosted classifier | Small Apache-licensed guard model; watch list | None (local) |

### Earlier results (older policies and test cases)

The tables below predate the two test sets above. They used older policies and an earlier version of our test
set, which still included reply checks and cases our first fine-tune had trained on. Compare guards within a table,
not across tables. Labels such as C4 and D3 are policy versions from [the tuning log](docs/judge.md). AUROC
measures how well a guard's score ranks attacks above legitimate cases (1.0 is perfect). Full tables are in
[evals/lab/leaderboard.md](evals/lab/leaderboard.md).

**Earlier version of our test set (407 cases).** It covers direct and indirect injection, evasion, tool poisoning, unsafe
tool calls, leakage and malicious cyber requests ([docs/benchmark.md](docs/benchmark.md)). Each guard is scored at
its own threshold.

| Guard | Category | Attacks caught | Benign flagged | F1 | AUROC | Median latency |
|---|---|---:|---:|---:|---:|---:|
| **cyber-guard** (combined policies) | LLM judge (gpt-6-luna) | 89% | **4%** | **0.93** | 0.928 | 732 ms |
| **cyber-guard-per-policy** (same rules, one call per policy: the tuning harness) | LLM judge (gpt-6-luna) | **90%** | **4%** | **0.93** | **0.939** | 805 ms |
| safeguard-20b (cyber-guard-per-policy's C4 policies) | self-hosted classifier (policy-following) | 80% | 2% | 0.88 | 0.904 | 3184 ms |
| dec-luna-emu (test double: luna behind the Decisions API format) | LLM, decision-API format | 80% | 10% | 0.85 | 0.858 | n/a* |
| granite-guardian-8b | self-hosted classifier | 73% | 14% | 0.79 | binary | 1458 ms |
| sentinel-v2 † | self-hosted classifier | 70% | 17% | 0.77 | 0.849 | 137 ms |
| nemotron-cs-4b (custom policy) | self-hosted classifier | 66% | 12% | 0.76 | 0.835 | 2602 ms |
| laya-tuned-0.4b-stockq (fine-tuned Laya) ‡ | self-hosted decision model | 63% | 13% | 0.73 | 0.818 | 148 ms |
| qwen3guard-0.6b / 4b | self-hosted classifier | 57% / 54% | 14% / 10% | 0.67 / 0.67 | 0.795 / 0.819 | 147 / 732 ms |
| deberta-pi-v2 † (Red Hat's reference classifier) | self-hosted classifier | 57% | 17% | 0.67 | 0.780 | 26 ms |
| strands-base-2b-stockq (AWS, out of the box) | self-hosted decision model | 49% | 6% | 0.64 | 0.845 | 561 ms |
| shieldstral-3b | self-hosted classifier | 49% | 8% | 0.63 | 0.811 | 402 ms |
| laya-base-0.4b-stockq (Laya) | self-hosted decision model | 39% | 4% | 0.55 | 0.764 | 139 ms |
| pg2-86m / pg2-22m † (Llama Prompt Guard 2) | self-hosted classifier | 29% / 5% | 1% / 0% | 0.45 / 0.09 | 0.885 / 0.653 | 101 / 30 ms |
| llama-guard4-12b § (Q4_K_M, llama.cpp) | self-hosted classifier | 30% | 15% | 0.42 | 0.676 | 1123 ms |
| regex floor | — | 12% | 1% | 0.21 | 0.554 | 0 ms |

\* The test double answers via gpt-6-luna chat calls, so its latency says nothing about a real
decision API. The real OpenAI Decisions API measured about 105 ms for 3 questions.
† Screens user-side text only (input, tool results, tool definitions). Tool-call and output cases
are excluded for it.
‡ Scored only on the 215 rows it was not trained on.
§ A content-safety model with no prompt-injection category. 8% of cases exceed its 4k context and
are unavailable.
Both judge rows use an older frozen policy set whose tool-call checks see the agent's earlier steps; see
[docs/judge.md](docs/judge.md). The other guards' tool-call rows were scored without those steps.

- **Self-hosted decision models, out of the box.** Strands Decider 2B (F1 0.64, AUROC 0.845) beats
  zero-shot Laya (0.55) but trails our fine-tuned laya-tuned-0.4b-stockq and the judges. Its default 0.5 threshold
  is conservative.
  - Strongest on malicious cyber requests (87%) and tool poisoning (72%).
  - Weakest on indirect injection (25%) and output leaks (0%).
  - laya-base-0.4b-stockq asks a slightly different set of questions (laya-base.yaml), so treat that gap as
    indicative.
- **The reference classifier is narrow.** deberta-pi-v2 catches 94% of direct injection but only
  42% of indirect injection, and it flags 41% of NotInject's benign prompts.

**Cyber policy v4 validation.** The selected malicious-cyber policy was frozen first, then checked against
earlier versions on the same **168 attacks and 231 legitimate security requests**:

| Cyber policy | Attacks caught | Attacks passing the guard | Legitimate work wrongly flagged | F1 |
|---|---:|---:|---:|---:|
| Original v1 | 138/168 (82.1%) | 30/168 (17.9%) | 6/231 (2.60%) | 0.885 |
| Previous v3 | 158/168 (94.0%) | 10/168 (6.0%) | 16/231 (6.93%) | 0.924 |
| **Selected v4** | **152/168 (90.5%)** | **16/168 (9.5%)** | **7/231 (3.03%)** | **0.930** |

V4 catches **14 more attacks than v1 for one more false flag**. Against v3 it removes nine false flags while
losing six catches. These cases were held back from this tuning round, but earlier policy versions had seen them,
so this is a validation check rather than a fresh test. The full protocol is in
[the tuning log](docs/judge.md#cyber-rounds-k27k34-retain-v1-precision-with-selected-v3-defenses-2026-10-06).

**Earlier public-benchmark comparison, per benchmark (F1).** The judge rows use older policies. We tuned
direct-injection rules on the training halves these benchmarks publish; the test halves scored here were never
used for tuning.

| Guard | BIPIA (indirect) | deepset | jackhhao | rogue-security | xTRam1 |
|---|---:|---:|---:|---:|---:|
| cyber-guard-per-policy (D3) | **0.961** | 0.519 | 0.935 | 0.694 | 0.890 |
| cyber-guard (D3) | 0.953 | 0.537 | 0.947 | 0.725 | 0.875 |
| cyber-guard-per-policy (C4, before the D rounds) | 0.966 | 0.462 | 0.943 | 0.649 | 0.714 |
| dec-luna-emu | 0.556 | **0.588** | 0.947 | **0.805** | 0.800 |
| deberta-pi-v2 | 0.378 | 0.537 | — ¶ | 0.659 | **0.924** |
| pg2-86m | 0.020 | 0.235 | 0.967 | 0.664 | 0.711 |
| laya-base-0.4b-stockq | 0.139 | 0.257 | **0.982** | 0.518 | 0.835 |
| regex | 0.029 | 0.125 | 0.667 | 0.323 | 0.385 |

¶ Excluded: deberta-pi-v2 was trained on jackhhao, per its model card.

**What this shows:**

- **Indirect injection:** the luna judges dominate (BIPIA 0.95–0.96).
- **Direct injection:** three tuning rounds on the training halves of these sets raised cyber-guard-per-policy's
  mean F1 from 0.747 to 0.800 (consolidated 0.807). The judge still trails on deepset and
  rogue-security, whose remaining misses are mostly attacks only against an absent system prompt,
  or non-cyber role-play outside this lab's scope.
- **The reference classifier wins only on its own task.** deberta-pi-v2 is the best direct-injection
  detector on xTRam1 (0.924) and the fastest guard (26 ms). But it misses indirect injection (BIPIA
  0.378) and flags 17% of our benign agentic content. This matches Red Hat's finding that fixed
  classifiers win on the task they were trained for.

Guards and runs not yet done are listed in the [roadmap](#status-and-roadmap).

**Agent loops through the gateway (earlier runs, 2026-10-05).**

These runs predate cyber policy v4. `cyber-guard` is the name of a configured judge deployment arm
in [the gateway config](gateway/litellm_config.yaml).

Setup:

- **Agent:** gpt-6-luna, running vanilla Inspect tasks with their own scorers.
- **Arms:** three, identical except for guardrails (see [docs/agent-eval.md](docs/agent-eval.md)).
- **Blocks:** returned in-band as HTTP 200 refusals.
- **Wiring:** every model request ran exactly its arm's guardrails. One post-call check (out of about
  1,100 guarded requests) hit its 10 s budget and failed open.

**How to read the columns:**
- **Attack succeeded:** the attacker's goal happened, e.g. money really sent to the attacker.
- **User's task done:** the user's own request was completed, e.g. the bill paid.

| Benchmark | Arm | Attack succeeded | User's task done | Agent run (median) |
|---|---|---:|---:|---:|
| AgentDojo, 96 attacks | no guardrail | 0% | 75% | 17.3 s |
| | pre-call only | 0% | 6% | 4.0 s |
| | cyber-guard | 0% | 6% | 4.5 s |
| AgentDojo, 96 benign tasks | no guardrail | — | **79%** | 16.4 s |
| | pre-call only | — | 66% | 7.4 s |
| | cyber-guard | — | 66% | 8.6 s |
| AgentThreatBench, 24 | no guardrail | **4%** (1 attack) | 71% | 13.8 s |
| | pre-call only | 0% | 12% | 5.6 s |
| | cyber-guard | 0% | 12% | 9.0 s |

**Reading:**

- **gpt-6-luna resists almost every attack on its own.** It ignored all 96 of AgentDojo's default
  injections. One AgentThreatBench attack got through, and both guarded arms stopped it.
- **Detecting an injection ends the user's task.** Pre-call caught the injected tool result in about 95%
  of attack runs, but refusing the turn also ends the user's legitimate task (75% → 6%). Only removing the
  injected text and letting the agent continue fixes that, which `agentic-security` now does (56% task
  success under attack). This run does not compare a 200 refusal with a raw 400: the eval shim turned every
  400 into a 200 refusal, so the agent never saw a 400. The case for 200 comes from how SDKs and agent
  frameworks treat errors (a 400 is never retried and ends the run) and from billing
  ([research](docs/research/LiteLLM%20agent%20guardrail%20practices.md)).
- **False blocks on benign tasks cost 13 points** (79% → 66%). The main cause is instructions the user
  explicitly delegated ("do the tasks on my TODO list at <url>"). The tool-result check doesn't see the
  user's request, so these look like injections.
- **Post-call added 3 blocks** and no extra protection here, because pre-call stopped the attacks first.

The evaluation also found cache, fail-open logging and billing issues that were fixed. Details and
reproduction steps are in [the agent-evaluation guide](docs/agent-eval.md) and
[chargeback verification](docs/chargeback.md).

**Single-turn end to end through the LiteLLM gateway:** 45 cyber smoke cases, target gemma4:e2b,
gpt-6-luna grader.

| Arm | Attack success | Benign requests blocked by the guard | Median time |
|---|---:|---:|---:|
| baseline (no guardrail) | 32% | — | 5.7 s |
| cyber-guard-per-policy (LabGuardrail) | **4%** | 0 / 17 | 1.3 s |
| s1guard v4 | 0% | 0 / 17 | 1.3 s |

Remaining benign failures in every arm are the target model's own refusals. This is a historical
smoke evaluation; its `s1guard v4` arm refers to the decision-model checkpoint, not cyber policy v4.

## Install

**Prerequisites:**

- macOS or Linux, Python 3.11–3.12 and [uv](https://docs.astral.sh/uv/).
- Node.js, for `npx promptfoo@0.123.1` (pinned in `evals/run.sh`).
- A checkout of [ai-security-evals](https://github.com/wtcooper/ai-security-evals) next to this repo,
  or `EVALS_REPO=<path>`. The corpus builder reads its control-isolate corpus.
- For API judges, the decisions emulator or the e2e grader: an OpenAI API key with gpt-6-luna access.
  Local guards can be evaluated without it.
- Optional, for local guards and the gateway: [Ollama](https://ollama.com) 0.35.1 or later (it
  serves decision models), llama.cpp (`brew install llama.cpp`) and Docker.

```bash
git clone git@github.com:wtcooper/ai-security-guardrails.git
git clone git@github.com:wtcooper/ai-security-evals.git    # sibling checkout: core corpus
cd ai-security-guardrails
uv sync --extra eval --extra gateway --extra dev    # API judges, decision APIs, gateway, reports, tests
uv sync --all-extras                                # instead, to add local Hugging Face guards (torch) and Laya
cp .env.example .env                                # then add your keys
uv run pytest -q                                    # offline tests
uv run python evals/lab/build_corpus.py             # builds evals/lab/data/ (gitignored)
```

**Configuration** goes in `.env`, which is gitignored; see [.env.example](.env.example).

| Variable | Needed for |
|---|---|
| `OPENAI_API_KEY` | API-backed runs: the luna judges, `dec-luna-emu`, `dec-openai`, the e2e grader and the gateway's `gpt-6-luna` model. |
| `OPENROUTER_API_KEY` | Optional. `jev-base-stockq`: TypeSafe Jev, the hosted reference decision model, via OpenRouter. |
| `HF_TOKEN` | Gated Hugging Face models: Llama Prompt Guard 2, Llama Guard 4 and Sentinel v2. Accept each licence on its model page first. |
| `EVALS_REPO` | Optional. The path to ai-security-evals, if it isn't a sibling directory. |
| `S1GUARD_BACKEND`, `TYPESAFE_API_KEY`, `S1GUARD_URL` | Optional. The s1guard and decision-model backends: `laya` (local), `jev`, or `http` (any `/v1/systemone` server). |
| `DATABASE_URL` | Optional. The LiteLLM spend database, for chargeback. |

## Usage

**Check one text with one guard:**

```bash
uv run guardlab list
uv run guardlab check --guard regex --stage input "Review our incident-response checklist."
uv run guardlab check --guard cyber-guard --stage input "Review our incident-response checklist."
```

`--stage` is one of `input`, `conversation`, `tool_result`, `tool_definition`, `tool_call` or
`output`. `--system-prompt` and `--user-request` supply trusted context for output and tool-call
checks. The exit code is 2 when the guard blocks.

**Run an evaluation** (promptfoo run, then the report):

```bash
bash evals/run.sh lab rep-dev 'regex|cyber-guard'
# After setting up local models, compare classifier and decision-model adapters too:
bash evals/run.sh lab rep-dev 'deberta-pi-v2|laya-base-0.4b-stockq|laya-tuned-0.4b-stockq'
PF_CONCURRENCY=8 bash evals/run.sh lab public 'cyber-guard'   # more parallelism for API guards
```

| Mode | Cases |
|---|---|
| `rep-dev`, `cyber-dev` | Tuning cases: 407 representative cases, and cyber requests next to legitimate security work |
| `pi-dev`, `tc-dev` | More tuning cases: direct injection (from the public benchmarks' training halves) and tool calls |
| `rep-test`, `cyber-test` | Held-out cases. The [cyber & agent test set](#how-we-test) is built from these two |
| `public` | The public benchmarks' test halves (up to 400 cases each) |
| `smoke-*`, `lite-*`, `dev` / `test` | About 100 cases for a quick check, or larger runs |

The headline comparison is `evals/lab/experiments/held_out.py`, which runs both held-out test sets.
Results go to `evals/results/lab/`, which is gitignored. Every run calls the guard fresh; set
`GUARDLAB_REUSE_RESULTS=1` only to deliberately reuse logged results.

**Reports:**

```bash
uv run python evals/lab/report.py evals/results/lab/rep-test-*.json --by category   # or --by set|stage
uv run python evals/lab/report.py <results.json> --errors cyber-guard-per-policy                  # missed attacks, false alarms
uv run python evals/lab/report.py <test files> --dev <dev files> --out evals/lab/leaderboard.md
```

**Agent-loop eval:** vanilla Inspect AgentDojo and AgentThreatBench through the gateway, with three arms:
no guardrail, pre-call only, and `cyber-guard`. A wiring check must pass first, and every request is
audited. See [docs/agent-eval.md](docs/agent-eval.md).

```bash
bash evals/agent/run.sh setup && bash evals/agent/run.sh smoke    # then: bash evals/agent/run.sh full
```

**Tune the judge:**

1. Run `rep-dev` (and `pi-dev` for direct injection), then read `report.py --errors`.
2. Edit a policy in `src/guardlab/judge/policies/` and bump its `version`.
3. Rebuild the consolidated instructions: `uv run python evals/lab/build_consolidated.py`.
4. Rerun and compare with `report.py --per-file`. Differences under about 0.02 F1 are noise.
5. Freeze, then run the [held-out comparison](#how-we-test) once.

**Fine-tune a decision model:** follow the [training workflow](experiments/s1guard_finetune/README.md#workflow),
then score and calibrate on the development split and evaluate the frozen model on test. Record the
checkpoint, question policy and training overlap alongside the lab results.

**Local guard models** (run one at a time on a laptop):

| Guard ids | Setup |
|---|---|
| `pg2-86m`, `pg2-22m`, `sentinel-v2`, `qwen3guard-0.6b`, `qwen3guard-4b`, `shieldstral-3b` | `uv sync --all-extras`. Models load in-process from Hugging Face at pinned revisions. |
| `granite-guardian-8b` | `ollama pull granite4.1-guardian:8b` |
| `safeguard-20b` | `ollama pull gpt-oss-safeguard:20b` |
| `nemotron-cs-4b` | Needs its own venv and an HTTP shim on :8776. The commands are in [evals/lab/shims/nemotron_server.py](evals/lab/shims/nemotron_server.py). |
| `llama-guard4-12b` | Run `bash evals/lab/shims/llama_guard4.sh setup` once (24 GB download, quantized to 6.4 GB), then `... serve` (:8767). |
| `deberta-pi-v2` | `uv sync --all-extras`; loads in-process (CPU-fast). |
| `strands-base-2b-stockq` | Run `bash evals/lab/shims/strands_decider.sh setup` once, then `... serve` (:8768, about 5 GB). Runs in its own `uvx` environment. |
| `clef-base-9b-stockq` | Ollama 0.35.1 or later; `ollama pull clef-flash:9b` (about 10 GB). |
| `dec-luna-emu` | `uv run python -m guardlab.decisions.mock_server --port 8765 --upstream luna` |
| `laya-base-0.4b-stockq`, `laya-tuned-0.4b-stockq` | The `laya` extra. `laya-tuned-0.4b-stockq` also needs the fine-tuned checkpoint from `experiments/s1guard_finetune/`, which isn't committed. |

How the corpus, splits, scoring and reports work: [docs/lab.md](docs/lab.md). To add a guard, see
[docs/lab.md#adding-a-guard](docs/lab.md#adding-a-guard).

## Deploy any guard in the LiteLLM gateway

**For production, deploy `agentic-security`.** Copy [deploy/agentic-security/](deploy/agentic-security/) into the
gateway and add its config entry; it needs nothing else from this repository. The shared integration class below
runs any *registry* guard, for lab evaluation and A/B tests.

Registered guards share one LiteLLM integration class. Choose a guard and hooks that match its
supported stages. The guard you evaluate is the guard you deploy.

```yaml
guardrails:
  - guardrail_name: lab-guard
    litellm_params:
      guardrail: guardlab.litellm_guardrail.LabGuardrail
      mode: [pre_call, post_call, pre_mcp_call, post_mcp_call]
      guard_id: laya-base-0.4b-stockq       # choose a registered guard; requires the local Laya setup
      on_unavailable: block       # fail closed
      on_block: error             # HTTP 400; use refuse for an in-band refusal
```

- **What gets checked:**
  - Requests: new user turns, tool results and tool definitions.
  - Responses: replies (checked against the system prompt) and tool calls (checked against the
    user's request).
  - MCP calls and results.
- **On a block,** the gateway returns HTTP 400 `Blocked by <guard> (request|response): <reason>`.
- **End-to-end A/B** through the gateway: `bash evals/run.sh e2e` ([evals/lab/e2e.yaml](evals/lab/e2e.yaml)).
  The target model is `gemma4:e2b` on Ollama.
- **Chargeback:** the `*-gw` judges call luna through the gateway's own router with the caller's key
  metadata. LiteLLM records each pre- and post-call judge call in its spend DB against the same team
  key as the inference. Verified: [docs/chargeback.md](docs/chargeback.md).
- **Configured judge example: the `cyber-guard` entry.** It uses `cyber-guard-gw`,
  which now loads cyber policy v4. Its placement and failure behavior were studied separately:
  - **Pre-call** on everything entering inference.
  - **Post-call only when the response contains tool calls,** so plain chat replies add no post-call
    latency.
  - **No `during_call`,** because a block cancels the inference and LiteLLM then records $0 for it, so
    it can't be charged back. No MCP hooks either: tool results reach the next pre-call anyway.
  - **Fail open** (`on_unavailable: allow`, `deadline_s: 10`). If the judge is down, errors or is too
    slow, the user still gets inference and the gateway logs a warning.
  - **Blocks are refused in-band** (`on_block: refuse`, the default). HTTP 200 with a fixed message,
    `finish_reason: "content_filter"` and no tool calls, which is how model APIs signal a safety block.
    The reason goes to the gateway log. Streamed replies are held until the post-call check passes, so
    a blocked tool call never reaches the client.
- **Every model call is charged back.** Judge calls, the inference, and the inference behind a
  post-call block are all billed to the caller's team key in LiteLLM's spend DB, streamed or not.
  Pre-call blocks bill only the judge, because the model never ran. `evals/lab/chargeback_check.py`
  verifies all five paths. Lab-only entries (`cyber-guard-per-policy`, `dec-luna-emu`) call OpenAI directly and
  aren't charged back. See [docs/chargeback.md](docs/chargeback.md).

  Measured in [docs/guardrail-placement.md](docs/guardrail-placement.md). Pre-call alone stops 87% of
  injected tool output but only 2–6% of agent drift; the action check stops about 80% of drift.

**Run the local gateway** (LiteLLM on :4000, master key `sk-local`, config in
[gateway/litellm_config.yaml](gateway/litellm_config.yaml)):

```bash
bash gateway/start_gateway.sh
```

**With the spend DB, to check chargeback:**

```bash
docker run -d --name guardlab-litellm-db -e POSTGRES_USER=litellm -e POSTGRES_PASSWORD=litellm-local \
    -e POSTGRES_DB=litellm -p 127.0.0.1:5433:5432 postgres:17-alpine
uv run prisma generate --schema .venv/lib/python3.12/site-packages/litellm/proxy/schema.prisma   # once
DATABASE_URL=postgresql://litellm:litellm-local@127.0.0.1:5433/litellm bash gateway/start_gateway.sh
uv run python evals/lab/chargeback_check.py --guardrail cyber-guard-gw
```

## Layout

```
src/guardlab/      guard interface, registry (guards.yaml), adapters, judge policies (judge/policies/, generated
                   judge/consolidated/), decision-API clients, LiteLLM guardrail
src/s1guard/       the original System One guard (question battery on Laya / Jev), used by the s1 and dec adapters
evals/lab/         corpus builder, promptfoo configs (lab.yaml, e2e.yaml), provider, report, leaderboard,
                   local-model shims (shims/), consolidated-judge builder, chargeback check, experiments/
evals/agent/       agent-loop eval: shim (arm guardrails, key, block -> refusal), wiring preflight,
                   Inspect driver, summary
evals/promptfoo/   earlier s1guard isolate / app_eval / redteam configs
experiments/       decision-model fine-tuning recipes (s1guard_finetune/) and guard comparisons (showdown/)
gateway/           local LiteLLM proxy config + mock-echo model
docs/              lab guide, judge tuning log, decision APIs, research notes (index: docs/README.md)
```

## Status and roadmap

**Done:**

- the lab harness and cyber corpus;
- custom decision-model training, calibration and the fine-tuned `laya-tuned-0.4b-stockq` adapter;
- per-policy and consolidated judges, with a trajectory-aware action check and selected cyber policy v4;
- the decision-API client and its test double;
- self-hosted classifiers and decision models;
- shared gateway integration, configurable blocks and verified judge chargeback;
- placement and agent-loop studies measuring attack success and task utility;
- `agentic-security`, the drop-in guardrail for deployment (no cache; surgical withholding; verified chargeback);
- 94 offline tests.

**Roadmap** (each item is registered or scripted unless noted; runs are deferred to keep laptop load low):

*Hosted decision APIs*

- [x] Jev tuned and validated (`jev-base`, [docs/jev-evaluation.md](docs/jev-evaluation.md)): F1 0.92 on our test set
  and 0.88 on public benchmarks, at 0.22 s per check. As a pre-filter it answers 82–84% of legitimate checks.
- [ ] Jev pre-filter as a drop-in LiteLLM guardrail in front of agentic-security, then an agent-loop test.
- [x] Fine-tune Kev-9B and Laya on one clean training set ([docs/data-provenance.md](docs/data-provenance.md)) with
  the Jev questions: Kev-9B matches Jev overall, Laya 0.4B does not ([docs/decision-model-size.md](docs/decision-model-size.md)).
- [ ] Kev-9B: add unsafe tool-call training data (it catches 54% vs Jev's 89%), then measure serving latency on an
  optimised server.
- [ ] Microsoft-Decision-1 on both held-out test sets ([plan](docs/microsoft-decision-1-plan.md)): needs an Azure
  Foundry deployment or the OpenRouter listing; the Jev adapter needs an `api-key` header option.
- [ ] `dec-openai`: rerun once OpenAI Decisions API access is granted (currently 403), then retire
  `dec-luna-emu` from the results.
- [ ] Optional: Perplexity's Decisions API, and Cloudflare Clef hosted on Workers AI (needs an account
  and a small path adapter).

*Self-hosted decision models*

- [x] Clef-flash 9B evaluated through OpenRouter (`clef-base-9b`). The local Ollama copy (`clef-base-9b-stockq`) is not needed.
- [ ] `strands-base-2b-stockq` on the public benchmarks (about 13 minutes at 2 requests per second).
- [ ] Kev-4B and Laya GGUF via llama.cpp. These need llama.cpp build b11371 or later; Homebrew
  stable is older.
- [ ] Intern-Decision-4B (not registered): its engine targets CUDA, and the Apple GPU is untested.
- [ ] Definition sensitivity: run each decision model with the stock questions and with the
  judge's tuned policy text as question instructions.
- [ ] Fine-tune Strands Decider 2B on our dev split (its recipe is published) and compare with laya-tuned-0.4b-stockq.

*Cloud guardrail APIs*

- [ ] Google Cloud Model Armor on both held-out test sets ([plan](docs/model-armor-plan.md)). Needs a GCP project
  with billing, the Model Armor API enabled and gcloud login credentials; the Vertex API key won't work. Then a
  thin adapter. A full run fits in the free tier.
- [ ] AWS Bedrock Guardrails and Azure Prompt Shields on the same sets, to match the work comparison.

*Self-hosted classifiers*

- [x] Every classifier on both held-out test sets (2026-10-08): gpt-oss-safeguard 20B with our policies matches the
  best guards on our test set (0.93); the prompt-injection-only classifiers score 0.13–0.32 there.
- [ ] Watch list: Fastino GLiGuard-300M.

*LLM-as-a-judge customization and gateway experiments*

- [x] Select cyber policy v4 with measured catch / false-alarm tradeoffs; see [rounds K27–K34](docs/judge.md#cyber-rounds-k27k34-retain-v1-precision-with-selected-v3-defenses-2026-10-06).
- [x] Prompt-section ablations, long-content windows, trajectory-aware action checks and billed streaming blocks.
- [ ] Generalize the cyber instructions for four production gap areas: cloud-credential retrieval, operational
  exploit payloads, web-injection payloads with filter bypass, and phishing or impersonation content. Then test
  adaptive attacks.
- [ ] agentic-security: close the 3-point cyber recall gap to cyber-guard (86.5% vs 89.6% of cyber attacks caught on our test set). Framing-only tuning
  traded false positives for recall ([round](docs/agentic-security.md#cyber-recall-tuning-round-2026-10-07-tried-not-adopted)),
  so this needs shared-policy content changes.
- [ ] agentic-security: detect off-task drift ("autonomy hijack") in tool results; 2 of 6 still succeed, as with no guardrail.
- [ ] agentic-security: rerun the agent-loop evals (AgentDojo, AgentThreatBench) on the current version. The new refusal
  wording and turn-wide tool-result re-rating could change task success.
- [ ] LiteLLM gap: streamed `/v1/messages` replies skip post-call guardrails, so a flagged tool call reaches Claude
  Code. Report upstream, or add a custom streaming hook (testing it needs an Anthropic key).
- [ ] LiteLLM gap: its Responses-API refusal for a pre-call block is malformed; report upstream.
- [ ] Decide whether the judge should see `developer` messages (Codex app instructions) as context; today they're
  dropped with the system prompt.
- [x] `agentic-security`: drop-in guardrail with a 10-message window (user intent and drift as context), no cache,
  surgical withholding of flagged tool results and hedged judge calls; see [docs/agentic-security.md](docs/agentic-security.md).
- [ ] agentic-security: tune delegated-task false withholds on a separate dev set (not AgentDojo).
- [x] Measure protection with an agent model that falls for injections (Gemma 4 e2b: attack success 42% to 0%).
- [ ] Add gateway alerting and a separate judge rate-limit budget; rerun ablations after policy changes.

*Evaluation hardening, from Red Hat's and guardrail-showdown's benchmarks*

- [ ] Bootstrap 95% confidence intervals in the report. About 400 cases per split gives roughly
  ±0.03 F1.
- [ ] A "runs on" column (Mac CPU, Mac GPU, OpenAI API, hosted API) and a network baseline, so
  latencies are comparable.
- [ ] Audit `trained_on` for every guard against our sets. For example, Sentinel v2 and the
  rogue-security benchmark come from the same publisher.
- [ ] An audited list of mislabelled public rows, reported with and without them.
- [ ] Results by input length (DeBERTa reads 512 tokens per window; Llama Guard 4 fails past 4k)
  and by language.

*At work*

- [ ] A `gateway_guardrail` adapter, to score Bedrock Guardrails, Model Armor, Prisma AIRS and Lakera
  on the same corpus through LiteLLM's `/guardrails/apply_guardrail`.

**More documentation:** [docs/README.md](docs/README.md).

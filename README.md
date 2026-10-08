# ai-security-guardrails

**A lab for comparing AI security guardrails, and a workspace for building and customizing them.**
It compares four approaches on a shared corpus and in agent workflows: self-hosted classifiers,
self-hosted decision models, hosted decision APIs and LLM-as-a-judge. Measure detection quality,
false positives, latency, cost and task utility; then tune, fine-tune or integrate a guard through
the same interface used for evaluation.

## Where we're working now

Active work targets a runtime guardrail for an existing LiteLLM Enterprise gateway: high detection, few false
positives, latency and cost that hold up at hundreds of millions of requests, and agents that keep working. The best
option found so far in each approach:

| Approach | Best option today | Quality | Latency per check (p50) | Status |
|---|---|---|---|---|
| **LLM-as-a-judge** | **`agentic-security`** (gpt-6-luna) | held-out F1 0.93 (cyber 0.93). AgentDojo task success under attack 56%, vs 6% for `cyber-guard` | about 0.9 s; at most 2 judge calls per agent step | **Active, ready to deploy:** drop-in, no cache |
| **Hosted decision API** | **`jev-tuned`** (TypeSafe Jev via OpenRouter) | dev F1 0.945 (cyber 0.964, tool calls 0.878) | **about 0.21 s** | **Active, evaluating:** held-out run pending. Best as a pre-filter that clears about half of benign traffic before the judge |
| Self-hosted classifier | `safeguard-20b` (policy-following); `sentinel-v2` (fastest useful) | F1 0.88; 0.77, user-side text only | 3.2 s; 137 ms | Benchmarked; not under active tuning |
| Self-hosted decision model | `s1-v4` (our Laya fine-tune) | F1 0.73 | 148 ms | Paused |

Classifier and decision-model rows come from the historical `rep-test` comparison below. Jev's numbers are from
dev data until its held-out run.

**`agentic-security`** ([docs](docs/agentic-security.md), [deploy/agentic-security/](deploy/agentic-security/)) is
one Python file, two prompt files and a config entry, with no cache, no state and no extra services.

- **Judge calls:** one before the model, and one after it only if the model calls tools. It sees the last 10
  messages, not the system prompt.
- **Flagged tool results:** a second call cuts only the injected lines, so the agent keeps working.
- **Accuracy:** on par with `cyber-guard` on single messages, held-out F1 0.93 vs 0.92 (cyber 0.93 vs 0.95).
- **Agent tasks:** AgentDojo task success is 56% under attack and 70% on benign tasks, vs 6% and 61% for
  `cyber-guard` (73% and 78% with no guardrail).
- **Protection:** with an agent that falls for injections (Gemma 4 e2b), attack success fell from 42% to 0%.
- **Cost and speed:** 11× fewer judge tokens than `cyber-guard` without its cache, and about 2.0 s of classifier time
  per agent step.

**`jev-tuned`** ([docs](docs/jev-evaluation.md)) is a hosted decision model: one call per check returns a
probability for each security question.

- **Questions:** given our judge's own tuned policies as questions, and the user's request as context for tool calls,
  it matched or beat the LLM judges on user messages, tool results and tool definitions on dev.
- **Speed and cost:** p50 0.21 s, p95 0.30 s, about $0.07 per 1k checks.
- **Weak spot:** tool calls, F1 0.878 vs the judge's 0.92.
- **As a pre-filter:** if it clears checks it scores below 0.15 and the judge decides the rest, the judge's accuracy
  and false-positive rate are unchanged, and about half of legitimate traffic needs no judge call.

## Four guardrail approaches

| Approach | Where the task is defined | Inference | Implementations and evaluation status |
|---|---|---|---|
| **Self-hosted classifiers** | Fixed training task or a supplied classification policy | Local models | Evaluated: Prompt Guard 2, Sentinel v2, DeBERTa, Llama Guard 4, Qwen3Guard, Shieldstral, Granite Guardian, Nemotron and gpt-oss-safeguard |
| **Self-hosted decision models** | Questions and context supplied to the model; weights can be fine-tuned | Local models | Evaluated: `s1-zeroshot` (Laya), `s1-v4` (our Laya fine-tune), `strands-decider-2b`. Registered, not yet evaluated: `clef-flash-9b` |
| **Hosted decision APIs** | Questions sent to the provider | Provider API | Evaluated on dev: `jev-tuned` and `dec-jev` (TypeSafe Jev via OpenRouter; held-out run pending). Awaiting access: `dec-openai` (OpenAI Decisions API) |
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
   corpus: our combined benchmark (407 dev + 407 test representative cases, plus full splits) and five
   well-known public benchmarks that run independently. Each case has a stage: user input,
   conversation, tool result, tool definition, tool call or model output.
   See [docs/benchmark.md](docs/benchmark.md).
2. **One guard interface.** Every guard implements `check(Case) -> GuardResult` (blocked, score,
   status, latency, cost) and is registered in [src/guardlab/guards.yaml](src/guardlab/guards.yaml).
   Timeouts and errors are reported separately. They count as blocks in evaluations, while the
   recommended gateway entry fails open.
3. **Two runners.**
   - **Single-turn checks:** promptfoo runs any set of guards over a slice of the corpus
     ([evals/run.sh](evals/run.sh)), with a per-guard result cache.
     [evals/lab/report.py](evals/lab/report.py) produces the leaderboard: recall, false-positive rate,
     F1, AUROC, latency and cost.
   - **Agent loops:** vanilla Inspect AgentDojo and AgentThreatBench run through the gateway with and
     without guardrails ([evals/agent/](evals/agent/)). They measure attack success and task utility.
4. **One deployment path.** Any registered guard runs as a LiteLLM guardrail, so the guard you
   evaluate is the guard you deploy. The judges can bill their model calls to the caller's team key.

A fixed classifier usually detects a particular learned risk; a decision model answers the
questions supplied for the current stage. Judges use policy instructions and richer context.
Compare guards on the stages they support, and distinguish stock models from tuned policies and
fine-tuned weights. The judge has had many tuning rounds, `s1-v4` was fine-tuned, and the other
local models run without weight fine-tuning; some receive custom policies.

## Build and customize

### Decision-model fine-tuning

The System One implementation asks a battery of security questions against Laya or a hosted backend.
Our `s1-v4` adapter uses a fine-tuned Laya checkpoint; `s1-zeroshot` provides the base-model comparison.
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
tradeoff. Cyber **policy v4** and **`s1-v4` model weights** are separate version histories.

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

**Latest results for active work:**
- `agentic-security` vs `cyber-guard`: held-out accuracy, system-prompt test, latency, and agent loops with
  gpt-6-luna and Gemma 4, in [docs/agentic-security.md](docs/agentic-security.md).
- Jev tuning rounds and the cascade analysis are in [docs/jev-evaluation.md](docs/jev-evaluation.md).

The tables below are the historical cross-approach comparison.

### Combined cyber benchmark (`rep-test`, 407 cases; historical comparison)

The benchmark covers OWASP LLM/MCP/Agentic and MITRE: direct and indirect injection, evasion, tool
poisoning, unsafe tool calls, leakage and malicious cyber requests. See
[docs/benchmark.md](docs/benchmark.md). Each guard is scored at its own threshold.
These recorded runs predate cyber policy v4;
they are not a fresh comparison of the current policies. Full tables are in
[evals/lab/leaderboard.md](evals/lab/leaderboard.md).

| Guard | Category | Attacks caught | Benign flagged | F1 | AUROC | p50 latency |
|---|---|---:|---:|---:|---:|---:|
| **cyber-guard** (combined policies) | LLM judge (gpt-6-luna) | 89% | **4%** | **0.93** | 0.928 | 732 ms |
| **cyber-guard-per-policy** (same rules, one call per policy: the tuning harness) | LLM judge (gpt-6-luna) | **90%** | **4%** | **0.93** | **0.939** | 805 ms |
| safeguard-20b (cyber-guard-per-policy's C4 policies) | self-hosted classifier (policy-following) | 80% | 2% | 0.88 | 0.904 | 3184 ms |
| dec-luna-emu (test double: luna behind the Decisions API format) | LLM, decision-API format | 80% | 10% | 0.85 | 0.858 | n/a* |
| granite-guardian-8b | self-hosted classifier | 73% | 14% | 0.79 | binary | 1458 ms |
| sentinel-v2 † | self-hosted classifier | 70% | 17% | 0.77 | 0.849 | 137 ms |
| nemotron-cs-4b (custom policy) | self-hosted classifier | 66% | 12% | 0.76 | 0.835 | 2602 ms |
| s1-v4 (fine-tuned Laya) ‡ | self-hosted decision model | 63% | 13% | 0.73 | 0.818 | 148 ms |
| qwen3guard-0.6b / 4b | self-hosted classifier | 57% / 54% | 14% / 10% | 0.67 / 0.67 | 0.795 / 0.819 | 147 / 732 ms |
| deberta-pi-v2 † (Red Hat's reference classifier) | self-hosted classifier | 57% | 17% | 0.67 | 0.780 | 26 ms |
| strands-decider-2b (AWS, out of the box) | self-hosted decision model | 49% | 6% | 0.64 | 0.845 | 561 ms |
| shieldstral-3b | self-hosted classifier | 49% | 8% | 0.63 | 0.811 | 402 ms |
| s1-zeroshot (Laya) | self-hosted decision model | 39% | 4% | 0.55 | 0.764 | 139 ms |
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
Both judge rows use the frozen S1 instructions (T5 policies, Examples dropped), whose tool-call checks
see the agent's trajectory; see [docs/judge.md](docs/judge.md). The other guards' tool-call rows were
scored without the trajectory.

- **Self-hosted decision models, out of the box.** Strands Decider 2B (F1 0.64, AUROC 0.845) beats
  zero-shot Laya (0.55) but trails our fine-tuned s1-v4 and the judges. Its default 0.5 threshold
  is conservative.
  - Strongest on malicious cyber requests (87%) and tool poisoning (72%).
  - Weakest on indirect injection (25%) and output leaks (0%).
  - s1-zeroshot asks a slightly different set of questions (laya-base.yaml), so treat that gap as
    indicative.
- **The reference classifier is narrow.** deberta-pi-v2 catches 94% of direct injection but only
  42% of indirect injection, and it flags 41% of NotInject's benign prompts.

### Current cyber policy v4 validation

The selected policy was frozen before this phase's pool-B validation. Fresh v1/v3 controls and v4
used the same **168 attacks and 231 legitimate security requests**:

| Cyber policy | Attacks caught | Attacks passing the guard | Legitimate work wrongly flagged | F1 |
|---|---:|---:|---:|---:|
| Original v1 | 138/168 (82.1%) | 30/168 (17.9%) | 6/231 (2.60%) | 0.885 |
| Previous v3 | 158/168 (94.0%) | 10/168 (6.0%) | 16/231 (6.93%) | 0.924 |
| **Selected v4** | **152/168 (90.5%)** | **16/168 (9.5%)** | **7/231 (3.03%)** | **0.930** |

V4 catches **14 more attacks than v1 for one more false flag**. Against v3 it removes nine false
flags while losing six catches. Its exact FPR is slightly above the 3% reference. Attacks passing
this classifier are detection misses; agent attack success is measured separately below.

Pool-B was excluded from this phase's tuning, but earlier full-pool v1/v3 evaluations had included
it. It is a validation slice, not a previously unmeasured external benchmark. An uncached development
repeat retained discovery **7/7**, reconnaissance **8/10**, and pool-A FPR **3.49%**. Whole-benchmark
`rep-dev` F1 is **0.927**, and **73 tests pass**. The current v4 has not been rerun on `cyber-test`,
`rep-test` or the agent-loop benchmarks. Protocol, repeats and limitations are in
[rounds K27–K34](docs/judge.md#cyber-rounds-k27k34-retain-v1-precision-with-selected-v3-defenses-2026-10-06).

For context, the historical consolidated judge's `cyber-test` run (209 attacks, 183 benign cases)
caught **87.6%** under original v1, with **2.7%** false positives; v3 caught **95.7%**, with **6.6%**
false positives. These are different cases from the v4 validation table. Run this benchmark with
`bash evals/run.sh lab cyber-test`.

### Public benchmarks (historical comparison; binary F1 on test splits)

The judge rows below use the recorded D3/C4 policies, before cyber policy v4. Direct-injection
policy tuning used the public train splits; these test splits were not used for tuning.

| Guard | BIPIA (indirect) | deepset | jackhhao | rogue-security | xTRam1 |
|---|---:|---:|---:|---:|---:|
| cyber-guard-per-policy (D3) | **0.961** | 0.519 | 0.935 | 0.694 | 0.890 |
| cyber-guard (D3) | 0.953 | 0.537 | 0.947 | 0.725 | 0.875 |
| cyber-guard-per-policy (C4, before the D rounds) | 0.966 | 0.462 | 0.943 | 0.649 | 0.714 |
| dec-luna-emu | 0.556 | **0.588** | 0.947 | **0.805** | 0.800 |
| deberta-pi-v2 | 0.378 | 0.537 | — ¶ | 0.659 | **0.924** |
| pg2-86m | 0.020 | 0.235 | 0.967 | 0.664 | 0.711 |
| s1-zeroshot | 0.139 | 0.257 | **0.982** | 0.518 | 0.835 |
| regex | 0.029 | 0.125 | 0.667 | 0.323 | 0.385 |

¶ Excluded: deberta-pi-v2 was trained on jackhhao, per its model card.

**What this shows:**

- **Indirect injection:** the luna judges dominate (BIPIA 0.95–0.96).
- **Direct injection:** rounds D1–D3 tuned on the *train* splits of these sets, raising cyber-guard-per-policy's
  mean F1 from 0.747 to 0.800 (consolidated 0.807). The judge still trails on deepset and
  rogue-security, whose remaining misses are mostly attacks only against an absent system prompt,
  or non-cyber role-play outside this lab's scope.
- **The reference classifier wins only on its own task.** deberta-pi-v2 is the best direct-injection
  detector on xTRam1 (0.924) and the fastest guard (26 ms). But it misses indirect injection (BIPIA
  0.378) and flags 17% of our benign agentic content. This matches Red Hat's finding that fixed
  classifiers win on the task they were trained for.

Guards and runs not yet done are listed in the [roadmap](#status-and-roadmap).

### Agent loops through the gateway (historical runs, 2026-10-05)

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

| Benchmark | Arm | Attack succeeded | User's task done | Agent run p50 |
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
  of attack runs, but refusing the turn also ends the user's legitimate task (75% → 6%). Returning a 200
  refusal instead of a 400 doesn't change that, because the agent stops either way. Only redacting the
  flagged tool result and letting the agent continue would. That is the next item on the roadmap.
- **False blocks on benign tasks cost 13 points** (79% → 66%). The main cause is instructions the user
  explicitly delegated ("do the tasks on my TODO list at <url>"). The tool-result check doesn't see the
  user's request, so these look like injections.
- **Post-call added 3 blocks** and no extra protection here, because pre-call stopped the attacks first.

The evaluation also found cache, fail-open logging and billing issues that were fixed. Details and
reproduction steps are in [the agent-evaluation guide](docs/agent-eval.md) and
[chargeback verification](docs/chargeback.md).

**Single-turn end to end through the LiteLLM gateway:** 45 cyber smoke cases, target gemma4:e2b,
gpt-6-luna grader.

| Arm | Attack success | Benign requests blocked by the guard | p50 |
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
| `OPENROUTER_API_KEY` | Optional. `dec-jev`: TypeSafe Jev, the hosted reference decision model, via OpenRouter. |
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
bash evals/run.sh lab rep-dev 'deberta-pi-v2|s1-zeroshot|s1-v4'
PF_CONCURRENCY=8 bash evals/run.sh lab public 'cyber-guard'   # more parallelism for API guards
```

| Mode | Cases |
|---|---|
| `rep-dev` / `rep-test` | The combined benchmark: 407 representative cases each. Tune on dev and test once. |
| `public` | Test splits of the five public benchmarks (up to 400 cases each); separate train splits support tuning. |
| `pi-dev` | Direct-injection tuning data from the public sets' train splits. |
| `tc-dev` | Tool-call tuning data (toolcall-guard-v1 `val`). |
| `cyber-dev` / `cyber-test` | Malicious cyber requests vs CyberSecEval's legitimate security work. |
| `smoke-dev` / `smoke-test` | About 100 cases each. |
| `lite-*`, `dev` / `test` | Larger cyber splits, for slow local models or full runs. |

Results go to `evals/results/lab/<mode>-<guards>.json`, which is gitignored. Repeat runs only score
new cases, because results are cached per guard version.

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
5. Freeze, then run `rep-test` and `public` once.

**Fine-tune a decision model:** follow the [training workflow](experiments/s1guard_finetune/README.md#workflow),
then score and calibrate on the development split and evaluate the frozen model on test. Record the
checkpoint, question policy and training overlap alongside the lab results.

**Local guard models** (run one at a time on a laptop):

| Guard ids | Setup |
|---|---|
| `pg2-86m`, `pg2-22m`, `sentinel-v2`, `qwen3guard-0.6b`, `qwen3guard-4b`, `shieldstral-3b` | `uv sync --all-extras`. Models load in-process from Hugging Face at pinned revisions. |
| `granite-guardian-8b` | `ollama pull granite4.1-guardian:8b` |
| `safeguard-20b` | `ollama pull gpt-oss-safeguard:20b` |
| `nemotron-cs-4b` | Needs its own venv and an HTTP shim on :8766. The commands are in [evals/lab/shims/nemotron_server.py](evals/lab/shims/nemotron_server.py). |
| `llama-guard4-12b` | Run `bash evals/lab/shims/llama_guard4.sh setup` once (24 GB download, quantized to 6.4 GB), then `... serve` (:8767). |
| `deberta-pi-v2` | `uv sync --all-extras`; loads in-process (CPU-fast). |
| `strands-decider-2b` | Run `bash evals/lab/shims/strands_decider.sh setup` once, then `... serve` (:8768, about 5 GB). Runs in its own `uvx` environment. |
| `clef-flash-9b` | Ollama 0.35.1 or later; `ollama pull clef-flash:9b` (about 10 GB). |
| `dec-luna-emu` | `uv run python -m guardlab.decisions.mock_server --port 8765 --upstream luna` |
| `s1-zeroshot`, `s1-v4` | The `laya` extra. `s1-v4` also needs the fine-tuned checkpoint from `experiments/s1guard_finetune/`, which isn't committed. |

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
      guard_id: s1-zeroshot       # choose a registered guard; requires the local Laya setup
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
- custom decision-model training, calibration and the fine-tuned `s1-v4` adapter;
- per-policy and consolidated judges, with a trajectory-aware action check and selected cyber policy v4;
- the decision-API client and its test double;
- self-hosted classifiers and decision models;
- shared gateway integration, configurable blocks and verified judge chargeback;
- placement and agent-loop studies measuring attack success and task utility;
- `agentic-security`, the drop-in guardrail for deployment (no cache; surgical withholding; verified chargeback);
- 91 offline tests.

**Roadmap** (each item is registered or scripted unless noted; runs are deferred to keep laptop load low):

*Hosted decision APIs*

- [x] Jev, tuned on dev (`jev-tuned`, [docs/jev-evaluation.md](docs/jev-evaluation.md)). With the judge's own policy
  text as questions it matches or beats the LLM judges on user messages, tool results and tool definitions, at about
  0.2 s per check; tool calls stay weaker (F1 0.878 vs 0.92). As a pre-filter it clears about half of benign traffic
  with no loss of the judge's precision.
- [ ] Jev: one held-out run of `jev-tuned` (blocked: OpenRouter credits), then a drop-in `deploy/jev-prefilter/`.
- [ ] `dec-openai`: rerun once OpenAI Decisions API access is granted (currently 403), then retire
  `dec-luna-emu` from the results.
- [ ] Optional: Perplexity's Decisions API, and Cloudflare Clef hosted on Workers AI (needs an account
  and a small path adapter).

*Self-hosted decision models*

- [ ] `clef-flash-9b`: pulled; run rep-dev/rep-test on its own (about 10 GB).
- [ ] `strands-decider-2b` on the public benchmarks (about 13 minutes at 2 requests per second).
- [ ] Kev-4B and Laya GGUF via llama.cpp. These need llama.cpp build b11371 or later; Homebrew
  stable is older.
- [ ] Intern-Decision-4B (not registered): its engine targets CUDA, and the Apple GPU is untested.
- [ ] Definition sensitivity: run each decision model with the stock questions and with the
  judge's tuned policy text as question instructions.
- [ ] Fine-tune Strands Decider 2B on our dev split (its recipe is published) and compare with s1-v4.

*Self-hosted classifiers*

- [ ] Public benchmarks for the slower local guards: Llama Guard 4, Granite Guardian, Nemotron,
  safeguard-20b, Qwen3Guard and Shieldstral.
- [ ] Watch list: Fastino GLiGuard-300M.

*LLM-as-a-judge customization and gateway experiments*

- [x] Select cyber policy v4 with measured defense/FPR tradeoffs; see [rounds K27–K34](docs/judge.md#cyber-rounds-k27k34-retain-v1-precision-with-selected-v3-defenses-2026-10-06).
- [x] Prompt-section ablations, long-content windows, trajectory-aware action checks and billed streaming blocks.
- [ ] Generalize the cyber instructions for four production gap areas: cloud-credential retrieval, operational
  exploit payloads, web-injection payloads with filter bypass, and phishing or impersonation content. Then test
  adaptive attacks.
- [ ] agentic-security: close the 3-point cyber recall gap to cyber-guard (91% vs 94% held-out). Framing-only tuning
  traded false positives for recall ([round](docs/agentic-security.md#cyber-recall-tuning-round-2026-10-07-tried-not-adopted)),
  so this needs shared-policy content changes.
- [ ] agentic-security: detect off-task drift ("autonomy hijack") in tool results; 2 of 6 still succeed, as with no guardrail.
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
  pb-rogue benchmark come from the same publisher.
- [ ] An audited list of mislabelled public rows, reported with and without them.
- [ ] Results by input length (DeBERTa reads 512 tokens per window; Llama Guard 4 fails past 4k)
  and by language.

*At work*

- [ ] A `gateway_guardrail` adapter, to score Bedrock Guardrails, Model Armor, Prisma AIRS and Lakera
  on the same corpus through LiteLLM's `/guardrails/apply_guardrail`.

**More documentation:** [docs/README.md](docs/README.md).

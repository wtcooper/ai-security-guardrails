# Plan: fine-tune a 9B (or 27B) open decision model on Modal serverless GPUs

**Goal:** see how close a self-hosted, fine-tuned open decision model can get to Jev on our cyber guardrail
questions, within a fixed GPU budget and time box. Nothing here has been run yet.

## Why, and the starting point

Same tuned question set (`jev-base`), held-out rep-test plus cyber-test, 744 checks
([size comparison](decision-model-size.md)):

| Model | Size | Training | AUROC | F1 | F1 at own calibrated threshold |
|---|---|---|---:|---:|---:|
| Jev (hosted) | large | proprietary | 0.975 | 0.930 | 0.933 |
| Clef-flash (hosted) | 9B | zero-shot on our task | 0.930 | 0.891 | 0.910 |
| Kev (hosted) | 4B | zero-shot on our task | 0.881 | 0.817 | 0.740 |

**Fine-tuning reliably helps decision models on a narrow domain:**
- Laya on typed-decisions: 0.36 to 0.77.
- Kev-4B on a support workload: 67.7% to 73.6% from about 1k examples.
- Our own Laya fine-tune `laya-tuned-0.4b-stockq`: F1 0.55 to 0.73.

A zero-shot 9B is already within about 0.02–0.04 F1 of Jev here, so a fine-tuned 9B reaching Jev parity on
our task is plausible, but not certain.

**What success would buy:**
- data never leaves your network;
- no per-call vendor fee or credit dependency;
- about 40–100 ms per check on one GPU (Clef reports 38.8 ms median on an H200);
- a model we can keep retraining on enterprise traffic.

The hosted options (Jev now, OpenAI Decisions later) already reach about 0.93 F1 at about $0.07 per 1k checks. So
the value is mostly **strategic** (residency, vendor independence, cost at very high volume), not raw accuracy.

## Which model to train

| Candidate | Training code | Effort | Notes |
|---|---|---|---|
| **Kev-9B** (Qwen3.5-9B + rank-16 LoRA + pointer head, Apache-2.0) | **Yes**: `kev.train`, a fine-tune script, `kev.serve` (`/v1/systemone`) and a Modal deploy script ([jaredpalmer/kev](https://github.com/jaredpalmer/kev)) | **Low** | **Recommended first.** Continues from the released checkpoint (`--init_from`). Same API as our Jev adapter, so evaluation is a URL change |
| Clef-flash 9B (Qwen3.5-9B + rank-256 LoRA + routing head, Apache-2.0) | **No.** Cloudflare fine-tunes it through its own engineers for now | High | Best zero-shot model here. We would write our own trainer around its head (Brier loss, as Cloudflare describes); undocumented internals are a risk |
| Kev-27B (Qwen3.8 27B base) | Yes, same repo | Low, but about 3× the GPU time | Only if 9B plateaus clearly below Jev |
| Strands Decider 2B | Yes ([GitHub](https://github.com/strands-labs), Apache-2.0) | Low | A cheap control for the effect of size |

## Data

| Source | Rows | Use |
|---|---:|---|
| `experiments/s1guard_finetune/data/train.jsonl` (cyber-scope: content-safety and harmful-compliance rows dropped) | about 7,000 of 9,019 | train |
| Corpus `pool` split | 1,035 user messages | train |
| toolcall-guard-v1 *train* split (tc-dev is its validation split) | to be measured | train: tool calls are the thin stage (294 rows) |
| Corpus `dev` (rep-dev, cyber-dev, tc-dev) | about 900 | validation, early stopping and threshold calibration |
| `rep-test`, `cyber-test`, `public` | — | **never trained on**; one final evaluation |

**Format:**
- **One Kev JSONL record per state:** the state (content plus context fields: the user's request, the agent's
  history, the system prompt), and every question of that stage from `jev-base`, including the policy-text
  questions. Each question carries a `label`.
- **Labels:** from the row's label and category, through a written category-to-question table. For example, a
  `cyber` attack sets `cyber_policy` and `cyber_offense` to true, and a benign row sets every question false.
  Labels come from our own data.
- **Distillation:** training on Jev's or GPT's scores would likely add accuracy, but needs a terms-of-use check
  first.
- **Contamination:** 326 of the 744 held-out rows were in the s1guard training set. Results are reported on the
  418 clean rows plus the public benchmarks, as for `laya-tuned-0.4b-stockq`.

## Compute and cost estimate

- **Sequence length:** a state is about 110 tokens at the median and 430 at p90. The question text is about
  1,900 tokens for user messages and 1,250 for tool calls. Kev scores all of a state's questions in one sequence,
  so a record averages about 2,000 tokens.
- **Volume:** about 7,500 records × 2,000 tokens × 2 epochs ≈ **30M training tokens**.
- **Throughput assumption:** 9B, rank-16 LoRA, bf16 with gradient checkpointing, about 2,500–4,000 tokens/s on one
  H100. That's consistent with Kev's "about 1 H100 hour" for its 4B recipe.

| Run | GPU | Time | Cost (H100 $3.95/h, H200 $4.54/h) |
|---|---|---:|---:|
| Smoke run (200 records, 1 epoch, checks the pipeline) | H100 | 0.2–0.3 h | ~$1 |
| Kev-9B full fine-tune (2 epochs) | H100 | 2–3.5 h | **$8–14** |
| Evaluation: serve on Modal, 744 held-out + 1,578 public checks | H100 | ~0.25 h | ~$1 |
| Kev-27B full fine-tune (if pursued) | H200 | 6–10 h | $27–45 |

Modal bills per second, and its free tier includes **$30 of credit per month**, which likely covers the whole
of phase 1.

## Budget and time box

- **Phase 1 (Kev-9B): hard cap $40, about 10 GPU-hours.**
  - One smoke run, two full runs (for example, with and without the long policy-text questions, or two learning
    rates), and evaluations.
  - Guard rails: a Modal workspace budget of $50 per month as a hard cap; a per-function `timeout` of 4 h on
    training and 30 min on evaluation; `min_containers=0` so the serving endpoint scales to zero.
  - Calendar: about one day of work, with most of the time in data export and evaluation.
- **Go/no-go after phase 1:**
  - Held-out F1 ≥ 0.92 with false positives ≤ 5%: worth hardening and comparing with OpenAI Decisions.
  - 0.90–0.92: try phase 2.
  - Below 0.90: stop; the hosted options win.
- **Phase 2 (only if justified): cap $80.** Either Kev-27B on an H200, or a custom trainer for Clef-flash.

## Steps

1. **Account (you):** a Modal account, `modal token new`, a workspace budget, and a Hugging Face token as a
   Modal secret.
2. **Data export (local, no GPU):** a script turns our corpus into Kev JSONL with the category-to-question
   table. It checks that no dev, test or public row leaks in.
3. **Modal app:** an image with the `kev` repo, a volume for data and checkpoints, and a `train` function on an
   H100 that runs
   `kev.train --base Qwen/Qwen3.5-9B-Base --init_from jaredpalmer/kev-9b --epochs 2 --lr 2e-5 --dtype bf16 --checkpointing 1`.
4. **Evaluate:** `kev.serve` on Modal, a scale-to-zero web endpoint. Point a `kev-tuned-9b` guard at it
   (`src/guardlab/adapters/jev.py`, same question set) and run `evals/lab/experiments/size_compare.py` plus public.
5. **Decide** with the go/no-go above, and write the results into this document.

## Open questions

- Is self-hosting a real requirement at work (residency, vendor policy)? That decides how much this is worth.
- Are training labels from Jev or GPT allowed (terms of use)? Distillation is the cheapest accuracy boost.
- Budget sign-off for phase 1 ($40 cap).

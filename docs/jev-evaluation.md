# Jev for runtime protection: evaluation (2026-10-07/08)

**Question:** how good is TypeSafe Jev (`typesafe/jev-1.13` via OpenRouter, a hosted decision model) as a cyber
runtime guardrail, and what is the best quality tuning and configuration can get out of it?

Jev answers typed questions about a state (here: yes/no "noul" questions) with a probability per question, in one
fast call. It does not generate text, so tuning means choosing the questions, their wording, the context fields
and the thresholds. The model itself can't be changed.

## Success criteria (set before running)

The reference is `agentic-security`, the deployable LLM judge, and its frozen v3 lab results.

**A. Standalone guardrail, replacing the judge.** All of the following on held-out data, run once after tuning on dev:

| Metric | Bar | agentic-security |
|---|---|---|
| rep-test F1 / FPR | ≥ 0.90 / ≤ 5% | 0.93 / 4% |
| cyber-test F1 / FPR | ≥ 0.90 / ≤ 5% | 0.93 / 6% |
| public benchmarks F1 | ≥ 0.84 | 0.87 |
| tool calls (tc-dev) F1 | ≥ 0.90 | 0.92 |
| latency per check, p50 / p95 | ≤ 0.6 s / ≤ 1.5 s | about 0.9 s / 3.5 s |
| cost per 1k checks | ≤ the judge's | $0.04–0.07 |

**B. Fast first-pass filter in front of the judge (cascade).** Jev's score routes each check:
- below a low threshold: allow;
- above a high threshold: block;
- in between: ask the judge.

The bar, on held-out data:
- cascade F1 is within 0.01 of the judge alone;
- false positives are no higher;
- at least 50% of checks are answered by Jev alone, so need no judge call.

**C. Usefulness of the score.** AUROC ≥ 0.93, so a threshold can trade recall against false positives.

**Verdict rules:**
- *applicable as a standalone guardrail* if A holds;
- *applicable as a pre-filter* if B holds;
- otherwise *not applicable yet*, with the gap named.

**Method:**
- Tuning uses dev slices only (rep-dev, cyber-dev, tc-dev). Every round is logged below.
- The frozen configuration runs once on rep-test, cyber-test and public.
- Report case ids and numbers only, never attack text.

## Status and verdict (2026-10-08)

**Jev is applicable.** Tuned, it matches or beats both LLM judges on held-out data at about a quarter of their latency.

- **Best role: a pre-filter in front of the judge.** It answers 78–87% of legitimate checks on its own, with the
  judge's held-out quality unchanged. That passes criterion B.
- **Standalone:** it meets the F1 and latency bars, but its false-positive rate is above the 5% bar on cyber-test
  (7%) and public (9%). So criterion A holds only where some extra false positives are acceptable.

Tuning used dev only (rounds J0–J8). The frozen configuration ran once on held-out. The total Jev spend was well
under $1.

## How it is set up

[`JevGuard`](../src/guardlab/adapters/jev.py) is a decision-model guardrail in its deployable shape: **one Jev call
per check**. Questions are set per stage in a YAML file
([final configuration](../src/guardlab/decisions/policies/jev/tuned.yaml)):
- **Context:** the state carries the content plus the user's request and the agent's earlier steps when known.
- **Policy questions:** a question can be `policy: <name>`, which gives Jev the LLM judge's own tuned policy text as
  the question, loaded at run time from [src/guardlab/judge/policies/](../src/guardlab/judge/policies/).
- **Cost:** each check records the provider-reported cost.

The out-of-box battery (`jev-base-stockq`, about 2 calls per tool-call check) stays registered for comparison.

## Rounds (dev only)

Each cell is caught / legitimate flagged / F1, with AUROC in brackets.

| Round | Change | rep-dev | cyber-dev | tool calls (tc-dev) |
|---|---|---|---|---|
| J0 | Out-of-box battery (`jev-base-stockq`) | 90% / 7% / 0.92 (0.954) | 88% / 4% / 0.92 (0.960) | 75% / 23% / 0.80 (0.842) |
| J1 | Same questions, one call per check | 90% / 9.4% / 0.911 | 88% / 3.7% / 0.919 | 76% / 28% / 0.793 |
| J2 | Tool calls: authorization-aware questions, with the user's request and the agent's history | 90% / **2.2%** / 0.938 | 89% / 3.7% / 0.925 | 79% / **8.1%** / 0.858 (0.931) |
| J3 | User messages: the judge's cyber and injection policies as questions. Tool calls: an off-task question | 92% / 3.3% / 0.946 | **96% / 3.7% / 0.964** (0.979) | 81% / 12.8% / 0.858 |
| J4 | Drop off-task. Add the judge's action policy for tool calls and its indirect-injection policy for tool results | 92% / 4.4% / 0.941 | 96% / 3.7% / 0.964 | 82% / 9.3% / 0.875 (0.942) |
| **J5** | Drop the indirect-injection policy question (it added 4 false flags on tool results) | **91% / 2.2% / 0.945** (0.969) | **96% / 3.7% / 0.964** (0.978) | **82% / 8.1% / 0.878** (0.940) |
| J6 | Injection-policy threshold 0.3: on dev scores, +2 attacks and no new false flags | 92% / 2.2% / 0.950 | 96% / 3.7% / 0.964 | 82% / 9.3% / 0.875 |
| J7 | Tool calls: the app's system prompt (its rules) added as context | 93% / 2.8% / 0.950 | 96% / 3.7% / 0.964 | **88% / 8.1% / 0.912** (0.950) |
| **J8 = `jev-base`** | J7 without the exfiltration question (it added nothing; checked offline) | **93% / 2.2% / 0.952** (0.973) | **96% / 3.7% / 0.964** (0.978) | 86% / 8.1% / 0.901 (0.949) |

**What mattered:**
- **The judge's own policy text as a Jev question** was the biggest single gain. cyber-dev went from 89% to 96% caught
  with no new false flags. Jev applies a long, nuanced policy well, so the tuning done for the LLM judge carries over.
- **Authorization-aware tool-call questions** ("risky and not asked for", "details planted by a tool result", the
  judge's action policy, given the user's request and the agent's history) cut legitimate tool calls flagged from 28%
  to 8%. Context-free questions ("would this delete or send data?") flag ordinary requested actions.
- **What didn't work:** an "off-task" question and the indirect-injection policy text both added false flags. Lower
  tool-call thresholds traded recall for false flags (at 0.3: 86% caught, 16% flagged).
- **The app's system prompt as tool-call context** (J7) raised tool calls from 82% to 88% caught with no new false
  flags. Its rules ("never send data externally") define what a call may do, as for the judges.
- **What isn't a lever:** different combining rules or per-question thresholds for tool calls didn't improve both
  tool-call sets. The "latest" model alias is the same model (`jev-1.13-20260917`).
- **One call per check** halved tool-call latency against the battery's two calls (426 to 223 ms p50).

## Held-out results (`jev-base`, one run)

Each cell is caught / legitimate flagged / F1, with AUROC in brackets.

| Slice | **Jev, tuned** | Jev, out of box | cyber-guard | agentic-security |
|---|---|---|---|---|
| rep-test | **89% / 2% / 0.94** (0.977) | 88% / 8% / 0.90 (0.960) | 88% / 4% / 0.92 | 89% / 4% / 0.93 |
| cyber-test | 93% / 7% / **0.94** (0.979) | 90% / 7% / 0.92 | 94% / 4% / 0.95 | 91% / 6% / 0.93 |
| public benchmarks | 88% / 9% / **0.88** (0.960) | 85% / 9% / 0.87 | 77% / 2% / 0.86 | 79% / 2% / 0.87 |
| latency p50 / p95 | **229 / 307 ms** | 242 / 496 ms | 808 / 3,328 ms | ~900 / 3,500 ms |
| cost per 1k checks | $0.06–0.09 | $0.03 | $0.05–0.06 | $0.05–0.07 |

**By stage on rep-test** (F1): user messages 0.94 (judges 0.94 / 0.93), tool results 0.92 (0.90 / 0.92), tool
definitions 1.00 (all), **tool calls 0.90 (both judges 0.85)**, replies 0.97 (cyber-guard 0.90).

### Against the criteria

| Criterion | Bar | Held-out | Met? |
|---|---|---|---|
| A: rep F1 / FPR | ≥ 0.90 / ≤ 5% | 0.94 / 2% | yes |
| A: cyber F1 / FPR | ≥ 0.90 / ≤ 5% | 0.94 / **7%** | F1 yes, **FPR no** |
| A: public F1 | ≥ 0.84 | 0.88 (FPR 9%) | yes |
| A: tool calls F1 | ≥ 0.90 | 0.90 on rep-test (0.90 on tc-dev) | yes (borderline) |
| A: latency p50 / p95 | ≤ 0.6 / ≤ 1.5 s | 0.23 / 0.31 s | yes |
| A: cost per 1k | ≤ judge | $0.06–0.09 vs $0.05–0.07 | about equal |
| B: cascade | F1 within 0.01, FP no higher, ≥ 50% answered by Jev | below | **yes** |
| C: AUROC | ≥ 0.93 | 0.977 / 0.979 / 0.960 | yes |

### Cascade: Jev clears, the judge decides the rest

The threshold was chosen on dev only: the largest that kept the judge's dev F1 and false positives. That gives
"clear below 0.27". It was then applied unchanged to held-out ([script](../evals/lab/experiments/jev_cascade.py)).
Plain replies are excluded, since agentic-security doesn't screen them.

| Held-out slice | Judge alone (caught / flagged / F1) | Jev clears < 0.27, judge decides rest | Legit checks Jev answers alone |
|---|---|---|---:|
| rep-test | 88.7% / 4.2% / 0.925 | 88.1% / **2.1%** / **0.929** | 83% |
| cyber-test | 90.9% / 6.0% / 0.927 | 90.0% / **5.5%** / 0.924 | 87% |
| public | 74.2% / 2.7% / 0.835 | 73.4% / 2.7% / 0.830 | 78% |

- **The judge's quality holds:** F1 stays within 0.005 and false positives never rise. They fall on rep-test and
  cyber-test.
- **Jev answers 78–87% of legitimate checks by itself.** These slices are 40–60% attacks, so it answers 38–47% of
  *all* their checks. Real traffic is overwhelmingly legitimate, so in practice most judge calls, with their 1–3 s
  latency and cost, disappear.
- **Letting Jev also block** (score ≥ 0.5) raises F1 further (0.941–0.947) but adds false positives on cyber-test and
  public.

## Verdict

- **Jev is applicable to runtime protection.** Tuned with the judge's own policies as questions and the right
  context per stage, it matches or beats both LLM judges on held-out F1 at about 0.23 s per check.
- **Recommended role: a pre-filter in front of agentic-security,** clearing checks that score below 0.27. It
  removes most judge calls on legitimate traffic and keeps the judge's precision.
- **Standalone use** (no judge) gives higher recall but more false positives on cyber requests and public
  injection sets (7–9% vs 2–6%).
- **Deployment caveats:**
  - Jev is a third-party hosted model via OpenRouter, a vendor and data-residency question for an enterprise.
  - OpenRouter credits and limits are a hard dependency; the overnight run stopped on credits.
  - A drop-in LiteLLM guardrail for the pre-filter isn't built yet.

## Next

1. **Build the pre-filter as a drop-in:** `deploy/jev-prefilter/`, or a Jev stage inside agentic-security. Jev clears
   checks scoring below 0.27, and the judge decides the rest. It would be stateless, like agentic-security.
2. **Agent-loop test of the cascade:** run the four-arm agent eval with the pre-filter in front of agentic-security,
   to measure task success and latency per step.
3. **Self-hosted alternative:** run the same question set on self-hosted decision models (Laya, our fine-tuned
   `laya-tuned-0.4b-stockq`, Clef-flash 9B) through the same adapter.

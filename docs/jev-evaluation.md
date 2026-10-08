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

## Status (2026-10-08 morning)

**Tuning is done; the held-out run is blocked.** After 4,844 checks ($0.24 in total), OpenRouter returned HTTP 402,
"Insufficient credits. This account never purchased credits." The free starting allowance is used up, and no calls
were made after that.

The frozen configuration (`jev-tuned`) has **not** had its one held-out run, so everything below is from dev data
and the verdict is preliminary. The held-out run needs about 2,400 checks, roughly $0.20 at the measured price
(steps under "Next" at the end).

## How it is set up

[`JevGuard`](../src/guardlab/adapters/jev.py) is a decision-model guardrail in its deployable shape: **one Jev call
per check**. Questions are set per stage in a YAML file
([final configuration](../src/guardlab/decisions/policies/jev/tuned.yaml)):
- **Context:** the state carries the content plus the user's request and the agent's earlier steps when known.
- **Policy questions:** a question can be `policy: <name>`, which gives Jev the LLM judge's own tuned policy text as
  the question, loaded at run time from [src/guardlab/judge/policies/](../src/guardlab/judge/policies/).
- **Cost:** each check records the provider-reported cost.

The out-of-box battery (`dec-jev`, about 2 calls per tool-call check) stays registered for comparison.

## Rounds (dev only)

Each cell is caught / legitimate flagged / F1, with AUROC in brackets.

| Round | Change | rep-dev | cyber-dev | tool calls (tc-dev) |
|---|---|---|---|---|
| J0 | Out-of-box battery (`dec-jev`) | 90% / 7% / 0.92 (0.954) | 88% / 4% / 0.92 (0.960) | 75% / 23% / 0.80 (0.842) |
| J1 | Same questions, one call per check | 90% / 9.4% / 0.911 | 88% / 3.7% / 0.919 | 76% / 28% / 0.793 |
| J2 | Tool calls: authorization-aware questions, with the user's request and the agent's history | 90% / **2.2%** / 0.938 | 89% / 3.7% / 0.925 | 79% / **8.1%** / 0.858 (0.931) |
| J3 | User messages: the judge's cyber and injection policies as questions. Tool calls: an off-task question | 92% / 3.3% / 0.946 | **96% / 3.7% / 0.964** (0.979) | 81% / 12.8% / 0.858 |
| J4 | Drop off-task. Add the judge's action policy for tool calls and its indirect-injection policy for tool results | 92% / 4.4% / 0.941 | 96% / 3.7% / 0.964 | 82% / 9.3% / 0.875 (0.942) |
| **J5** | Drop the indirect-injection policy question (it added 4 false flags on tool results) | **91% / 2.2% / 0.945** (0.969) | **96% / 3.7% / 0.964** (0.978) | **82% / 8.1% / 0.878** (0.940) |
| J6 = `jev-tuned` | Injection-policy threshold 0.3: on dev scores, +2 attacks and no new false flags | not re-run (402) | | |

**What mattered:**
- **The judge's own policy text as a Jev question** was the biggest single gain. cyber-dev went from 89% to 96% caught
  with no new false flags. Jev applies a long, nuanced policy well, so the tuning done for the LLM judge carries over.
- **Authorization-aware tool-call questions** ("risky and not asked for", "details planted by a tool result", the
  judge's action policy, given the user's request and the agent's history) cut legitimate tool calls flagged from 28%
  to 8%. Context-free questions ("would this delete or send data?") flag ordinary requested actions.
- **What didn't work:** an "off-task" question and the indirect-injection policy text both added false flags. Lower
  tool-call thresholds traded recall for false flags (at 0.3: 86% caught, 16% flagged).
- **One call per check** halved tool-call latency against the battery's two calls (426 to 223 ms p50).

## Results against the criteria (dev; preliminary)

**Speed and cost:**
- **Jev J5 latency per check:** p50 213 ms, p90 267, p95 296, p99 816, worst 1.1 s (804 checks). That's about 4×
  faster than the judge at the median and 12× at p95 (the judge: about 0.9–1.2 s p50, 3.5 s p95).
- **Cost:** $0.072 per 1,000 checks. The policy questions add input tokens; the stock battery costs $0.026.

| Criterion | Bar | Jev (J5, dev) | Met? |
|---|---|---|---|
| A: rep F1 / FPR | ≥ 0.90 / ≤ 5% | 0.945 / 2.2% | yes (dev) |
| A: cyber F1 / FPR | ≥ 0.90 / ≤ 5% | 0.964 / 3.7% | yes (dev) |
| A: tool calls F1 | ≥ 0.90 | 0.878 | **no** (judge 0.92) |
| A: public F1 | ≥ 0.84 | not run (402) | — |
| A: latency p50 / p95 | ≤ 0.6 s / ≤ 1.5 s | 0.21 / 0.30 s | yes |
| A: cost per 1k | ≤ judge ($0.04–0.07) | $0.072 | borderline |
| B: cascade | F1 within 0.01, FP no higher, ≥ 50% answered by Jev | see below | yes on dev, for clearing benign traffic |
| C: AUROC | ≥ 0.93 | 0.969 / 0.978 / 0.940 | yes |

**Cascade on dev** (742 cases scored by both Jev J5 and agentic-security; plain replies excluded):

| Design | Caught | Flagged | F1 | Judge calls avoided |
|---|---:|---:|---:|---:|
| agentic-security alone | 88.2% | 2.9% | 0.927 | — |
| Jev J5 alone | 88.9% | 4.2% | 0.926 | 100% |
| **Jev clears below 0.15, judge decides the rest** | 88.0% | **2.9%** | **0.926** | 22% of this attack-heavy mix; **50% of legitimate traffic** |
| Jev clears below 0.20, judge decides the rest | 87.7% | 2.9% | 0.924 | 30%; 69% of legitimate traffic |
| Jev blocks at 0.5 or above, clears below 0.1, judge in between | 93.8% | 5.8% | 0.947 | 65% |

The filter-only design keeps the judge's precision exactly. Real traffic is mostly benign, so clearing 50–69% of
legitimate checks means about half the judge calls, with their 1–3 s latency, disappear. Letting Jev also *block*
raises recall and F1 but adds false flags, which fails criterion B. The cascade thresholds were picked on the same
dev data, so held-out confirmation is needed.

## Preliminary verdict

- **Jev is applicable to runtime protection,** in two roles:
  1. **As a fast pre-filter in front of the judge:** it clears about half of legitimate traffic in about 0.2 s, with
     no loss of the judge's precision. This is the strongest, lowest-risk use.
  2. **As the standalone request-side check** (user messages, tool results, tool definitions): there it matched or
     beat the LLM judges on dev at about 4× lower latency. Tool calls (post-call) should stay with the judge: Jev's
     0.878 vs 0.92 is the one real gap, and it isn't closable by thresholds.
- **Deployment caveats:**
  - Jev is a third-party hosted model via OpenRouter, a vendor and data-residency question for your enterprise.
  - OpenRouter credits and limits are a hard dependency: this run stopped on credits.
  - It would need a drop-in LiteLLM guardrail of its own, like agentic-security; none exists yet.

## Next (morning)

1. **Add OpenRouter credits.** About $5 covers the held-out suite many times over.
2. **Run the frozen configuration once on held-out, next to the out-of-box battery and cyber-guard:**
   `bash evals/run.sh lab rep-test '^(cyber-guard|dec-jev|jev-tuned)$'`, then the same for `cyber-test` and
   `public`. Confirm the cascade on held-out using the same thresholds.
3. **If it holds,** build `deploy/jev-prefilter/`: a drop-in pre-call guardrail that clears low-score checks and
   hands the rest to agentic-security. It would be stateless, like agentic-security.

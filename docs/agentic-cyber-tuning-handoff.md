# Handoff: raise agentic-security's catch rate on malicious cyber requests

**For:** an AI agent (or engineer) taking over cyber-policy tuning for `agentic-security`.

**Status:** 2026-10-10. Measurement tools are ready; rounds that change only the wrapper or settings are exhausted
(§4). The policy wording is the open part.

**Why this is handed off:** the previous agent (Claude) could run and measure everything below, but its own safety
system stopped it while it was drafting new policy criteria that describe kinds of offensive tooling. You write the
candidate wording; the harness here measures it. Keep the wording at the category level (see
[Rules for the wording](#rules-for-the-wording)).

## 1. The goal

`agentic-security` is the deployable LLM-as-a-judge guardrail. It catches fewer malicious cyber requests than the
lab judge `cyber-guard`, even though both read the **same policy text**:

| On the held-out cyber requests (239 cases) | Caught | Legitimate flagged |
|---|---:|---:|
| `cyber-guard` | 89.6% | 5.3% |
| **`agentic-security`** | **86.5%** | 5.3% |

The same gap shows on the validation slice: pool B, 168 attacks and 231 legitimate requests.

| On pool B | Caught | Legitimate flagged | F1 |
|---|---:|---:|---:|
| `cyber-guard` (policy v4) | 152 (90.5%) | 7 (3.0%) | 0.930 |
| `agentic-security` | 146 (86.9%) | 5 (2.2%) | 0.915 |

**Target:**
- Catch at least as many as `cyber-guard` (about 90% on pool B).
- Flag no more legitimate requests than today (3% or less on pool B).
- **F1 must rise.** Trading false positives for catches doesn't count.

## 2. What the judge sees, and where the policy text lives

- **The guard:** [deploy/agentic-security/agentic_security.py](../deploy/agentic-security/agentic_security.py).
  One judge call (gpt-6-luna) before the model runs rates each new user message and each tool result: a digit from
  0 to 9.
  - 7–9 is flagged.
  - 0–3 passes.
  - 4–6 goes to a second "review" call that reasons briefly and decides.
- **The prompt it uses:** [prompts/request.md](../deploy/agentic-security/prompts/request.md). It is **generated** by
  [evals/lab/build_agentic.py](../evals/lab/build_agentic.py):
  - a header (task framing, delegation and drift rules, answer format);
  - section 1, prompt injection;
  - section 2, malicious cyber requests;
  - section 3, indirect injection.

  The sections are copied from the shared policy files, **with each policy's Examples section left out**.
- **The cyber policy:** [src/guardlab/judge/policies/cyber.md](../src/guardlab/judge/policies/cyber.md), v4, 292
  words. It is short and has no Definitions section, and its four examples are deliberately abstract.
- **The policy file is shared.** It also feeds:
  - `cyber-guard`, through `evals/lab/build_consolidated.py`;
  - `safeguard-20b` (gpt-oss-safeguard);
  - the `policy: cyber` question in Jev's tuned question set.

  Editing it changes all of them. That's fine if the change is an improvement, but they then need re-checking (§5,
  step 6).

## 3. Where the misses are

From the latest baseline run on the tuning slices (dev + pool A), attacks the judge let through, by the dataset's own
tactic tag. Most were rated a **confident 0**, not a borderline 4–6:

| Tag (corpus `family`) | Missed | Tag | Missed |
|---|---:|---|---:|
| collection | 8 | interpreter_container_escape | 2 |
| discovery | 6 | evasion | 2 |
| direct_harmful | 5 | m2s_actor | 2 |
| recon | 3 | persistence | 2 |
| execution | 3 | one each: interpreter_post_exploitation, c2, interpreter_reflected_attack, exfil, m2s_pythonize, m2s_numberize | 6 |

**What the tags mean:**
- MITRE ATT&CK tactic names come from CyberSecEval-MITRE.
- `interpreter_*` rows come from CyberSecEval's interpreter set: requests aimed at the AI's own code-execution
  environment.
- `m2s_*` are multi-turn attacks rewritten into one message in another form (as code, a numbered list, an actor
  script and so on).

To read the actual misses, open the round file (it lists `fn_ids` and `fp_ids`) and look the IDs up in
`evals/lab/data/cases.jsonl`. **Don't paste attack text into docs, commits or logs;** refer to cases by ID.

**Why the confident 0s matter:** settings changes such as review bands can't rescue them. The gap is either the
policy's coverage or the prompt wrapper. `cyber-guard` reads the same policy and does better, which points partly at
the wrapper. Its header asks the judge to check one piece of content against every risk and "rate the most severe
violation"; `agentic-security`'s header is longer and agent-oriented.

## 4. What has already been tried

| Round | Change | Result |
|---|---|---|
| Cyber rounds K1–K34 (for `cyber-guard`, [judge.md](judge.md)) | Policy rewrites v1 → v3 → v4 | v3 caught the most, but with about twice the false positives; v4 was adopted for precision |
| agentic-security round 1 (2026-10-07, [agentic-security.md](agentic-security.md)) | Framing only: "rate the most severe violation" (`maxsev`), policy-vocabulary entry labels (`typed`) | Within noise: recall up 1–2 points, false positives up 1–2 points, F1 flat. Rejected |
| agentic-security round 2 (2026-10-10, [results](agentic-security.md#cyber-recall-tuning-round-2-2026-10-10-no-new-policy-text-nothing-adopted)) | `examples` (put the cyber Examples back), `lean` (diagnostic: drop the delegation/drift preamble), `rb26` (review band 2–6 for user messages), `rbmed` (review at medium effort) | Nothing adopted. Examples hurt (−16 caught). The preamble isn't the cause (+1, noise). Settings flat. **The gap is in the policy wording: that's your job.** Same-session baseline on dev + pool A: 292/336 caught, 14/336 flagged, F1 0.910 |

**Noise:** identical runs of the same prompt move by about ±2 points (4 attacks and 3 false flags on pool A). Run
the baseline again in the same session as every variant, and replicate anything that looks like a win.

## 5. How to tune (the exact loop)

**Setup:**
- Python through `uv run`.
- `.env` must hold `OPENAI_API_KEY` (judge model `gpt-6-luna`; use no other OpenAI model).
- Each run of one variant over dev + pool A is about 670 judge calls and costs a few cents.
- Don't run tuning while an agent-loop eval is running: they share the API rate limit, and rate-limited checks fail
  open.

**1. Write a variant.** Choose one of two routes:

- **(a) Agentic-only (recommended first):**
  - Add a branch to `variant()` in
    [evals/lab/experiments/agentic_tune.py](../evals/lab/experiments/agentic_tune.py). It returns (prompt text,
    entry-label map, judge settings), starting from the shipped `request.md` text (`BASE`).
  - Change one thing per variant, for example the header framing, or added wording in the section 2 Criteria.
  - The shared policy file and `cyber-guard` stay untouched.
- **(b) Shared policy:**
  - Copy `src/guardlab/judge/policies/cyber.md` and edit it as v5: bump `version:` in the frontmatter, keeping the
    Instruction / Criteria / Examples layout.
  - Run `uv run python evals/lab/build_agentic.py` and `uv run python evals/lab/build_consolidated.py`.
  - Score `agentic-security` with the `base` variant, which reads the rebuilt prompt, and `cyber-guard` with
    `uv run python evals/lab/experiments/cyber_tune.py <label> --slices dev,poolA`.

**2. Score on the tuning slices**, always with a fresh baseline in the same run:

```bash
uv run python evals/lab/experiments/agentic_tune.py base,<your-variant> --slices dev,poolA
```

It prints per slice: attacks caught, legitimate flagged, F1 and errors. It saves the IDs of every miss and false
flag, plus the missed-tag counts, to `evals/results/lab/rounds/agentic-tune-*.json`. It never prints prompt text.

**3. Accept or reject on the tuning slices.** On dev + pool A combined, the variant must catch more attacks than the
same-run baseline and flag **no more** legitimate requests. Replicate once; keep it only if both runs agree.

**4. Validate once on pool B.** Pool B is never looked at while tuning.

```bash
uv run python evals/lab/experiments/agentic_tune.py base,<your-variant> --slices poolB
```

The same rule applies: more caught, no more flagged, F1 up. If pool B disagrees, reject. Don't tune on pool B.

**5. Adopt it in the deployable prompt.**
- **Route (a):** move the change into the generator (`evals/lab/build_agentic.py`) so `request.md` is rebuilt rather
  than hand-edited.
- **Route (b):** commit the new `cyber.md` v5 and both rebuilt prompt sets.
- Then run `uv run pytest -q` (102 tests should pass).

**6. One held-out run.** This is the final confirmation, not a tuning step.

```bash
uv run python evals/lab/experiments/held_out.py --run agentic-security
uv run python evals/lab/experiments/held_out.py --report agentic-security,cyber-guard
```

- Compare with today's `agentic-security`: 0.91 (95% interval 0.88–0.93) on the cyber & agent test set, 0.86
  public; 86.5% of cyber requests caught.
- On route (b), also rerun `cyber-guard`, `safeguard-20b` and `jev-base`, since they share the policy.
- Then regenerate the README table with `uv run python evals/lab/experiments/comparison_table.py` and paste it into
  the README's full comparison.

**7. Record the round** in [agentic-security.md](agentic-security.md): a table of variant, caught, flagged and F1
per slice, plus the decision. Cite case IDs, never case text.

## Rules for the wording

- **Cyber scope only.** No content-safety, bio or chem material. Never send such prompts to the OpenAI API.
- **Category level.** Describe what makes a request malicious in terms of intent, authorization, target and
  capability handed over, using MITRE ATT&CK tactic names where useful. No step-by-step techniques, commands,
  payloads or working code, in the policy or its examples. The current examples ("Automate profiling targets for an
  intrusion.") show the level of abstraction.
- **Keep the legitimate side explicit.** Defensive work, administration of one's own systems, education and
  explicitly authorized testing must keep passing. Every new "violates" line needs a matching thought about what it
  might wrongly catch. False positives are the reason v3 was replaced.
- **Keep it short.** The prompt is resent on every judge call, so every word costs latency and money.

## What not to do

- Don't tune on, or look at, the held-out test sets (`rep-test`, `cyber-test`, the public benchmarks, or the
  combined cyber & agent set). Run them once at the end.
- Don't change the guard's code (`agentic_security.py`) for this; prompt and settings only.
- Don't hand-edit `deploy/agentic-security/prompts/*.md` or `src/guardlab/judge/consolidated/*.md`; they're generated.
- Don't commit `.env` or anything under `evals/lab/data/` (gitignored).

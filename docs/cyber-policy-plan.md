# Plan: harden `cyber.md` (the malicious-cyber-request policy)

**The job.** Rewrite one file, [`src/guardlab/judge/policies/cyber.md`](../src/guardlab/judge/policies/cyber.md),
so the guardrail catches offensive **reconnaissance** and **discovery** requests it currently rates as
harmless, without flagging more legitimate security work. Everything else in this repo stays as it is.

This is a **classification policy**, not security content: it tells a judge model how to decide, in terms
of intent, authorization and framing. See [Constraints](#constraints) — it must contain no attack
techniques, tool names, commands or procedures, and a writer who adds them will likely be stopped by
their own safety filter (that is what happened to the previous attempt, and why this spec exists).

## 1. Where this file sits

`cyber-guard` is an LLM-as-a-judge guardrail on a LiteLLM gateway. On every request it runs one
gpt-6-luna call with the **pre-call** instruction set, which is three policies concatenated:

| Section | Source file | Judges |
|---|---|---|
| 1 | `policies/injection.md` (950 words) | prompt injection, jailbreak, secret extraction |
| **2** | **`policies/cyber.md` (243 words) — the file to rewrite** | **malicious cyber requests** |
| 3 | `policies/indirect_injection.md` (645 words) | instructions hidden in tool output |
| appended | `judge/common.md` (143 words) | rules that apply to every check |

The judge answers with **one digit, 0–9**: 7 or more blocks, 3 or less allows, and 4–6 escalates to a
short reasoning review that decides. So the policy's job is to make the model *rate* the right things
highly; it never writes prose to the user.

The shipped prompt is generated from these files by
[`evals/lab/build_consolidated.py`](../evals/lab/build_consolidated.py), which also drops each policy's
`## Examples` section (measured as worth nothing — [docs/judge.md](judge.md), round S1).

## 2. The measured gap

On the `cyber-dev` slice (110 offensive requests vs 107 legitimate-security-work prompts) the current
policy catches **90%** at **2%** false flags. The misses are not spread out:

| Category (MITRE tactic or CyberSecEval class) | Caught | Status |
|---|---:|---|
| **Discovery** — enumerating an environment from inside it | **4/7 (57%)** | **primary target** |
| **Reconnaissance** — profiling a target from outside | **6/10 (60%)** | **primary target** |
| Defense evasion | 5/6 (83%) | secondary |
| Collection | 4/5 (80%) | secondary |
| Container escape (CyberSecEval Interpreter) | 3/4 (75%) | secondary |
| Jailbreak-rewrapped cyber requests | 20/21 (95%) | fine |
| Execution, persistence, privilege escalation, lateral movement, C2, exfiltration | 100% | fine |
| Direct harmful cyber requests (AdvBench subset) | 16/16 (100%) | fine |

**Two facts that determine the fix:**

1. **The judge rates 10 of the 11 missed requests a flat `0`** — not 4, not 6. They never reach the
   reasoning review, and no change to `block_at` or the review band can reach them. The policy text is
   the only lever.
2. **False flags are at 2–3%, so there is headroom to tighten.** A rewrite may spend some of that, up to
   the limit in [§5](#5-acceptance-criteria). Being stricter is allowed; being vague is not.

**Why these two tactics are missed.** The missed requests share a shape, and the policy has no rule that
reaches it:

- They are **framed as software engineering** — build a tool, write a script, design an algorithm — so
  they read as a development task rather than a request for attack capability.
- They **name ordinary administrative and networking utilities**, the same ones legitimate operators use,
  so nothing in the wording looks hostile.
- The **target is unstated or implicitly someone else's**: the request never says the systems belong to
  the user or that testing is authorized.
- The requested capability is **enumeration and mapping** rather than intrusion or damage, which the
  current policy's "Criteria" implicitly treats as benign because it emphasises *functional,
  ready-to-use offensive capability* and *obtaining credentials or data*.

The current policy therefore reads reconnaissance and discovery as out of its own scope. It also, unlike
every other policy in the set, has **no `## Definitions` section** — and the ablation in round S1 measured
Definitions as worth about 5 recall points across the prompt. That is the main structural gap.

## 3. What the new policy must do

Write rules, in the policy's own vocabulary, that cause the judge to rate highly:

1. **Every stage of an intrusion, named as such.** The policy should make explicit that offensive activity
   covers the full MITRE ATT&CK lifecycle — reconnaissance and discovery included — and not only the
   stages that cause direct damage. Naming the tactics at the level of the public MITRE taxonomy
   (reconnaissance, discovery, collection, defense evasion, and so on) is both sufficient and the
   expected level of detail.
2. **Capability judged by what it does, not how it is framed.** A request to design, build, script or
   automate something is judged by the capability the answer would hand over. "Design a tool that…",
   "write a script that…" and "for research / a demo / hypothetically" must not lower the rating.
3. **Dual-use utilities judged by purpose and scope.** The same utility can serve an administrator or an
   intruder. The discriminator the policy should give the judge is **authorization and scope**: does the
   request concern systems the user states they own, administer or are authorized to test, or does it
   concern unspecified or third-party targets? Absence of any ownership or authorization signal, combined
   with an enumeration-of-targets goal, should push the rating up.
4. **A `## Definitions` section**, matching the other policies' style, that defines the offensive-activity
   classes in one line each — at tactic level, in terms of the attacker's *goal*.

Keep and sharpen what already works: the existing "does not violate" list is why false flags are at 2%,
and the 107 legitimate-security-work prompts it protects are detection engineering, hardening, incident
response, secure coding, security education and administering one's own systems.

**Format contract** (the build and the tests depend on it):

```markdown
---
id: cyber
version: 2          # bump from 1
stages: [input, conversation]
category: cyber
---
# Policy: malicious cyber requests (user message to an AI assistant)

## Instruction      <- one paragraph: what to decide
## Definitions      <- NEW: the offensive-activity classes, one line each, goal-level
## Criteria         <- "Violates (high score):" then "Does not violate (low score):" bullets
## Examples         <- kept for human readers; dropped from the shipped prompt
```

**Budget: 400–600 words** (currently 243). The other policies run 365–950 words, and the pre-call prompt
is 1,524 words today; staying inside this budget keeps it near its previous size. Do not grow the other
policies.

## 4. Constraints

- **No offensive technique content.** No command lines, code, tool or utility names, payloads,
  procedures, step lists, or "how an attacker would" explanations. Everything stays at the level of
  intent, goal and authorization. This is both a safety requirement and a design one: the judge needs
  decision rules, and technique catalogues would bloat the prompt without improving classification.
- **No text copied from the evaluation corpus.** `tests/test_judge.py::test_judge_policies_do_not_copy_eval_text`
  fails if any policy line reuses more than half of an 8-word shingle from a dev or test case. Examples
  must be written from scratch and kept short and synthetic.
- **Do not tune on the test split.** Iterate on `cyber-dev` and `rep-dev` only. `cyber-test` is run once,
  after freezing.
- **One file.** Do not edit the other policies, `common.md`, the adapter, or the registry. If the work
  seems to need a change elsewhere, stop and report it instead.

## 5. Acceptance criteria

Measured on `cyber-dev` (tuning) and `rep-dev` (regression). The run-to-run noise floor is **±0.02 F1**,
so changes smaller than that do not count.

| # | Criterion | Now | Target |
|---|---|---:|---:|
| 1 | `cyber-dev` recall | 90% | **≥ 95%** |
| 2 | `cyber-dev` false flags on legitimate security work | 2% | **≤ 5%** |
| 3 | `cyber-dev` F1 | 0.94 | **≥ 0.95** |
| 4 | Discovery caught | 4/7 | **≥ 6/7** |
| 5 | Reconnaissance caught | 6/10 | **≥ 9/10** |
| 6 | `rep-dev` F1 (no regression elsewhere) | 0.92 | **≥ 0.90** |
| 7 | Prompt injection and indirect injection caught on `rep-dev` | 72% / 95% | within 3 points |

Then, and only then: freeze, and run `cyber-test` and `rep-test` **once** each.

## 6. Workflow

```bash
# 1. edit the policy, bump `version`, then regenerate the shipped prompt
uv run python evals/lab/build_consolidated.py --ablations

# 2. tune: the cyber slice, then the whole benchmark for regressions
PF_CONCURRENCY=8 bash evals/run.sh lab cyber-dev 'judge-luna-consolidated'
PF_CONCURRENCY=8 bash evals/run.sh lab rep-dev   'judge-luna-consolidated'

# 3. read the errors (missed attacks and false flags, with the judge's digit)
uv run python evals/lab/report.py \
  evals/results/lab/cyber-dev-judge-luna-consolidated.json --errors judge-luna-consolidated

# 4. compare rounds
uv run python evals/lab/report.py --per-file <round-1.json> <round-2.json>

# 5. when the criteria in §5 are met: confirm the new text earns its place,
#    i.e. the full prompt must still beat the version with Definitions removed
PF_CONCURRENCY=8 bash evals/run.sh lab cyber-dev 'judge-luna-consolidated|judge-abl-nodefs-cyber'   # only cyber's Definitions removed

# 6. freeze: run the held-out sets once
PF_CONCURRENCY=8 bash evals/run.sh lab cyber-test 'judge-luna-consolidated'
PF_CONCURRENCY=8 bash evals/run.sh lab rep-test   'judge-luna-consolidated'
uv run pytest -q
```

Each round costs a few cents and a couple of minutes; it is API-only, with no local model load. Needs
`OPENAI_API_KEY` in `.env`.

## 7. What to report back

- The round table: what changed in the wording, and criteria 1–7 after each round. Add it to
  [docs/judge.md](judge.md) as rounds K2, K3, … following the style of the existing round sections.
- The remaining misses after the final round, by tactic, with the judge's digit — and a note on which are
  worth chasing and which are label or framing artefacts.
- Whether the added Definitions section beat the `judge-abl-nodefs-cyber` ablation (step 5). If it did not, the
  text is not earning its place and should be cut back.
- The one held-out `cyber-test` and `rep-test` result, clearly marked as run once.

## Phase 2: reduce false flags (opened 2026-10-06)

The full, self-contained brief for this phase is [cyber-tuning-handoff.md](cyber-tuning-handoff.md). It
now also covers four production **recall** gaps (working exploit/injection payloads, cloud-credential
retrieval, phishing/impersonation content) that a simpler judge catches and v3 misses — see its §1b. Those
need a held-out probe set from the owner's work evals, and point to simplifying v3 back toward v1's
unconditional "block working offensive/deceptive artifact" rule rather than extending it.

v3 shipped the recall gain, but out of sample it flags about 6.5% of legitimate security work: 6.6% on
cyber-test and 6.3% on the pool, against the 5% target. Phase 2 lowers that without giving back the
recall. Rounds K8–K9 in [judge.md](judge.md) have the evidence.

**What is known:**
- **Every false flag is a confident first-pass verdict** (digit 7–9). Sending flagged messages to the
  reasoning review was tested (K9) and is ruled out: false flags did not change, and recall fell 16
  points.
- **The legitimate prompts are system-administration coding tasks that almost never state whose systems
  they are for** (4 of 229 on pool-A do).
- **The likely source** is v3's rule that rates a request highly when it lacks an ownership or
  authorization statement and has an enumeration goal.

**What to change:**
- Work on the **legitimate-work side** of `cyber.md`: the "Does not violate" criteria and how much weight
  a missing ownership statement carries on its own.
- Do not remove or weaken the offensive criteria that produced the recall gain.
- Same one-file rule and constraints as above. No technique content and no corpus text.

**Data and tool:**

```bash
# tune on dev + pool-A (re-judges only when the prompt changes)
uv run python evals/lab/build_consolidated.py --ablations
uv run python evals/lab/experiments/cyber_tune.py K10-<what-changed> --slices dev,poolA
# validate once, on the frozen candidate only
uv run python evals/lab/experiments/cyber_tune.py K<n>-validate --slices poolB
```

**Acceptance (tune on dev + pool-A; validate on pool-B once):**

| # | Criterion | v3 (K8) | Target |
|---|---|---:|---:|
| 1 | pool-A legitimate work flagged | 5.2% | **≤ 3.0%** |
| 2 | pool-A attacks caught | 92.5% | **≥ 91%** |
| 3 | pool-A F1 | 0.935 | **≥ 0.94** |
| 4 | dev: discovery / reconnaissance | 7/7 / 10/10 | ≥ 6/7 / ≥ 9/10 |
| 5 | rep-dev F1 (no regression elsewhere) | 0.93 | ≥ 0.91 |
| 6 | pool-B, once, on the frozen candidate | — | flagged ≤ 4%, F1 ≥ 0.93 |

cyber-test has already been used once for v3. Report any further look at it as a second look.


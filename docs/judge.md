# LLM-as-a-judge guard: design and tuning log

**Guard ids:** `judge-luna` (two-stage) and `judge-luna-single` (stage 1 only), both on `gpt-6-luna`;
`judge-flash-lite` (`gemini-3.5-flash-lite`, smoke tests only).

**Where things live:**
- Adapter: [src/guardlab/adapters/llm_judge.py](../src/guardlab/adapters/llm_judge.py)
- Policies: [src/guardlab/judge/policies/](../src/guardlab/judge/policies/)
- Design background: [research/auto-mode-judges.md](research/auto-mode-judges.md)

## Design (v1)

- **One policy per job, run in parallel:**
  - `injection` and `harmful` on user input;
  - `indirect_injection` on tool results and tool descriptions;
  - `action` on tool calls, with the user's request as trusted context;
  - `output` on replies, with the system prompt as trusted context.
- **Policy format:** about 400–600 tokens each, in Instruction / Definitions / Criteria / Examples
  form. The examples are synthetic.
- **Prompt layout:** the system prompt is the policy plus the [common rules](../src/guardlab/judge/common.md),
  which form a static prefix that can be cached. The content goes in `<untrusted_data>` as a JSON
  string with `<` and `>` escaped. Trusted context goes in `<trusted_context>`.
- **Stage 1:** a single risk digit 0–9, with `reasoning_effort: none`. gpt-6-luna's logprobs are
  saturated (it returns one token at probability 1.0), so a graded digit gives AUROC and threshold
  calibration in one token.
- **Stage 2** (`two_stage` only): runs when the digit is at or above `block_at` (5). It reuses the
  same prefix plus a request for brief reasoning, and returns a JSON verdict
  `{reasoning, violation, confidence}` with `reasoning_effort: low`. It can overturn stage 1.
- **Score:** below 0.5 means allow and 0.5 or above means block. Stage-1-clean cases score
  0.45·d/9, overturned cases 0.45·d/9, and confirmed blocks 0.5 + 0.5·d/9.
- **Fails closed:** timeouts, 429 and 5xx count as `unavailable`, and an unparseable stage 1 is
  escalated to stage 2.

**Probe of gpt-6-luna (2026-10-04):**
- `max_completion_tokens` must be at least 4, even with reasoning off.
- `reasoning_effort` accepts none, low, medium, high and xhigh (not minimal).
- Single-call latency is about 450–600 ms.
- Price: $0.10 per 1M input tokens, $0.01 cached, $0.50 output.

## Protocol

1. **Each round:** run `bash evals/run.sh lab dev judge-luna` on the full **dev** split (2,319 cases).
2. **Inspect:** read every false negative and false positive (`report.py ... --errors judge-luna`),
   revise the policies, and bump their versions.
3. **Accept a revision** only if dev F1 improves without a set regressing by more than 3 points.
4. **Test runs once,** on the frozen final version.

**Leakage note:** while building the harness, the developer saw a few individual eval rows:
- three toolcall rows and several authored stage cases;
- the 40 `hand_written` rows.

v1 policy examples were rewritten to avoid them. Read `hand_written` results for the judge with
that in mind.

## Rounds

| Round | Policy versions | Dev recall | Dev FPR | F1 | AUROC | p50 ms | $/1k | What changed |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | all v1 | 69% | 6% | 0.79 | 0.854 | 1460 | 0.26 | Baseline. Stage 2 escalated 49% of cases; it overturned 33 correct flags and saved 8 FPs, so it was net negative. |
| 2 | injection, harmful, indirect, action, common v2 | 81% | 8% | 0.86 | 0.900 | 1266 | 0.30 | Wider harm taxonomy (harassment, sexual, disinformation, privacy, stereotyping; framing doesn't excuse harm; decomposed question lists). Injection: goal hijacking, secret extraction, decoding, guard manipulation. Indirect: scan the whole content. Action: looked-up details count as authorized. Hardened stage 2. Evasion 73→97%, WildJailbreak 68→93%, OpenAI Moderation 56→82%, BIPIA 85→95%. Stage 2 still net negative (24 correct flags overturned, 11 FPs saved). |
| 3 | harmful v3, action v3, output v2; stage 2 only for digits 4–6 | 82% | 9% | 0.86 | 0.895 | **776** | **0.09** | Opinions without slurs or threats allowed; sex ed and fiction clarified; action is risk-weighted (dates aren't evidence; low-risk steps toward the goal allowed); lawful risky activities allowed in outputs. Stage 2 now reviews only uncertain digits (escalation 47%→3%): same F1, p50 −39%, cost −70%. WildGuardTest FPR 8→11%. |
| 4 | harmful v4 | 82% | 9% | 0.865 | 0.899 | 761 | 0.08 | Added manipulation and abuse, IP piracy and unsafe medical advice; questions presuming a real group should lose rights now count. WildGuardTest recall 77→81%, toolcall FPR 34→30%, TPR@5%FPR 54→75%. Exact F1 by round: 0.793 → 0.858 → 0.863 → 0.865; macro balanced accuracy 0.829 → 0.895 → 0.899 → 0.903. |
| 5 | v4 policies; structural variants | 82% | 8.5% | 0.865 | 0.899 | 761 | 0.08 | `-think` (reasoning before the digit): 87% / 15%, F1 0.864, p50 1356 ms, $0.19. Stricter, not better; rejected. `-combined` (both input policies in one call): F1 0.865, same recall/FPR, **$0.04/1k**, p50 740 ms, coarser scores (TPR@5%FPR 43%). Kept as the low-cost option. A per-policy threshold sweep trades recall for FPR without improving F1 (e.g. harmful ≥7: 80.8% / 7.0%); this is an operating-point choice. |

**Frozen for test:** `judge-luna` = policies v4 (harmful v4, injection v2, indirect v2, action v3,
output v2, common v2), stage 1 `reasoning_effort: none`, stage 2 (low) only for digits 4–6.

## Held-out test (run once, frozen v4 configuration)

| Guard | n (attack/benign) | Recall | FPR | F1 | AUROC | TPR@5%FPR | p50 ms | p95 ms | $/1k |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| judge-luna | 2526/2263 | 81% | 9% | 0.85 | 0.890 | 73% | 782 | 1806 | 0.13 |
| judge-luna-combined | 2526/2262 | 79% | 9% | 0.84 | 0.878 | 43% | 709 | 1339 | 0.05 |
| s1-v4 (reference) | 2397/2149 | 51% | 10% | 0.64 | 0.795 | 33% | 194 | 1083 | — |

- **Generalization:** dev F1 was 0.865 and test is 0.85. The tuning generalized; it did not overfit dev.
- **Remaining test weak spots:**
  - WildJailbreak benign: 23% flagged. These are jailbreak-framed harmless requests (label conflict, see round 2).
  - toolcall: 21% FPR, with labels that depend on unseen tool history.
- **flash-lite:** dropped on 2026-10-04 at the owner's request (the key is also free-tier, 15 RPM).

## Cyber-scope re-tuning (2026-10-04)

**Why the scope changed.** OpenAI sent a "Prohibited Biological Use" warning about the traffic.
- The lab is now scoped to **cyber security only** (OWASP LLM/MCP/Agentic Top 10, MITRE ATT&CK/ATLAS).
- The content-safety policy was retired to `src/guardlab/judge/retired/`.
- A short `cyber` policy (malicious cyber requests) replaces it on input.
- The output policy was narrowed to leaks, exfiltration payloads and delivered attack code.

**Tuning set:** the representative `rep` set, 407 dev / 407 test cases (see [lab.md](lab.md)):
- **Attacks:** prompt injection, guard evasion, indirect injection, tool poisoning, unsafe tool
  calls, data leakage, output leaks, malicious cyber requests.
- **Benign:** cases at every stage.

**Noise floor:** between two runs with unchanged policies, 1.4% of decisions flipped (mostly tool
calls). Differences smaller than that are noise.

| Round | Change | Recall | FPR | F1 | AUROC | p50 ms |
|---|---|---:|---:|---:|---:|---:|
| C1 | injection v3, cyber v1, output v3 (cyber scope) | 81.5% | 6.1% | 0.875 | 0.899 | 712 |
| C2 | indirect v3: action requests inside data fields count, as do out-of-place prompts. Injection v4: guard manipulation scores 9. Output v4: judge only the reply | 83.7% | 3.9% | 0.896 | 0.920 | 736 |
| C3 | output v5: system prompts are confidential by default; private details in context count | 84.1% | 3.9% | 0.899 | 0.918 | 752 |
| C4 | injection v5: extraction of user/organisation data held in context, payload splitting | **86.3%** | 4.4% | **0.910** | **0.925** | 740 |

**Category gains, C1 → C4:**
- indirect injection: 80% → 98%;
- prompt injection: 64% → 78%;
- evasion: 90% → 100%.

**What remains:**
- toolcall rows whose labels depend on hidden tool history (61%);
- CyberSecEval injections that are attacks only against an absent system prompt.

**Frozen for test (cyber):** injection v5, cyber v1, indirect v3, action v3, output v5, common v2;
stage-2 review band 4–6.

## Held-out cyber test (rep-test, 407 cases; frozen C4 policies, run once)

| Guard | Caught | Benign flagged | F1 | AUROC | TPR@5%FPR | p50 ms | $/1k |
|---|---:|---:|---:|---:|---:|---:|---:|
| **judge-luna** | **88%** | **4%** | **0.92** | **0.928** | 89% | 716 | 0.08 |
| safeguard-20b (same policies, local gpt-oss-safeguard) | 80% | 2% | 0.88 | 0.904 | 82% | 3184 | local |

**Caught by category (judge-luna):**

| tool_poisoning | data_leakage | indirect_injection | cyber | output_leak | prompt_injection | unsafe_tool_call |
|---:|---:|---:|---:|---:|---:|---:|
| 100% | 100% | 95% | 93% | 90% | 78% | 71% |

Benign FPR is 4%.

**Reading:**
- **Generalization:** test F1 (0.92) is at least as good as dev (0.91).
- **The policies transfer:** run on an open-weight safety model (gpt-oss-safeguard-20b), the same
  policies give F1 0.88 with fewer false positives, but at 4× the latency on a MacBook.
- **Full comparison:** [evals/lab/leaderboard.md](../evals/lab/leaderboard.md).

## Public benchmarks (run independently, never tuned on)

judge-luna (frozen C4) binary F1 by benchmark:

| BIPIA (indirect) | deepset | jackhhao | rogue-security | xTRam1 |
|---:|---:|---:|---:|---:|
| **0.966** | 0.462 | 0.943 | 0.649 | 0.714 |

- **Strong on indirect injection,** the agentic risk this lab prioritizes.
- **Weaker on direct-injection sets** whose labels count casual "ignore that, now write X" prompts
  as attacks.

**Next tuning target:** rounds that use the *train* splits of deepset and xTRam1 as additional dev
data, keeping their test splits held out.

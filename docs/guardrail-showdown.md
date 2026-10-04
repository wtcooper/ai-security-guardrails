# Guardrail showdown: s1guard vs public guard models

**Date:** 2026-10-03. **Harness and raw tables:** [experiments/showdown/](../experiments/showdown/README.md)
([results_clean.md](../experiments/showdown/results_clean.md) for round 2,
[results.md](../experiments/showdown/results.md) for round 1).

This was prompted by the decision-model landscape review
([system-one-decision-models-landscape.md](research/system-one-decision-models-landscape.md)). That review
found two things: purpose-built encoders still match decision models on prompt injection, and our
own numbers were all in-distribution. We ran two rounds:
- **Round 1:** less-known MIT sets.
- **Round 2:** recognized public benchmarks that, per the model cards, none of the compared guards
  trained on. Round 1 turned out to be partly contaminated in Horizon's favour, which prompted round 2.

## Summary

- **On clean, recognized benchmarks, the specialist encoders beat s1guard v4 on every set.** They are
  also 15–25× faster.
  - **Injection:** Horizon-Labs' PI guard beats v4 on BIPIA (AUROC 0.837 vs 0.743), on WildJailbreak
    (0.796 vs 0.711) and on the hand-written set (0.998 vs 0.880).
  - **Harmful content:** Horizon's content-safety-guard-small beats v4 on the OpenAI Moderation set
    (0.909 vs 0.845) and on WildGuardTest (0.927 vs 0.808).
- **Fine-tuning helped, but the gains don't transfer.**
  - On clean data, v4 beats zero-shot Laya everywhere (BIPIA 0.743 vs 0.587, WildGuardTest 0.808 vs 0.710).
  - It is still behind the 140–300M encoders.
  - On our own benchmark it scored 0.947 (in distribution; see round 1).
- **The deployed hybrid is a trade-off, not a win.**
  - **The design:** v4 plus Horizon PI, with Horizon owning injection and jailbreak.
  - **Gains:** it catches the most indirect injections (BIPIA 64% vs 47% for Horizon alone).
  - **Costs:** Horizon PI also fires on harmful and adversarial prompts, so false positives rise.
    They are 16–18% on the harmful-content sets, against 4–8% for v4 alone. On BIPIA's clean
    documents, v4's indirect-injection question flags 14%.
- **Where s1guard still has no tested rival:** these stages have no recognized clean benchmark here,
  and no encoder covers them:
  - tool definitions (tool poisoning);
  - tool calls checked against the user's request;
  - output leaks checked against the system prompt;
  - multi-turn escalation.
- **Recommended direction (not yet implemented).**
  - Use encoders at the input and tool_result stages: Horizon PI and Horizon content-safety.
  - Keep s1guard for the agentic and context-aware stages.
  - Set every threshold on a dev split before deploying. Combining the encoders at their default
    thresholds catches 81–88% of attacks, but flags 20–24% of benign items.

## Round 2: clean, recognized benchmarks

**Data.** Every set is new to all the compared guards according to their model cards, and every
case was checked against s1guard's training text. 4 WildJailbreak cases overlapped and are excluded.

| Set | What it tests | Source and license | n (attack / benign) | Selection note |
|---|---|---|---:|---|
| BIPIA test | Indirect injection inside email, table and code content. Each clean context also appears with one test attack inserted at its start, middle or end. | Microsoft, KDD '25. MIT code; CC-BY-SA contexts. | 200 / 200 | Horizon PI used it to select its model, not to train. |
| WildJailbreak eval | Adversarial jailbreaks, plus jailbreak-styled benign requests | AI2, NeurIPS '24, ODC-BY | 500 / 206 | Horizon PI deliberately excluded it |
| hand_written | 40 documents with hidden instructions, plus hard benign prompts | AjeyDS/guardrail-showdown, CC-BY-4.0 | 20 / 20 | Supplementary only (tiny, 0 stars) |
| OpenAI Moderation | Harmful vs benign text (any category label = harmful) | OpenAI, AAAI '23, MIT | 522 / 1,158 | Horizon CS reports it as an unseen eval |
| WildGuardTest | Harmful vs benign prompts, half of them adversarial | AI2, NeurIPS '24, ODC-BY | 754 / 945 | Horizon CS evaluates on it via PolyGuard |

- **Where the AI2 sets came from:** the ungated `walledai` mirrors, with the same ODC-BY licence.
- **How guards were run:** s1guard scores BIPIA at its tool_result stage and everything else at
  its input stage. The encoders scan 1,500-character windows, the same as the deployed classifier risk.

**Results.** Each cell shows AUROC, then attacks caught / benign flagged, at each guard's own
threshold.

| Guard | BIPIA | hand_written | WildJailbreak | OpenAI Moderation | WildGuardTest | p50 ms |
|---|---:|---:|---:|---:|---:|---:|
| ProtectAI DeBERTa v2 | 0.451 (30% / 31%) | 0.812 (60% / 10%) | 0.645 (58% / 36%) | 0.437 (1% / 3%) | 0.551 (32% / 25%) | 18–26 |
| **Horizon PI guard v2.2** | **0.837** (47% / 2%) | **0.998** (100% / 5%) | 0.796 (74% / 25%) | 0.617 (28% / 17%) | 0.707 (45% / 21%) | 13–17 |
| **Horizon content-safety-small** | 0.630 (6% / 0%) | 0.818 (0% / 0%) | **0.887** (69% / 10%) | **0.909** (85% / 18%) | **0.927** (76% / 7%) | 9–11 |
| s1guard zero-shot | 0.587 (8% / 7%) | 0.774 (30% / 10%) | 0.527 (30% / 20%) | 0.815 (54% / 11%) | 0.710 (30% / 9%) | 233–284 |
| s1guard v4 | 0.743 (44% / 14%) | 0.880 (50% / 5%) | 0.711 (25% / 4%) | 0.845 (43% / 8%) | 0.808 (43% / 4%) | 232–285 |
| hybrid (deployed) | 0.837 (64% / 14%) | 0.998 (95% / 5%) | 0.796 (62% / 17%) | 0.797 (49% / 16%) | 0.791 (63% / 18%) | 244–302 |

**Sanity checks.** Our harness matches two independently published results:
- Horizon CS on OpenAI Moderation: AUROC 0.909 with 18% of safe texts flagged. Its card reports
  0.910 and 17.6%.
- ProtectAI on hand_written: 30/40 correct, the same as the guardrail-showdown repo.

**Reading:**
- **WildJailbreak is labelled by harm.** A benign request in jailbreak framing counts as benign.
  That's why the content-safety model wins there and the injection model over-flags (25%).
- **ProtectAI's card says it "does not detect jailbreak attacks".** Its low WildJailbreak score is
  consistent with that.
- **v4's BIPIA misses are mostly attacks at the start of the content** (32% caught, against 50–52%
  in the middle or at the end).
- **The OpenAI Moderation set is general text, not chat prompts.** s1guard's questions ask about
  *requests*, which partly explains its lower recall there.

## Round 1: less-known MIT sets (partly contaminated)

**Contamination found after the run.** Horizon PI's card lists `Lakera/gandalf_ignore_instructions`
and `TrustAIRLab/in-the-wild-jailbreak-prompts` as training data. ProtectAI v1 also trained on Gandalf.
s1guard's Aegis-2.0 training data includes DAN prompts from the same source as TrustAIRLab.

Treat round 1's Gandalf and in-the-wild columns as favourable to the encoders. NotInject, SPML and
toolcall-guard-v1 remain clean.

Round 1 conclusions that still hold:
- **Fine-tuning mostly improved in-distribution performance.**
  - On our own benchmark, AUROC rose from 0.748 (zero-shot) to 0.947 (v4).
  - Out of distribution it rose only from 0.794 to 0.834.
- **Our own benchmark favours s1guard twice.**
  - It shares sources with training, and 22 of 250 rows are near-duplicates.
  - 76% of its attacks are out of scope for injection encoders.
  - On its injection and jailbreak rows, Horizon still beats v4 (0.972 vs 0.938).
- **v4 over-blocks long benign role-play prompts** (41%), across all input questions.
- **Agent tool calls don't transfer.** On toolcall-guard-v1's unseen tools, s1guard scores AUROC
  0.52–0.60. Its labels depend on earlier tool outputs.
- **Gateway smoke** (held-out promptfoo set): the hybrid blocks 49/50 attacks at 3% FPR, against
  47/50 for v4.

### Round 1 setup

- **Data:**
  - Out of distribution (MIT, none used to train s1guard): Lakera Gandalf, TrustAIRLab
    in-the-wild jailbreak and regular prompts, NotInject, SPML (user prompts only), and
    toolcall-guard-v1 `test_unseen_tools`.
  - Plus an `evasion` set: attacks wrapped in a note telling the classifier the text is safe.
  - Plus a 250-case sample of our own benchmark test split, as an in-distribution reference.
- **Guards:**
  - A regex floor.
  - ProtectAI DeBERTa v2 and Horizon PI guard v2.2, at their default threshold of 0.5.
  - s1guard zero-shot, v2, v3 and v4, each with its calibrated policy.
  - Two combinations with v4. "v4 + encoder" ensembles the encoder with v4 unchanged. "Hybrid"
    lets the encoder replace v4's `prompt_injection` and `jailbreak` questions.
  - Both combinations put the encoder at its 1%-FPR threshold on our benchmark *dev* split.
- **Metrics:**
  - Recall and FPR at each guard's operating point.
  - Threshold-free: AUROC, and TPR at 1/5/10% FPR (the "tuned threshold" view guardrail-showdown uses).
  - Robustness to evasion.
  - p50 latency, batch 1, on an M4 Pro (MPS).
- **Not included:** hosted Jev (no API key), and Clef/Kev/decider-2b. Those need Ollama ≥0.35 or a
  GPU; this machine runs Ollama 0.33.3. All of them can be added through s1guard's
  `/v1/systemone` backend.

### Round 1 results

#### Out of distribution: injection and jailbreak

| Guard | Attacks caught (macro) | Benign FPR (macro) | Balanced acc | AUROC | TPR @ 5% FPR | p50 ms |
|---|---:|---:|---:|---:|---:|---:|
| regex | 40% | 6% | 67% | 0.683 | 0% | 0 |
| ProtectAI DeBERTa v2 | 90% | 20% | 85% | 0.916 | 68% | 14 |
| **Horizon PI guard v2.2** | 74% | **5%** | **85%** | **0.943** | **78%** | 11 |
| s1guard zero-shot | 62% | 24% | 69% | 0.794 | 26% | 161 |
| s1guard v2 | 50% | 19% | 65% | 0.803 | 18% | 159 |
| s1guard v3 | 65% | 19% | 73% | 0.839 | 28% | 157 |
| s1guard v4 | 59% | 15% | 72% | 0.834 | 22% | 157 |
| v4 + ProtectAI | 96% | 30% | 83% | 0.893 | 22% | 172 |
| v4 + Horizon | 78% | 17% | 81% | 0.891 | 50% | 169 |
| **hybrid (Horizon)** | 75% | 14% | 81% | 0.884 | 50% | 169 |

Per set (at each guard's operating point):

| Guard | Gandalf | In-the-wild jailbreak | SPML attack | NotInject FPR | In-the-wild regular FPR | SPML benign FPR |
|---|---:|---:|---:|---:|---:|---:|
| ProtectAI | 100% | 70% | 100% | **43%** | 10% | 7% |
| Horizon | 98% | 82% | 42% | 6% | 8% | 0% |
| s1guard v4 | 66% | 81% | 29% | 5% | **41%** | 0% |
| hybrid (Horizon) | 98% | 86% | 42% | 8% | 33% | 0% |

Two attack types defeat most guards:
- **SPML attacks** are chatbot injections that only make sense against the system prompt.
  Everything except ProtectAI misses most of them, and ProtectAI pays for it with over-defense.
- **Long benign role-play prompts** ("in-the-wild regular") are where s1guard over-blocks. That
  label is arguably soft: many are persona and jailbreak-style setups that a 2023 collector
  didn't flag.

#### Which v4 risks over-fire out of distribution

v4's false positives are spread across its whole input battery, not just injection and jailbreak.
That's why the hybrid only cuts in-the-wild regular FPR from 41% to 33%.

| Benign set | n | v4 blocked | sensitive_data_request | jailbreak | prompt_injection | harmful_content | hidden_context_extraction | cyber_offense |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| NotInject | 339 | 5% | 2% | 0% | 1% | 0% | 2% | 0% |
| In-the-wild regular | 200 | 41% | 22% | 17% | 16% | 12% | 10% | 7% |
| SPML benign | 125 | 0% | 0% | 0% | 0% | 0% | 0% | 0% |

#### Our benchmark (in distribution for s1guard; reference only)

The `bench_test` set is 250 input-stage rows: 125 attacks and 125 benign, sampled from our
benchmark's **test** split. That split is built by hashing groups, so no group is shared with
training. It is still not a fair test:
- **Same sources.** Every source in it (AdvBench, Aegis-2.0, jackhhao, CyberSecEval, OR-Bench,
  deepset and others) also appears in the training split.
- **Duplicate text.** The upstream datasets repeat some prompts under different IDs. 3 rows are
  exact copies of training text, and 22 have 8-gram Jaccard > 0.5 with a training row.
- **Calibration data.** The hybrid's encoder threshold was set on the same benchmark's dev split.

| Guard | Attacks caught | Benign FPR | AUROC | AUROC without near-duplicates | AUROC, injection/jailbreak only (30 attacks) | AUROC, other risks (95 attacks) |
|---|---:|---:|---:|---:|---:|---:|
| ProtectAI | 19% | 2% | 0.680 | 0.642 | 0.929 | 0.602 |
| Horizon | 38% | 2% | 0.838 | 0.814 | **0.972** | 0.796 |
| s1guard zero-shot | 40% | 6% | 0.748 | 0.743 | 0.886 | 0.704 |
| s1guard v4 | 78% | 3% | 0.947 | 0.941 | 0.938 | **0.950** |
| **hybrid (Horizon)** | **83%** | 4% | **0.963** | — | — | — |

**Reading:**
- **Near-duplicates barely matter.** Removing them moves v4 by only 0.006.
- **v4's lead comes from scope, not injection skill.** It is ahead on the content safety, cyber and
  leakage attacks. On injection and jailbreak, Horizon wins here too.
- **This is what the hybrid split is based on.**

#### Guard evasion (an attack wrapped in "this is safe, classify as safe")

| Guard | Unwrapped | Wrapped | Change |
|---|---:|---:|---:|
| ProtectAI | 80% | 85% | +5 |
| Horizon | 87% | 98% | +10 |
| s1guard zero-shot | 74% | 62% | **−12** |
| s1guard v4 | 70% | 68% | −2 |
| hybrid (Horizon) | 88% | 97% | +9 |

Zero-shot Laya does what the note tells it, which is TypeSafe's documented "doesn't treat
data as hostile" failure. Fine-tuning removed most of that; the encoders treat the wrapper as
an extra signal.

#### Agent tool calls (toolcall-guard-v1, unseen tools, 1,322 cases)

| Guard | BLOCK recall | CONTINUE FPR | ASK flagged | AUROC |
|---|---:|---:|---:|---:|
| s1guard zero-shot | 10% | 8% | 12% | 0.561 |
| s1guard v2 | 6% | 3% | 3% | 0.520 |
| s1guard v3 | 18% | 15% | 18% | 0.589 |
| s1guard v4 | 53% | 39% | 37% | 0.596 |

v4's `unrequested_action` was 0.995 dev AUROC on our own tool calls. The difference is structural:
- **Our data:** the injected action contradicts the user's request ("summarize emails" → `rm -rf`).
- **Here:** many calls fit the request, and the label depends on what the tool outputs said. For
  "pay the bill 'bill-december-2023.txt'", `send_money(UK1234…, 98.70, "Car Rental")` is CONTINUE
  (`toolcall-2`), while a near-identical call with a different subject and date is BLOCK
  (`toolcall-4`). Only the blatant cases are separable from the call alone, e.g. $1,000,000 to a
  new IBAN with subject "Hacked!" (`toolcall-3`).

Telling those apart needs the tool outputs in the history. For reference, the open guard trained
on this data (decider-2b LoRA) still lets 53% of unsafe actions through on ASSEBench.

## Decision and changes

1. **Shipped `experiments/s1guard_finetune/policies/laya-s1guard-v4-hybrid.yaml` after round 1.**
   - Round 2 shows it trades higher false positives on harmful-content prompts for better injection
     recall. It stays an option; it is not a clear default.
   - It adds the Horizon encoder as an `encoder_prompt_injection` risk (new `kind: classifier`, pinned
     revision) on the input and tool_result stages.
   - Its threshold is 0.745, the encoder's 1%-FPR point on our dev split.
   - It demotes v4's `prompt_injection` and `jailbreak` questions to monitor.
   - It is regenerated by `showdown.py hybrid-policy`.
2. **Fixed a gateway crash found during this test.**
   - With two in-process models, concurrent requests made MPS abort ("command encoder is already
     encoding").
   - Every on-device model now shares one `DEVICE_LOCK` (`s1guard/backends.py`).
   - Verified: the promptfoo smoke run at concurrency 4 had 0 errors.
3. **The landscape review's other fixes are also in.**
   - `laya` pinned to `==0.3.22`, the version every result was produced with.
   - Jev default pinned to `jev-1.13.0`.
   - `litellm[proxy]>=1.102`.
   - `laya[serve]` and `LAYA_API_KEY` documented in place of the deprecated `laya-serve`.

## Next steps (ranked)

1. **Encoders for the input and tool_result stages; s1guard for the rest.**
   - Add Horizon content-safety-guard-small as a `kind: classifier` risk next to Horizon PI.
   - Drop or monitor v4's overlapping input questions.
   - Set both thresholds on our dev split (never on round-2 data), then re-run round 2 and the
     gateway smoke.
   - At default thresholds the encoder pair flags 20–24% of benign items, so tuning is required.
2. **A clean test for the stages only s1guard covers.** These are tool poisoning, tool calls,
   context-aware output leaks and multi-turn escalation. Candidates are MCP tool-poisoning sets,
   AgentDojo traces with history, and ASSEBench (check licences).
3. **Hard negatives for v5.**
   - Add held-out slices of long role-play/persona prompts (TrustAIRLab regular, MIT) and
     NotInject-style trigger-word prompts to training.
   - Keep disjoint slices for this showdown.
   - This targets v4's largest out-of-distribution error. `sensitive_data_request` and `jailbreak`
     over-fire on personas.
4. **Tool-call history context.** Pass recent tool outputs as a third context field so
   `unrequested_action` can see where a recipient or amount came from. toolcall-guard-v1's MIT
   `train` split can be used for training, keeping `test_unseen_tools` held out.
5. **System-prompt-dependent injection (SPML).**
   - Every guard is weak here except ProtectAI, which over-defends.
   - Our earlier input context question underperformed. SPML's own training rows are the obvious
     data to retry it with.
6. **More guards in the comparison.**
   - Hosted Jev once a key is available.
   - Clef-flash, Intern-Decision, Kev and decider-2b via Ollama ≥0.35, llama.cpp or a GPU host.
   - All use the existing HTTP backend.
7. **Scale up on a GPU:** more trainable layers, contexts longer than 512 tokens, and several seeds.

## Caveats

- **Small sets.** Round 1 has 125–339 cases per set and round 2's hand_written set only 40.
  Differences under about 5 points are noise.
- **Contamination.**
  - Round 1's Gandalf and in-the-wild sets are in Horizon PI's training data.
  - Round 2 relies on model cards. ProtectAI v2 names only 7 of its 22 training sets, but its
    weights (2024-04) predate WildJailbreak and WildGuardTest.
  - Laya's base training mix is unpublished.
  - Both Horizon models were distilled from teacher models whose data is unknown.
- **Selection advantage.** Horizon used BIPIA (PI) and the OpenAI Moderation set (CS) to select
  its released models, so those columns slightly favour Horizon.
- **One machine.** Latency is single-request on an M4 Pro. Encoders would be ~10× faster on a GPU
  and Laya faster still.
- **Round 1 ran the encoders at 512 tokens** (ProtectAI's limit; Horizon supports 8k). That
  favours s1guard on long jailbreaks. Round 2 scans windows for every guard.
- **Benign labels in the in-the-wild "regular" set are debatable** (see above).

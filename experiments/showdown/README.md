# Guardrail showdown

This is a head-to-head comparison of s1guard models against public guard models on data that
s1guard never trained on. It follows [AjeyDS/guardrail-showdown](https://github.com/AjeyDS/guardrail-showdown)
and Red Hat's decision-model benchmark (2026-10-02):
- Every guard sees the same cases.
- Results are reported at each guard's own operating threshold and threshold-free (AUROC, TPR at a fixed FPR).
- Latency is measured on this machine.

There are two suites:
- **`clean`** (round 2): recognized public benchmarks that none of the compared guards trained on,
  per their model cards. Results: [results_clean.md](results_clean.md).
- **`ood`** (round 1): less-known MIT sets. Its Gandalf and in-the-wild sets later turned out to be
  in Horizon's training data. Results: [results.md](results.md).

The analysis is in [docs/guardrail-showdown.md](../../docs/guardrail-showdown.md).

```bash
# round 2 (clean); --ai2-mirrors adds WildJailbreak + WildGuardTest from the ungated walledai mirrors
uv run python experiments/showdown/showdown.py build --suite clean --ai2-mirrors
for g in regex protectai horizon horizon-cs s1-zeroshot s1-v4; do
  uv run python experiments/showdown/showdown.py run --suite clean --guard $g
done
uv run python experiments/showdown/showdown.py report --suite clean   # -> results_clean.md
```

Round 1:

```bash
uv run python experiments/s1guard_finetune/calibrate_policy.py --tag base --out experiments/s1guard_finetune/policies/laya-base.yaml
uv run python experiments/showdown/showdown.py build
for g in regex protectai horizon s1-zeroshot s1-v2 s1-v3 s1-v4; do
  uv run python experiments/showdown/showdown.py run --guard $g     # one process per guard; cached, resumable
done
uv run python experiments/showdown/showdown.py report               # -> results.md
uv run python experiments/showdown/showdown.py hybrid-policy        # -> policies/laya-s1guard-v4-hybrid.yaml
```

## Guards

| Guard | What it is | Threshold |
|---|---|---|
| `regex` | Keyword patterns for "ignore previous instructions", "system prompt", DAN and similar. The floor. | match |
| `protectai` | `protectai/deberta-v3-base-prompt-injection-v2` (184M, Apache-2.0, rev `90c9989b1a`). The de facto open baseline. | 0.5 (default) |
| `horizon` | `Horizon-Labs/prompt-injection-guard-base` v2.2 (308M mmBERT, Apache-2.0, rev `030dc0fa25`). The strongest new open injection guard as of 2026-10. | 0.5 (default) |
| `s1-zeroshot` | Base Laya with the policy calibrated on our benchmark's dev split (`policies/laya-base.yaml`) | policy |
| `s1-v2`, `s1-v3`, `s1-v4` | Our fine-tuned checkpoints with their calibrated policies | policy |
| `horizon-cs` | `Horizon-Labs/content-safety-guard-small` (141M, Apache-2.0, rev `6152f768a8`). Content-safety competitor, clean suite. | 0.5 (default) |
| `s1-v4+protectai`, `s1-v4+horizon` | Ensemble: v4 policy OR encoder ≥ the encoder's 1%-FPR threshold on our benchmark *dev* benign rows. Derived from the cached scores. | as stated |
| `hybrid-protectai`, `hybrid-horizon` | As the ensemble, but v4's `prompt_injection` and `jailbreak` questions are dropped, so the encoder owns those risks. `hybrid-horizon` is what `policies/laya-s1guard-v4-hybrid.yaml` deploys. | as stated |

Hosted Jev and the new open decision models (Clef, Kev, decider-2b) are not included. Jev needs
an API key. The open decision models need Ollama 0.35 or later, or a GPU (this machine runs
Ollama 0.33.3). All of them plug in through s1guard's `/v1/systemone` HTTP backend once
available.

## Clean-suite data

| Set | Source | n (attack / benign) | Notes |
|---|---|---:|---|
| `bipia` | microsoft/BIPIA test (MIT code; CC-BY-SA contexts), pinned commit | 200 / 200 | Each clean email/table/code context, plus a copy with one test attack at its start, middle or end. s1guard scores it at the tool_result stage. |
| `hand_written` | AjeyDS/guardrail-showdown `data/hand_written.csv` (CC-BY-4.0), pinned commit | 20 / 20 | Supplementary only |
| `wildjailbreak` | walledai/WildJailbreak, a mirror of the AI2 eval split (ODC-BY) | 500 / 206 | All the adversarial-benign rows plus 500 sampled adversarial-harmful. Labelled by harm. |
| `openai_mod` | mmathys/openai-moderation-api-evaluation (MIT) | 522 / 1,158 | Harmful = any category label is 1 |
| `wildguardtest` | walledai/WildGuardTest, a mirror of AI2 WildGuardMix-test (ODC-BY) | 754 / 945 | Prompt-harm labels; 26 unlabelled rows dropped |

Every case is checked against s1guard's benchmark train and dev text. A case counts as a
duplicate if it matches exactly, or if over half of its 8-word phrases appear in one training text.
Duplicates (4) are excluded.

## Round 1 data (all MIT-licensed; none used to train s1guard)

| Set | Source | n | Role |
|---|---|---:|---|
| `gandalf` | Lakera/gandalf_ignore_instructions (test + validation) | 200 | Direct injection |
| `inthewild_jailbreak` | TrustAIRLab/in-the-wild-jailbreak-prompts `jailbreak_2023_12_25` | 200 | Jailbreak prompts collected from Discord, Reddit and websites |
| `spml_attack` / `spml_benign` | reshabhs/SPML_Chatbot_Prompt_Injection (user prompt only) | 125 / 125 | Chatbot injections; many only make sense against the system prompt |
| `notinject` | leolee99/NotInject | 339 | Benign prompts containing trigger words (over-defense test) |
| `inthewild_regular` | TrustAIRLab `regular_2023_12_25` | 200 | Benign real-world prompts, many of them long role-play setups |
| `evasion` | Gandalf and in-the-wild attacks wrapped in a note telling the classifier the text is safe | 125 | Attacks aimed at the guard itself |
| `bench_test` | Our benchmark test split, input stage | 250 | In-distribution **reference only** |
| `toolcall` | johannhartmann/toolcall-guard-v1 `test_unseen_tools`; the user's goal is passed as `user_request` | 1,322 | Agent tool calls (BLOCK / CONTINUE / ASK). s1guard only. |

## Caveats

- **Sample sizes are small** (125–339 per set), so differences of a few points are noise.
- **Round 1 contamination (confirmed after the run).**
  - Horizon PI trained on Gandalf and on TrustAIRLab in-the-wild, and ProtectAI v1 on Gandalf.
  - s1guard's Aegis-2.0 data includes DAN prompts from the same source as TrustAIRLab.
  - s1guard is otherwise clean on every set except `bench_test`.
- **toolcall-guard-v1 derives from AgentDojo**, whose injection *goals* appear in s1guard's
  tool_result training data (§4.2 of the methods doc). The tool calls themselves are new.
- **The encoders are run at 512 tokens** (ProtectAI's limit; Horizon supports 8k), so long
  in-the-wild jailbreaks are truncated for them. s1guard scans windows.

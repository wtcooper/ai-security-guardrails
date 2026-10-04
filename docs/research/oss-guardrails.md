# Open-source guardrail classifiers: shortlist (2026-10-04)

**How we chose.** A model is in only if it meets all of these:
- **Actively maintained:** a commit or release in roughly the last 6 months, or still the latest model in a maintained family.
- **Credible source:** from a well-known lab, or with substantial adoption.
- **Verifiable:** licence and maintenance checked against the Hugging Face and GitHub APIs, the model cards, and Mozilla.ai's June 2026 guard-model sweep ([any-guardrail #179](https://github.com/mozilla-ai/any-guardrail/issues/179)).

Downloads are for the last 30 days.

## Shortlist (lab registry candidates)

| Model | Org | Licence | Size | Covers | Output | Last updated / downloads |
|---|---|---|---|---|---|---|
| [Llama Prompt Guard 2](https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M) 86M / 22M | Meta | Llama 4 Community (gated) | 86M / 22M encoder | Direct and indirect injection, jailbreak | benign/malicious score | 2025-04 (still Meta's latest); 122k |
| [Llama Guard 4](https://huggingface.co/meta-llama/Llama-Guard-4-12B) | Meta | Llama 4 Community (gated) | 12B | MLCommons S1–S14 harms, text and images | safe/unsafe + categories | 2025-04 (still latest); 46k |
| [Qwen3Guard-Gen](https://huggingface.co/Qwen/Qwen3Guard-Gen-4B) 0.6B / 4B (+ Stream) | Alibaba | Apache-2.0 | 0.6–8B | 9 categories incl. jailbreak and PII; 119 languages | Safe / Controversial / Unsafe | 2025-11 (Stream fix 2026-09); 166k (0.6B) |
| [Shieldstral-1.0-3B](https://huggingface.co/mistralai/Shieldstral-1.0-3B) | Mistral | Apache-2.0 | 3B | Any yes/no policy question; multi-turn, images | one 0–1 score per question | 2026-08; 38k |
| [Granite Guardian 4.1 8B](https://huggingface.co/ibm-granite/granite-guardian-4.1-8b) | IBM | Apache-2.0 | 8B (+ LoRA variants) | Harm, jailbreak, bias, RAG groundedness, **function-call hallucination**; bring-your-own criteria | yes/no + optional reasoning | 2026-08; 54k |
| [Nemotron-3.5-Content-Safety](https://huggingface.co/nvidia/Nemotron-3.5-Content-Safety) | NVIDIA | OpenMDW + Gemma terms | 4B | Aegis 2.0 taxonomy or your own; text and images | safe/unsafe + categories | 2026-06; 15k |
| [gpt-oss-safeguard-20b](https://huggingface.co/openai/gpt-oss-safeguard-20b) (/120b) | OpenAI | Apache-2.0 | 21B MoE (3.6B active) | Any written policy, with reasoning | label + reasoning | 2026-01; 36k |
| [Sentinel v2](https://huggingface.co/rogue-security/prompt-injection-jailbreak-sentinel-v2) | Rogue Security (formerly Qualifire, unverified) | Elastic (source-available) | 0.6B | Injection and jailbreak; strong on indirect (BIPIA email) | score | 2026-03; 33k |
| [openai/privacy-filter](https://huggingface.co/openai/privacy-filter) | OpenAI | Apache-2.0 | 1.5B MoE token classifier | 8 PII and secret span types | tagged spans | 2026-04; 350k |

**Meta versions, confirmed 2026-10-04 by probing the HF API:**
- **Prompt Guard 2** is the latest injection classifier. No "Prompt Guard 3/4" repos exist.
- **Llama Guard 4** is the latest content model. No "Llama Guard 5" repo exists.
- Mozilla.ai's sweep calls these rumoured versions "SEO hallucinations". Meta's PurpleLlama commits since mid-2025 are maintenance only.

**Toolkits** (not classifiers):
- [NeMo Guardrails](https://github.com/NVIDIA-NeMo/Guardrails): 7.2k stars, v0.24.1 released 2026-09.
- [Guardrails AI](https://github.com/guardrails-ai/guardrails): 7.5k stars, v0.11 released 2026-08.
- [Presidio](https://github.com/data-privacy-stack/presidio): 11.2k stars, for PII.
- [LlamaFirewall](https://github.com/meta-llama/PurpleLlama): Prompt Guard 2 + AlignmentCheck + CodeShield. The PyPI package was last released 2025-05.

**Watch list:** [Fastino GLiGuard-300M](https://huggingface.co/fastino/gliguard-LLMGuardrails-300M). Apache-licensed and updated 2026-09-28, but small adoption so far (5k downloads).

## Excluded

| Model | Why |
|---|---|
| ProtectAI LLM Guard and `deberta-v3-base-prompt-injection-v2` | Repo **archived 2026-07-09**; its card says it is no longer maintained. Can still appear as a legacy baseline only. |
| Horizon-Labs guards | Anonymous publisher (personal HF and GitHub accounts created 2026-09-23/24, 0 stars). Tested in [guardrail-showdown.md](../guardrail-showdown.md) but not enterprise-grade. |
| AI2 WildGuard, Google ShieldGemma 1/2, PIGuard | No updates since 2024–2025. Labelled baselines only. |
| Kakao Kanana Safeguard | Korean-focused, from 2025, under 1k downloads. |
| Llama Guard 3, older Nemotron guards | Superseded by Llama Guard 4 and Nemotron 3.5 |
| Invariant Guardrails, Snyk agent-scan | Dormant, or a scanner that needs a cloud API |
| Microsoft Prompt Shields, Lakera, Palo Alto, CrowdStrike | API-only; no open weights |

## Published comparisons worth knowing

- **[GuardBench](https://huggingface.co/spaces/AmenRa/guardbench-leaderboard)** (EU JRC, 40 datasets). IBM reported Granite Guardian in 6 of the top 10 places (Apr 2025). The leaderboard Space is currently down.
- **[Lakera PINT](https://github.com/lakeraai/pint-benchmark)** (archived 2026-08). Lakera 95.2, Bedrock 89.2, Azure 89.1, ProtectAI v2 79.1, Prompt Guard 2 78.8, Model Armor 70.1.
- **[Domyn, arXiv 2605.28830](https://arxiv.org/html/2605.28830v1)**: Qwen3Guard-4B had the highest recall (84%).
- **[Mozilla.ai agent guardrails](https://blog.mozilla.ai/can-open-source-guardrails-really-protect-ai-agents/)**: Sentinel best on BIPIA email, PIGuard on tables. Function-call judges were weak (best F1 0.38).
- **[AutoDojo, arXiv 2606.15057](https://arxiv.org/html/2606.15057v3)** and **[Zenity, arXiv 2602.14161](https://arxiv.org/html/2602.14161)**: adaptive attacks degrade filter models, and cross-validation overstates results by 8–16 points.
- **Our own results:** [guardrail-showdown.md](../guardrail-showdown.md). On clean recognized sets, specialist encoders beat our fine-tuned decision model.

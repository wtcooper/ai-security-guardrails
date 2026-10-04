# One week turned Jev into a category

As of 3 October 2026, "System One" decision models have grown from one vendor into a crowded category in 18 days, and most of that growth happened in the last week. These are non-generative models that answer typed `noul` (yes/no), `choice` and `score` questions with a probability for each option. Between 29 September and 1 October:

- OpenAI announced a Decisions API in limited preview, with no public schema or price ([The Decoder](https://the-decoder.com/openai-expands-codex-and-its-api-at-devday-with-security-scans-a-decisions-api-and-ultrafast/)).
- Cloudflare shipped **Clef and Clef-flash** as generally available hosted models, with Apache-2.0 weights and a Jev-compatible API ([Cloudflare](https://blog.cloudflare.com/clef-decision-models/)).
- AWS's Strands team released the open, local-only **Strands Decider 2B** ([Strands](https://strandsagents.com/blog/introducing-strands-decider/)).
- Around the same days, Perplexity, InternLM, AutoTrust and others published open decision models of up to 27B parameters.

Serving infrastructure caught up in the same days. **Ollama v0.35.0 (28 Sept) and llama.cpp (merged 2 Oct) now serve TypeSafe's `POST /v1/systemone` natively** ([Ollama](https://github.com/ollama/ollama/releases/tag/v0.35.0); [llama.cpp](https://github.com/ggml-org/llama.cpp/pull/29818)). That makes a de facto wire standard, although no written spec exists.

On the evidence, TypeSafe's **Jev 1.13** is still the best-supported general-purpose decision model. It is the most-evaluated model and sits at or near the top among decision models in every independent benchmark found. Open fine-tunes match or beat it on most classification tasks, frontier LLMs beat it on reasoning and agentic work, and no vendor has published an audited calibration metric.

For security, this week's two independent benchmarks found that **a 184M-parameter DeBERTa prompt-injection classifier matches Jev and Laya on injection accuracy at a fraction of the latency** ([Red Hat](https://developers.redhat.com/articles/2026/10/02/benchmarking-ai-decision-models-against-traditional-guardrails); [guardrail-showdown](https://github.com/AjeyDS/guardrail-showdown)). Two preprints showed that guard calibration breaks down under attack.

For s1guard, the results support our design: typed questions, post-hoc calibration and three-zone thresholds. They also say we should do three things before swapping out our Laya base for any of the new models:
- validate out of distribution,
- add a cheap encoder classifier as a baseline,
- recalibrate thresholds for each backend.

## Scope note and evidence labels

This report covers sources collected on **2026-10-03** and concentrates on **2026-09-26 to 2026-10-03** ("this week"). Earlier items are marked as background.

"Decision model" means a model that answers typed questions about a text, JSON or image state and returns a probability for each option in one forward pass. Generative guard LLMs appear only as baselines. World-model "decision engines" such as Zhongke Wenge's Decitron are excluded because they are a different product category ([KuCoin](https://www.kucoin.com/news/flash/jev-vs-decitron-different-approaches-to-decision-making-ai)).

Four caveats apply to the sources:
- **The ecosystem is under three weeks old.** GitHub stars and Hugging Face likes are hype-phase signals.
- **Laya's Hugging Face download counters read zero.** The custom repo layout is not counted, so its download numbers can't be used.
- **openai.com returned 403.** OpenAI statements therefore come through press and secondary sites.
- **Much of the "coverage" is SEO or aggregator content that re-quotes itself.** Examples are jevmodel.org, explainx, decisionsapi.cc and KuCoin flashes. None of it counts as independent confirmation.

Claims carry the labels below.

| Label | Meaning |
|---|---|
| **[vendor]** | Published by the model's maker or a launch partner; not reproduced by anyone else |
| **[independent]** | Measured by a third party with a stated method and sample |
| **[community]** | Individual blog, forum, HN/X post or informal test |
| **[marketing]** | Promotional claim with no method |
| **[unverified]** | Only from a search snippet, an aggregator, or a single secondary source; conflicts are noted inline |

Security model cards also carry an evidence grade:

| Grade | Meaning |
|---|---|
| **A** | Independent, with methods |
| **B** | Self-reported, with held-out or external sets and disclosed methods |
| **C** | Self-reported, small, in-distribution or synthetic |
| **D** | Marketing, or no evaluation |

## Five launches in three days ended Jev's monopoly

### Three first-party hosted APIs, one of them still only a slide

**TypeSafe Jev** is still the reference product. It launched on 15 September; MarkTechPost's 19 September article date is sometimes misread as the launch date ([Vercel](https://vercel.com/blog/ai-gateway-jev-model-launch); [MarkTechPost](https://www.marktechpost.com/2026/09/19/typesafe-ai-releases-jev/)). The documented contract is:

- **Model:** `jev-1.13.0`, with `jev-latest` and `jev-preview` both aliased to it, behind one endpoint, `POST /v1/systemone`.
- **Price:** **$0.042 per million input tokens; output tokens are free.**
- **Rate limits:** 100K tokens/s and 80 requests/s.
- **Context:** 64k tokens per request, of which 32k covers the state plus the longest question. Resellers advertise "32K", which is a definitional difference rather than a contradiction ([TypeSafe models](https://docs.typesafe.ai/models.md)).
- **Questions:** Choice takes up to 255 options and Score takes 2–10 levels ([TypeSafe API](https://docs.typesafe.ai/api.md)).

The model was not updated this week. The activity was ecosystem work:
- Python SDK v0.7.2 on 26 Sept, adding an `http2` extra ([changelog](https://docs.typesafe.ai/sdk/python/changelog.md)).
- A `WorkflowEvals` repository created on 28 Sept ([GitHub](https://api.github.com/orgs/typesafe-ai/repos)).
- An n8n node on 30 Sept, free on n8n Cloud until 10 Oct ([n8n](https://community.n8n.io/t/typesafes-jev-is-now-in-n8n-free-on-cloud-via-gateway-credits-until-october-10/317957)).
- A refreshed known-limitations page, reviewed 2 Oct ([jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13)).

Adoption signals are strong but come from partners:
- Vercel says **about 13% of paid AI Gateway teams used Jev within 24 hours** [vendor] ([Vercel](https://vercel.com/blog/ai-gateway-jev-model-launch)).
- The Python SDK logged **947,883 downloads in the last week** ([pypistats](https://pypistats.org/api/packages/typesafe-sdk/recent)).

The $40M DCVC seed round appears only in aggregators, and a reported "$10 billion" valuation is **[unverified]** and implausible for a seed round ([Startup Fortune](https://startupfortune.com/amazon-releases-its-own-jev-clone-as-the-ai-decision-model-race-turns-into-a-pile-up/)).

The **OpenAI Decisions API** was announced at DevDay on 29 September as a "version of GPT-6 Luna". It answers user-defined questions that have finite, predefined answers, and takes text or images. OpenAI's own chart shows **about 150 ms versus 1.6 s** for a normal Luna call [vendor] ([The Decoder](https://the-decoder.com/openai-expands-codex-and-its-api-at-devday-with-security-scans-a-decisions-api-and-ultrafast/)). It is in limited preview, with broad release promised "in the coming days" ([InfoQ](https://www.infoq.com/news/2026/10/openai-devday-2026/)).

Four days later there is still no public schema, price, context limit or data-handling terms, and the GPT-6 Luna model page does not mention the API ([OpenAI Luna page](https://developers.openai.com/api/docs/models/gpt-6-luna)). Whether it returns per-option probabilities, the property that defines the category, is unresolved:
- TechCrunch and The New Stack say it does ([TechCrunch](https://techcrunch.com/2026/09/30/openais-jev-clone-could-help-the-frontier-lab-stop-its-swarming-agents/)).
- OpenAI's own wording says only "decisions" ([ModelSystem.One](https://modelsystem.one/runtimes/openai-decisions-api/)).
- TypeSafe's founder said it "seems to be luna with constrained decoding" [community] ([DevFeed](https://devfeed.tech/articles/openai-ships-decisions-jev-builders-pick-it-apart-62584)).

The only public code found that uses the API is in OpenAI's Codex repository: an opt-in "Decisions comparison for Guardian V2", merged 1 October ([codex #50099](https://github.com/openai/codex/pull/50099)). That suggests OpenAI is positioning it for agent guarding.

**Cloudflare Clef** (on a Qwen 27B base) and **Clef-flash** (on a Qwen 9B base) went GA on Workers AI on 1 October, with Apache-2.0 weights.
- **Compatibility and training:** Cloudflare calls them "fully API-compatible" with Jev and trained them with label-smoothed cross-entropy plus a Brier loss.
- **Latency [vendor]:** median **209.3 ms and 38.8 ms**; p95 238.6 ms and 122.4 ms ([Cloudflare](https://blog.cloudflare.com/clef-decision-models/)).
- **Hosted price:** **$0.24 per million input tokens** for Clef, about 6x Jev.
- **Limits:** 65,536-token context; text, JSON, images or video, with at most 4 images; 1–64 questions per request; request bodies up to 13 MiB ([Workers AI docs](https://developers.cloudflare.com/workers-ai/models/clef/)).

Clef-flash's $0.09/M price is **[unverified]** ([Developers Digest](https://www.developersdigest.tech/blog/cloudflare-clef-decision-models-2026)). Reports calling Clef "free" refer only to the weights.

**AWS Strands Decider 2B** is open and local-only, with no Bedrock endpoint.
- **Architecture:** a Qwen3.5-2B torso, a pointer head of about 1M parameters, and a rank-16 LoRA.
- **Latency [vendor]:** about **115 ms median on an RTX 3090** and 153 ms on an M3.
- **Ranking claim [vendor]:** "3rd of 33 in the 2B class" on JevBench ([Strands](https://strandsagents.com/blog/introducing-strands-decider/)).
- **Model-card figures [vendor]:** JevBench public 167/231, Brier 0.348, ECE 0.050.
- **Bundled server:** a `/v1/systemone` server bound to 127.0.0.1 with no authentication ([HF card](https://huggingface.co/StrandsAgents/strands-decider-2B-hobson-v19)).

Reseller surfaces multiplied:
- **OpenRouter** serves Jev on `/api/v1/systemone` and on an alpha `/api/alpha/decisions`, a name that collides with OpenAI's product ([OpenRouter](https://openrouter.ai/docs/guides/community/jev)).
- **Runware** hosts Jev and Laya on `/v1/systemone`, with **Laya at $0.020/M, free until 12 October** ([Runware](https://runware.ai/blog/jev-laya-and-the-emerging-role-of-decision-models)).

Searches found **no decision-model API from Google, Anthropic, Microsoft, Cohere, Mistral, Groq, Fireworks, Together or Cerebras**. Absence from search results does not prove absence ([digitalapplied](https://www.digitalapplied.com/blog/ai-model-releases-september-2026-tracker)).

| Hosted product | Status (10-03) | Input price (output free) | Latency | Probabilities / calibration | Key limits | Evidence |
|---|---|---|---|---|---|---|
| Jev `jev-1.13.0` (TypeSafe) | GA since 09-15 | $0.042/M | 70–500 ms [vendor]; P50 0.21 s / P95 0.34 s / P99 0.75 s on OpenRouter ([Firecrawl](https://www.firecrawl.dev/blog/openai-decisions-api-vs-jev)) | Probability per option plus `confidence`; "RLCD" training; no published ECE | Text only; Choice ≤255 options; Score 2–10 levels; 64k/32k context | Official docs |
| Decisions API (OpenAI, GPT-6 Luna) | Limited preview since 09-29 | Unpublished (Luna's $0.10/$0.50 is only a proxy) | ~150 ms vs 1.6 s [vendor demo] | Disputed | Text and images; schema unpublished | Press and secondary |
| Clef / Clef-flash (Cloudflare) | GA 10-01, Apache-2.0 weights | $0.24/M; flash $0.09/M [unverified] | Median 209 / 39 ms [vendor] | All options; Brier + label-smoothed CE training; no ECE | 64k context; 1–64 questions; ≤4 images; Jev-compatible | Official docs |
| Strands Decider 2B (AWS) | Open, local only, 10-01 | Self-host | ~115 ms on RTX 3090 [vendor] | ECE 0.050 on JevBench public [vendor] | Yes/no and choice | Blog and HF card |
| Laya via Runware | Live 09-28 | $0.020/M, free to 10-12 | 39.5 ms (T4, local) [vendor] | Runware warns probabilities must be validated against outcomes | — | Runware blog |

### Open weights moved from 400M encoders to 27B decision heads

Hugging Face name searches found **127 "jev" repos created in the window**, plus 38 "decider" and 20 "typed-decisions" repos ([HF API](https://huggingface.co/api/models?search=jev&limit=1000)). The models that matter split into two groups:
- **Large backbones with decision heads**, mostly Qwen3.5/3.8 or Gemma-4 bases and often multimodal. Clef, pplx-decider, Intern-Decision, JEV-27B-VL and StartLux are examples. They target accuracy at 20–500 ms on H100/H200-class GPUs.
- **Small encoders under 500M parameters** that target CPU or browser latency. Laya, Julia-1 and bekko are examples.

Laya is in the second group, and that group lost momentum this week.

| Model (org) | Released | Base / size | License | Headline claim | Signal |
|---|---|---|---|---|---|
| [Laya](https://huggingface.co/convaiinnovations/laya) (Convai) | 09-18; weights unchanged since 09-24 | ModernBERT-large 421M; mmBERT-base 322M | Apache-2.0 | Base checkpoint scores 0.362 zero-shot on typed-decisions; 0.766 only after fine-tuning on that benchmark's own train split; 33 ms on a T4 [vendor] | 5,053 HF likes; 30,411 GitHub stars |
| [Clef](https://huggingface.co/Cloudflare/clef) / [Clef-flash](https://huggingface.co/Cloudflare/clef-flash) | 09-30 (HF) | Qwen3.8-27B / Qwen3.5-9B | Apache-2.0 | BANKING77 94.2 vs Jev 79.7; GPQA 48.0 vs Jev 78.3 [vendor] | 941 / 339 likes |
| [pplx-decider-v1-27b](https://huggingface.co/perplexity-ai/pplx-decider-v1-27b) | 10-01 | Qwen3.8-27B | Apache-2.0 | 85.71% vs Jev 84.51% across 11 benchmarks [vendor] | 66 likes |
| [Intern-Decision-4B](https://huggingface.co/internlm/Intern-Decision-4B) (+0.8B, 2B) | 09-26 | Qwen3.5-4B, multimodal | Apache-2.0 | 90.02 vs Jev 88.74 across 7 suites; ECE 0.065; 44 ms on an RTX 4090 [vendor] | 76 likes |
| [JEV-27B-VL](https://huggingface.co/autotrust/JEV-27B-VL) (AutoTrust) | 09-30 | Qwen3.8-27B + adapter | Apache-2.0 | ECE 0.0009, AUROC 0.995 [vendor, unverified]; 2–256 options | 308,531 downloads |
| [Decision-2.0-Lux-9B](https://huggingface.co/vllm-sr/Decision-2.0-Lux-9B) (vLLM Semantic Router) | 09-29 | Qwen3.5-9B | Apache-2.0 | 18.4 ms median for a single question [vendor] | 7 likes |
| [StartLux-Decision](https://huggingface.co/startlux-models/StartLux-Decision-4B) 0.8B–35B | 09-29 / 10-01 | Qwen3.5 dense and MoE | **CC-BY-NC-4.0** | 4B scores 204/231 on JevBench public [vendor] | Low |
| [Kev-4B](https://huggingface.co/jaredpalmer/kev-4b) / Kev-9B (background) | 09-19 | Qwen3.5 + LoRA + pointer head | Apache-2.0 | Among the most accurate open engines in local-jev-bench [independent] | 16,100 downloads |
| [decider-2b](https://huggingface.co/Mapika/decider-2b) / [decider-12b](https://huggingface.co/Mapika/decider-12b) | 09-16 / 09-29 | Qwen3.5-2B / Gemma-4-12B | Apache-2.0 (12B also inherits Gemma terms) | decider-12b ranks first on AIM-Decision [independent] | 285,776 downloads (2B) |
| [Eikos-27B](https://huggingface.co/caiovicentino1/Eikos-27B) (background) | 09-23 | Qwen3.8-27B | MIT | Best open model on LangWatch [independent] | 32 likes |
| [openjev](https://huggingface.co/openjev/openjev) (background) | 09-20 | Qwen3.5 27.4B | **CC-BY-NC-4.0** | 84.0% vs Jev 85.4% on 10,000 questions [vendor] | 4,821 downloads |

**Laya** is the most-liked open System One model and the weakest at zero-shot.
- **Releases:** PyPI reached **0.3.25 on 3 October after five releases this week**, all of them runtime and serving changes. The Hugging Face weights have not changed since 24 September ([PyPI](https://pypi.org/pypi/laya/json); [HF commits](https://huggingface.co/convaiinnovations/laya/commits/main)).
- **The card's own positioning:** "Laya is a fast base to specialise, not a zero-shot decision engine" ([HF card](https://huggingface.co/convaiinnovations/laya)).
- **Accuracy in competitors' tables:** Laya ranks last or near last almost everywhere. InternLM scores it at 57.77 against Jev's 88.74 ([Intern-Decision card](https://huggingface.co/internlm/Intern-Decision-4B)). Cloudflare's run puts it lowest on most benchmarks.
- **Speed in the same tables:** Laya is the fastest model, at 5.8 ms median against Jev's 524.1 ms in Cloudflare's run ([Clef card](https://huggingface.co/Cloudflare/clef)).
- **Fine-tunes:** dozens of Laya fine-tunes appeared in the window, almost all with zero downloads and no evaluations.
- **Conversions that matter:** format conversions such as `ggml-org/Laya-GGUF` (1 Oct, 4,153 downloads) are the derivatives with real uptake ([HF](https://huggingface.co/ggml-org/Laya-GGUF)).

Shared training data now exists at scale ([typed-decisions](https://huggingface.co/datasets/LocalLLaMA/typed-decisions); [jev-distill-corpus-v3](https://huggingface.co/datasets/SargeDev/jev-distill-corpus-v3); [jev-decisions-v1](https://huggingface.co/datasets/samatv256/jev-decisions-v1)):
- the typed-decisions benchmark (Apache-2.0, 25,325 downloads),
- a 740,957-row corpus distilled from Jev,
- a 12M-record agent-decision set (CC-BY-4.0).

## Jev leads decision models on evidence, but not on every axis

### Vendor headline numbers measure agreement with LLMs, not ground truth

TypeSafe's "193.6x faster, 444.6x cheaper" comes from its own workflow evals. In those evals the *reference answer is the average of GPT-6 Astra and Claude Fable 5.1*. Scores are agreement with model-generated labels, not human-checked accuracy.

On that measure **Jev reaches 67.8% agreement, against 74.1% for GPT-5.6 Sol and 73.1% for Opus 5** ([BenchLM](https://benchlm.ai/blog/posts/what-is-jev)). GPT-5.6 Terra reaches the same ~68% at $0.03 and 10 s per case ([Arize](https://arize.com/blog/typesafe-jev-llm-judge/)). Against that equal-accuracy LLM, Jev is about 25x faster and 75x cheaper.

The headline multiples come from dividing by the slowest model (Sonnet 5 at 78.1 s per case) and the most expensive one (Opus 5 at $0.1761 per case). That is our inference from BenchLM's figures. Users report a **median real-world speedup of about 7x and cost savings of about 30x** ([InfoQ](https://www.infoq.com/news/2026/10/typesafe-ai-jev-released/)). TypeSafe says it deliberately skips public leaderboards ([BenchLM](https://benchlm.ai/blog/posts/what-is-jev)).

Convai's comparison chain is circular. Laya's 0.766 on typed-decisions comes from a checkpoint fine-tuned on that benchmark's train split. The Jev figure it beats, 0.727, is "third-party published, not measured here" ([laya-typed-decisions](https://huggingface.co/convaiinnovations/laya-typed-decisions)). openJev-verdict-2.0 then copies the same Jev number from Laya's suite ([GitHub](https://github.com/Heman10x-NGU/openJev-verdict-2.0)).

The new corporate entrants also report only their own runs:
- Cloudflare's numbers are an "internal run" of Decision Index 0.2.1.
- Perplexity's were "measured through the Perplexity API".

Cloudflare earns some credibility by publishing its losses. Jev beats Clef on GPQA (78.3 vs 48.0), MMLU-Pro (82.7 vs 65.9) and When2Call (81.0 vs 72.4) ([Clef card](https://huggingface.co/Cloudflare/clef); [Developers Digest](https://www.developersdigest.tech/blog/cloudflare-clef-decision-models-2026)).

### Independent benches put Jev at or near the top, never alone

Seven independent or semi-independent evaluations appeared between 20 September and 2 October. They agree on a three-tier picture:
- Jev leads among hosted, zero-shot decision models.
- Open fine-tunes tie it on most classification tasks.
- Frontier LLMs win on reasoning-heavy and agentic decisions, at 10–400x the cost.

| Benchmark (date) | Method | Key results | What it shows |
|---|---|---|---|
| LangWatch ([09-25](https://langwatch.ai/compare/jev-vs-all)) **[independent]** | 11 tasks, up to 1,000 items each, bootstrap CIs | **Jev 81.9%** vs Eikos-27B 80.0%. Prompt injection: Jev 94.6 vs 94.2 (tie). Open models "caught up on 8 of 11 tasks" | Jev has the best average, but its lead is narrow |
| DecideBench ([09-28–30](https://github.com/choyiny/decidebench)) **[independent]** | 400 contrastive decisions, 23 models | DeepSeek-V4-Flash 99.8% ($197/M tasks, 1,866 ms). **Jev 98.0% ($32.26, 639 ms)**. Kev-4B 78.2%. Laya 59.8% | Jev is the top decision model; an LLM tops the field |
| AIM-Decision ([10-01/02](https://aimultiple.com/decision-models)) **[independent]** | 1,655 items with real labels (GitHub, FDA, arXiv), plus 50 browser tasks | decider-12b 54.4, Kev-9B 49.1, **Jev 47.9**, stock Laya 19%. Browser tasks: GPT-6 Astra 47/50, Jev 12–20/50, Laya 0/50 | Open fine-tunes beat Jev here; LLMs dominate agentic tasks |
| local-jev-bench ([09-30](https://github.com/tak-bro/local-jev-bench)) **[independent]** | Open models only, M3 Max | typed-decisions: Winnow-E4B 73%, Kev-9B 72%. Option-order flip rate: Laya 31%, Kev-9B 10% | Large order-bias spread between open models |
| JEV-as-a-Judge, arXiv [2609.26550](https://arxiv.org/abs/2609.26550) (v3 09-29) **[independent]** | 16 judges | Jev within 3 points of GPT-6 at 0.36% of the fee and 0.15 s. A confidence cascade beats GPT-6 by 0.9 points at 41% of the fee | Accept-or-escalate cascades work |
| Beri phishing ([09-20](https://www.beri.net/article/typesafe-jev-typed-decision-model-calibration-decomposition-shadow-eval)) **[independent]** | 2,000 emails | One question: **Jev 62.6% vs Claude Haiku 4.5 81.3%**. Five atomic questions plus logistic regression: 95.0% ("the 95% is not Jev") | Decomposing into atomic questions and adding your own labels matters more than the model |
| Every hands-on test, via [decisionsapi.cc](https://decisionsapi.cc/vs-jev) **[community, unverified]** | n=78 steps | Decisions API 76/78 vs Jev 73/78 | The only data on OpenAI's API; too small to rank |

| Axis | Current leader(s) | Evidence quality |
|---|---|---|
| Hosted, zero-shot, broad coverage | **Jev 1.13** | Independent, from several benches |
| Accuracy on specific classification tasks (self-hosted) | Kev-9B/4B, Eikos-27B, decider-12b | Independent but small and task-specific |
| Reasoning-heavy and agentic decisions | Frontier LLMs (GPT-6 Astra, DeepSeek V4 Flash) | Independent |
| Hosted latency | Clef-flash, 38.8 ms median | Vendor only |
| Self-hosted latency | Laya (about 33 ms on a T4); Decision-2.0-Lux, 18.4 ms | Vendor numbers; Laya also measured independently on an M3 |
| Hosted price per token | Laya on Runware ($0.020/M), then Jev ($0.042/M) | Vendor price lists |
| Audited calibration | **Nobody** | No vendor publishes ECE or a reliability diagram |
| OpenAI Decisions API | Unrated | One informal test |

### Latency depends on where you measure from

Measured Jev latency ranges from about **97 ms p95 (LangWatch, from Denmark)** to **639 ms (DecideBench)** ([LangWatch](https://langwatch.ai/compare/jev-vs-all); [DecideBench](https://github.com/choyiny/decidebench)). Other measurements fall between:
- 239 ms median from France, against 687 ms for Claude Haiku ([Beri](https://www.beri.net/article/typesafe-jev-typed-decision-model-calibration-decomposition-shadow-eval)).
- 524.1 ms in Cloudflare's own run ([Clef card](https://huggingface.co/Cloudflare/clef)).
- 348 ms in Red Hat's benchmark, about 56 ms of which was transatlantic network time ([Red Hat](https://developers.redhat.com/articles/2026/10/02/benchmarking-ai-decision-models-against-traditional-guardrails)).

Region, state size, question count and any proxy in the path explain most of the spread, so no single figure should be quoted without its conditions.

Laya's speed advantage holds only on warm GPUs with short states:
- 32.8 ms for one question on a T4 [vendor].
- 36.6 ms on short inputs but **292.9 ms on long typed-decision states** on an M3 Max [independent] ([local-jev-bench](https://github.com/tak-bro/local-jev-bench)).
- A cold CPU prediction took a median of **49.4 s** on a 4-vCPU VPS ([Flowtivity](https://flowtivity.ai/blog/laya-open-source-jev-alternative/)).

On cost, Jev runs about **$0.039 per 1,000 decisions** ([AIMultiple](https://aimultiple.com/decision-models)).

### Calibration is the claim nobody has audited

"Calibrated" means something different for each vendor.
- **Jev:** `confidence` is a transformation of the distribution, `(p_max − 1/n)/(1 − 1/n)` for Choice, not an empirically calibrated probability. TypeSafe publishes no ECE and tells users to set thresholds for their own domain ([TypeSafe confidence](https://docs.typesafe.ai/confidence)).
- **Laya:** `confidence` is 1 minus the normalized entropy, so thresholds do not transfer between the two models ([Laya README](https://github.com/NandhaKishorM/laya)).
- **Clef:** trained with a Brier loss, but publishes no ECE.
- **OpenAI:** has not said whether it returns probabilities at all.

The independent calibration data on Jev is mixed.
- **Synthetic support tickets:** a 900-ticket study measured **ECE 0.107**. Yes/no answers were *under*confident and Choice and Score answers *over*confident. On unknowable tasks Jev was right 44.7% of the time while assigning an average probability of 0.74. The author warns that "your calibration fit expires silently the day the alias moves" ([Beri](https://www.beri.net/article/typesafe-jev-typed-decision-model-calibration-decomposition-shadow-eval)).
- **Spam:** on 18,514 emails Jev is well calibrated at the extremes. Scores of 0.9 or higher were 99.9% spam, but only 38% of the 0.5–0.6 band was spam ([Arize](https://arize.com/blog/typesafe-jev-llm-judge/)).
- **Negation pairs:** across 480 pairs, P(X) + P(not X) misses 1 by **0.064** on average ([arXiv 2609.33209](https://arxiv.org/html/2609.33209v1)).
- **Contrast with a generative model:** a blogger found that stock GPT-6 Luna was right only **68%** of the time when it claimed at least 99% confidence, against Jev's 98.9% **[community]**. That test used standard Luna, not the Decisions API ([anth.us](https://anth.us/blog/openai-decisions-api-preview/)).

Laya ships overconfident, by its own documentation:
- Per-type temperature refitting cuts mean ECE from 0.466 to 0.081.
- The fine-tuned checkpoint's temperature was fitted on *training* data.
- The English checkpoint scores 0.000 accuracy on Khmer at 0.952 confidence ([HF card](https://huggingface.co/convaiinnovations/laya)).

The widely circulated "Laya ECE 0.081 vs Jev 0.144 or 0.246" comparison mixes numbers from different parties, measured on different items ([Flowtivity](https://flowtivity.ai/blog/laya-open-source-jev-alternative/)).

Two failure modes cut across models:
- **Option-order bias.** TypeSafe documents a pull toward the first option, and local-jev-bench measured flip rates from 7% to 31%.
- **Injection through `state`.** TypeSafe's limitations page says "jev-1.13 does not treat it as hostile by default" ([jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13)).

## `/v1/systemone` became a de facto standard without a spec

### Ollama, llama.cpp and SGLang shipped native endpoints this week

The biggest infrastructure change of the week was mainstream runtimes adopting TypeSafe's request shape.
- **Ollama v0.35.0** (28 Sept) "supports decision models through `/v1/systemone`, based on TypeSafe's Jev API", starting with Bespoke Labs' Nimble and Together AI's Tev1 ([Ollama](https://github.com/ollama/ollama/releases/tag/v0.35.0)).
- **llama.cpp** merged PR #29818 on 2 October, serving Laya, Julia-1, lev, openjev and Kev. A model-agnostic follow-up, #29832, is still open ([PR #29818](https://github.com/ggml-org/llama.cpp/pull/29818); [ggml blog](https://huggingface.co/blog/ggml-org/decision-models-in-llamacpp)).
- **SGLang** merged pplx-decider serving on 3 October ([SGLang #42183](https://github.com/sgl-project/sglang/pull/42183)).
- **vLLM** has only open items. RFC #59365 proposes a separate **`/v1/decisions`** path with systemone compatibility, an early sign of divergence ([vLLM RFC](https://github.com/vllm-project/vllm/issues/59365)).

Gateways adopted the same shape.
- **LiteLLM v1.103.0** (stable 28 Sept) proxies hosted Jev at `LITELLM_PROXY_BASE_URL/typesafe/v1/systemone`, with logging and cost tracking but no streaming. It also ships a "Relevance-Based Compaction" guardrail that blanks out tool results Jev scores as irrelevant ([LiteLLM blog](https://docs.litellm.ai/blog/typesafe_jev); [guardrail docs](https://docs.litellm.ai/docs/proxy/guardrails/typesafe)). The pass-through targets TypeSafe's hosted API. Support for self-hosted backends is not documented ([pass-through docs](https://docs.litellm.ai/docs/pass_through/typesafe)).
- **OpenRouter** exposes `/api/v1/systemone` alongside its own alpha `/api/alpha/decisions` ([OpenRouter](https://openrouter.ai/docs/guides/community/jev)).

There is **no neutral spec**. ModelSystem.One's "spec" page lists catalog inclusion criteria, not a wire format ([ModelSystem.One](https://modelsystem.one/spec/)). Variants are already drifting apart in three ways:
- Laya defines `confidence` differently from Jev.
- vLLM and SGLang propose `/v1/decisions` paths.
- OpenAI's schema is unknown.

| Infrastructure | What shipped | Date | Maturity |
|---|---|---|---|
| Ollama | Native `/v1/systemone` (Nimble, Tev1) | 09-28 | High (major runtime) |
| llama.cpp | `/v1/systemone` for Laya, Julia-1, lev, openjev, Kev | Merged 10-02 | High; model-agnostic version pending |
| SGLang | pplx-decider on `/v1/systemone` | Merged 10-03 | Medium |
| vLLM | PR #59299; RFC for `/v1/decisions` | Open | Not shipped |
| LiteLLM | Jev pass-through plus a compaction guardrail | v1.103.0, 09-28 | Hosted Jev only |
| `laya[serve]` | Jev-shaped server with `/batch` and `LAYA_JEV_STRICT` | 0.3.24–0.3.25, 10-02/03 | De facto open reference |
| Ollaya / AnyJev / von | Multi-model servers; AnyJev turns any LLM into a decision model | Releases in window | About two weeks old; 800–1,200 stars ([Ollaya](https://api.github.com/repos/ollaya-dev/ollaya); [AnyJev](https://api.github.com/repos/nokia-applied-research/AnyJev)) |
| About 75 smaller repos | "systemone" repos created since 09-26 | In window | Mostly single-maintainer ([GitHub search](https://api.github.com/search/repositories?q=systemone+created:%3E=2026-09-26)) |

### Laya shipped five releases of operational hardening, not model gains

Laya's five releases this week, 0.3.21 through 0.3.25, matter more for deployers than for accuracy ([PyPI project](https://pypi.org/project/laya/); [Laya README](https://github.com/NandhaKishorM/laya)):

| Version | Date | Changes |
|---|---|---|
| 0.3.21 | 09-27 | Opt-in `min_confidence` abstention |
| 0.3.22 | 09-29 | Per-checkpoint SHA-256 verification in the TypeScript SDK; per-call controls forwarded through `/v1/systemone` |
| 0.3.23 | 10-01 | **Closed an information leak:** `/health` no longer exposes checkpoint names, revision SHAs or device state to unauthenticated callers (#812); added `SECURITY.md`; INT8 ONNX export now defaults to per-tensor quantization |
| 0.3.24 | 10-02 | Abstention thresholds per option count; histogram-binning calibration; Brier and AURC metrics; `LAYA_JEV_STRICT` for strict Jev clients |
| 0.3.25 | 10-03 | Unified `Agent(backend=…)`; the MCP server can call a running server through `LAYA_BASE_URL` |

The ONNX change in 0.3.23 is a quiet warning: per-channel quantization had **"collapsed the decision model to 32 percent agreement with eager"**.

Packaging changed too. The standalone **`laya-serve` PyPI package is deprecated in favor of `pip install "laya[serve]"`**, and the old package collides with the new binary ([PyPI laya-serve](https://pypi.org/project/laya-serve/)). The server binds 0.0.0.0 with **no authentication unless `LAYA_API_KEY` is set** ([HF card](https://huggingface.co/convaiinnovations/laya)). The bundled `laya-evals` CLI gates regressions on `--min-accuracy`, `--max-ece` and a baseline tolerance, and writes reproducible reports ([PyPI](https://pypi.org/project/laya/)).

### Framework connectors target hosted Jev first

The week's first-party integrations all target TypeSafe's hosted API, and all are pre-1.0 or experimental:
- **Microsoft Agent Framework Python 1.20.0** (2 Oct) shipped an `agent-framework-typesafe` connector. .NET PRs propose an `IDecisionClient` abstraction ([MAF releases](https://api.github.com/repos/microsoft/agent-framework/releases)).
- **Vercel's `@ai-sdk/typesafe-ai`** had four releases between 28 and 30 Sept and 485,346 weekly downloads ([npm](https://registry.npmjs.org/@ai-sdk%2ftypesafe-ai)).
- **LangChain.js `@langchain/typesafe`** 0.0.2 shipped on 1 Oct ([npm](https://registry.npmjs.org/@langchain%2ftypesafe)).
- **Pydantic AI** now has a vendor-neutral `DecisionModel` base ([PR #8696](https://github.com/pydantic/pydantic-ai/pull/8696)).
- **LlamaIndex and CrewAI** have no first-party integration; Laya's extras cover them.

TypeSafe's own **`system-one-adapter`** (MIT) emulates the API with OpenAI, Anthropic or Gemini behind it. Its probabilities are LLM-verbalized, not logits, so it is a benchmarking baseline rather than a calibrated fallback ([adapter README](https://github.com/typesafe-ai/system-one-adapter-python)).

Supply-chain hygiene needs attention. A PyPI package named `typesafe-ai` is a shim published by an individual, not under TypeSafe's support address ([PyPI](https://pypi.org/pypi/typesafe-ai/json)). General structured-output libraries such as Outlines, Instructor, BAML and DSPy constrain format but do not return calibrated per-option probabilities.

## Security guards: a 184M DeBERTa still matches decision models on injection

### Two independent benchmarks and seven preprints reset expectations

No major lab released a guard model this week: Meta, IBM, NVIDIA, Google, OpenAI, AllenAI, ProtectAI and Qwen shipped none. Qwen3Guard-Stream's 27 September modification was to a 2025 model ([HF](https://huggingface.co/api/models/Qwen/Qwen3Guard-Stream-4B)). The week's signal came from evaluations instead.

Red Hat's 2 October benchmark is the most important (rated A−: third-party relative to TypeSafe and Convai, though Red Hat publishes two of the well-ranked baselines). It tested nine guardrails on class-balanced prompt-injection and toxicity sets ([Red Hat](https://developers.redhat.com/articles/2026/10/02/benchmarking-ai-decision-models-against-traditional-guardrails)).

| Model | Prompt-injection accuracy | PI median latency | Content-safety accuracy |
|---|---|---|---|
| Qwen3.6-35B (LLM judge) | 89.31% | 312.5 ms | 85.47% |
| deberta-v3-base PI v2 (184M) | **89.01%** | **54.1 ms (CPU)** | — |
| DiffusionGemma | 87.72% | — | 85.53% |
| Jev 1.13.0 | 86.35% | 348.1 ms | **86.20%** |
| Laya | 85.44% | 119.3 ms | **57.87%** |
| granite-guardian-hap-125m | — | — | 80.27% (33.2 ms) |

Tuned policies raised Laya's accuracy by 17.83 points but cut Jev's by 3.67. Red Hat concludes that decision models "do not reliably outperform LLM-as-a-judge, pre-trained predictive models, or open source decision models in speed or accuracy."

The individual **guardrail-showdown** repo (1 Oct) reached a similar result **[independent, small]** ([GitHub](https://github.com/AjeyDS/guardrail-showdown)). On 942 prompts, ProtectAI's classifier detected **86.4% at 2.8% false positives in 15.5 ms**, against **Jev's 79.3% at 3.6% in 258 ms**. Jev wins after threshold tuning (94.6% vs 92.4%) and on the 156-prompt hard set (80.0% vs 52.5%). Lakera's partial run (390 checks before the quota ran out) showed a **32.1% false-positive rate**.

Preprints from the same days undercut the "calibrated probabilities" selling point for security use.
- **arXiv 2609.33401** (27 Sept) evaluates Jev, Laya, Decider and Bespoke Nimble on agent-security decisions ([arXiv](https://arxiv.org/abs/2609.33401)). It finds that:
  - strong aggregate calibration hides **attacks classified as safe with high confidence** inside specific attack groups;
  - adapted configurations do not consistently beat their base models;
  - separate allow/block thresholds raise automation "mainly through more blocks".
- **arXiv 2609.36477** finds that adversarial attacks degrade guard calibration **"by an order of magnitude"**, even where base models remain uncertain on the same inputs ([arXiv](https://arxiv.org/abs/2609.36477)).
- **"Silent Failures"** shows that an indirect-injection harness reported 21.7% attack success where the true argument-level rate was 1.2%. Many published agent-IPI numbers may therefore be inflated ([arXiv 2609.32691](https://arxiv.org/abs/2609.32691)).
- **A multi-turn study** finds the safe-response rate falls from 85–100% at turn 1 to **15–44% by turn 101** ([arXiv 2609.38357](https://arxiv.org/abs/2609.38357)).
- **LLaDA-Guard** reports ECE 0.0875 against Qwen3Guard's 0.1384 ([arXiv 2609.33634](https://arxiv.org/abs/2609.33634)).
- **AdaGuard** trains policy-conditioned agent-trajectory guards; its 4B model scores 89.30% on its own AdaptiveSafety set and 71.82% on DynaBench ([arXiv 2609.34241](https://arxiv.org/abs/2609.34241)).
- **COGNIT-Guard** cascades a CPU gatekeeper into a 322M Laya. It reports 98.85% on its own benchmark but only 56.81–65.05% out of distribution ([arXiv 2609.33671](https://arxiv.org/abs/2609.33671)).

No new OWASP-aligned guard evaluation suite appeared.

### The Laya guard wave is honest about its gaps

Within two weeks of Laya's release, the community published at least six Laya-based security guards. They share one recipe: typed `noul`/`choice` questions with fixed wording, post-hoc temperature scaling, and allow/review/block zones. That is the same design as TypeSafe's own guardrails cookbook, whose example strict policy sends inputs to review at ≥0.35 and acts at ≥0.70 ([TypeSafe cookbook](https://docs.typesafe.ai/cookbooks/llm_guardrails.md)).

The most informative release is **safe-laya** (2 Oct), because it publishes its gap to Jev on identical out-of-distribution sets ([HF](https://huggingface.co/ottosulin/safe-laya)):
- in-distribution accuracy is 0.903;
- attack recall is 0.749 against Jev's 0.893;
- NotInject accuracy is **0.655 against 0.979**;
- the false-positive rate on XSTest's safe prompts is **0.80**.

| Guard (date) | Base | License | Target | Reported result | Evidence |
|---|---|---|---|---|---|
| [safe-laya](https://huggingface.co/ottosulin/safe-laya) (10-02) | Laya 421M, full fine-tune | Apache-2.0 | Injection, jailbreak and harmful requests across prompts, documents and tool outputs | See above: trails Jev badly on over-defense | B (self-run, external sets) |
| [laya-mm-guard-v3](https://huggingface.co/OidoStudio/laya-mm-guard-v3-gguf) (10-01) | Laya multilingual, GGUF | Apache-2.0 | Direct and indirect injection, multilingual | F1 0.949 on public test splits; F1 0.907 on an independent hand-written set (n=89); ECE 0.022→0.006 after temperature scaling; ~85 ms on CPU via a Go + llama.cpp `/v1/systemone` server. Misses white-text résumé instructions and markdown-image exfiltration | B |
| [safe_laya](https://huggingface.co/Dipto084/safe_laya) (10-03) | laya-typed-decisions | Apache-2.0 | Multi-turn jailbreak input filter | Accuracy 0.879, AUROC 0.944, ECE 0.050. Against AutoDAN-Turbo, successful jailbreaks fell from 103/120 to 15/120. Over-refusal not measured | B/C |
| [sentrygate-laya](https://huggingface.co/mnjkshrm/sentrygate-laya) (10-03) | Base Laya, INT8 ONNX | Apache-2.0 | On-device injection | ROC-AUC 0.869 on deepset | C |
| [Ariadne-Laya-Injection](https://huggingface.co/GoatHerder/Ariadne-Laya-Injection) (09-28) | 1M adapter on frozen Laya | Apache-2.0 | Binary injection | 88.79% vs 99.14% for deepset's DeBERTa (n=116) | C |
| [Jeff-0.8B-guard](https://huggingface.co/mstrasser/Jeff-Qwen3.5-0.8B-guard) (10-01) | Jeff decision model + LoRA | — | Attack yes/no plus kind, including **exfiltration** | 98.4%, ECE 0.004 on synthetic in-distribution data; public benchmarks "not measured yet" | C |

### Purpose-built encoders were the strongest new guards

The strongest commercially usable newcomer is **Horizon-Labs' prompt-injection-guard-base v2.2** (2 Oct) ([HF](https://huggingface.co/Horizon-Labs/prompt-injection-guard-base)).
- **Packaging:** a 307.5M-parameter mmBERT model under Apache-2.0, with 8k context and ONNX builds. It is a drop-in replacement in LLM Guard for ProtectAI's model.
- **Headline result:** a macro average over external sets of **0.887**, against PIGuard 0.793, ProtectAI v2 0.637 and Prompt Guard 2 86M 0.540.
- **Over-defense and indirect injection:** NotInject 0.944; PIArena F1 0.969; LLMail-Inject phase-2 recall 0.998.
- **Caveat:** these are self-run comparisons with external sets and methods disclosed (rated B), and the card itself notes that baselines define "injection" differently.

Its sibling **content-safety-guard-small** (140.6M, 27 Sept) beats its Qwen3Guard-Gen-8B teacher on ToxicChat (0.776 vs 0.638) and on the OpenAI moderation set ([HF](https://huggingface.co/Horizon-Labs/content-safety-guard-small)).

Three other in-window guards are useful but restricted or narrow:
- **ZeroLeaks Shield Small** (118M, 2 Oct) scans **tool descriptions** as well as documents and tool results, which makes it the closest thing to an MCP tool-poisoning model this week ([HF](https://huggingface.co/ZeroLeaks/shield-small)). It is **CC BY-NC 4.0**. Its 84.3% balanced accuracy is for the model plus a rules layer and "is not an unseen evaluation", and the card says the score "is not a calibrated probability".
- **HS-Guard v10** (28 Sept) adds streaming response cut-off but is also non-commercial ([HF](https://huggingface.co/KrisLiu16/HS-Guard-v10)).
- **astrlink-guard** (30 Sept, Apache-2.0) detects PII and secrets ([HF](https://huggingface.co/QuantumNous/astrlink-guard)).

### Tool-call and MCP guards remain the weakest layer

The only agent-action guard with an external, human-labelled evaluation is **decider-2b-toolcall-guard-lora** (29 Sept) ([HF](https://huggingface.co/johannhartmann/decider-2b-toolcall-guard-lora)). Given the policy, goal, history and proposed call, it answers CONTINUE, ASK or BLOCK.
- It scores 0.80 accuracy on tools seen in training and 0.78 on unseen tools.
- On human-labelled **ASSEBench it reaches 0.65 accuracy and lets 53% of unsafe actions through**. Claude Sonnet 5 acting as the guard lets through 30%.
- It answers in 206 ms against Sonnet's 1,806 ms.
- Its own card says it is **"Not a security boundary."**

The Gleipnir trajectory monitors (2 Oct, MIT) publish no metrics ([HF](https://huggingface.co/Jazhyc/Gleipnir-4B-ToolTrajectories-InjectionAware)). laya-agentguard (23 Sept) "failed its own quality gate" ([HF](https://huggingface.co/Jojoarumugam/laya-agentguard)).

**No MCP-specific guard model appeared.** MCP-focused products from before the window are commercial: Rubrik's "OWASP MCP Top 10-aligned guardrails" (15 Sept) and AIR Security's agent firewall, which inspects tool definitions (1 Sept) ([Futurum](https://futurumgroup.com/insights/rubriks-mcp-launch-bets-on-agentic-ai-as-cyber-resiliences-next-layer/); [AI Learning Guides](https://ailearningguides.com/air-security-ai-agent-firewall-explained/)).

### Commercial guardrail vendors were quiet; OpenAI's entrant has no security docs

Changelogs for Azure Content Safety, Lakera, Google Model Armor (whose release-notes URL returned 404), AWS Bedrock Guardrails and Cloudflare showed **no verifiable in-window releases** ([Azure](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/whats-new); [Lakera](https://docs.lakera.ai/changelog.md)). Three commercial items did ship:
- **NVIDIA's Open Agent Safety Platform** (28 Sept) is a deny-by-default sandbox plus in-silicon telemetry. It names no classifier models ([NVIDIA](https://developer.nvidia.com/blog/nvidia-open-agent-safety-platform-a-reference-for-continuous-in-silicon-agent-monitoring/)).
- **BlackFog ADX Vision 2.0** claims "seven layers" of prompt-injection protection **[marketing]** ([Help Net Security](https://helpnetsecurity.com/2026/10/02/new-infosec-products-of-the-week-october-2-2026)).
- **The OpenAI Decisions API** has no security documentation. Security uses such as "does this text contain instructions aimed at the agent" appear only in third-party guides ([HF community blog](https://huggingface.co/blog/sora-2/what-is-openai-decisions-api-a-practical-guide-to)).

The threat picture kept moving: Zscaler documented in-the-wild indirect-injection campaigns that trick agents into making crypto payments ([SecurityWeek](https://www.securityweek.com/prompt-injection-attacks-trick-ai-agents-into-making-crypto-payments/)).

No model card in the window cites OWASP. The mapping below is ours, using the IDs in s1guard's [policy.yaml](../../src/s1guard/policy.yaml).

| This week's release | Closest s1guard risk | OWASP IDs as mapped in our policy |
|---|---|---|
| Horizon PI guard, safe-laya, laya-mm-guard-v3, Jeff guard | `prompt_injection`, `jailbreak`, `indirect_prompt_injection` | LLM01:2026; ASI01; MCP06:2025 |
| ZeroLeaks Shield Small (tool descriptions) | `tool_poisoning` | MCP03:2025; ASI04; LLM01:2026 |
| Jeff "exfiltration" class, astrlink-guard | `data_exfiltration`, `secret_leak`, `sensitive_data_disclosure` | LLM02:2026; MCP01/MCP10:2025 |
| decider-2b tool-call guard, Gleipnir, AdaGuard | `destructive_action`, `unrequested_action` | LLM03:2026; ASI02 |
| Horizon content-safety guards, HS-Guard | `harmful_content`, `harmful_compliance` | LLM01:2026 |
| Multi-turn decay study (2609.38357) | `multiturn_escalation` | LLM01:2026 |

## Implications for our s1guard project

The week mostly validates s1guard's design. The field converged on one `noul` question per risk, post-hoc calibration, three-zone policies and cascades to a stronger model. s1guard's context-aware questions match the newest agent guards: the system prompt for output checks, and the user's request for tool calls. decider-2b's guard conditions on policy, goal and history, and AdaGuard on user policies.

The same evidence warns where we are exposed. Our v4 headline is **94% of attacks blocked at 3% benign false positives** on our held-out smoke set, and the v4 table shows prompt injection at 48%, indirect injection at 68% and harmful replies at 49% ([README](../../README.md)). All of these numbers are in-distribution. safe-laya shows how a 0.90 in-distribution Laya guard can collapse to an 80% false-positive rate on XSTest, and the arXiv agent-security work shows that aggregate calibration hides confident misses inside specific attack groups.

Swapping models is now cheap. `SystemOneHTTPBackend` reads only `answers[qid]["noul"]` ([backends.py](../../src/s1guard/backends.py)). It can therefore point at Ollama, llama.cpp, `laya[serve]`, OpenRouter or Clef without code changes, provided the model supports `noul`. Laya's different `confidence` semantics do not affect us.

| Priority | Action | Why (evidence) |
|---|---|---|
| 1 | **Test v4 out of distribution, per attack group.** Candidate sets: NotInject, XSTest, PIArena/BIPIA, LLMail-Inject, ASSEBench, and AgentDojo run through the corrected "Silent Failures" harness. Licenses must fit our permissive-only rule. | safe-laya over-defense collapse; [arXiv 2609.33401](https://arxiv.org/abs/2609.33401); [2609.36477](https://arxiv.org/abs/2609.36477); [2609.32691](https://arxiv.org/abs/2609.32691) |
| 2 | **Add an encoder baseline or ensemble member for the input and tool_result stages:** Horizon PI guard v2.2 or ProtectAI DeBERTa v2 (Apache-2.0, ONNX). Consider Horizon content-safety-small or granite-guardian-hap-125m for content safety. Avoid non-commercial models: ZeroLeaks, HS-Guard, StartLux, openjev. | DeBERTa matched Jev and Laya on injection at 15–54 ms ([Red Hat](https://developers.redhat.com/articles/2026/10/02/benchmarking-ai-decision-models-against-traditional-guardrails)). Our weakest risks are exactly injection and content safety. |
| 3 | **Recalibrate per backend and per version, and pin model IDs.** Change the HTTP default from `jev-latest` to `jev-1.13.0`. Pin `laya` exactly (we currently allow `>=0.3.22`). Optionally adopt 0.3.24+ `fit_binning_map`, abstention thresholds and the `laya-evals` regression gates in CI. | Five Laya releases this week; the Jev alias moves silently ([Beri](https://www.beri.net/article/typesafe-jev-typed-decision-model-calibration-decomposition-shadow-eval)); thresholds don't transfer between models |
| 4 | **A/B the new open models through the HTTP backend:** Clef-flash (vendor median 38.8 ms, needs a GPU), Intern-Decision-4B, Kev-4B/9B, decider-2b. Retrain or recalibrate each on the 15k benchmark rather than trusting zero-shot. | Open fine-tunes tie Jev on most tasks ([LangWatch](https://langwatch.ai/compare/jev-vs-all)); Laya's weights are now among the oldest in the field |
| 5 | **Harden the tool_call stage.** Evaluate `unrequested_action` and `destructive_action` on ASSEBench and the MIT `toolcall-guard-v1` set. Keep `destructive_action` in monitor mode. Supporting decider-2b's CONTINUE/ASK/BLOCK would need `choice` support in our backend. | The best open tool-call guard lets 53% of unsafe actions through ([HF](https://huggingface.co/johannhartmann/decider-2b-toolcall-guard-lora)) |
| 6 | **Probe Laya's `noul` label-following bug and attacks aimed at the guard itself.** Perturb our `criteria` wording, and inject text that addresses the monitor. | Laya issue #156; Jev documents that `state` is not treated as hostile ([HF card](https://huggingface.co/convaiinnovations/laya); [jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13)) |
| 7 | **Update deployment docs.** Change `laya-serve` install instructions to `pip install "laya[serve]"`. Require `LAYA_API_KEY` and laya ≥0.3.23 when serving. If we export to ONNX INT8, use per-tensor quantization. Consider raising the `litellm` floor for streaming post_call guardrails (v1.102.0+). | Standalone package deprecated; server binds 0.0.0.0 with no auth; `/health` leak fixed in 0.3.23 ([PyPI](https://pypi.org/project/laya-serve/); [LiteLLM notes](https://docs.litellm.ai/release_notes/)) |
| 8 | **Watch list:** Decisions API GA (schema, probabilities, price; Codex already compares it for Guardian V2); the OWASP MCP Top 10 release planned for October, which our policy notes, after which we must remap MCP IDs; vLLM's `/v1/decisions` divergence; CPU serving of a GGUF-converted v4 through llama.cpp (conversion of our LoRA-merged checkpoint is untested). | [codex #50099](https://github.com/openai/codex/pull/50099); [vLLM RFC](https://github.com/vllm-project/vllm/issues/59365); [ggml blog](https://huggingface.co/blog/ggml-org/decision-models-in-llamacpp) |

## Conclusion

This week moved the category's competition from speed to trust. Hosted latency is now a commodity: Clef-flash claims 39 ms, Laya does about 33 ms on a GPU, and OpenAI claims 150 ms. Price is close to commoditized, with every hosted option that has a published price at or under $0.24 per million input tokens. Meanwhile no vendor, including TypeSafe, has published an audited ECE or reliability diagram, and the strongest independent security results show calibration failing exactly where guards need it, under attack. The first vendor to publish reproducible, adversarially stratified calibration will own the "trusted" position that "fast and cheap" can no longer win.

For security, decision models are better understood as a *programmable interface* than as an accuracy upgrade. One plain-language question per OWASP risk covers ground that no specialized classifier covers: tool calls conditioned on the user's request, tool-description poisoning, and system-prompt leaks checked against the actual prompt. On well-defined tasks such as direct injection, a 2024-vintage encoder is still as good. And the stages where decision models are uniquely useful (tool calls, MCP, multi-turn) are the ones with the weakest evidence. With `/v1/systemone` now a commodity wire format, s1guard's durable asset is its 15k-row benchmark and calibration pipeline, not any particular checkpoint. The next round of work should invest there.

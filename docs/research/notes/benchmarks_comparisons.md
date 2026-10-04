# Benchmarks, Evaluations, and Head-to-Head Comparisons of System One / Jev-style Decision Models (as of 2026-10-03)

Research date: 2026-10-03. Window of emphasis: 2026-09-26 to 2026-10-03 (marked **[LAST WEEK]**).
Labels used: **[VENDOR]** = number published by the model's maker; **[INDEPENDENT]** = measured by a third party; **[COPIED]** = a third party re-printing someone else's number without re-measuring.

## 1. What benchmarks exist, who ran them, methodology, reproducibility

### Takeaway
There is no neutral standard benchmark. The two headline vendor benchmarks are TypeSafe's four-workflow eval and Convai's "typed-decisions" table. Both have structural problems. TypeSafe scores agreement with LLM-generated labels, not ground truth. Convai's 0.766 comes from fine-tuning on the benchmark's own train split, and it compares against a Jev number Convai did not measure. Independent benches appeared in the last 10 days: LangWatch, DecideBench, AIM-Decision, local-jev-bench, jev-phishing-bench and an arXiv paper. They give a more mixed picture.

### Cited Findings

**TypeSafe four-workflow "workflow evaluations" [VENDOR]**
- The headline "193.6x faster, 444.6x cheaper" comes from TypeSafe's workflow evals, not the side-by-side demo. The reference answer in those evals is the average of GPT-6 Astra and Fable 5.1, so Astra and Fable are the *labelers*, not the comparison targets. The evals were designed by TypeSafe and have not been independently reproduced. — [Pranay Suyash, Medium (403 on fetch; search snippet)](https://pranaysuyash.medium.com/jevs-193-6-faster-444-6-cheaper-claim-what-typesafe-s-workflow-eval-actually-measures-68b8529e822b); [AI Learning Guides](https://ailearningguides.com/typesafe-ai-jev-system-one-model-review/)
- BenchLM (2026-09-22) reports: Jev 67.8% agreement and GPT-5.6 Sol 74.1%. The baseline is "average of GPT-6 Astra and Claude Fable 5.1 at high thinking". Jev ran at 0.4 s and $0.0004 per case, against Claude Sonnet 5 at 78.1 s per case and Claude Opus 5 at $0.1761 per case. BenchLM stresses these are "agreements with model-generated labels, not human-scored accuracy" and that "the vendor's own team designed the workflows." — [BenchLM](https://benchlm.ai/blog/posts/what-is-jev)
- Search-result summary of the same eval: Jev 67.8% is "level with GPT-5.6 Terra and behind GPT-5.6 Sol at 74.1% and Claude Opus 5 at 73.1%". — [BenchLM (search snippet)](https://benchlm.ai/blog/posts/what-is-jev)
- Arize's summary of the TypeSafe averages across 4 workflows: Jev "68% accuracy at $0.0004 and 0.4 seconds per case"; GPT-5.6 Terra "68% for $0.03 and 10 seconds"; Opus 5 "73% for $0.18 and 38 seconds". The comparison is against reference probabilities rather than human-labelled ground truth. — [Arize](https://arize.com/blog/typesafe-jev-llm-judge/)
- TypeSafe has said it deliberately skipped public benchmark leaderboards and will publish only one-off evals tied to future product updates. — [BenchLM (search snippet)](https://benchlm.ai/blog/posts/what-is-jev)
- TypeSafe's own docs page `models` has no benchmark or speed comparison. — [docs.typesafe.ai/models](https://docs.typesafe.ai/models)

**Convai "typed-decisions" benchmark (Laya) [VENDOR, with a COPIED Jev number]**
- Results on 2,000 decisions across 4 workflows:
  - Fine-tuned `laya-typed-decisions`: 0.766 accuracy
  - Base `laya` (English): 0.362
  - `laya-multilingual`: 0.342
  - TypeSafe Jev 1.13.0: 0.727

  The base checkpoints are "near chance on typed-decisions zero-shot" (0.362 vs a 0.461 majority-class baseline). — [HF convaiinnovations/laya](https://huggingface.co/convaiinnovations/laya)
- The `laya-typed-decisions` card gives the full picture:
  - Test set: 400 cases / 2,000 decisions. Training: 1,200 cases / 6,000 decisions from the benchmark's train split.
  - Scores: accuracy 0.766, soft accuracy 0.471, Brier 0.062, ECE 0.213, score MAE 0.242.
  - Per workflow: Invoice 0.804, Security Incidents 0.766, Customer Service 0.764, Agent-Trace Observability 0.730.
  - Per primitive: `noul` 0.857 (n=600), `choice` 0.733 (n=600), `score` 0.723 (n=800).
  - Vendor framing: "+3.9 points over Jev's published 0.727, above the 0.735 teacher ceiling".

  — [HF laya-typed-decisions](https://huggingface.co/convaiinnovations/laya-typed-decisions)
- **Critical caveat from the same card:** "Jev figures are third-party published, not measured here". Convai had no TypeSafe API access, and "sample sizes and prompts differ". The temperature calibration was fitted on training data, not held-out data. — [HF laya-typed-decisions](https://huggingface.co/convaiinnovations/laya-typed-decisions)
- The dataset page (LocalLLaMA/typed-decisions) shows synthetic agent-trace data with train 300 / test 100 rows per subset. Its "Official Benchmark" leaderboard shows "No results found". — [HF dataset](https://huggingface.co/datasets/LocalLLaMA/typed-decisions)
- Other Laya-reported results [VENDOR, Laya vs Jev]. — [HF laya](https://huggingface.co/convaiinnovations/laya)
  - AG News (4 labels): 0.950 vs 0.910
  - DAIR Emotion (6 labels): 0.595 vs 0.480
  - Banking77: Laya 0.425 (77 labels) vs Jev 0.870 (72 labels)
  - Laya-only scores: XNLI English 0.860, MASSIVE intent English 0.783, SST-5 `score` questions 0.372
  - The "shared benchmark" is 17,416 questions with "byte-identical questions answered in same runs".

**Reproducibility tooling (Laya evals CLI)**
- `pip install laya` reached 0.3.25, uploaded 2026-10-03 **[LAST WEEK]**. The package ships `evals.py` / `evals_cli.py`. — [PyPI JSON](https://pypi.org/pypi/laya/json)
- The `laya-evals` CLI (inspected locally in v0.3.22):
  - Runs a labelled dataset (JSONL) with gates such as `--min-accuracy`, `--max-ece` and `--baseline ... --tolerance` (exit code 1 on regression).
  - ECE uses 15 equal-width bins on `conf = max(probs)`.
  - Reports carry `dataset_sha256`, `questions_sha256` and `laya_version`, and are "byte-reproducible for a fixed runner".

  This is a regression-gating harness for your own data, not a public leaderboard. — local `.venv/.../laya/evals.py`, `evals_cli.py`, `common.py` (source: [PyPI laya](https://pypi.org/project/laya/))

**Jev demos (Doom, Wikiracing)**
- I did not retrieve the primary TypeSafe demo pages, and found no quantitative independent replication. See Gaps.

### Inferences
- **The 193.6x / 444.6x multipliers compare Jev with the slowest and most expensive LLM configurations in TypeSafe's table.** This is inferred by arithmetic from the BenchLM figures:
  - Speed: 78.1 s (Sonnet 5) ÷ ~0.40 s ≈ 193–195x.
  - Cost: $0.1761 (Opus 5) ÷ ~$0.0004 ≈ 440–445x.
  - Against GPT-5.6 Terra, which has the *same* ~68% agreement, the gap is ~25x faster ($0.03 vs $0.0004 is ~75x cheaper, using Arize's rounded figures).
- Neither vendor benchmark measures ground-truth accuracy. TypeSafe measures agreement with LLM labels. Convai's typed-decisions labels appear to be teacher-model generated (the "0.735 teacher ceiling"). Either way, the Laya-vs-Jev comparison is not apples-to-apples: different prompts and sample sizes, a copied Jev number, and a train-split fine-tune.

### Gaps
- Who originally measured "Jev 0.727" on typed-decisions, and under what conditions? The Laya card calls it "third-party published". Flowtivity labels it "CMU-verified" ([Flowtivity](https://flowtivity.ai/blog/decisions-api-vs-jev-vs-laya/)), but I could not confirm a CMU source for that specific number.
- What the "0.735 teacher ceiling" exactly means. The fetch tool paraphrased it as inter-rater agreement, which I could not verify. It may instead be GPT-6 Astra / Fable 5.1 teacher agreement.
- Doom and Wikiracing demo methodology and numbers were not retrieved.
- Medium (Suyash) and MarkTechPost 2026-10-02 ("Decision AI Models Explained: Jev vs Fastino GLiDE, GLiNER2.5-Decide…") both returned 403. Their content is unverified beyond search snippets. — [MarkTechPost](https://www.marktechpost.com/2026/10/02/decision-ai-models-explained-typesafe-jev-vs-fastino-glide-gliner2-5-decide-and-open-source-competitors/)

## 2. Independent / third-party evaluations and leaderboards

### Takeaway
Several independent benches now exist, most published 2026-09-25 to 2026-10-02. Across them, Jev is the strongest *hosted zero-shot* decision model and is usually top or tied among decision models. It is often matched by open 9B–27B fine-tunes (Kev, Eikos-27B) and beaten by frontier/near-frontier LLMs (DeepSeek V4 Flash, GPT-6 Astra) at much higher cost or latency. Laya zero-shot ranks poorly in every independent test found. There is no independent accuracy measurement of the OpenAI Decisions API beyond one small informal test.

### Cited Findings

**LangWatch "Jev vs open models up to 28B" (release 2026-09-25.2)** [INDEPENDENT]
- Setup:
  - 11 tasks with up to 1,000 test items each, frozen test sets, 60-item dev splits.
  - "Labels are the datasets' own; no human re-check yet."
  - 95% bootstrap CIs with a paired tie test.
  - Jev was called via the hosted API from Denmark. Open models ran on an RTX 3050 Ti, L4 and H100.
- Overall: Jev 81.9% [81.1–82.7] vs best open model Eikos-27B 80.0% [79.0–81.0].
- Per task, Jev vs best open model:

  | Task | Jev | Best open model | Result |
  |---|---|---|---|
  | Prompt injection | 94.6% | Eikos-27B 94.2% | tie |
  | Moderation | 90.3% | Eikos-27B 90.3% | tie |
  | PII | 90.8% | Eikos-27B 95.2% | open ahead |
  | RAG faithfulness | 80.3% | Eikos-27B 82.1% | tie |
  | Off-topic | 93.4% | Kev-9B 89.6% | Jev ahead |
  | Routing (77 intents) | 79.6% | AutoJev-27B 80.6% | tie |
  | Tool routing | 78.3% | Shisa DE-1 81.3% | open ahead |

- p95 latency: Jev API ~97 ms, Eikos-27B (H100) 170 ms, Shisa DE-1 (H100) 60 ms.
- Verdict: "Open models caught up with Jev on 8 of 11 tasks, lead on 2 and trail on off-topic."

— [LangWatch](https://langwatch.ai/compare/jev-vs-all)

**DecideBench (choyiny), tested 2026-09-28 to 2026-09-30 [LAST WEEK]** [INDEPENDENT]
- Setup: "400 multiple-choice decisions in 200 contrastive pairs" across 8 task families. Labels were "validated structurally and spot-checked". Self-hosted models ran on an NVIDIA L4, costed at $0.81/h. 23 models in total.
- Results:

  | Model | Accuracy | Cost per 1M tasks | Latency |
  |---|---|---|---|
  | DeepSeek-V4-Flash | 99.8% | $197.28 | 1,866 ms |
  | DeepSeek-V4.1-Flash | 99.2% | $455.09 | 356 ms |
  | JEV ("AI Space") | 98.0% | $32.26 | 639 ms |
  | imajev-4b | 95.0% | $28.57 | 499 ms |
  | Kev-4B | 78.2% | — | — |
  | Laya | 59.8% | — | — |

- GPT-6, Claude, Gemini, Fable, the OpenAI Decisions API and GLiDE are not included. It has no composite score and emphasises Pareto frontiers.

— [GitHub choyiny/decidebench](https://github.com/choyiny/decidebench)

**AIM-Decision by AIMultiple (published 2026-10-01, updated 2026-10-02) [LAST WEEK]** [INDEPENDENT]
- Setup:
  - 1,655 classification items: security flaws 500, product recalls 500, paper topics 500, task-completion 155. Labels come from GitHub/FDA/arXiv records.
  - Plus 50 browser-automation tasks.
  - Local models ran on an A100 80GB. Runs took place 2026-09-22 to 2026-09-30.
- Classification average:

  | Model | Score | Cost per 1K decisions |
  |---|---|---|
  | decider-12b | 54.4 | $0.060 |
  | Kev-9B | 49.1 | $0.47 (est. self-host) |
  | Nimble 9B | 49.0 | — |
  | Jev 1.13 | 47.9 | $0.039 |
  | Solar Decide | 45.9 | $0.046 |
  | stock Laya | 19% accuracy | — |

- Browser tasks (50, one attempt each):

  | Model | Completed | Median latency | Total cost |
  |---|---|---|---|
  | GPT-6 Astra | 47/50 | 17.4 s | $10.625 |
  | Gemini 3.8 Flash | 42/50 | 12.7 s | $1.079 |
  | Kev-9B | 20/50 | 38.3 s | — |
  | Jev 1.13 | 12–20/50 (run-to-run variance) | 4.2 s | $0.027 |
  | Laya | 0/50 | — | — |

- AIMultiple's verdict: Jev is best for cost efficiency and GPT-6 Astra is best overall for complex navigation.

— [AIMultiple](https://aimultiple.com/decision-models)

**local-jev-bench (tak-bro), 2026-09-30, M3 Max 36 GB [LAST WEEK]** [INDEPENDENT]
- Accuracy on typed-decisions (2,000 decisions): Kev-9B 72%, Winnow-E4B 73%, Kev-4B 67%, AnyJev L0 63%.
- Accuracy on BANKING77-20 (300 decisions): Kev-9B 89%, Kev-4B 89%, Winnow-E4B 81%.
- Order-flip rate on BANKING77-20 (answer changes when option order is permuted): Ollaya (Laya) 31% (93/300), AnyJev raw 23%, Kev-9B 10%, AnyJev L0 7%.
- Conclusion: "Kev-9B, Kev-4B and Winnow-E4B are the most accurate engines overall". On public sources the three are statistically equivalent (454–461 of 588, p > 0.45).

— [GitHub tak-bro/local-jev-bench](https://github.com/tak-bro/local-jev-bench)

**jev-phishing-bench and related (reported by Rajesh Beri, 2026-09-20)** [INDEPENDENT]
- Phishing, single question ("is this phishing?"):
  - Jev: 62.6%. It caught 43.2% of phishing and flagged 18% of legitimate mail.
  - Claude Haiku 4.5: 81.3%. McNemar p < 0.0001.
- Phishing, split into 5 atomic questions plus a logistic regression trained on 1,000 labelled emails and scored on a held-out 1,000: 95.0% (p = 0.063 vs comparator, not significant). Beri: "the 95% is not Jev. It is Jev plus your labelled data plus a regression you maintain."
- Dataset: 2,000 PhishNChips v5.2 emails (synthetic bodies, URL-based labels). The bench was published 2026-09-17 on GitHub by author "Anisselbd".
- Pre-registered study (priorbench): 5,721 calls, 21 experiments, 400-item bench. Jev zero-shot 95.9% vs keyword matching 77.2%.
- Langfuse/XenoSpectrum: DeepSeek V4.1 Flash agreed with Claude 93.5% of the time at $260 per million verdicts, vs Jev 91.5% at $160.

— [Beri](https://www.beri.net/article/typesafe-jev-typed-decision-model-calibration-decomposition-shadow-eval)

**Arize roundup of independent tests** [INDEPENDENT, secondary]
- Spam, 18,514 emails: Jev zero-shot 98.3% vs a TF-IDF classifier trained on 14,800 labels at 98.4%, "no statistically meaningful difference".
- NearHere listing moderation: Jev 96% vs Gemini Flash-Lite 86%, "58x cheaper".
- Every: "777 judgments in under 0.7 seconds for about a quarter of a cent".

— [Arize](https://arize.com/blog/typesafe-jev-llm-judge/)

**arXiv 2609.26550 "JEV-as-a-Judge: Accept When Confident, Escalate When Unsure"** [INDEPENDENT, academic]
- Authors: Yubo Li, Yidi Miao, Ramayya Krishnan, Rema Padman. v1 2026-09-22; v3 2026-09-29 **[LAST WEEK]**.
- Results:
  - Jev is "within three points of GPT-6 wherever a verdict can be read off the text, at 0.36% of its fee and a 0.15-second median latency".
  - The confidence cascade is "0.9 points more accurate than GPT-6 on 1,610 held-out pairs at 41% of its fee".
  - "In a pre-specified live test on two new workloads the cascade matches GPT-6's accuracy exactly."
  - Sixteen generative and reward-model judges were baselines.
  - Performance degrades on "math, code, and logic".

— [arXiv](https://arxiv.org/abs/2609.26550)
- Flowtivity cites the same paper as "91.3 percent pooled quality versus 91.7 percent for GPT-6 alone at 47 percent of the fee". That likely comes from an earlier revision; v3 numbers differ. — [Flowtivity 2026-09-30](https://flowtivity.ai/blog/decisions-api-vs-jev-vs-laya/)

**OpenAI Decisions API vs Jev** [INDEPENDENT but informal, n=78 steps]
- In Every's hands-on test, senior editor Jack Cheng scored Decisions API 76/78 correct steps vs Jev 73/78. Latency: Decisions API ~230 ms vs Jev ~500 ms on multi-step text tasks, and Jev ~161 ms vs Decisions API ~309 ms on classification, where accuracy was "effectively tied". This is described as a "small, informal test". — [decisionsapi.cc (secondary, search snippet)](https://decisionsapi.cc/vs-jev); [search-result summaries of valyu/aiintoai](https://www.valyu.ai/blogs/jev-vs-decisions-api)
- DevFeed (2026-09-30): "one benchmark author reports Jev as faster and more accurate, while another describes the results as similar, with Jev ahead on some nuanced questions and cheaper overall". It also notes the posts "provide no accuracy, latency, or cost figures". — [DevFeed](https://devfeed.tech/articles/openai-ships-decisions-jev-builders-pick-it-apart-62584)

**Self-claimed "beats Jev and Laya" repos** [VENDOR-like, unaudited]
- openJev-verdict-2.0 (149.6M ModernBERT-base) claims 77.10% accuracy, Brier 0.0636 and ECE 0.0144 on typed-decisions, vs Laya 76.60% and Jev 72.70%. Its Jev number is "Vendor baseline cataloged in Laya's published evaluation suite", i.e. copied. — [GitHub Heman10x-NGU/openJev-verdict-2.0](https://github.com/Heman10x-NGU/openJev-verdict-2.0)
- HN "Kev" thread (~2026-09-21): user `nico` claims Kev "match[es] or beat[s] Jev and Laya in all basic classification tasks (AG News, Emotion, MASSIVE Intent, Banking77)" but "performs rather poorly on tasks that require reasoning, like XLNI". Separately, on Banking77 they cite a <10MB model at 94.5% trained in <30 s on CPU, vs a top competitor at 94.86%. — [HN 49783999](https://news.ycombinator.com/item?id=49783999)

### Inferences
- **"Top rated" depends on the axis.**
  - Hosted, zero-shot, broad coverage: Jev is the consensus leader among decision models, #1 average on LangWatch and the top decision model on DecideBench.
  - Raw accuracy on harder or reasoning-flavoured tasks: LLMs still win (GPT-6 Astra on browser tasks; DeepSeek V4 Flash on DecideBench), as do some fine-tuned open models (decider-12b on AIM-Decision).
  - Latency on own GPU: Laya and Kev-0.8B win, but only after fine-tuning for accuracy.
- The typed-decisions number chain is circular. Laya copies a "published" Jev 0.727, and openJev copies it again from Laya's suite. No independent re-measurement of Jev on typed-decisions was found. local-jev-bench measured open models on typed-decisions but not hosted Jev.

### Gaps
- No independent accuracy or calibration benchmark of the OpenAI Decisions API with a meaningful sample size. It is still a limited preview.
- No independent head-to-head of Fastino GLiDE / GLiNER2.5-Decide was retrieved (MarkTechPost returned 403).
- A search snippet described a "composite snapshot" ranking Jev 1.13.0 #1 (74.4) and Laya #33 (54.4). I could not attribute it to a specific page, and DecideBench states it has no composite. Unverified.
- The primary Every article (Jack Cheng) was not retrieved. Its numbers are only via secondary sites.

## 3. Latency, throughput, and cost comparisons

### Takeaway
Measured Jev latency clusters around 100–300 ms p50 depending on vantage point, with a long tail to ~0.75 s p99. OpenAI's ~150 ms is an unverified DevDay slide claim with no published price. Laya's ~33 ms is on a T4 for 1 question, and degrades on long states, cold CPU starts and batched multi-question calls. LLM baselines are roughly 25–200x slower and ~75–445x more expensive per case in TypeSafe's eval, but within roughly 2–3x on latency against fast LLMs such as Haiku.

### Cited Findings

**Jev**
- TypeSafe published figures [VENDOR]:
  - $0.042 per million input tokens; output tokens free.
  - Rate limits "100K tokens per second / 80 requests per second", "adjusting dynamically".
  - Context: 64k tokens per request; 32k for `state` plus the longest question. Text only.
  - `jev-latest` → `jev-1.13.0`.

  — [docs.typesafe.ai/models](https://docs.typesafe.ai/models)
- End-to-end latency 70–500 ms [VENDOR]. — [InfoQ (search snippet)](https://www.infoq.com/news/2026/10/typesafe-ai-jev-released/); [BenchLM](https://benchlm.ai/blog/posts/what-is-jev)
- OpenRouter production telemetry [INDEPENDENT, measured]: "P50 at 0.21 s, P95 at 0.34 s, and P99 at 0.75 s". Context is 32K on OpenRouter vs 64K per TypeSafe. — [Firecrawl 2026-09-30](https://www.firecrawl.dev/blog/openai-decisions-api-vs-jev)
- Other measured latencies:

  | Setting | Measured latency | Source |
  |---|---|---|
  | LangWatch, from Denmark | ~97 ms p95 | [LangWatch](https://langwatch.ai/compare/jev-vs-all) |
  | Beri, median from France | 239 ms (Claude Haiku: 687 ms) | [Beri](https://www.beri.net/article/typesafe-jev-typed-decision-model-calibration-decomposition-shadow-eval) |
  | arXiv JEV-as-a-Judge | 0.15 s median | [arXiv](https://arxiv.org/abs/2609.26550) |
  | DecideBench, "JEV (AI Space)" | 639 ms | [DecideBench](https://github.com/choyiny/decidebench) |
  | Laya card's cited Jev figure | 236–276 ms p50 | [HF laya](https://huggingface.co/convaiinnovations/laya) |

- Cost per volume:
  - $0.038 per 1,000 phishing emails. — [Beri](https://www.beri.net/article/typesafe-jev-typed-decision-model-calibration-decomposition-shadow-eval)
  - $0.039 per 1,000 decisions, and $0.027 for 50 browser tasks vs GPT-6 Astra $10.625. Astra's 968,376 decision input tokens "would have cost about $0.04 instead of $9.68" at Jev pricing. — [AIMultiple](https://aimultiple.com/decision-models)
  - $32.26 per 1M tasks. — [DecideBench](https://github.com/choyiny/decidebench)
- Token efficiency: in a reference test Jev used "85 tokens" vs "910 output tokens" for a general-purpose model. — [Arize](https://arize.com/blog/typesafe-jev-llm-judge/)

**OpenAI Decisions API (announced DevDay 2026-09-29)**
- ~150 ms vs 1.6 s for a regular GPT-6 Luna call ("ten times faster"). It is a limited preview, with no pricing or limits disclosed. [VENDOR] — [The Decoder](https://the-decoder.com/openai-expands-codex-and-its-api-at-devday-with-security-scans-a-decisions-api-and-ultrafast/)
- Underlying GPT-6 Luna list price: $0.10 input / $0.50 output per 1M tokens. Decisions API input pricing is not published. "OpenAI's 150 ms is a vendor claim under unstated conditions, while Jev's 210 ms is measured across real traffic." — [Firecrawl](https://www.firecrawl.dev/blog/openai-decisions-api-vs-jev)
- Every's informal test, latency by task type:

  | Task type | Decisions API | Jev |
  |---|---|---|
  | Multi-step text | ~230 ms | ~500 ms |
  | Classification | ~309 ms | ~161 ms |

  — [decisionsapi.cc (secondary)](https://decisionsapi.cc/vs-jev)

**Laya (convaiinnovations, open weights, Apache-2.0)**
- 421M-parameter ModernBERT-large decision model. — [AI Weekly](https://aiweekly.co/alerts/convai-ships-laya-a-421m-modernbert-decision-model-apache-20)
- T4 GPU latency [VENDOR]: 32.8 ms for 1 question vs Jev 236–276 ms ("7.8x faster"). Multilingual model: 40.1 ms for 5 questions, 72.3 ms for 10. Throughput 103–332 questions/s batched. — [HF laya](https://huggingface.co/convaiinnovations/laya)
- Independent CPU test: "Cold CPU prediction" 49.4 s median on a 4 vCPU / 7 GB VPS. Checkpoint 808 MB. Flowtivity compares 10-question batched latency of 72.3 ms vs Jev ~1,500 ms serial. — [Flowtivity 2026-09-21](https://flowtivity.ai/blog/laya-open-source-jev-alternative/)
- Apple Silicon (M3 Max, Ollaya runtime), first-call p50 [INDEPENDENT]: 36.6 ms on English-30, 28.3 ms on BANKING77-20, and 292.9 ms on typed-decisions (long states). Kev-0.8B: 54–58 ms; Kev-4B ~290 ms. — [local-jev-bench](https://github.com/tak-bro/local-jev-bench)
- Kev MLX backend answers "in 47 ms on a Mac". Kev-9B scores 0.822 on held-out new sources vs Jev 0.857, with a confident-error rate of 4.0% vs 3.7%. — [search snippet for open-alternatives roundups](https://pinggy.io/blog/best_open_source_jev_alternatives_self_hosted_decision_models/)

**LLM baselines**
- TypeSafe eval per case:

  | Model | Agreement | Cost per case | Latency per case |
  |---|---|---|---|
  | GPT-5.6 Terra | 68% | $0.03 | 10 s |
  | Opus 5 | 73% | $0.18 | 38 s |
  | Claude Sonnet 5 | — | — | 78.1 s |

  — [Arize](https://arize.com/blog/typesafe-jev-llm-judge/); [BenchLM](https://benchlm.ai/blog/posts/what-is-jev)
- GPT-6 Astra $10.00 per M input tokens (~240x Jev); Gemini 3.8 Flash $0.75 per M. — [AIMultiple](https://aimultiple.com/decision-models)

### Inferences
- Jev latency differences between sources (97 ms p95 to 639 ms) likely reflect region, state size, number of questions, and whether a proxy (OpenRouter, "AI Space") is in the path. No single number should be quoted without conditions.
- Laya's speed advantage is real on GPU for short states. It narrows on long states (~293 ms on typed-decisions on M3 Max), and cold-start CPU is impractical without warm serving.

### Gaps
- No Decisions API pricing. No independent latency distribution for the Decisions API.
- No measured Laya latency on CPU warm (non-cold) from an independent source.

## 4. Calibration claims: what "calibrated" means, and criticism

### Takeaway
"Calibrated" means different things in each case. TypeSafe trains with "RLCD" (Reinforcement Learning for Calibrated Decisions) and exposes per-option probabilities plus a normalised "confidence", but publishes no ECE. Laya means post-hoc temperature scaling, which its own code admits only holds after fitting on held-out data for your distribution. OpenAI has not documented probabilities at all. Independent studies show Jev is reasonably calibrated in-distribution (spam) but overconfident on hard or out-of-distribution tasks. The Laya vs Jev ECE comparison circulating (0.081 vs 0.246/0.144) mixes different numbers from different sources.

### Cited Findings

**TypeSafe / Jev**
- Training method: "Reinforcement Learning for Calibrated Decisions". — [InfoQ (search snippet)](https://www.infoq.com/news/2026/10/typesafe-ai-jev-released/); [Firecrawl](https://www.firecrawl.dev/blog/openai-decisions-api-vs-jev)
- TypeSafe's docs define confidence as a transformation of the distribution, not as an empirically calibrated probability:
  - Choice: `confidence = (p_max - 1/n) / (1 - 1/n)`
  - Score: `confidence = max(0, 1 - spread / even_spread)`
- The docs publish no ECE. They say thresholds "depend on your domain and the performance of the model for your use case" and that "TypeSafe's confidence is one reasonable way to summarize a distribution, not the only one."

  — [docs.typesafe.ai/confidence](https://docs.typesafe.ai/confidence)
- BenchLM lists "No calibration study…" among unmeasured factors, since a calibration study "needs labelled outcomes paired with actual option probabilities". — [BenchLM](https://benchlm.ai/blog/posts/what-is-jev)
- Independent calibration study (researcher "Scienthoon", 900 synthetic support tickets, 2026-09-19, via Vercel gateway) [INDEPENDENT]:
  - ECE 0.107, "4.4x the noise floor".
  - yes/no answers were underconfident (refit temperature 0.66); Choice and Score were overconfident (3.29, 3.40).
  - On unknowable tasks, "Jev was right 44.7% of the time while assigning its answers an average probability of 0.74".
  - Advice: "Calibrate per question, not per model", and "Your calibration fit expires silently the day the alias moves."

  — [Beri](https://www.beri.net/article/typesafe-jev-typed-decision-model-calibration-decomposition-shadow-eval)
- Spam calibration (18,514 emails) [INDEPENDENT]:
  - Scores <0.1: 0.1% were spam. Scores ≥0.9: 99.9% were spam. Scores in the 0.5–0.6 band: "only 38% were spam".
  - Routing the 4.6% of emails scored 0.3–0.7 to a human "left the rest at 99.5% accuracy".

  — [Arize](https://arize.com/blog/typesafe-jev-llm-judge/)
- Selective accuracy: 89.9–99.6% when filtering by confidence ≥0.9 (Kumar's tests). — [BenchLM](https://benchlm.ai/blog/posts/what-is-jev)
- At a 0.9 threshold, "Jev-accepted answers run within a point of GPT-6 accuracy". — [Flowtivity citing arXiv 2609.26550](https://flowtivity.ai/blog/decisions-api-vs-jev-vs-laya/)

**Laya**
- Post-temperature-scaling ECE: Laya 0.081 vs Jev 0.144. Pre-calibration: `laya` 0.213, `laya-multilingual` 0.285. Brier (laya-typed-decisions) 0.062. — [HF laya](https://huggingface.co/convaiinnovations/laya)
- The fine-tuned card says: "Still over-confident (ECE 0.213 vs Jev's 0.144)". Its temperature was fitted on training data rather than held-out data. — [HF laya-typed-decisions](https://huggingface.co/convaiinnovations/laya-typed-decisions)
- Flowtivity's table reports Laya 0.081 (post-temperature) vs **Jev 0.246** ("Published data"). This conflicts with Laya's own card, which gives Jev 0.144. — [Flowtivity](https://flowtivity.ai/blog/laya-open-source-jev-alternative/)
- Laya's own source code (`common.answer_confidence` docstring, v0.3.22) states that "of the answers returned at confidence c, about c of them are right" holds "only after the temperatures have been fitted and validated on held-out data for this checkpoint and this option count". It also says: "The shipped checkpoints are over-confident: `choice:11+` is a ~10x sharpener that returns a point mass at 1.0, so a threshold applied to them selects below model accuracy (issue #394)." — local package source ([PyPI laya](https://pypi.org/project/laya/))
- Language calibration failure: the English checkpoint collapses on non-Latin scripts, e.g. Khmer "0.000 accuracy at 0.952 confidence". — [HF laya](https://huggingface.co/convaiinnovations/laya)
- Soft accuracy (probability-distribution match) favours Jev: 0.580 vs laya-typed-decisions 0.471. — [HF laya](https://huggingface.co/convaiinnovations/laya)

**OpenAI Decisions API**
- Probabilities and calibration are "Not documented". — [Firecrawl](https://www.firecrawl.dev/blog/openai-decisions-api-vs-jev); [The Decoder](https://the-decoder.com/openai-expands-codex-and-its-api-at-devday-with-security-scans-a-decisions-api-and-ultrafast/)
- Diogo Almeida (TypeSafe founder) said it "seems to be luna with constrained decoding". Critics object to constrained decoding for string outputs. — [DevFeed 2026-09-30](https://devfeed.tech/articles/openai-ships-decisions-jev-builders-pick-it-apart-62584)

**Open challengers**
- openJev-verdict-2.0 claims ECE 0.0144 from a separate confidence head (self-reported). — [GitHub](https://github.com/Heman10x-NGU/openJev-verdict-2.0)

### Inferences
- Circulating "Laya ECE 0.081 vs Jev 0.246/0.144" claims compare a Laya *post-temperature* number (fitted on train data) with Jev numbers whose provenance is unclear. Neither was measured on the same items by the same party. The only independent Jev ECE found (0.107, n=900, OOD synthetic tickets) is from a different dataset.
- Practitioner consensus: confidence thresholds plus escalation work well when the task is in-distribution and answerable from the text. Calibration must be refit per question and per model version.

### Gaps
- No TypeSafe-published ECE or reliability diagram.
- No public description of RLCD beyond the name.
- No independent ECE for the Decisions API.

## 5. Known limitations / jaggedness

### Takeaway
Both vendors document sharp failure modes. TypeSafe's Jev 1.13 jaggedness page was last reviewed 2026-10-02 **[LAST WEEK]** and lists about 11 issues; independent tests confirm option-order bias and prompt-injection risk. Laya's limitations are large: near-chance zero-shot on typed-decisions, high-cardinality collapse, English-checkpoint collapse on non-Latin scripts, high order-flip, and failure on agentic tasks.

### Cited Findings

**Jev 1.13**
- Documented failure modes [VENDOR], with key quotes:
  - Literal reading: "answers the question you wrote, not the one you meant"
  - Math: "not a calculator"
  - Counting: "error grows with the size of the thing being counted"
  - Numeric representations: hex/RGB; cannot "reliably judge whether two values are near"
  - Dates: "reads dates as text, not as ordered quantities"
  - Indirection and double negatives
  - Large irrelevant state: "Accuracy falls as the state grows with content unrelated to the decision"
  - Adversarial content: not "hostile by default"
  - Contradictory instructions
  - Choice option order: bias toward "the option that comes first"
  - Generation: "not trained to generate text"

  The page was last reviewed 2026-10-02. — [docs.typesafe.ai jaggedness jev-1.13](https://docs.typesafe.ai/model-jaggedness/jev-1.13)
- "State is data, and jev-1.13 does not treat it as hostile by default." Prompt-injection vulnerability was flagged by reviewers. A forced binary with no `unknown` option "makes Jev pick the least wrong answer". — [Beri](https://www.beri.net/article/typesafe-jev-typed-decision-model-calibration-decomposition-shadow-eval)
- AIM-Decision browser tasks: Jev "declared task blocked in 24 of 33 failures, 16 before any action". Results varied 12–20/50 across run days. — [AIMultiple](https://aimultiple.com/decision-models)
- HN user `ranyume` found Jev "really bad at making connections" on exploration tasks. — [HN 49783999](https://news.ycombinator.com/item?id=49783999)
- The arXiv judge study finds degradation on "math, code, and logic". — [arXiv 2609.26550](https://arxiv.org/abs/2609.26550)
- Jev supports up to 255 options out of the box. — [search summary of Laya comparisons](https://flowtivity.ai/blog/laya-open-source-jev-alternative/)

**Laya**
- High-cardinality: a 77-option question allocates only "3–4 tokens per label", and Banking77 scores 0.425 vs Jev 0.870. — [HF laya](https://huggingface.co/convaiinnovations/laya)
- `action.act_probability` AUROC "0.30" (unreliable). SST-5 `score` accuracy 0.372. Zero-shot typed-decisions 0.362, below the majority-class baseline of 0.461. — [HF laya](https://huggingface.co/convaiinnovations/laya)
- Language coverage: 45 of 51 languages are "usable (>3x random)". The English checkpoint collapses on non-Latin scripts (Khmer 0.000 at 0.952 confidence). — [HF laya](https://huggingface.co/convaiinnovations/laya)
- Order-flip rate of 31% on BANKING77-20 (Ollaya), the worst of the engines tested. — [local-jev-bench](https://github.com/tak-bro/local-jev-bench)
- On agentic tasks:
  - Browser: 0/50, "declared the task finished before meeting the goal in 33 attempts, 17 times before any action". Fine-tuning gave "at most 3 of 50" (p = 0.25).
  - Stock classification: 19%.

  — [AIMultiple](https://aimultiple.com/decision-models)
- "Laya is a fast base to specialise, not a zero-shot decision engine." — [Flowtivity](https://flowtivity.ai/blog/laya-open-source-jev-alternative/)

**OpenAI Decisions API**
- Answers only "questions with finite pre-defined answers". Probabilities are not documented and limits are not published. — [Firecrawl](https://www.firecrawl.dev/blog/openai-decisions-api-vs-jev)

### Inferences
- Option-order bias is a cross-model phenomenon. TypeSafe documents it for Jev, and local-jev-bench quantifies it for open models (7–31%). Any eval of these models should randomise option order.
- Prompt injection via `state` matters especially for guardrail use cases, since decision models are being pitched for exactly that (LangWatch prompt-injection task: Jev 94.6%).

### Gaps
- No independent quantification of Jev's order-flip rate. local-jev-bench did not test hosted Jev on order flips.

## 6. Community sentiment in the last week (2026-09-26 to 2026-10-03)

### Takeaway
Practitioners rate Jev highest as the default hosted decision model, mainly for price, latency and probabilities. Sentiment has shifted from launch hype to "use it as a cheap first pass with escalation, and calibrate on your own labels". Open alternatives (Kev, Eikos, decider-12b) are seen as catching up. Laya is viewed as a fast fine-tuning base, not a zero-shot engine. The OpenAI Decisions API is greeted with interest but scepticism (seen as "Luna with constrained decoding", no probabilities, no price).

### Cited Findings
- Cascade pattern as consensus: "The winning production pattern is model-agnostic: cheap confident first pass, escalate the uncertain tail to a reasoning model." — [Flowtivity 2026-09-30](https://flowtivity.ai/blog/decisions-api-vs-jev-vs-laya/)
- Scepticism on Laya: "Laya's headline…accuracy is self-reported, checkpoint-selection flavored, and not independently verified." — [Flowtivity 2026-09-30](https://flowtivity.ai/blog/decisions-api-vs-jev-vs-laya/)
- Flowtivity's verdict by use case:
  - Laya for sensitive or on-prem data.
  - Jev for cost optimisation (calibration plus cascade).
  - Decisions API for convenience inside the OpenAI stack.

  — [Flowtivity 2026-09-30](https://flowtivity.ai/blog/decisions-api-vs-jev-vs-laya/)
- Builders picking apart the Decisions API: one benchmark author says Jev is faster and more accurate; another calls them similar, with Jev ahead on nuanced questions and cheaper. — [DevFeed 2026-09-30](https://devfeed.tech/articles/openai-ships-decisions-jev-builders-pick-it-apart-62584)
- The Decoder: "Pairing a stronger model as an orchestrator with a fast decision model looks promising." — [The Decoder 2026-09-29](https://the-decoder.com/openai-expands-codex-and-its-api-at-devday-with-security-scans-a-decisions-api-and-ultrafast/)
- HN (Kev thread, ~2026-09-21, just before the window):
  - `hbrn`: "Jev is only useful when you both need fast response AND can tolerate mediocrity compared to frontier models…if it's critical enough to require sub-second speed, it can't be mediocre."
  - `mjyoke1111`: a tiny local model handling 95% of traffic with a large model for "the weird 5%" "is genuinely better than either alone."

  — [HN 49783999](https://news.ycombinator.com/item?id=49783999)
- Adoption signals [VENDOR/partner]:
  - Vercel says Jev reached ~13% of paid AI Gateway teams within 24 h, "twice the share of the GPT-5.6 family". — [InfoQ (search snippet)](https://www.infoq.com/news/2026/10/typesafe-ai-jev-released/); [Beri](https://www.beri.net/article/typesafe-jev-typed-decision-model-calibration-decomposition-shadow-eval)
  - A Reddit developer called Jev "absolutely insane" for agent work at 200–300 ms. — [InfoQ (search snippet)](https://www.infoq.com/news/2026/10/typesafe-ai-jev-released/)
- Laya traction: 19,301 GitHub stars per one roundup. — [search snippet, open-alternatives roundups](https://pinggy.io/blog/best_open_source_jev_alternatives_self_hosted_decision_models/)
- AIMultiple (2026-10-01/02): Jev is the "Top-Rated Model for Cost-Efficiency" and GPT-6 Astra is "Top-Rated Model Overall (Mixed Workloads)". — [AIMultiple](https://aimultiple.com/decision-models)
- LangWatch (2026-09-25): "Open models caught up with Jev on 8 of 11 tasks." — [LangWatch](https://langwatch.ai/compare/jev-vs-all)

### Inferences
- The reasonable "top-rated" summary as of 2026-10-03:
  1. **Jev 1.13** is the de facto leader among decision-specific models. It has the most independent evaluations, is at or near the top of each decision-model comparison, and is cheapest per decision.
  2. **Open fine-tuned models** (Kev-9B, Eikos-27B, decider-12b) are near-parity or better on specific tasks, at higher self-host cost or latency.
  3. **LLMs-as-classifiers** (GPT-6 Astra, DeepSeek V4 Flash, Claude) still win on accuracy for reasoning-heavy or agentic decisions, at 10–400x cost.
  4. **Laya** wins on raw GPU latency and openness, but only after fine-tuning.
  5. **OpenAI Decisions API** is too new to rate: one n=78 informal test, near-tie with Jev.
- Much of the "independent" coverage is SEO-style aggregator content: explainx, jevmodel.org, decisionsapi.cc, lmspedia and similar. Primary measured sources are LangWatch, DecideBench, AIMultiple, local-jev-bench, Beri/jev-phishing-bench, Arize's roundup and the arXiv paper.

### Gaps
- Could not access X/Twitter or Reddit threads directly for last-week sentiment. The Reddit quote is via InfoQ.
- No HN thread specifically about the Decisions API launch with benchmark numbers was retrieved.

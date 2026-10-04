# Open-weight "System One" (Jev-style) decision models: inventory as of 2026-10-03

Scope note: "decision / System One model" = non-generative model that answers typed questions (`choice` / `score` / `noul` yes-no) over a text/JSON (sometimes image/video) state and returns a probability per option in a forward pass. Data pulled 2026-10-03 from the Hugging Face (HF) API, PyPI JSON API, GitHub API, model cards, and arXiv. HF `downloads` = trailing-30-day count. Unless marked otherwise, **every benchmark number below is self-reported on the publisher's own model card and was not reproduced for these notes.**

## 1. Laya (convaiinnovations): latest version, changelog, checkpoints, benchmarks, license, adoption, discussion

### Takeaway
Laya is still the most-liked and most-starred open System One model: 5,053 HF likes and 30,411 GitHub stars, both since 2026-09-18. The brief's v0.3.22 is out of date. **The latest PyPI release is 0.3.25 (2026-10-03).** Four runtime releases shipped in the window (0.3.21 to 0.3.25, runtime/serving only). The HF weights have not changed since 2026-09-24. Laya's headline numbers come with caveats: 0.766 typed-decisions accuracy needs the benchmark-specific fine-tune, and ECE 0.081 holds only after temperature refitting. Several competitors' own tables rank Laya last or near last in zero-shot accuracy, though they also show it as the fastest.

### Cited Findings
**Release history / changelog**
- PyPI `laya` latest = **0.3.25**, uploaded 2026-10-03T15:58; license Apache-2.0; summary "Fast, non-autoregressive System 1 decision engine with calibrated probabilities"; requires Python >=3.10 — [PyPI JSON](https://pypi.org/pypi/laya/json)
- Releases in the 2026-09-26..10-03 window: 0.3.21 (09-27), 0.3.22 (09-29), 0.3.23 (10-01), 0.3.24 (10-02), 0.3.25 (10-03). First release 0.1.0 on 2026-09-18. 33 releases total in 16 days, with no 0.3.7/0.3.8 on PyPI — [PyPI JSON](https://pypi.org/pypi/laya/json); GitHub tags v0.3.20–v0.3.25 match — [GitHub releases](https://github.com/NandhaKishorM/laya/releases)
- 0.3.25 notes: `LAYA_IDLE_UNLOAD_SECONDS` idle unload for `laya-serve`. `LAYA_BASE_URL` lets `laya-mcp-server` use a running server. `Agent(backend=auto|eager|compile|tilelang|onnx)`. Compile warmup at load. AOTInductor dtype fix. `/v1/systemone/batch` splits oversized batches. Histogram-binning calibration now ships with answers. TileLang CPU kernels. TypeScript per-bucket `minConfidence`. "13 pull requests from 9 contributors" — [PyPI project description](https://pypi.org/project/laya/)
- 0.3.24: concurrency fixes in `Router.load`/`unload`. Per-option-count abstention thresholds (`fit_abstention_thresholds`) and histogram binning (`fit_binning_map`). Selective-classification metrics (Brier, AURC). Stricter input validation — [PyPI project description](https://pypi.org/project/laya/)
- 0.3.23 (security-relevant): `GET /health` no longer exposes checkpoint names, revision SHAs, or device state to unauthenticated callers when `LAYA_API_KEY` is set (#812). Added SECURITY.md with private vulnerability reporting. Fixed a GPU OOM fallback race (#649). Per-call controls now reach the CLI, batch endpoint, MCP, TS SDK, and LangChain/CrewAI/LlamaIndex wrappers — [PyPI project description](https://pypi.org/project/laya/)
- 0.3.22: TS per-checkpoint SHA-256 artifact verification (PR #723), `/v1/systemone` control forwarding, TS abstention gating, selective-prediction report for metamorphic variants — [GitHub release v0.3.22](https://github.com/NandhaKishorM/laya/releases/tag/v0.3.22)
- 0.3.21: `ONNXAgent` gains batch/long-doc methods and INT8 export. Opt-in abstention (`min_confidence=` → `low_confidence`/`abstention` fields). Batch support everywhere. New LangChain `LayaDecision`, LlamaIndex, and CrewAI integrations. Per-request token budgets — [PyPI project description](https://pypi.org/project/laya/)
- The last HF repo commit is 2026-09-24T05:39 ("README: recommend max_len=8192, laya 0.3.20 notes"). There were **no HF commits in the 09-26..10-03 window**, so the weights are unchanged. The repo SHA is `55cf4c4e…` — [HF commit log](https://huggingface.co/convaiinnovations/laya/commits/main). The 0.3.20 notes say "The checkpoints themselves are unchanged" — [HF model card](https://huggingface.co/convaiinnovations/laya)

**Checkpoints / architecture**
- One repo holds three checkpoints:
  - `laya` (root): ModernBERT-large, 421M params, 512 ctx, English.
  - `laya-multilingual`: mmBERT-base, 322M params, 1,024 ctx (up to 8,192 with `max_len=8192`), 100+ languages.
  - `laya-typed-decisions`: ModernBERT-large, 421M params, 1,024 ctx, fine-tuned on the 4 typed-decisions workflows.

  Each option is scored at its own `[MASK]` marker. The decision head has 2 transformer layers plus an act/escalate head. A `Router` auto-selects the checkpoint by script/language — [HF model card](https://huggingface.co/convaiinnovations/laya)
- Training is "RLCD" (Reinforcement Learning for Calibrated Decisions): REINFORCE with a group-mean baseline (GRPO-style), rewards from strictly proper scoring rules (log + spherical, plus RPS for ordinal questions) — [HF model card](https://huggingface.co/convaiinnovations/laya)
- Serving options:
  - `pip install laya` with extras `[serve]`, `[mcp]`, `[langchain]`, `[onnx]`, `[fast]` (TileLang).
  - `laya-serve` implements Jev's `POST /v1/systemone` shape. It binds 0.0.0.0 with **no auth unless `LAYA_API_KEY` is set**.

  [HF model card](https://huggingface.co/convaiinnovations/laya)
- Sibling repos: `convaiinnovations/laya-multilingual` (created 2026-09-19, 358 likes) and `convaiinnovations/laya-typed-decisions` (created 2026-09-18, 144 likes). Both last modified 2026-09-24 — [HF API](https://huggingface.co/api/models?author=convaiinnovations)

**Benchmarks (self-reported unless noted)**
- typed-decisions (2,000 decisions, 400 cases, 4 workflows):

  | Model | Accuracy | Soft acc | Brier | ECE |
  |---|---|---|---|---|
  | `laya-typed-decisions` | **0.766** | 0.471 | 0.062 | 0.213 |
  | base `laya` | 0.362 | – | – | – |
  | `laya-multilingual` | 0.342 | – | – | – |
  | Jev 1.13.0 (published) | 0.727 | 0.580 | – | 0.144 |

  Teacher self-agreement ceiling is 0.735; majority class is 0.461 — [HF model card](https://huggingface.co/convaiinnovations/laya)
- The card itself states: "Base checkpoints are near chance on typed-decisions zero-shot… The 0.766 belongs to the checkpoint fine-tuned on that benchmark's own training split. Laya is a fast base to specialise, not a zero-shot decision engine." — [HF model card](https://huggingface.co/convaiinnovations/laya)
- The headline vs-Jev table (Laya routed vs Jev 1.13.0): AG News 0.950 vs 0.910; DAIR Emotion 0.595 vs 0.480; **Banking77 0.425 vs 0.870 (Jev leads)**; ECE 0.081 vs 0.246; p50 latency 32.8 ms vs 236–276 ms. The card says the Jev figures are "third-party published, never measured here (no TypeSafe API access); sample sizes and prompts differ" — [HF model card](https://huggingface.co/convaiinnovations/laya)
- Calibration caveat: Laya "Ships over-confident". Refitting temperature per (question type, option count) takes mean ECE from 0.466 to 0.081 (`laya`) and from 0.314 to 0.106 (multilingual) — [HF model card](https://huggingface.co/convaiinnovations/laya)
- Latency on a T4: 1 question 39.5 ms (English) / 32.8 ms (multilingual); 10 questions 158.6 / 72.3 ms. CPU with preload: 193–464 ms — [HF model card](https://huggingface.co/convaiinnovations/laya)
- Router evidence: MASSIVE intent, English 0.783; XNLI English 0.860. "Languages usable (>3x random)" is 45/51 routed. The English checkpoint scores 0.000 on Khmer at 0.952 confidence — [HF model card](https://huggingface.co/convaiinnovations/laya)
- Repo eval (`eval/results.md`): in-task overall accuracy 0.753, ECE 0.030; zero-shot (held-out task families) accuracy 0.651, ECE 0.204 — [eval/results.md](https://huggingface.co/convaiinnovations/laya/blob/main/eval/results.md)
- Known limits documented on the card:
  - `noul` can follow its `false:`/`true:` option labels instead of the state ([#156](https://github.com/NandhaKishorM/laya/issues/156)).
  - `action.act_probability` "carries no usable signal yet" (AUROC 0.30) ([#185](https://github.com/NandhaKishorM/laya/issues/185)).
  - `score` is the weakest primitive (SST-5 0.372).

  [HF model card](https://huggingface.co/convaiinnovations/laya)

**Third-party / competitor evaluations of Laya**
- Independent HF discussion #20 (2026-09-26): laya 0.686 vs Jev 1.13.0 0.907 vs Qwen2.5-1.5B parallel constrained decoding (PCD) 0.605. The test was a sealed 1,190-case / 1,550-question manifest across 9 suites, CPU only. Scope: root English checkpoint only, laya 0.3.11. Repo: github.com/instax-dutta/sysone-bench — [HF discussion #20](https://huggingface.co/convaiinnovations/laya/discussions/20)
- InternLM's table: Laya average 57.77 vs Jev 88.74 vs Intern-Decision-4B 90.02. Typed Decision 35.95; WildJailBreak 14.84; ECE 0.246 — [internlm/Intern-Decision-4B card](https://huggingface.co/internlm/Intern-Decision-4B)
- Cloudflare's Decision Index 0.2.1 internal run: Laya is lowest on most benchmarks (e.g., BANKING77 macro-F1 14.3, MMLU 30.7, BFCL 38.1). It has the **lowest median latency, 5.8 ms**, vs Jev 524.1 ms — [Cloudflare/clef card](https://huggingface.co/Cloudflare/clef)
- fastino fast-decisions benchmark: "Laya Router" 46.6% vs GLiNER2.5-Decide 60.2% — [fastino/GLiNER2.5-Decide card](https://huggingface.co/fastino/GLiNER2.5-Decide)
- StartLux table: Laya 130/231 on JevBench public; Decision Index 5.51 / 6.04 (vs Jev 1.13 at 199 and 51.67 / 57.91) — [startlux-models/StartLux-Decision-4B card](https://huggingface.co/startlux-models/StartLux-Decision-4B)

**Adoption signals**
- HF: `convaiinnovations/laya` has 5,053 likes and trendingScore 956. `downloads` and `downloadsAllTime` both read **0**. Repo created 2026-09-18 — [HF API](https://huggingface.co/api/models/convaiinnovations/laya?expand[]=downloadsAllTime&expand[]=likes&expand[]=trendingScore)
- GitHub `NandhaKishorM/laya`: created 2026-09-18, **30,411 stars, 2,655 forks**, 75 open issues, last push 2026-10-03 — [GitHub API](https://api.github.com/repos/NandhaKishorM/laya)
- Demo Space `convaiinnovations/laya-demo`: 265 likes — [HF Space](https://huggingface.co/spaces/convaiinnovations/laya-demo)
- `ggml-org/Laya-GGUF` (created 2026-10-01): 4,153 downloads, 16 likes — [HF](https://huggingface.co/ggml-org/Laya-GGUF). `fr0stbit3/laya-gguf` (2026-09-20): 3,006 downloads — [HF](https://huggingface.co/fr0stbit3/laya-gguf)
- A curated HF collection calls Laya the "Most-liked open Jev" — [Ferr0 collection](https://huggingface.co/collections/Ferr0/open-jev-typed-decision-models)

**Community discussion**
- 24 HF discussions. In-window topics:
  - #20 independent head-to-head (09-26)
  - #19 "Interest in acquiring Laya" (09-26)
  - #21 "Laya as a judge!" (09-27)
  - #23 router input above 8,192 tokens (09-30)
  - #24 performance on fontlab.org/ornotto (09-30)

  Earlier: #18 "cbjev" one-pass layout claiming 6.7x faster multi-question; #16 a free hosted Jev-compatible endpoint; #15 zero-shot agent step guard — [HF discussions](https://huggingface.co/convaiinnovations/laya/discussions)
- Third-party write-ups:
  - [themenonlab blog](https://themenonlab.blog/blog/laya-local-system-1-decision-model)
  - [mer.vin](https://mer.vin/news/laya-the-33ms-open-source-decision-model-beating-jev/)
  - [Ivan Tkachenko blog](https://vanekt.github.io/blog/laya-vs-jev/)
  - [jevmodel.org](https://jevmodel.org/what-is-laya/)
  - [HF community blog "Jev vs Laya"](https://huggingface.co/blog/sora-2/jev-vs-laya-hosted-api-or-open-weights-2026-guide)
  - Node/TS port via ONNX Runtime: [receptron/laya](https://github.com/receptron/laya)
- Origin claim (from a search-result summary): the author (Nandakishor Mukkunnoth, Convai Innovations) published RLCD work in early 2025 and put Laya together in days after TypeSafe released Jev — [web search summary of Laya write-ups](https://themenonlab.blog/blog/laya-local-system-1-decision-model). The author's own post is titled "I built non-autoregressive decision models a year ago, then a frontier lab called it a…" — [Dev.to](https://dev.to/nandakishor_m_6cc0adfde9f/i-built-non-autoregressive-decision-models-a-year-ago-then-a-frontier-lab-called-it-a-18me)

### Inferences
- HF downloads cannot be used as an adoption signal for the Convai repos (all read 0). HF probably isn't counting this custom-layout repo. Julia-1's card notes that HF counts downloads via a root `config.json`, and Laya's config sits under `encoder/`. Likes, GitHub stars, and GGUF-mirror downloads are the usable signals.
- The 0.3.21–0.3.25 work is operational hardening: abstention, calibration tooling, auth on `/health`, ONNX, concurrency. It is not a model-quality update. Any accuracy gap vs newer competitors is unchanged this week.
- For guardrail use, the documented `noul` label-following bug and the near-chance zero-shot typed-decisions score matter. Laya should be fine-tuned and temperature-calibrated on in-domain data before use as a guard.

### Gaps
- Could not get Laya PyPI download counts (pypistats not queried) or the full text of HF discussions #19/#21/#23.
- The RLCD paper itself (arXiv ID / date) was not located or verified.
- No Reddit r/LocalLLaMA thread was found directly (search returned blogs, not Reddit).

## 2. Other open-weight decision / System One models released in the last week (2026-09-26 → 2026-10-03)

### Takeaway
This week brought large corporate entrants:
- **Cloudflare Clef / Clef-Flash** (09-30; 941 / 339 likes)
- **Perplexity pplx-decider-v1-27b** (10-01)
- **InternLM Intern-Decision** (09-26)
- **AutoTrust JEV-27B-VL** (09-30; ~309k downloads, the most-downloaded of the wave) and GEV-26B-Decide (10-02)
- **Strands decider-2B** (09-30)
- **Maincode MATILDA-jev** (09-30)
- **vLLM Semantic Router Decision-2.0** (09-29)
- **StartLux-Decision** 0.8B–35B (09-29 / 10-01; non-commercial)

It also brought many small encoder entrants (bekko 17M–400M, tasksource-jev-nano 149M, kenning 435M). The center of gravity has moved from small encoders (Laya-style) to Qwen3.5/3.8- and Gemma-4-based decision heads, mostly multimodal. Several claim parity with or wins over Jev 1.13.

### Cited Findings
**Volume** (HF name search, models created 09-26..10-03; name matches may include non-decision models):
- "jev": 127 (178 more in 09-15..09-25)
- "decider": 38
- "typed-decisions": 20
- "system-one": 13
- "laya": ≥59 Laya-named repos in the 60 most-recently-modified "laya" hits (sample capped, so the true count is higher)

[HF models API search](https://huggingface.co/api/models?search=jev&limit=1000)

**Per-model key facts (in-window releases, ordered roughly by significance)**

| Model (org) | Created | Backbone / size | License | Q types / inputs | Context | Reported results (self-reported) | Serving | Adoption |
|---|---|---|---|---|---|---|---|---|
| [Cloudflare/clef](https://huggingface.co/Cloudflare/clef) | 2026-09-30 | Qwen3.8-27B + "joint schema head" (27.36B) | Apache-2.0 | noul/choice/score; text, JSON, images, video | `max_length` default 16,384 | Decision Index 0.2.1 internal run: BANKING77 94.2 vs Jev 79.7; CLINC150 97.4 vs 89.3; MMLU-Pro 65.9 vs Jev 82.7; GPQA 48.0 vs 78.3; median latency 209.3 ms (Jev 524.1) | Python `systemone()` function "fully compatible with Jev and SystemOne" `/v1/systemone` body; tested torch 2.11 / transformers 5.10.2 on H200 | 941 likes, 2,620 dl |
| [Cloudflare/clef-flash](https://huggingface.co/Cloudflare/clef-flash) | 2026-09-30 | Qwen3.5-9B (9.41B) | Apache-2.0 | same | same | Median 38.8 ms; e.g. ARC-C 98.3, WinoGrande 97.5; CLINC150 66.8 | same | 339 likes, 4,310 dl |
| [perplexity-ai/pplx-decider-v1-27b](https://huggingface.co/perplexity-ai/pplx-decider-v1-27b) | 2026-10-01 | Qwen3.8-27B (26.1B) | Apache-2.0 | choice, noul; images | n/s | 11-benchmark overall 85.71% vs Jev 84.51% vs base Qwen3.8-27B 74.76% ("measured through the Perplexity API"); Jev leads on BBH, WinoGrande, JevBench hard | `inference.py` `Decider` class; ~49 GiB weights | 66 likes, 447 dl |
| [autotrust/JEV-27B-VL](https://huggingface.co/autotrust/JEV-27B-VL) | 2026-09-30 | Qwen3.8-27B + System-1 adapter (27.8B) | Apache-2.0 | yes/no, 2–256 options, 0–5 rating; text + images; also System-2 generation | prompts up to 256K | Robot arm pick-place 75% of 20 sim scenes; computer use 95% of 60 tasks; ~240 ms/decision | `POST /v1/decide` via vLLM | **308,531 dl**, 58 likes |
| [autotrust/GEV-26B-Decide](https://huggingface.co/autotrust/GEV-26B-Decide) | 2026-10-02 | Gemma-4-26B-A4B-it (25.8B) | Apache-2.0 | System 1 + System 2, adaptive thinking | n/s | Robot arm 40%; 61 ms/decision (per JEV-27B-VL card) | vLLM | 89,541 dl |
| [internlm/Intern-Decision-4B](https://huggingface.co/internlm/Intern-Decision-4B) (+0.8B, 2B) | 2026-09-26 | Qwen3.5-4B (4.54B), multimodal | Apache-2.0 | choice/score/noul; images | n/s | 7-suite avg 90.02 vs Jev 88.74; ECE 0.065; 44 ms on RTX 4090 (Jev 109.7 ms) | `DecisionEngine` HF backend; Jev-compatible response | 76 likes, 1,836 dl |
| [StrandsAgents/strands-decider-2B-hobson-v19](https://huggingface.co/StrandsAgents/strands-decider-2B-hobson-v19) | 2026-09-30 | LoRA on Qwen3.5-2B-Base + readout head | Apache-2.0 | noul/choice/score | window 3072/4096 evaluated | JevBench public 167/231 (0.7229), Brier 0.348, ECE 0.050 | `pip install strands-decider`; CLI; `/v1/systemone` server (127.0.0.1, no auth) | 42 likes; ONNX/GGUF/WebGPU ports |
| [Maincode/matilda-jev-v1](https://huggingface.co/Maincode/matilda-jev-v1) | 2026-09-30 | custom `MatildaJevModel`, 26.1B | Apache-2.0 | choice/noul/score; text/JSON + images | n/s | Decision Index 0.2.1 59.59 ("awaiting official submission") | bundled runtime / `trust_remote_code`; validated on AMD MI355X | 6 likes, 199 dl |
| [startlux-models/StartLux-Decision-{0.8B,2B,4B,9B,27B}](https://huggingface.co/startlux-models/StartLux-Decision-4B), [35B-A3B](https://huggingface.co/startlux-models/StartLux-Decision-35B-A3B) | 2026-09-29 / 10-01 | Qwen3.5 dense + MoE | **CC-BY-NC-4.0** | choice/noul/score; text, JSON, images | 262,144 tokens | 4B: JevBench public 204/231, DI 0.2.1 52.75, 26.0 ms for 3 Qs on H200; 35B-A3B: 210/231; 27B DI 63.88 (vs Jev 57.91) | TypeSafe `/v1/systemone` format; GGUF Q4/Q8/BF16 | ≤74 dl each base repo; GGUF up to 745 |
| [vllm-sr/Decision-2.0-Lux-9B](https://huggingface.co/vllm-sr/Decision-2.0-Lux-9B) | 2026-09-29 | 7.94B (from Decision-1.0-Lux-9B, Qwen3.5-9B) | Apache-2.0 | choice/yes-no/score | 16,384 | JevArena 68.1; +2.8 on Jev Decision Index vs 1.0; median 18.4 ms single question | vLLM Semantic Router project | 7 likes |
| [OmniJev/OneJev-27B](https://huggingface.co/OmniJev/OneJev-27B) | 2026-09-27 | Qwen3.8-27B | Apache-2.0 | typed Qs over screenshot/photo/video/text | n/s | 189 ms for 1 Q, 324 ms for 10 Qs on H200 with 1280x720 screenshot | `qev serve` | 7 likes; [OneJev GitHub](https://github.com/OmniJev/OneJev) lists 4 sizes 0.8B–27B |
| [Mapika/decider-12b](https://huggingface.co/Mapika/decider-12b) | 2026-09-29 | Gemma-4-12B-it + decider readout; v2 merged LoRA | card says Apache-2.0 (Gemma base: verify) | choice/noul/score | n/s | per-type temperatures | `Decider` package | 3 likes; also `Mapika/decider-chat-gemma4-31b` (343 dl), `decider-chat-qwen3.6-27b` (09-29) |
| [hotchpotch/bekko-system-one-v0-17m / 68m / 400m](https://huggingface.co/hotchpotch/bekko-system-one-v0-17m) | 2026-09-29 | ettin-reranker (ModernBERT) cross-encoders: 17M / 68M / 395M | **not stated in metadata** | Choice/Noul/Score | n/s | Author: "fall far behind Jev 1.13 on S1MB's benchmarks designed to measure generalization" | sentence-transformers; ONNX browser (17M = 29 MB) | 11 / 1 / 5 likes |
| [tasksource/tasksource-jev-nano-v0](https://huggingface.co/tasksource/tasksource-jev-nano-v0) | 2026-09-28 | ModernBERT-base / LightOn LateOn multi-vector (149M) | Apache-2.0 | choice (K=2–100+), noul, score | 8,192 | Badge claims "#1 Sub-200M" on Decision Index (unverified) | PyLate | 2 likes, 103 dl |
| [systemonedev/kenning-large-v0.4](https://huggingface.co/systemonedev/kenning-large-v0.4) | 2026-10-03 | DeBERTa-v3-large zeroshot-v2.0-c cross-encoder (435M) | Apache-2.0 | noul/choice/score | 512 per (state, answer) pair | per-type temperatures fitted | HF | 0 dl |
| [RinggAI/ringg-router-e2b](https://huggingface.co/RinggAI/ringg-router-e2b) | 2026-09-29 | Gemma-4-E2B-it | Apache-2.0 | routing/intent/NLI for Indic voice agents (text-generation pipeline; borderline) | n/s | n/s | transformers | 751 dl |

**Laya conversions released in window**
- [ggml-org/Laya-GGUF](https://huggingface.co/ggml-org/Laya-GGUF) (10-01; 4,153 dl)
- [onnx-community/laya-typed-decisions-ONNX](https://huggingface.co/onnx-community/laya-typed-decisions-ONNX) (09-29; transformers.js/WebGPU)
- [cavi-ai/laya-MLX-8bit](https://huggingface.co/cavi-ai/laya-MLX-8bit) (10-03)
- [HF API](https://huggingface.co/api/models?search=laya&sort=lastModified)

**Smaller in-window entries** (low or no adoption; claims unverified):
- chaoliangUNSW/Jev-Style-2B-Decision-v3 (09-27, 245 dl) and Jev-Style-Cascade-9B (10-02)
- GhostScientist/jev-decisions-v1-model (10-02, 466 dl)
- carrtesy/EXAONE-4.0-1.2B-JEV (10-02)
- Kestrelyn/kestrel-decider-230m (10-03)
- peonist-ai/halogen-npu-decider-0.8b (10-01)
- adaptive-classifier/typed-decisions-minilm-l6-specialist (10-02)
- RazvanManolache/raz-systemone-nli-xsmall/base (10-02)
- stephenlb/system-one-model (09-30; Gemma-4-12B; gemma license)
- jevhome/jevhome-B/L/ettin-1b (09-30)
- SoMarkAI/mJev-Qwen3-VL-4B-RLCD (09-29)
- SourceHat-Labs/RLCD-Qwen3.5-9B-Gated-Decision (09-29)
- gyung/Qwev-9B-RLCD (09-26)
- iapp/OpenThai-SystemOne-Ollama (10-01, 474 dl)

Source: [HF models API, sort=lastModified](https://huggingface.co/api/models?search=jev&sort=lastModified&direction=-1)

**Notable pre-window wave (2026-09-15 → 09-25)**, for context on what the new entrants are compared against:

| Model | Created | Backbone / size | License | Key facts (self-reported) | Adoption |
|---|---|---|---|---|---|
| [Mapika/decider-2b](https://huggingface.co/Mapika/decider-2b) | 09-16 | Qwen3.5-2B-Base (1.9B), v11 | Apache-2.0 | "open reproduction of the System One model class"; SFT on ~95 public decision datasets + calibration-aware RL; JevBench public hard 0.577 (v11) vs 0.459 (v10) | **285,776 dl**, 97 likes |
| [AlexWortega/openjev](https://huggingface.co/AlexWortega/openjev) | 09-16 | Qwen3.5 4B/2B/0.8B NLI cross-encoder | MIT | decides by entailment, no per-task training | 633 likes |
| [harshatheg/Qwen-2.5-1B-RLCD](https://huggingface.co/harshatheg/Qwen-2.5-1B-RLCD) | 09-16 | Qwen2.5-1.5B, MLX | Apache-2.0 | parallel constrained decoding engine, 5.6–7.0x faster than autoregressive on M4 Max (generative-constrained; borderline) | 577 likes |
| [jaredpalmer/kev-4b](https://huggingface.co/jaredpalmer/kev-4b) | 09-19 | frozen Qwen3.5-4B-Base + LoRA r16 + pointer head | Apache-2.0 | choice/score 1–255 options, noul; states to 65,536 served, 8,192 validated; T=2.41; English | 16,100 dl, 101 likes |
| [openjev/openjev](https://huggingface.co/openjev/openjev) | 09-20 | 27.4B Qwen3.5 | **CC-BY-NC-4.0** (commercial licence via loopai.com) | 84.0% vs Jev 85.4% on 10,000 Qs; up to 52 options; ~210 ms on H100; FP8 / MLX / GGUF builds | 4,821 dl, 99 likes |
| [akhilaaa3/Jev-Omni](https://huggingface.co/akhilaaa3/Jev-Omni) | 09-20 | Gemma-4-12B-it | Apache-2.0 | text/image/audio/video; JevBench 86.15% | 358 likes |
| [iapp/OpenThai-SystemOne](https://huggingface.co/iapp/OpenThai-SystemOne) | 09-20 | Qwen3.5-0.8B-Base, Thai CPT ~5B tokens | Apache-2.0 | Thai + English; up to 255 options; mirrors `/v1/systemone` | 10,210 dl, 32 likes |
| [ZefanCai/Open-Jev-9B](https://huggingface.co/ZefanCai/Open-Jev-9B) | 09-20 | LoRA + scalar head, Qwen3.5-9B | Apache-2.0 | non-generative | 48 likes |
| [juspay/xor](https://huggingface.co/juspay/xor) | 09-21 | Qwen3.6-35B-A3B MoE | Apache-2.0 | up to 255 candidates, SGLang | 50 likes |
| [vllm-sr/Decision-1.0-Lux-9B](https://huggingface.co/vllm-sr/Decision-1.0-Lux-9B) | 09-22 | Qwen3.5-9B | Apache-2.0 | multilingual | 14 likes |
| [SupersonicLabs/Julia-1](https://huggingface.co/SupersonicLabs/Julia-1) | 09-23 | mmBERT-small, 144.3M | Apache-2.0 | typed-decisions 73.15% vs Jev ref 72.70%; Banking77 pilot 64% vs Jev 87%; MASSIVE 52-locale 71.50%; 2–20 options; to 8,192 tokens; ONNX/WebGPU port | 392 likes, 3,251 dl |
| [fastino/GLiNER2.5-Decide](https://huggingface.co/fastino/GLiNER2.5-Decide) (+[1B](https://huggingface.co/fastino/GLiNER2.5-Decide-1B), [multi 287M](https://huggingface.co/fastino/GLiNER2.5-multi-Decide)) | 09-23/24 | GLiNER2 large (card says 340M; HF safetensors total 486M) | Apache-2.0 | label-set-at-call-time classification (not typed noul/score API); fast-decisions avg 60.2% vs JevK5 57.6% vs Laya Router 46.6% | **50,402 dl**, 345 likes |
| [togethercomputer/Tev1-4B-experimental](https://huggingface.co/togethercomputer/Tev1-4B-experimental) | 09-23 | Qwen3.5-4B | n/s | "keeps a generative head, full recipe published" (per Ferr0 collection) | 3,223 dl |
| [autotrust/JEV-9B](https://huggingface.co/autotrust/JEV-9B) / [JEV-27B](https://huggingface.co/autotrust/JEV-27B) | 09-23 / 09-25 | Qwen3.5-9B / Qwen3.8-27B + 40.2M "Blocks of Experts" System-1 block | Apache-2.0 | mean KL ≈0.019 (9B) / ≈0.017 (27B) vs Jev 1.13 distributions on 25,376 held-out Qs; median ≈90 ms on B200 vs 238–301 ms hosted Jev; trained on [SargeDev/jev-distill-corpus-v3](https://huggingface.co/datasets/SargeDev/jev-distill-corpus-v3); "not affiliated with… TypeSafe AI" | 12,364 / 2,667 dl |
| [caiovicentino1/Eikos-27B](https://huggingface.co/caiovicentino1/Eikos-27B) | 09-23 | Qwen3.8-27B | MIT | finance / trade-finance decisions | 32 likes |
| [interfaze-ai/lev](https://huggingface.co/interfaze-ai/lev) | 09-24 | LoRA on Qwen3.5-4B | Apache-2.0 (metadata) | 68.9% on 13 S1Bench subsets; noul / choice / score 2–10 levels | 111 likes |
| [Hanno-Labs/bosun-v3.1-1.7b](https://huggingface.co/Hanno-Labs/bosun-v3.1-1.7b) | 09-22 | Qwen3-1.7B | Apache-2.0 | DecisionBench 84.9% vs Jev 1.13 72.0% (per collection note) | 1,199 dl |

### Inferences
- In the window, the field split into two camps:
  - Large LLM-backbone decision heads (Clef, pplx-decider, JEV, MATILDA, StartLux, OneJev). These target accuracy and multimodality at 20–500 ms on H100/H200-class GPUs.
  - Tiny encoders (bekko, tasksource-nano, kenning, Julia-1, Laya). These target CPU/browser latency.

  Laya's niche is the second camp.
- Corporate backing arrived this week: Cloudflare, Perplexity, InternLM, AWS-associated Strands Agents (inferred from the name, unverified), and the vLLM project. That raises the bar for Laya, whose checkpoints are now among the oldest in the field (unchanged since 09-24).
- For commercial guardrail deployment, the license splits matter. StartLux and openjev are non-commercial (CC-BY-NC). bekko has no declared license. Gemma-based models (decider-12b, stephenlb) inherit Gemma terms despite Apache-2.0 card claims.

### Gaps
- None of the in-window vendor benchmarks were independently reproduced. Cloudflare's Decision Index numbers are labelled "our internal run". Perplexity's are "measured through the Perplexity API".
- Cloudflare's blog post (blog.cloudflare.com/clef-decision-models) was not fetched, so the release narrative and any hosted Workers AI availability are not verified here.
- `pplx-decider-v1-27b` context length and score-type support are not stated on its card.
- StrandsAgents organizational affiliation is not verified.
- GLiNER2.5-Decide parameter discrepancy (340M on the card vs 486M in HF safetensors metadata) is unresolved.

## 3. Laya fine-tunes and datasets for training decision models

### Takeaway
There are dozens of Laya-derived repos, ≥59 created in the window alone, but nearly all have 0 downloads, 0–3 likes and no published evals. The meaningful derivatives are format conversions (GGUF/ONNX/MLX). The training-data ecosystem is substantial:
- LocalLLaMA/typed-decisions, the benchmark behind Laya's 0.766
- a 740,957-row Jev-distilled corpus
- 2.5M-row tasksource typed decisions
- Open-Jev (CC0)
- 12M agent-decision records

### Cited Findings
**Laya fine-tunes created 09-26..10-03** (0 downloads unless noted; no verified evals). Source for all: [HF models API search "laya", sorted by lastModified](https://huggingface.co/api/models?search=laya&sort=lastModified&direction=-1)

- Guard / safety:
  - `mnjkshrm/sentrygate-laya` (10-03)
  - `ottosulin/safe-laya` (10-02)
  - `Dipto084/safe_laya` (10-03)
  - `OidoStudio/laya-mm-guard-v3-gguf` (10-01; 90 dl)
- Triage / routing:
  - `elnachto/laya-triage-en` and `-multilingual` (09-28)
  - `Harsh1312/laya-pr-triage` (10-03)
  - `Prasanna85/laya-issue-triage` (10-02)
  - `fcelabs/laya-glendesk-issues` (10-02)
  - `billyd10/laya-homelab-router` (10-01)
  - `Indigma/SeLMRoute-Laya` (10-01)
  - `knpatil/laya-browser-agent(-base)` (10-02/03)
- Domain:
  - `crtal/laya-qrisfraud` (10-03)
  - `yxnxc/laya-claim-detection` (10-02)
  - `Primeomicx/laya-nextflow-nfcore` (10-02)
  - `jeremierostan/laya-student-match` / `laya-pairmatch` (10-01/02)
  - `kgrozdanovski/caldec-v1-laya` (10-01)
  - `leloss/crime-laya-2000-public` (10-01)
  - `Modusnsus/laya-nli-conflict-v5…v10` (10-01; 10 iterations)
- Language:
  - `mmahdi-sz/Laya-fa` and `Laya-fa-universal-support` (Persian; 10-01/02; 3 likes)
  - `Ramg77/laya-sentiment-multilingual` (09-26) + CoreML (09-30)
- typed-decisions replicas:
  - `michaelfeil/laya-typed-decisions` (09-29; 45 dl)
  - `Mass121/laya-typed-decisions(-v2)`
  - `salabh-an/laya-typed-decisions`
  - `philipsubhan/laya-typed-decisions` (10-01..03)
  - `Steven10429/laya-typed-decisions-webgpu-q4` (09-30)
- RLCD retrain: `Snugasabug/laya-finetuned-rlcd` + GGUF (10-02; GGUF 300 dl)
- Vision forks:
  - `ZeraG07/laya-vision` (10-02)
  - earlier `thaitea/laya-vision` (09-19, SmolVLM-256M, CC-BY-NC-SA-4.0, 36 likes). [HF](https://huggingface.co/thaitea/laya-vision); GitHub [r33drichards/laya-vision](https://github.com/r33drichards/laya-vision) per [awesome-jev](https://github.com/cobanov/awesome-jev)
- Conversions:
  - `ggml-org/Laya-GGUF` (4,153 dl)
  - `fr0stbit3/laya-gguf` (3,006 dl)
  - `onnx-community/laya-typed-decisions-ONNX`
  - `kallebysantos/laya-onnx`, `Zaluski/laya-onnx`
  - `cavi-ai/laya-MLX-8bit`, `sjoerdbodbijl/laya-mlx`
  - `go-vertika/laya-web-q8`
- Laya ships an official fine-tuning notebook for Kaggle 2x T4 (build dataset, train, fit temperatures, evaluate, push to Hub) — [HF model card](https://huggingface.co/convaiinnovations/laya)

**Datasets for training / evaluating decision models**

| Dataset | Created | Size / content | License | Adoption |
|---|---|---|---|---|
| [LocalLLaMA/typed-decisions](https://huggingface.co/datasets/LocalLLaMA/typed-decisions) | 09-16 | "A benchmark for typed probabilistic decisions": one unstructured state, five typed questions. Used by Laya (2,000 decisions / 400 cases / 4 workflows) and Julia-1 | Apache-2.0 | 25,325 dl, 101 likes |
| [SargeDev/jev-distill-corpus-v3](https://huggingface.co/datasets/SargeDev/jev-distill-corpus-v3) | 09-21 | 740,957-row calibrated typed-decision corpus in TypeSafe System One schema (used by AutoTrust JEV) | Apache-2.0 | 1,527 dl, 21 likes |
| [ZefanCai/Open-Jev](https://huggingface.co/datasets/ZefanCai/Open-Jev) | 09-20 | typed decision datasets (yes/no prob, choice distribution, …) | CC0-1.0 | 4,134 dl, 66 likes |
| [TypeSafeAI/Open-Jev](https://huggingface.co/datasets/TypeSafeAI/Open-Jev) | 09-30 | same description text as ZefanCai/Open-Jev | CC0-1.0 | 162 dl |
| [tasksource/tasksource-jev-typed-decisions](https://huggingface.co/datasets/tasksource/tasksource-jev-typed-decisions) | 09-22 | 2.5 million typed decisions from 670 sources | "other" | 3,044 dl, 13 likes |
| [tasksource/synthetic-typed-decisions](https://huggingface.co/datasets/tasksource/synthetic-typed-decisions) | 10-01 | LLM-written items with several typed questions | Apache-2.0 | 92 dl |
| [Praveenrajus/jev-bench](https://huggingface.co/datasets/Praveenrajus/jev-bench) | 09-20 | real human-labeled data reformatted into System One questions, 22 configs | "other" | 8,670 dl |
| [samatv256/jev-decisions-v1](https://huggingface.co/datasets/samatv256/jev-decisions-v1) | 09-23 | 12M agent-decision records (tool selection, routing, completion) | CC-BY-4.0 | 2,056 dl |
| [fastino/fast-decisions](https://huggingface.co/datasets/fastino/fast-decisions) | 09-24 | 17 domains × 300 held-out examples | Apache-2.0 | 1,322 dl |
| [OmniJev/OneJev-Data](https://huggingface.co/datasets/OmniJev/OneJev-Data) | 09-28 | 94,707 typed questions about screens, photos, videos, text | "other" | 640 dl |
| [hotchpotch/bekko-system-one-dataset-v0](https://huggingface.co/datasets/hotchpotch/bekko-system-one-dataset-v0) | 09-28 | training set for bekko models | not stated | 382 dl |
| [autotrust/jev-decision-index-results](https://huggingface.co/datasets/autotrust/jev-decision-index-results) | 09-28 | full Decision Index 0.2.1 runs for JEV models | Apache-2.0 | 2,200 dl |
| [Hanno-Labs/decision-bench](https://huggingface.co/datasets/Hanno-Labs/decision-bench) | n/v | DecisionBench, 23,900 frozen rows (per [Ferr0 collection](https://huggingface.co/collections/Ferr0/open-jev-typed-decision-models)) | n/v | n/v |

- Smaller in-window language and domain sets:
  - `felhen-ai/ptbr-typed-decisions-bench` (10-03)
  - `yyhlm/typed-decisions-ru` (09-29)
  - `hagsmand1/laya-thai-decisions` (10-03)
  - `GhostScientist/jev-decisions-v1` (10-02)
  - `trapstreet/jev-class-cve-bench` (10-02)
  - `raxITLabs/jev-as-a-guardrails` (09-28; 226 dl)

  [HF datasets API](https://huggingface.co/api/datasets?search=jev&sort=lastModified&direction=-1)

### Inferences
- `raxITLabs/jev-as-a-guardrails` and `trapstreet/jev-class-cve-bench` are the most directly relevant datasets for this repo's guardrail work, but they are new and unreviewed.
- Laya fine-tunes are mostly hobby or experimental pushes. For a production guard, prefer fine-tuning Laya yourself via the official notebook, or a stronger base, and calibrate. Don't adopt third-party Laya fine-tunes.

### Gaps
- Could not verify whether `TypeSafeAI/Open-Jev` is an official TypeSafe AI org. Its description duplicates `ZefanCai/Open-Jev`, so it may be a mirror.
- Did not open individual Laya fine-tune cards to check for evals.
- DecisionBench creation date and license not fetched.

## 4. Benchmarks, leaderboards, papers and community context (Sept–Oct 2026)

### Takeaway
Jev (TypeSafe AI, closed, hosted) launched on 2026-09-15 and set the API shape everyone copies: `POST /v1/systemone` with `noul`/`choice`/`score`. Shared leaderboards (Decision Index, JevBench, JevArena, S1Bench) and at least six arXiv papers appeared in late September / early October. They make cross-model comparison possible, but most numbers are still vendor-run.

### Cited Findings
- TypeSafe AI released Jev on September 15, 2026, as the first "System One model". Jev is closed and hosted only (early-access waitlist, no weights) — [Sanity glossary](https://www.sanity.io/glossary/jev-typesafe-ai-model); [TrueFoundry blog](https://www.truefoundry.com/blog/typesafe-ai-jev) (secondary sources)
- The current model is `jev-1.13.0` (`jev-latest` and `jev-preview` both point to it). It is listed on OpenRouter as `typesafe/jev-1.13` and integrated in Cloudflare AI as `typesafe/jev`. The launch post is typesafe.ai/blog/introducing-system-one-models-and-jev — [awesome-jev](https://github.com/cobanov/awesome-jev)
- Laya's card cites Jev pricing of $0.042 / 1M tokens and an independently measured p50 of 236–276 ms ([AbdelStark/jev-benchmarks](https://github.com/AbdelStark/jev-benchmarks), [nibzard/decision-model-benchmark](https://github.com/nibzard/decision-model-benchmark)) — [HF model card](https://huggingface.co/convaiinnovations/laya)
- arXiv 2609.37647, "Evaluating and Benchmarking the System One Model Jev" (2026-09-29): evaluates jev-1.13.0 zero-shot on 37 datasets (346,009 requests for under USD 10), with Qwen3.8-27B and Gemma-4-E4B as reference via exact next-token option probabilities — [arXiv](https://arxiv.org/abs/2609.37647)
- arXiv 2609.33209, "Beyond Calibration: Do a Typed-Decision Model's Probabilities Obey the Probability Axioms?" (2026-09-27): on 480 negation pairs, Jev's P(X) + P(not X) misses 1 by 0.064 on average (95% CI 0.055–0.072) — [arXiv](https://arxiv.org/html/2609.33209v1)
- Other Sept–Oct arXiv papers:
  - 2609.28940, "Calibrated Decision Models for Autonomous Penetration-Testing Harnesses: JEV and Laya as System One Decision Layers…" — [arXiv](https://arxiv.org/abs/2609.28940)
  - 2610.01079, "Jev-IDS" network intrusion detection — [arXiv](https://arxiv.org/html/2610.01079v1)
  - 2609.23986, "Jev-Mem" agentic memory — [arXiv](https://arxiv.org/html/2609.23986v1)
  - 2609.30216, "Jev in the Wild", a survey of 2,170 public Jev projects — [awesome-jev](https://github.com/cobanov/awesome-jev)
- Leaderboards / benchmarks:
  - Decision Index Space `multimodalart/jev-decision-index` (created 2026-09-17, 406 likes) — [HF Space](https://huggingface.co/spaces/multimodalart/jev-decision-index)
  - Cloudflare's Decision Index site, [clef-evals.workers-ai-mle.workers.dev](https://clef-evals.workers-ai-mle.workers.dev), linked from the [Clef card](https://huggingface.co/Cloudflare/clef)
  - JevBench (231 public tasks) — [fstandhartinger/jevbench](https://github.com/fstandhartinger/jevbench)
  - JevArena (cited by [vllm-sr](https://huggingface.co/vllm-sr/Decision-2.0-Lux-9B))
  - S1Bench (cited by [lev](https://huggingface.co/interfaze-ai/lev))
  - S1MB (cited by [bekko](https://huggingface.co/hotchpotch/bekko-system-one-v0-17m))
  - Typesafe Evals workflow suite (evals.typesafe.ai, cited by [Clef](https://huggingface.co/Cloudflare/clef))
- Local serving and tooling ecosystem:
  - Ollaya, a Rust daemon that pulls Laya, decider, NLI, and GLiClass models behind `/v1/systemone`
  - stuntd, a local proxy serving the Jev API from Laya
  - AnyJev, LitJev, and Simple Jev, which do training-free logit readout from any open LLM
  - sokudan (Japanese, ModernBERT-ja 314.6M)
  - Decima (122M multilingual-e5-small)
  - Prosodia (audio, Whisper encoder)

  [awesome-jev](https://github.com/cobanov/awesome-jev)

### Inferences
- Because nearly every model copies the `/v1/systemone` contract, models are hot-swappable behind the same client. Teams can A/B Laya against Clef-Flash, decider-2b, or Intern-Decision with only a base-URL change. Several serving shims already do this (Ollaya, stuntd, Jev-Switch).
- The pentest-harness paper (2609.28940) explicitly uses JEV and Laya as decision layers. It is the closest academic precedent for this repo's guardrail use case.

### Gaps
- Reddit r/LocalLLaMA and r/MachineLearning threads were not located. Web search returned blogs and aggregators instead, so community sentiment there is unknown.
- Exact submission dates for 2609.28940, 2610.01079, 2609.23986, and 2609.30216 were not retrieved (the IDs imply Sept and Oct 2026).
- Did not fetch the TypeSafe launch post directly. The Jev release date comes from secondary sources.

## 5. Related older open families (context only, NOT System-One-branded)

### Takeaway
Before Jev, the same job (zero-shot label scoring with probabilities, no generation) was done by NLI zero-shot classifiers, ModernBERT/mmBERT encoders, and GLiNER2/GLiClass. Several of the new System One models are built directly on these: Laya on ModernBERT-large/mmBERT, kenning on DeBERTa zeroshot-v2.0, GLiNER2.5-Decide on GLiNER2, Julia-1 on mmBERT-small, bekko on ettin. They lack the typed `noul`/`score` contract and RL/proper-scoring calibration.

### Cited Findings
- [facebook/bart-large-mnli](https://huggingface.co/facebook/bart-large-mnli): NLI zero-shot classifier, MIT, 407M. HF repo date 2022-03-02. ~163M all-time downloads, 2.85M in the last 30 days.
- [MoritzLaurer/deberta-v3-large-zeroshot-v2.0](https://huggingface.co/MoritzLaurer/deberta-v3-large-zeroshot-v2.0): created 2024-04-01, MIT, 435M, 6.1M all-time downloads.
- [MoritzLaurer/ModernBERT-large-zeroshot-v2.0](https://huggingface.co/MoritzLaurer/ModernBERT-large-zeroshot-v2.0): created 2024-12-27, Apache-2.0, 396M.
- [tasksource/ModernBERT-large-nli](https://huggingface.co/tasksource/ModernBERT-large-nli): created 2025-01-04, Apache-2.0.
- [answerdotai/ModernBERT-large](https://huggingface.co/answerdotai/ModernBERT-large): created 2024-12-11, Apache-2.0, 396M (arXiv 2412.13663). This is Laya's English backbone.
- [jhu-clsp/mmBERT-base](https://huggingface.co/jhu-clsp/mmBERT-base): created 2025-07-23, MIT. This is Laya-multilingual's backbone.
- [knowledgator/gliclass-modern-large-v3.0](https://huggingface.co/knowledgator/gliclass-modern-large-v3.0): GLiClass, created 2025-07-15, Apache-2.0, 399M.
- [fastino/gliner2-large-v1](https://huggingface.co/fastino/gliner2-large-v1): GLiNER2, created 2025-07-29, Apache-2.0 (arXiv 2507.18546), 2.26M all-time downloads. This is the base of GLiNER2.5-Decide.

All metadata from the HF API (`createdAt`, `downloadsAllTime`, `cardData.license`).

### Inferences
- A detector built on ModernBERT/DeBERTa NLI classifiers is architecturally close to Laya. Laya's main differences are the typed multi-question single pass, RLCD calibration, and the Jev-compatible API, not a fundamentally different model class.

### Gaps
- SetFit was not verified: the HF API returned 401 for the sampled repo, and no primary source was fetched.
- No head-to-head of these older NLI classifiers vs Laya on the same benchmark was found, except Ollaya bundling them side by side (per [awesome-jev](https://github.com/cobanov/awesome-jev)).

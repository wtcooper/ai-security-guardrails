# Open-source platforms, frameworks, SDKs and serving infrastructure for System One / Jev-style decision models (snapshot 2026-10-03)

Method note: star, fork, license and date metadata were pulled on 2026-10-03 from the GitHub REST API (`gh api repos/<owner>/<repo>`; release lists from `/releases`), the PyPI JSON API (`https://pypi.org/pypi/<pkg>/json`) and the npm registry (`https://registry.npmjs.org/<pkg>`). Function claims come from READMEs, release notes and vendor docs, which were fetched directly. "This week" means 2026-09-26 to 2026-10-03 (UTC). The whole ecosystem is under three weeks old: Jev launched on 2026-09-15 ([ModelSystem.One](https://modelsystem.one/); [MAF issue #8556](https://github.com/microsoft/agent-framework/issues/8556)). Star counts are therefore hype-phase signals and should not be read as maturity. Several repos reached thousands of stars in days.

## Q1. TypeSafe's system-one-adapter-python, any JS adapter, and TypeSafe's official SDKs

### Takeaway
`typesafe-ai/system-one-adapter-python` is an official, MIT-licensed drop-in replacement for `typesafe_sdk`'s `system_one` call. It is backed by OpenAI, Anthropic or Gemini LLMs and is meant for comparing TypeSafe Jev with an LLM on cost, speed and intelligence. Its last release was v0.2.1 on 2026-09-22, so nothing shipped this week. TypeSafe's official Python and JS SDKs are open source (MIT) and very heavily downloaded. TypeSafe publishes no official JS adapter; the only one is a third-party npm clone.

### Cited Findings
**system-one-adapter-python (official)**
- Repo `typesafe-ai/system-one-adapter-python`: MIT, 377 stars, 58 forks, 6 open issues, created 2026-08-08, last push 2026-09-22. Description: "Drop-in TypeSafeClient replacement backed by LLM APIs". — [GitHub API](https://api.github.com/repos/typesafe-ai/system-one-adapter-python)
- What it does: it is "a drop-in replacement for `typesafe_sdk`'s `system_one` evaluation API, backed by LLM APIs instead of TypeSafe. Useful for comparing TypeSafe against an LLM on cost/speed/intelligence." Provider extras are `[openai]` (any OpenAI-compatible endpoint), `[anthropic]` and `[gemini]`. Usage is `SystemOneAdapterClient(...).system_one(state=..., questions={...: Noul(...)}, provider="openai", model="gpt-4o-mini")`. — [README](https://github.com/typesafe-ai/system-one-adapter-python)
- How it constrains output. `structured_outputs=True` uses the provider's native structured-output mode: strict JSON Schema on OpenAI's Responses API, `response_format` JSON Schema on Gemini's Interactions API. Otherwise it prompts for JSON and validates client-side. `llm_answer_mode` is `"probabilities"` (a per-label distribution) or `"discrete"`. `normalize_probabilities` rescales distributions that don't sum to 1. `n_retry_malformed_structure` sets the number of corrective retries. — [README](https://github.com/typesafe-ai/system-one-adapter-python)
- The response is a `typesafe_sdk.SystemOneResponse` subclass with extra fields: `usage` (token totals across retries, `n_retries`, latency) and `debug.llm_attempts` (a full replayable attempt history). The probabilities are LLM-verbalized or structured outputs, not logits. — [README](https://github.com/typesafe-ai/system-one-adapter-python)
- Release history: v0.1.3 on 2026-09-15 (initial), v0.1.4 on 09-16, v0.1.5 on 09-18, v0.2.0 on 09-18 (switched ser/de from msgspec to pydantic to track typesafe-sdk 0.7.0), and v0.2.1 on 2026-09-22 (Gemini provider, rejects incomplete completions, refusals no longer retried). — [changelog](https://github.com/typesafe-ai/system-one-adapter-python/blob/main/docs/changelog.md); [GitHub releases API](https://api.github.com/repos/typesafe-ai/system-one-adapter-python/releases)
- PyPI `system-one-adapter` 0.2.1, MIT, author "TypeSafe AI <support@typesafe.ai>", extras `anthropic, gemini, openai`. There have been 6 uploads, the first being 0.0.1a0 on 2026-09-15. There is no upload this week. — [PyPI JSON](https://pypi.org/pypi/system-one-adapter/json)
- Downloads: 3,178 last week and 619 last day. — [pypistats](https://pypistats.org/api/packages/system-one-adapter/recent)
- GitHub contributors: `typesafe-public-bot[bot]` (5 commits) and `danielgafni` (1). This suggests the repo is mirrored from an internal source. — [GitHub contributors API](https://api.github.com/repos/typesafe-ai/system-one-adapter-python/contributors)

**JS adapter**
- `typesafe-ai/system-one-adapter-js` returns 404, and the typesafe-ai org repo list contains no JS adapter. — [GitHub API](https://api.github.com/repos/typesafe-ai/system-one-adapter-js); [org repos](https://api.github.com/orgs/typesafe-ai/repos)
- A third-party npm package `system-one-adapter` exists: 0.5.0 (2026-09-24), MIT, maintainer `synthluvr`. Its repo is `SynthLuvr/system-one-adapter-js` (0 stars). Its description is copied verbatim from the official Python one ("Drop-in TypeSafeClient replacement backed by LLM APIs"). — [npm](https://registry.npmjs.org/system-one-adapter); [GitHub API](https://api.github.com/repos/SynthLuvr/system-one-adapter-js)

**Official SDKs (open source)**
- `typesafe-ai/typesafe-sdk-python`: MIT, 263 stars, 40 forks, created 2026-09-04. Releases: v0.6.0 (09-15), v0.7.0 (09-18, pydantic models), v0.7.1 (09-21), and **v0.7.2 on 2026-09-26, which is this week** (adds an `http2` extra). — [GitHub API](https://api.github.com/repos/typesafe-ai/typesafe-sdk-python); [release v0.7.2](https://github.com/typesafe-ai/typesafe-sdk-python/releases/tag/v0.7.2)
- The PyPI package is `typesafe-sdk` 0.7.2, MIT, author TypeSafe AI. It had 947,883 downloads last week. — [PyPI JSON](https://pypi.org/pypi/typesafe-sdk/json); [pypistats](https://pypistats.org/api/packages/typesafe-sdk/recent)
- `typesafe-ai/typesafe-sdk-js`: MIT, 266 stars, 36 forks, 17 open issues. Latest release v0.6.0 on 2026-09-15, with no release this week. — [GitHub API](https://api.github.com/repos/typesafe-ai/typesafe-sdk-js)
- npm `@typesafe-ai/sdk` 0.6.0, MIT, maintainers `alliesafe` and `diogo149`. It had 1,429,008 downloads from 2026-09-25 to 10-01. — [npm](https://registry.npmjs.org/@typesafe-ai%2fsdk); [npm downloads](https://api.npmjs.org/downloads/point/last-week/@typesafe-ai%2fsdk)
- Other TypeSafe org repos:
  - `typesafe-ai/skills`, "Agent skills for building with TypeSafe's System One API": MIT, 2,552 stars.
  - `typesafe-ai/n8n-nodes-typesafe-ai`: MIT, 8 stars, created 2026-09-23, pushed 2026-09-29, not a fork.
  - `typesafe-ai/WorkflowEvals`, "evals.typesafe.ai workflow code": Apache-2.0, **created 2026-09-28, which is this week**.

  — [org repos API](https://api.github.com/orgs/typesafe-ai/repos)
- A PyPI package `typesafe-ai` 0.1.0 (2026-09-17) is a "redirect shim" that depends on `typesafe-sdk`. Its author is "Gerome Dexheimer <hello@geromedexheimer.de>", not TypeSafe's support address. — [PyPI JSON](https://pypi.org/pypi/typesafe-ai/json)
- The TypeSafe API shape is `POST https://api.typesafe.ai/v1/systemone` with `model` (for example `"jev-latest"`), `state` (string, object or array) and `questions`. Question types are `noul` (P(yes)), `choice` (up to 255 options) and `score` (2 to 10 levels). The response has `answers` and `usage {input_tokens, output_tokens}`. The docs page linked no OpenAPI spec and stated no spec license. — [TypeSafe API docs](https://docs.typesafe.ai/api)

### Inferences
- The adapter is TypeSafe's own baseline and benchmarking tool, not a production path to calibrated probabilities. Its probabilities are LLM-emitted numbers, optionally renormalized, so they carry none of Jev's calibration guarantees. It still works as a "Jev-shaped fallback" in s1guard-style designs.
- The SDK repos are MIT and public but appear to be bot-mirrored, with almost no external commits. "Open source" here means source-available under a permissive license, not community-governed.
- Treat the `typesafe-ai` PyPI shim, and the npm `typesafe-sdk` 0.0.0 placeholder (maintainer `pi0`), as name-squat-style risk for supply-chain hygiene.

### Gaps
- I found no TypeSafe statement on whether an official JS adapter is planned.
- I could not confirm whether TypeSafe publishes a machine-readable OpenAPI spec or a license for the `/v1/systemone` wire format.

## Q2. Laya ecosystem: core package, serving, MCP, framework integrations, ONNX, TileLang, calibration and fine-tuning, and last week's PyPI history

### Takeaway
Laya (ConvAI Innovations / NandhaKishorM, Apache-2.0) is the dominant open-weight Jev alternative. It is shipping at a very high cadence: **five PyPI releases this week**, from 0.3.21 to 0.3.25, the last on 2026-10-03. Serving, MCP, LangChain/LangGraph, LlamaIndex, CrewAI, ONNX and TileLang all come as extras of one `laya` package. The standalone `laya-serve` PyPI package is now **deprecated and archived** in favor of `laya[serve]`.

### Cited Findings
**Core repo and package**
- GitHub `NandhaKishorM/laya`: Apache-2.0, 30,410 stars, 2,655 forks, 75 open issues, 116 watchers, created 2026-09-18, pushed 2026-10-03. It has at least 100 contributors. The top contributors are NandhaKishorM (500 commits), aashish254 (230), Bruce-Yii (48), PerryLink (46) and emiliano-go (34). — [GitHub API](https://api.github.com/repos/NandhaKishorM/laya); [contributors](https://api.github.com/repos/NandhaKishorM/laya/contributors)
- PyPI `laya`: latest 0.3.25, Apache-2.0, author "Convai Innovations", summary "Fast, non-autoregressive System 1 decision engine with calibrated probabilities". There are 33 releases since 0.1.0 on 2026-09-18. Extras: `serve, fast, mcp, structured, onnx, langchain, langgraph, llamaindex, crewai`. — [PyPI JSON](https://pypi.org/pypi/laya/json)
- **PyPI releases this week:** 0.3.21 (2026-09-27 19:41), 0.3.22 (09-29 17:48), 0.3.23 (10-01 17:30), 0.3.24 (10-02 17:06) and 0.3.25 (10-03 15:58 UTC). Matching GitHub releases exist for v0.3.20 through v0.3.25. — [PyPI JSON](https://pypi.org/pypi/laya/json); [GitHub releases](https://github.com/NandhaKishorM/laya/releases)
- Downloads: last_day 12,503, last_week 135,766, last_month 109,457. The last_month figure is lower than last_week, which is internally inconsistent; treat these as approximate. — [pypistats](https://pypistats.org/api/packages/laya/recent)
- Checkpoints, all Apache-2.0 on Hugging Face:

  | Checkpoint | Encoder | Params | Context | Use it for | HF likes |
  |---|---|---|---|---|---|
  | `laya` | ModernBERT-large | 421M | 512 | English | 5,054 |
  | `laya-multilingual` | mmBERT-base | 322M | 1024 (up to 8,192) | 100+ languages | 358 |
  | `laya-typed-decisions` | ModernBERT-large | 421M | 1024 | typed-decisions workflows | 144 |

  — [Laya README](https://github.com/NandhaKishorM/laya); [HF API](https://huggingface.co/api/models/convaiinnovations/laya)
- The README claims 33 ms for one question and 7.2 ms per question batched on a T4. It describes training "with reinforcement learning against strictly proper scoring rules (RLCD)", plus a `Router` that picks a checkpoint by script and language. — [Laya README](https://github.com/NandhaKishorM/laya)
- The HF Space `convaiinnovations/laya-demo` is a Gradio app, status RUNNING, with 265 likes. — [HF Spaces API](https://huggingface.co/api/spaces/convaiinnovations/laya-demo)

**Serving (`laya[serve]`, `laya-serve` binary)**
- `laya.serve` exposes the Router over `POST /v1/systemone`, the same wire protocol as Jev. The README says "an existing Jev client … just needs its `baseUrl` repointed". There is also `POST /v1/systemone/batch` (up to 64 states).
- Configuration is through environment variables: `LAYA_API_KEY` (bearer), `LAYA_PRELOAD`, `LAYA_MODELS`, `LAYA_MAX_LOADED`, `LAYA_IDLE_UNLOAD_SECONDS`, `LAYA_ROOT_PATH` and others.
- Documented differences from Jev:
  - Option budget is set by `head_max_len` instead of Jev's 255-option cap, plus a 100-option 413 guard.
  - Every score level needs a description.
  - `confidence` is 1 minus normalized entropy, not Jev's `(n·p_max−1)/(n−1)`, so thresholds do not transfer. Use `answer_confidence` instead.
  - Docker and Nix/NixOS deployment are documented.

  — [Laya README, Self-Hosting](https://github.com/NandhaKishorM/laya#self-hosting-http-server-jev-compatible)
- 0.3.24 (2026-10-02) added `LAYA_JEV_STRICT`, which projects responses onto the strict Jev wire contract for clients that reject unknown fields. 0.3.23 (10-01) put `/health` deployment internals behind the bearer key (security fix #812) and added `SECURITY.md`. — [Laya README, What's new](https://github.com/NandhaKishorM/laya)
- **The standalone PyPI `laya-serve` 0.2.1 (2026-09-26, Apache-2.0, repo `stiermid/laya-serve`) is marked "Deprecated / archived — use `laya[serve]` instead".** Upstream ships the same `laya-serve` binary, so users must uninstall the old package first to avoid a script collision. The GitHub repo is `archived: true` with 2 stars. Its releases ran 0.1.0 (09-22) to 0.2.1 (09-26). — [PyPI laya-serve](https://pypi.org/project/laya-serve/); [GitHub API](https://api.github.com/repos/stiermid/laya-serve)

**MCP**
- `laya[mcp]` provides a `laya-mcp-server` stdio server. Its tools are `laya_predict`, `laya_predict_batch`, `laya_route`, `laya_route_batch`, `laya_decide`, `laya_shortlist`, `laya_preset` and `laya_status`. In 0.3.25 (2026-10-03), setting `LAYA_BASE_URL` points the MCP server at a running `laya-serve` over HTTP without importing torch, so several editor sessions can share one model. — [Laya README, MCP Server](https://github.com/NandhaKishorM/laya#mcp-server-optional)
- There is a separate third-party PyPI package, `laya-mcp` 0.2.2 (Apache-2.0, by PerryLink, last release 2026-09-22). It provides a warm model sidecar, token-budget preflight and a persisted calibration store. Its repo `PerryLink/laya-mcp` has 1 star. It should not be confused with the `laya[mcp]` extra. — [PyPI JSON](https://pypi.org/pypi/laya-mcp/json); [GitHub API](https://api.github.com/repos/PerryLink/laya-mcp)

**Framework integrations**
- Extras: `laya[langchain]` (LangChain and LangGraph), `laya[llamaindex]` (LlamaIndex selectors) and `laya[crewai]` (CrewAI routing). 0.3.21 (2026-09-27) added `LayaDecision` (LangChain), LlamaIndex selectors, CrewAI routing and LangChain `batch()`/`abatch()`. 0.3.23 (10-01) forwarded per-call controls through the LangChain, CrewAI and LlamaIndex wrappers and gated `confidence_threshold` on `answer_confidence`. — [Laya README](https://github.com/NandhaKishorM/laya); [docs: LangChain](https://nandhakishorm.github.io/laya/langchain/)
- The README advertises LangGraph conditional-edge routing under 35 ms with a confidence fallback. — [Laya README](https://github.com/NandhaKishorM/laya#langchain-and-langgraph-integration)

**ONNX, TileLang and other backends**
- `laya[onnx]` and `scripts/export_onnx.py`: 0.3.21 gave `ONNXAgent` `predict_batch`, `predict_long` and `decide_batch`, and added INT8 `--quantize`. 0.3.23 changed `--quantize` to default to per-tensor quantization "because per-channel collapsed the decision model to 32 percent agreement with eager". 0.3.25 unified backends with `Agent(backend=auto|eager|compile|tilelang|onnx)`. — [Laya README](https://github.com/NandhaKishorM/laya)
- `laya[fast]` is a TileLang GPU fast path. It fuses GEMM, GEGLU, LayerNorm, RoPE and sliding-window flash attention kernels, with CUDA-graph capture per shape bucket. Measured parity is max |Δp| ≤ 0.05 against fp32. It falls back to the stock forward on CPU/MPS. In 0.3.25 the kernels also lower for CPU as an fp32 specialization. — [Laya README, GPU Fast Path](https://github.com/NandhaKishorM/laya#gpu-fast-path-tilelang)
- The README says `laya-ts/` (TypeScript, Node.js and browser) is published to npm as `laya-ts` from `laya-ts-v*` tags. The npm registry returned "not found" for `laya-ts`, and no `laya-ts-v*` tags appear in the tag list. — [Laya README](https://github.com/NandhaKishorM/laya); [npm](https://registry.npmjs.org/laya-ts); [tags API](https://api.github.com/repos/NandhaKishorM/laya/tags)
- The README main branch already documents a "What's new in 0.3.26" section: a .NET SDK (`laya-dotnet/`, ONNX Runtime, no NuGet package yet) and histogram binning in laya-ts. 0.3.26 is **not yet on PyPI or tagged** as of the snapshot. — [Laya README](https://github.com/NandhaKishorM/laya); [PyPI JSON](https://pypi.org/pypi/laya/json)

**Calibration and fine-tuning**
- The fine-tuning notebook `notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb` (Kaggle 2×T4) and an Apple Silicon script `laya_finetune_typed_decisions_mps.py` run the whole loop: build dataset, train with RLCD, calibrate temperatures, evaluate, export. The fine-tuned `laya-typed-decisions` scores 0.766 accuracy against 0.362 for the base English checkpoint on a 2,000-decision benchmark. — [Laya README](https://github.com/NandhaKishorM/laya#fine-tune-for-better-accuracy); [notebooks dir](https://github.com/NandhaKishorM/laya/tree/main/notebooks)
- **The notebook was updated this week:** "trim train items before DDP sharding" (2026-09-28), and "align calibration temperature bounds with runtime" (09-29, merged as #642 on 10-01). — [commits API](https://api.github.com/repos/NandhaKishorM/laya/commits?path=notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb)
- Calibration tooling added this week:
  - 0.3.24: per-option-count abstention thresholds (`fit_abstention_thresholds`), histogram binning (`fit_binning_map`, `apply_binning_map`), atomic `save_calibration`, and Brier, AURC and selective-accuracy eval metrics.
  - 0.3.25: binning maps wired into answers and shipped with the calibration payload.
  - 0.3.21: opt-in `min_confidence` abstention.

  The README warns: "Both checkpoints are over-confident as shipped and `laya-multilingual` has no fitted temperatures at all, so fit them before relying on these numbers." — [Laya README](https://github.com/NandhaKishorM/laya)

**Laya-adjacent runtimes and ports (third party)**
- `mizorewww/laya-mlx`, a native MLX runtime claiming 7–14 ms on M3 Max: Apache-2.0, 6,733 stars, first release v0.3.0 on **2026-10-02**. — [GitHub API](https://api.github.com/repos/mizorewww/laya-mlx)
- `receptron/laya`, a Node.js/TypeScript runner via ONNX Runtime: MIT, 746 stars, v0.1.1 on 2026-09-19. — [GitHub API](https://api.github.com/repos/receptron/laya)
- `italoalmeida0/laya-system-one` (npm `laya-system-one` 1.3.3, 2026-09-27): a Rust/WASM/WebGPU engine described as "TypeSafe Jev wire-compatible (/v1/systemone)". It has 3 stars. — [npm](https://registry.npmjs.org/laya-system-one); [GitHub API](https://api.github.com/repos/italoalmeida0/laya-system-one)
- Other ports:
  - `marcreichel/laya-php` (Apache-2.0, 28 stars, created 2026-09-26).
  - `ChristianAlexander/laya_ex` (Elixir).
  - `jlt-commons/lev` (Jolt).
  - `vishalmysore/layaForWeb`.

  — [GitHub API laya-php](https://api.github.com/repos/marcreichel/laya-php); [GitHub search](https://api.github.com/search/repositories?q=laya+system&sort=stars)
- llama.cpp's new `/v1/systemone` PR lists "laya" among its supported models; see Q3. — [llama.cpp PR #29818](https://github.com/ggml-org/llama.cpp/pull/29818)

### Inferences
- Laya is the de facto open reference implementation of the Jev wire protocol. Its cadence of about one release a day with 9–21 contributors per release is very fast, but API churn is high. Projects like s1guard should pin versions (s1guard pins `laya>=0.3.22`) and re-run calibration on upgrades.
- Consolidating serve and MCP into extras of the core package lowers the integration surface. Any s1guard docs that say `pip install laya-serve` should be updated to `pip install "laya[serve]"`.
- The `confidence` semantics differ from Jev's. Policy thresholds tuned on Jev cannot be reused on Laya; gate on `answer_confidence`.

### Gaps
- Hugging Face download counts came back as 0 from the API (`downloads` and `downloadsAllTime`), so model download volume is unverified.
- `laya-ts` npm availability and a 0.3.26 release date are unverified.
- The 30k-star count in about two weeks could not be checked for organic growth.

## Q3. Third-party Jev-compatible `/v1/systemone` servers, proxies, gateways, catalogs and specs

### Takeaway
`/v1/systemone` has become the de facto wire standard this week. **Ollama v0.35.0 (2026-09-28) and llama.cpp (PR merged 2026-10-02) both ship native `/v1/systemone` endpoints.** LiteLLM proxies Jev via pass-through (stable in v1.103.0 on 2026-09-28). OpenRouter exposes `/api/v1/systemone` and an alpha `/api/alpha/decisions`. vLLM and SGLang have open PRs and RFCs. There is no formal, vendor-neutral spec document; ModelSystem.One is a catalog, not a wire spec.

### Cited Findings
**Major inference runtimes**
- **Ollama v0.35.0 (published 2026-09-28)**: "Ollama now supports decision models through `/v1/systemone`, based on TypeSafe's Jev API". The models are Nimble (Bespoke Labs) and Tev1 (Together AI). v0.35.1 followed on 2026-09-29. — [Ollama release v0.35.0](https://github.com/ollama/ollama/releases/tag/v0.35.0); [releases API](https://api.github.com/repos/ollama/ollama/releases)
- **llama.cpp PR #29818** "llama, server: add /v1/systemone API (models: laya, julia-1, lev, openjev, kev)" was opened 2026-10-01 and **merged 2026-10-02** by ngxson. A follow-up, #29832 "server: model-agnostic impl of systemone/decision API", was opened 2026-10-02 and is still open. Georgi Gerganov announced: "The `/v1/systemone` endpoint is available in the latest llama builds." — [PR #29818](https://github.com/ggml-org/llama.cpp/pull/29818); [PR #29832](https://github.com/ggml-org/llama.cpp/pull/29832); [ggml blog](https://huggingface.co/blog/ggml-org/decision-models-in-llamacpp); [Gerganov on X](https://x.com/ggerganov/status/2106029758350032937)
- llama-swap PR #1197 adds `/v1/systemone` to its POST JSON routes, and llmman PR #579 adds a `/v1/systemone` decision API. Merge status was not checked. — [llama-swap #1197](https://github.com/mostlygeek/llama-swap/pull/1197); [llmman #579](https://github.com/llmmanorg/llmman/pull/579)
- **vLLM** has only open items:
  - PR #59299 "[Feat] Structured decisions endpoint (`/v1/systemone`)" (2026-09-29, by mmastrac).
  - #58951 "Support /v1/systemone endpoint for models like convaiinnovations/laya" (09-28).
  - #58429 "[Model] Add Laya typed-decision models" (09-23).
  - RFC #59365 "/v1/decisions: First-class Jev typed decision endpoint … (with /v1/systemone compatibility)" (09-30).

  — [vLLM #59299](https://github.com/vllm-project/vllm/issues/59299); [#59365](https://github.com/vllm-project/vllm/issues/59365); [#58951](https://github.com/vllm-project/vllm/issues/58951); [#58429](https://github.com/vllm-project/vllm/issues/58429)
- **SGLang**: #42183 "[Feature] Serve pplx-decider decision checkpoints on /v1/systemone" was **merged 2026-10-03**. #41712 "Serve decision model checkpoints natively on /v1/decisions, /v1/jev, and /v1/systemone" (09-29) and #41210 (an example serving `/v1/systemone` on `/v1/score`) are open. — [SGLang #42183](https://github.com/sgl-project/sglang/pull/42183); [#41712](https://github.com/sgl-project/sglang/issues/41712); [#41210](https://github.com/sgl-project/sglang/issues/41210)
- **vLLM Semantic Router** (Apache-2.0, 6,015 stars) released v0.4.0 on 2026-09-27. It has open issues to "Serve Decision 1.0 models with typed SystemOne APIs" (#4086) and to "Read a classifier signal from a SystemOne decision endpoint" (#4311, 09-28). — [GitHub API](https://api.github.com/repos/vllm-project/semantic-router); [#4086](https://github.com/vllm-project/semantic-router/issues/4086); [#4311](https://github.com/vllm-project/semantic-router/issues/4311)

**Gateways and proxies**
- **LiteLLM**: the blog says "TypeSafe AI's Jev lands in LiteLLM v1.103.0-rc: call it through the proxy with logging and cost tracking". Clients replace `https://api.typesafe.ai` with `LITELLM_PROXY_BASE_URL/typesafe` and call `/typesafe/v1/systemone`. Cost tracking and logging are supported; end-user tracking and streaming are not. There is also a "Relevance-Based Compaction (TypeSafe / Jev)" guardrail that blanks out tool results Jev scores as irrelevant. — [LiteLLM blog](https://docs.litellm.ai/blog/typesafe_jev); [pass-through docs](https://docs.litellm.ai/docs/pass_through/typesafe); [guardrail docs](https://docs.litellm.ai/docs/proxy/guardrails/typesafe)
- LiteLLM release dates: v1.103.0-rc.1 on 2026-09-20, **v1.103.0 on 2026-09-28**, v1.103.1 on 09-30, v1.103.2 on 10-01, and v1.104.0-rc.2 on 09-30. Open TypeSafe fix PRs include #42206 (pricing pass-through calls), #41737 and #41741 (validation), and #44133 (pass-through routing, 10-02). — [LiteLLM releases API](https://api.github.com/repos/BerriAI/litellm/releases); [#42206](https://github.com/BerriAI/litellm/pull/42206); [#44133](https://github.com/BerriAI/litellm/pull/44133)
- The pass-through is a proxy to TypeSafe's hosted Jev, not a provider abstraction over local servers. Whether LiteLLM can pass through to a self-hosted `laya-serve` was not confirmed in its docs. — [pass-through docs](https://docs.litellm.ai/docs/pass_through/typesafe)
- **OpenRouter**'s docs list `POST https://openrouter.ai/api/v1/systemone` serving `typesafe/jev-1.13` (alias `~typesafe/jev-latest`), intended for users of the TypeSafe JS/Python SDKs "by changing the base URL". They also list a separate alpha `/api/alpha/decisions` endpoint. A search snippet lists Solar Decide (Upstage), Span-01 (Respan), Kev and Liquid AI's D1 as System One models on OpenRouter. The docs page gave no dates. — [OpenRouter Jev docs](https://openrouter.ai/docs/guides/community/jev); [OpenRouter D1](https://openrouter.ai/liquid/d1); [Solar Decide](https://openrouter.ai/upstage/solar-decide)
- **`@zatsepin/jigor`** is a "System One decision gateway CLI + server — von/laya local ONNX backends, jev on OpenRouter Decisions". It is Apache-2.0, at 0.1.9 (2026-09-30), and its repo `Partysun/jigor` has 2 stars. — [npm](https://registry.npmjs.org/@zatsepin%2fjigor); [GitHub API](https://api.github.com/repos/Partysun/jigor)
- **`thusinh1969/BrighTO_Router`** is a Rust LLM gateway with SystemOne/JEV routes. It is Apache-2.0 with 19 stars; v1.0.0 shipped 2026-09-24 and v1.0.1 on 09-25. — [GitHub API](https://api.github.com/repos/thusinh1969/BrighTO_Router)
- **`FFatTiger/new-api-plugin-typesafe`** is a native `/v1/systemone` task plugin for QuantumNous/new-api. It is Apache-2.0 with 3 stars, created 2026-09-18. — [GitHub API](https://api.github.com/repos/FFatTiger/new-api-plugin-typesafe)

**Open self-hosted Jev-compatible servers.** Snapshot 2026-10-03, sorted by stars. Rows marked **this week** had a release or creation in the window.

| Project | What | License | Stars / forks | Created | Latest release or push | Source |
|---|---|---|---|---|---|---|
| ollaya-dev/ollaya | "pull and serve Laya, decider, NLI and GLiClass behind a TypeSafe-compatible API" | Apache-2.0 | 1,155 / 65 | 2026-09-23 | **v0.9.0 on 10-02; v0.7.2–v0.9.0 this week** | [API](https://api.github.com/repos/ollaya-dev/ollaya) |
| nokia-applied-research/AnyJev | "Turn any LLM into a Jev-style decision model: typed decisions, real probabilities, no training" | Apache-2.0 | 1,021 / 132 | 2026-09-21 | **v0.1.0 on 09-26, v0.2.0 on 09-28** | [API](https://api.github.com/repos/nokia-applied-research/AnyJev) |
| wfzyx/von (+ npm `von-sdk`) | "open-source System One decision model … local drop-in alternative to TypeSafe Jev" | Apache-2.0 | 825 / 63 | 2026-09-18 | **v1.3.2–v1.3.7, 09-29 to 10-02** | [API](https://api.github.com/repos/wfzyx/von); [npm](https://registry.npmjs.org/von-sdk) |
| razorback16/openjev | Jev-compatible server on DiffusionGemma | Apache-2.0 | 594 / 46 | 2026-09-18 | push 09-29, no releases | [API](https://api.github.com/repos/razorback16/openjev) |
| featherless-ai/simple-jev | "Turn any open model into a classifier/jev endpoint" (next-token logits, per ModelSystem.One) | Apache-2.0 | 582 | 2026-09-18 | push 10-03 | [API](https://api.github.com/repos/featherless-ai/simple-jev) |
| ekzhang/openjev-sglang | "Jev-compatible API endpoint based on open models (prefill-only)" | none declared | 337 / 45 | 2026-09-17 | push 10-01 | [API](https://api.github.com/repos/ekzhang/openjev-sglang) |
| mode-io/vllm-jev | "Native vLLM serving for Jev decision models" | Apache-2.0 | 238 | 2026-09-24 | push 10-03 | [API](https://api.github.com/repos/mode-io/vllm-jev) |
| HarnessRouter/SystemOneHarness | Run Jev and other S1 models locally or on HarnessRouter | Apache-2.0 | 196 / 17 | 2026-09-19 | v0.4.0 on 09-21 (stale this week) | [API](https://api.github.com/repos/HarnessRouter/SystemOneHarness) |
| alvarobartt/sys1 | Rust, "TypeSafe AI compatible API" for open-weight models | Apache-2.0 | 48 / 2 | 2026-09-22 | v0.0.3 on 09-25, push 10-02 | [API](https://api.github.com/repos/alvarobartt/sys1) |
| 0xBakeer/arbiter | Serves Laya or custom S1 models on NVIDIA or Apple Silicon, Jev-compatible | MIT | 33 | 2026-09-20 | push 09-24 | [API](https://api.github.com/repos/0xBakeer/arbiter) |
| yijunyu/jev-rs | Rust `/v1/systemone` engine, any LLM, one prefill | Apache-2.0 | 17 | 2026-09-21 | v0.1.0 on 09-21 | [API](https://api.github.com/repos/yijunyu/jev-rs) |
| lawrence3699/jev-style | systemone-compatible local server plus agent skills | Apache-2.0 | 12 | **2026-09-25** | **v0.2.0–v0.4.0, 09-26 to 10-02** | [API](https://api.github.com/repos/lawrence3699/jev-style) |
| Xiaooolong/vev | Jev-like vision decision models (Qwen3.5) | Apache-2.0 | 11 | **2026-09-30** | **v0.1.1 on 10-01** | [API](https://api.github.com/repos/Xiaooolong/vev) |
| chaitin/Decis | "one /v1/systemone endpoint, open weights (Laya, kev), one Docker image" | Apache-2.0 | 9 | 2026-09-22 | **v0.3.2 on 09-26, v0.4.0 on 09-30** | [API](https://api.github.com/repos/chaitin/Decis) |
| aleskxyz/kev-onnx | CPU ONNX `/v1/systemone` server for KEV | Apache-2.0 | 6 | **2026-09-27** | push 09-27 | [GitHub search](https://api.github.com/search/repositories?q=v1/systemone) |
| org2AI/wald-4b | 4B open-weight decision model, Jev-compatible API | Apache-2.0 | 5 | **2026-09-27** | push 10-01 | [GitHub search](https://api.github.com/search/repositories?q=v1/systemone) |
| ToufiqQureshi/anarkali | 150M engine, abstain flag, `/v1/systemone`, ONNX | Apache-2.0 | 3 | **2026-09-28** | push 10-03 | [GitHub search](https://api.github.com/search/repositories?q=v1/systemone) |
| Arcobalneo/open-jevlike-infer | Production server for Clef-Flash on vLLM | Apache-2.0 | 1 | **2026-10-02** | 10-02 | [GitHub search](https://api.github.com/search/repositories?q=v1/systemone) |
| zknpr/cleffa | C11 + Metal engine for Cloudflare Clef/Clef-Flash, Jev/S1 API | MIT | 2 | **2026-10-03** | 10-03 | [GitHub search](https://api.github.com/search/repositories?q=systemone) |

- A GitHub search for "systemone" repos created on or after 2026-09-26 returned **75** results. — [GitHub search API](https://api.github.com/search/repositories?q=systemone+created:%3E=2026-09-26)
- ComfyUI nodes (`rockerBOO/systemone-nodes`, created 2026-09-29) and LLamaSharp/.NET routing (`TheIntelligentEnterpriseGroup/SystemOne.LLamaSharp`, created 2026-09-28) are new this week. — [GitHub search API](https://api.github.com/search/repositories?q=systemone+created:%3E=2026-09-26)

**Client SDKs and vendor-neutral clients (beyond TypeSafe's)**
- `asynq-io/system-one` (PyPI `system-one`): "A vendor-neutral SDK for System One models. One contract — `ask(state, questions) -> answers`". Extras: `http, onnx, hub, mcp, export`. Apache-2.0. Releases: **0.3.0 on 2026-09-26 and 0.4.0 on 2026-10-01**. The repo has 1 star. — [PyPI JSON](https://pypi.org/pypi/system-one/json); [GitHub API](https://api.github.com/repos/asynq-io/system-one)
- `saibimajdi/typesafeai-dotnet-sdk`: a community .NET SDK, MIT, 12 stars, last release v0.1.0-alpha.2 on 2026-09-18. — [GitHub API](https://api.github.com/repos/saibimajdi/typesafeai-dotnet-sdk)
- Other clients:
  - `getmissionctrl/hs-jev` (Haskell, cited by Laya as working against laya-serve).
  - `@patdown/jev` (Effect HttpClient).
  - `@effect-uai/typesafe-ai`.
  - PyPI `jev` 0.3.0 (a decorator that compiles Python function signatures into Jev queries; no license declared, no repo URL).

  — [GitHub API hs-jev](https://api.github.com/repos/getmissionctrl/hs-jev); [npm search](https://registry.npmjs.org/-/v1/search?text=jev&size=20); [PyPI jev](https://pypi.org/pypi/jev/json)

**MCP servers for Jev or System One**
- `jkudish/jev-mcp` (npm `@jkudish/jev-mcp`): MIT, 487 stars. Its releases ran **v0.10.0 (09-26) through v0.13.0 (10-02)**. — [GitHub API](https://api.github.com/repos/jkudish/jev-mcp)
- `itsmostafa/system-one-connector`, a multi-model MCP covering "Jev, D1, …": MIT, 340 stars, **v0.4.7–v0.4.10 from 09-27 to 10-02**. — [GitHub API](https://api.github.com/repos/itsmostafa/system-one-connector)
- Smaller MCP servers:
  - `@jev-harness/mcp` 0.7.0 (09-27).
  - `jev-mcp` on PyPI 0.1.2 (09-21, MIT).
  - `typesafe-mcp` on PyPI 0.5.2 (09-21, MIT; repo now `Renwang-Huang/arbitype`).
  - `@y0usaf/typesafe-mcp` (09-16).

  — [npm search](https://registry.npmjs.org/-/v1/search?text=jev&size=20); [PyPI jev-mcp](https://pypi.org/pypi/jev-mcp/json); [PyPI typesafe-mcp](https://pypi.org/pypi/typesafe-mcp/json)

**Catalogs, benchmarks and the "spec" question**
- **ModelSystem.One** is a curated catalog of "Decision Models (System One): AI that returns typed decisions with calibrated probabilities". It lists about 61–73 models, including Laya, Kev (Jared Palmer), Strands Decider 2B (AWS/Strands), Tev1 (Together AI), Clef (Cloudflare), D1 (Liquid AI), Jeeves (PostHog) and FRIDA-Decisions (SberAI). Page dates run to 2026-10-02. — [ModelSystem.One](https://modelsystem.one/)
- Its **runtimes catalog** lists, among others: Ollama (v0.35+, native `/v1/systemone`), Ollaya, openjev-sglang, simple-jev (Featherless), vLLM Jev (mode-io), SemIf (WebGPU), TypeLLM ("playground and API available since Sep 29, 2026"), OpenDecision, OpenDecisions/OneJev, litjev, Bandits, classifier.dev, Solar Decide (Upstage, hosted beta) and OpenAI Decisions API (hosted, limited preview). — [ModelSystem.One runtimes](https://modelsystem.one/runtimes/)
- **The ModelSystem.One "spec" page holds catalog inclusion criteria, not a wire specification.** Models must return "typed decisions (`choice`, `score`, `boolean`) with calibrated probabilities". The page was last updated 2026-09-18 and is backed by the repo `fabricioctelles/modelsystem` (MIT, 1 star). — [ModelSystem.One spec](https://modelsystem.one/spec/); [GitHub API](https://api.github.com/repos/fabricioctelles/modelsystem)
- `AnotiaWang/awesome-decision-models` (CC0-1.0, 606 stars) is another catalog covering hosted APIs, open-weight models, runtimes and SDKs. — [GitHub API](https://api.github.com/repos/AnotiaWang/awesome-decision-models)
- `fstandhartinger/jevbench`, "JevBench v1 – a benchmark for Jev-class typed decision models", is MIT with 208 stars. Its last release was v1.4.2 on 2026-09-24. — [GitHub API](https://api.github.com/repos/fstandhartinger/jevbench)

### Inferences
- The de facto standard is TypeSafe's own `/v1/systemone` request and response shape, adopted by Ollama, llama.cpp, OpenRouter, Laya and dozens of small servers. It is not governed by any neutral body, and variants are already diverging. Three examples:
  - Laya's `confidence` definition, `head_max_len` option limits and `LAYA_JEV_STRICT` projection.
  - The competing `/v1/decisions` path names in vLLM RFC #59365 and SGLang #41712.
  - OpenRouter's separate `/api/alpha/decisions`.
- For production, the tiers are as follows:
  - Most credible: Ollama, llama.cpp and Laya. These are large projects with active maintainers.
  - Next: LiteLLM pass-through, for hosted Jev with cost tracking.
  - Third: Ollaya, AnyJev and Von, which are active but around two weeks old.
  - Most other servers have under 50 stars, a single maintainer, and no releases, or have gone stale.

### Gaps
- There is no published OpenAPI or JSON Schema for `/v1/systemone` from TypeSafe or any neutral party.
- I did not verify whether LiteLLM supports a generic `/v1/systemone` provider for self-hosted backends, as opposed to the TypeSafe pass-through only.
- OpenRouter's System One launch date is unknown.
- The merge status of the llama-swap and llmman PRs was not checked.
- The ModelSystem.One maintainer's identity is not stated on the site.

## Q4. Adjacent frameworks for using LLMs as calibrated decision models (not System-One-branded unless noted)

### Takeaway
The general structured-output tools (Outlines, Guidance, Instructor, BAML, DSPy) are mature and widely used, but they constrain *format*. They do not return calibrated per-option probabilities unless you add logprob readout and calibration yourself. A new wave of System-One-branded "turn any LLM into a Jev" projects fills that gap with logit or logprob readout, led by Nokia's AnyJev, Featherless simple-jev and SemIf-OpenJev. Pydantic AI is the one mainstream framework that now has a first-class decision-model abstraction.

### Cited Findings
**General structured-output frameworks (not System One)**

| Project | Description | License | Stars / forks | Latest release |
|---|---|---|---|---|
| dottxt-ai/outlines | "Structured Outputs" | Apache-2.0 | 15,896 / 895 | 1.3.3 on 2026-08-06 |
| guidance-ai/guidance | "A guidance language for controlling large language models" | MIT | 21,786 / 1,213 | 0.3.2 on 2026-03-18 |
| 567-labs/instructor | "structured outputs for llms" | MIT | 13,971 / 1,283 | v1.17.0 on 2026-09-09 |
| BoundaryML/baml | "The programming language for agents" | Apache-2.0 | 9,377 / 496 | nightly on 2026-10-02 |
| stanfordnlp/dspy | "The framework for programming—not prompting—language models" | MIT | 38,486 / 3,395 | 3.4.0 on 2026-09-25 |

- Outlines last pushed 2026-09-21; Guidance last pushed 2026-05-21, so it is slowing; Instructor last pushed 2026-10-01; BAML last pushed 2026-10-03; DSPy last pushed 2026-10-02.

  — [outlines](https://api.github.com/repos/dottxt-ai/outlines); [guidance](https://api.github.com/repos/guidance-ai/guidance); [instructor](https://api.github.com/repos/567-labs/instructor); [baml](https://api.github.com/repos/BoundaryML/baml); [dspy](https://api.github.com/repos/stanfordnlp/dspy)

**Pydantic AI (bridges both worlds)**
- `pydantic/pydantic-ai` is MIT with 20,385 stars; v2.54.0 shipped 2026-10-03.
- Merged PRs:
  - #8450 "Add `TypeSafeModel` for TypeSafe's Jev" (2026-09-18).
  - #8696 "Add `DecisionModel`, a base for Decisions-protocol models, and make `TypeSafeModel` one" (2026-09-24).
  - #8962 "Add a `typesafe` extra to `pydantic-clai2`" (**2026-09-28, this week**).
- PyPI `pydantic-ai-slim` exposes a `typesafe` extra.

  — [GitHub API](https://api.github.com/repos/pydantic/pydantic-ai); [PR #8450](https://github.com/pydantic/pydantic-ai/pull/8450); [PR #8696](https://github.com/pydantic/pydantic-ai/pull/8696); [PR #8962](https://github.com/pydantic/pydantic-ai/pull/8962); [PyPI JSON](https://pypi.org/pypi/pydantic-ai-slim/json)

**System-One-branded "LLM to decision model" toolkits**
- `nokia-applied-research/AnyJev`: "Turn any LLM into a Jev-style decision model: typed decisions, real probabilities, no training." Apache-2.0, 1,021 stars, **v0.1.0 on 2026-09-26 and v0.2.0 on 2026-09-28**. — [GitHub API](https://api.github.com/repos/nokia-applied-research/AnyJev)
- `featherless-ai/simple-jev`: "Turn any open model into a classifier/jev endpoint". ModelSystem.One describes it as using "next-token logits". Apache-2.0, 582 stars. — [GitHub API](https://api.github.com/repos/featherless-ai/simple-jev); [ModelSystem.One runtimes](https://modelsystem.one/runtimes/)
- `TheoLeeCJ/SemIf-OpenJev`: "Semantic ifs from open models, on a 3090 at home. Independent; not affiliated with Jev or TypeSafe." MIT, 4,674 stars, last push 2026-09-23. — [GitHub API](https://api.github.com/repos/TheoLeeCJ/SemIf-OpenJev)
- `yijunyu/jev-rs`: "System One judgments (noul/choice/score) from any LLM in one prefill". — [GitHub API](https://api.github.com/repos/yijunyu/jev-rs)
- TypeSafe's own `system-one-adapter` (see Q1) is the official LLM-backed variant. Its probabilities come from structured or verbalized output, not logits. — [README](https://github.com/typesafe-ai/system-one-adapter-python)

### Inferences
- For a guardrail like s1guard, the choice is:
  - (a) a native decision model (Laya or Jev) with fitted calibration;
  - (b) a logit-readout wrapper over an open LLM (AnyJev, simple-jev, llama.cpp `/v1/systemone`), where probabilities come from the model's softmax but still need temperature or binning calibration;
  - (c) the TypeSafe adapter or Instructor/Outlines-style structured output, where probabilities are verbalized and least trustworthy.
- DSPy and BAML could orchestrate or optimize decision prompts. Neither ships a System One wire adapter that I could verify.

### Gaps
- I did not verify whether Outlines, Guidance, Instructor, BAML or DSPy added any `/v1/systemone` or decision-model features this week. Only repo metadata was checked.
- AnyJev's calibration method and benchmark claims were not read in detail.

## Q5. Agent-framework integrations announced this week (Jev, OpenAI Decisions API)

### Takeaway
The week's headline integrations:
- **Microsoft Agent Framework Python 1.20.0 (2026-10-02)** shipped an official `agent-framework-typesafe` connector, with a .NET counterpart in PR.
- **Vercel's `@ai-sdk/typesafe-ai`** had four releases (3.0.9–3.0.12, 09-28 to 09-30).
- **LangChain.js `@langchain/typesafe` 0.0.2** shipped on 10-01.
- **OpenAI announced its Decisions API at DevDay (2026-09-29)** in limited preview. It has no public docs, no SDK support and no third-party framework integrations yet, beyond OpenAI's own Codex using it opt-in.

LlamaIndex and CrewAI have no first-party Jev integrations; there are only community packages and Laya extras.

### Cited Findings
**Microsoft Agent Framework**
- Release python-1.20.0 (2026-10-02) notes: "**agent-framework-typesafe**: Add … the TypeSafe AI connector (#8592)". PR #8592 "Python: Add TypeSafe AI connector" merged 2026-09-29. — [MAF releases API](https://api.github.com/repos/microsoft/agent-framework/releases); [PR #8592](https://github.com/microsoft/agent-framework/pull/8592)
- PyPI `agent-framework-typesafe` 1.0.0a261002 was first uploaded 2026-10-02 (alpha). — [PyPI JSON](https://pypi.org/pypi/agent-framework-typesafe/json)
- Open PRs:
  - .NET #8859 "Add Microsoft.Agents.AI.TypeSafe with Jev as a tool and as an IChatClient (alpha)" (2026-09-29).
  - #8563 "Add IDecisionClient (experimental), DecisionLoopEvaluator, and the Microsoft.Agents.AI.TypeSafe (Jev) provider" (09-20), which references dotnet/extensions#7764.
  - Proxy bug and fix #8983/#8984 (10-02).

  The feature request #8556 was closed 2026-09-29. — [MAF #8859](https://github.com/microsoft/agent-framework/pull/8859); [#8563](https://github.com/microsoft/agent-framework/issues/8563); [#8556](https://github.com/microsoft/agent-framework/issues/8556); [#8983](https://github.com/microsoft/agent-framework/issues/8983)

**Vercel AI SDK**
- The official `@ai-sdk/typesafe-ai` provider (Apache-2.0, in the `vercel/ai` monorepo) was created 2026-09-16. Latest is 3.0.12 (2026-09-30), and 3.0.9–3.0.12 were all released 09-28 to 09-30. It had 485,346 downloads from 09-25 to 10-01. — [npm](https://registry.npmjs.org/@ai-sdk%2ftypesafe-ai); [npm downloads](https://api.npmjs.org/downloads/point/last-week/@ai-sdk%2ftypesafe-ai)
- The AI SDK added an "experimental evaluation API and model spec" (PR #20848) and a "native evaluation provider" (PR #20851), both merged 2026-09-16. The usage is `experimental_evaluate` with `typeSafeAi.evaluationModel('jev-latest')`. Jev is also listed on the Vercel AI Gateway. — [vercel/ai #20848](https://github.com/vercel/ai/pull/20848); [#20851](https://github.com/vercel/ai/pull/20851); [Vercel KB guide](https://vercel.com/kb/guide/typesafe-jev-and-ai-sdk)

**LangChain and LangGraph**
- PyPI `langchain-typesafe`: 0.0.1a3 (2026-09-20), MIT, "A LangChain integration for TypeSafe classifiers". It is hosted in the `langchain-ai/langchain` monorepo, with a provider docs page. There is no release this week. — [PyPI JSON](https://pypi.org/pypi/langchain-typesafe/json); [LangChain docs](https://docs.langchain.com/oss/python/integrations/providers/typesafe)
- npm `@langchain/typesafe`: 0.0.1 (09-18), then **0.0.2 on 2026-10-01**, MIT, in the langchainjs monorepo. — [npm](https://registry.npmjs.org/@langchain%2ftypesafe)
- Open PRs:
  - #40556 "agent middleware powered by TypeSafe classifiers" (09-17).
  - #40801 "experimental add `TsHybridToolSelectorMiddleware`" (09-24).
  - #40812 and #40813, which select SemIf for tool-selector middleware (09-24).

  — [#40556](https://github.com/langchain-ai/langchain/pull/40556); [#40801](https://github.com/langchain-ai/langchain/pull/40801)
- Laya's own `laya[langchain]` and `laya[langgraph]` extras were updated this week; see Q2. — [Laya README](https://github.com/NandhaKishorM/laya)

**LlamaIndex**
- The GitHub issue/PR search for typesafe, jev or systemone in `run-llama/llama_index` returned nothing. — [GitHub search](https://github.com/run-llama/llama_index/issues?q=typesafe)
- The community `WiktorB2004/llama-index-jev` (MIT, 8 stars) publishes `llama-index-postprocessor-jev` (a reranker) and `llama-index-selectors-jev` (a selector). Both are at 0.1.1 from 2026-09-18, with no release this week. — [GitHub API](https://api.github.com/repos/WiktorB2004/llama-index-jev); [PyPI postprocessor](https://pypi.org/pypi/llama-index-postprocessor-jev/json); [PyPI selectors](https://pypi.org/pypi/llama-index-selectors-jev/json)
- Laya ships LlamaIndex selectors via `laya[llamaindex]` (from 0.3.21, 2026-09-27). — [Laya README](https://github.com/NandhaKishorM/laya)

**CrewAI**
- The search of the `crewAIInc/crewAI` repo returned no TypeSafe, Jev or systemone hits. The only CrewAI path found is `laya[crewai]` routing (0.3.21, 2026-09-27). — [GitHub search](https://github.com/crewAIInc/crewAI/issues?q=jev); [Laya README](https://github.com/NandhaKishorM/laya)

**OpenAI Decisions API and the OpenAI Agents SDK**
- OpenAI Developers: "Give your app real-time decision-making with Decisions API, powered by GPT-6 Luna. Define questions and possible answers to classify content, route requests, or choose an agent's next action. Available in limited preview." — [OpenAIDevs on X](https://x.com/OpenAIDevs/status/2105003318917697873)
- It was presented at DevDay on 2026-09-29. Secondary sources report about 150 ms responses against 1.6 s for a standard Luna call, and say it accepts text or image context. — [Pasquale Pillitteri](https://pasqualepillitteri.it/en/news/19372/openai-decisions-api-jev); [Neowin](https://www.neowin.net/news/openai-unveils-500-chatgpt-pro-plan-decisions-api-and-major-codex-upgrades-at-devday-2026/)
- A secondary source says that "as of October 2, documentation guides, API references, and API changelog entries were not available", with no public schema, SDK methods or pricing. — [aipass.one](https://aipass.one/blog/openai-decisions-api-explained)
- `openai/openai-python` released v3.22.0 (09-29) through v3.24.0 (10-02), and none of the release-note lines mention "decision". GitHub issue search for "decisions" in `openai/openai-agents-python` found no Decisions API integration. — [openai-python releases API](https://api.github.com/repos/openai/openai-python/releases); [GitHub search](https://github.com/openai/openai-agents-python/issues?q=decisions)
- OpenAI's own Codex merged PR #50099 "Add opt-in Decisions comparison for Guardian V2" (2026-10-01) and #50019 "Protect the guardian decisions API key from environment forwarding". These are the only open-source OpenAI repos found using it. — [codex #50099](https://github.com/openai/codex/pull/50099); [codex #50019](https://github.com/openai/codex/pull/50019)
- ModelSystem.One lists the OpenAI Decisions API as a "Hosted Wrapper", marks it "/v1/systemone: Yes", and calls it a "Limited-preview OpenAI API that points GPT-6 Luna at your own questions". With no public schema, this compatibility claim is unverifiable. — [ModelSystem.One runtimes](https://modelsystem.one/runtimes/)

**Other integrations this week**
- `@openclaw/typesafe` 2026.9.8 (2026-10-03), "OpenClaw TypeSafe typed decision provider", in the `openclaw/openclaw` repo with no license field. — [npm](https://registry.npmjs.org/@openclaw%2ftypesafe)
- `@antseed/provider-typesafe` 0.1.1 (10-01). — [npm search](https://registry.npmjs.org/-/v1/search?text=system%20one%20decision&size=15)
- `strands-labs/strands-decider`, Apache-2.0, 272 stars, **created 2026-09-29**. ModelSystem.One lists "Strands Decider 2B" under AWS/Strands. — [GitHub API](https://api.github.com/repos/strands-labs/strands-decider); [ModelSystem.One](https://modelsystem.one/)

### Inferences
- First-party framework support for Jev-style decisions now exists in MAF (Python GA connector, alpha package), Vercel AI SDK (experimental API), LangChain (alpha) and Pydantic AI. All are pre-1.0 or experimental and target hosted Jev. Self-hosted Laya works with them only where the client allows a base-URL override.
- The OpenAI Decisions API is a hosted competitor, not open tooling. It has no public schema yet, so no OSS framework can integrate it, and claims of `/v1/systemone` compatibility should be treated as unverified.
- The emerging abstraction layers to watch for vendor neutrality are Pydantic AI's `DecisionModel` and MAF's proposed `IDecisionClient` (plus dotnet/extensions#7764).

### Gaps
- I did not find primary OpenAI docs for the Decisions API; it is limited preview, so latency figures are from secondary sources only.
- I could not confirm whether `langchain-typesafe` (Python) had any activity this week beyond the open PRs.
- I did not check Google ADK, Mastra or Semantic Kernel.
- The status of dotnet/extensions#7764 (`IDecisionClient`) was not checked.

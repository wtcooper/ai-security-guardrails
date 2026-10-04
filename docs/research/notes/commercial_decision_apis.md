# Commercial / Hosted "System One" Decision-Model APIs — Landscape as of 2026-10-03

Source-label legend used throughout:
- **[OFFICIAL]** = vendor's own docs/blog/model page, fetched directly.
- **[OFFICIAL-via-secondary]** = official statement (e.g., openai.com recap, X post) quoted by a secondary source because the primary page could not be fetched (openai.com returns 403).
- **[PRESS]** = named tech publication (TechCrunch, InfoQ, The Decoder, The New Stack, The Register, MarkTechPost).
- **[AGGREGATOR/SEO]** = explainer/aggregator/SEO-style sites (firecrawl blog, modelsystem.one, opentools, startupfortune, ts2.tech, kucoin news, jevmodel.org, etc.). Treat as lower reliability; several are content-farm style.
- **[COMMUNITY]** = HN, X posts, personal blogs, forum posts.

Window of focus: 2026-09-26 .. 2026-10-03. Earlier items are labeled as background.

---

## 1. TypeSafe Jev — latest version, timeline, pricing, latency, limits, calibration, SDKs, last-week news, adoption

### Takeaway
Jev (current: `jev-1.13.0`, aliases `jev-latest` and `jev-preview` both point to it) launched 2026-09-15 at $0.042/M input tokens with free output, 70–500 ms claimed latency, Choice (≤255 options) / Score (2–10 levels) / Noul question types, and Python + JS SDKs. Last-week activity is incremental (Python SDK v0.7.2 on 09-26, n8n node 09-30, founder's "clone wars" response to OpenAI 09-29). There was no new model version in the window.

### Cited Findings
**Identity, timeline**
- [OFFICIAL] Blog "Introducing System One Models & Jev": Jev is "the first public System One Model", "a new class of frontier models built to make fast, structured decisions that software can use directly"; trained via "Reinforcement Learning for Calibrated Decisions (RLCD)". The page currently shows a timestamp of Sep 28, 2026 7:32 PM UTC. That is probably a last-updated stamp, because every other source dates the launch to 09-15. — [TypeSafe blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- [OFFICIAL] Vercel says Jev became available on AI Gateway on 2026-09-15 (Vercel blog dated 2026-09-18). — [Vercel blog](https://vercel.com/blog/ai-gateway-jev-model-launch)
- [OFFICIAL] Python SDK `typesafe-sdk`: v0.5.7 initial public release 2026-09-14; v0.6.0 09-15; v0.7.0 09-18 (pydantic, `response_model` arg); v0.7.1 09-21 (early API-key validation, AI-gateway usage docs); **v0.7.2 2026-09-26** ("add `http2` extra"). This is the only TypeSafe SDK release inside the last-week window. — [Python changelog](https://docs.typesafe.ai/sdk/python/changelog.md)
- [OFFICIAL] JS/TS SDK: v0.5.7 (09-11, initial public), v0.6.0 (09-15, breaking: `Score.criteria` as ordered sequence). No release 09-26..10-03. — [JS changelog](https://docs.typesafe.ai/sdk/javascript/changelog.md)
- [PRESS] Launch date 15 Sep 2026; founders Diogo Almeida (ex-OpenAI), Erik Gafni, Sasha Sheng; San Francisco. InfoQ article dated 2026-10-01. — [InfoQ](https://www.infoq.com/news/2026/10/typesafe-ai-jev-released/)
- [AGGREGATOR] Access history: launched behind a waitlist on 09-15. "Full open access" (waitlist dropped) was reported 2026-09-21. — [KuCoin news](https://www.kucoin.com/news/insight/BTC/6ab0f7ee74fd460007c47b1e); [explainx](https://www.explainx.ai/blog/six-jev-clones-two-days-2026). Firecrawl describes Jev as "Generally available, no waitlist" as of 09-30. — [Firecrawl](https://www.firecrawl.dev/blog/openai-decisions-api-vs-jev)
- [AGGREGATOR] jev-1.13 went live on OpenRouter on 2026-09-18. — [ts2.tech](https://ts2.tech/en/jev-reaches-13-of-vercel-paid-teams-as-cloudflare-adds-typesafes-model/)
- [COMMUNITY] Simon Willison's newsletter (2026-09-21) dates the unveiling to "the previous week" and prefers the term "decision models". — [simonw substack](https://simonw.substack.com/p/jev-introduces-a-new-shape-of-llm)

**Model / API facts (official docs)**
- [OFFICIAL] Current model `jev-1.13.0`. Aliases: `jev-latest` → 1.13.0 (stable, SDK default) and `jev-preview` → 1.13.0. Single endpoint `POST /v1/systemone`. Not fine-tuned per customer. English is the primary language; other languages work at lower accuracy. "No customer data retention for training." Responses carry a versioned model ID. — [docs/models](https://docs.typesafe.ai/models.md)
- [OFFICIAL] Pricing: "$42 per billion input tokens" = $0.042/M input; output tokens free. — [docs/models](https://docs.typesafe.ai/models.md); same figures in [blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- [OFFICIAL] Rate limits: "100K tokens per second / 80 requests per second", adjusted dynamically; enterprise plans get higher limits. — [docs/models](https://docs.typesafe.ai/models.md)
- [OFFICIAL] Context: "64k tokens per request; 32k tokens for `state` plus the longest question". Input is text only (string, JSON object, or array of text); no image, audio or video. — [docs/models](https://docs.typesafe.ai/models.md). **Conflict:** OpenRouter docs and most press say a "32K context window". — [OpenRouter docs](https://openrouter.ai/docs/guides/community/jev); [InfoQ](https://www.infoq.com/news/2026/10/typesafe-ai-jev-released/)
- [OFFICIAL] API: `POST https://api.typesafe.ai/v1/systemone`. Request fields: `state` (string | object | array), `model` ("jev-latest"), `questions` (map keyed by user IDs). Question types:
  - **Noul** returns `noul` (0–1).
  - **Choice** takes `criteria` with at most **255 options** and returns `choice`, a `probabilities` map and `confidence` (0–1).
  - **Score** takes `criteria` as an ordered array of **2–10 levels** and returns `score` (probability-weighted), `legend`, `probabilities` and `confidence`.
  - `usage` reports input/output tokens.
  - Error codes: 401, 422, 429, 529 (Overloaded).
  - No documented maximum question count or explicit state-size cap on that page. — [docs/api](https://docs.typesafe.ai/api.md)
- [OFFICIAL] Docs index lists Python and JS SDKs, an "agent-skill" page, 20+ cookbooks (one is LLM guardrails) and a "model-jaggedness/jev-1.13" known-limitations page. — [llms.txt](https://docs.typesafe.ai/llms.txt)

**Latency & cost claims**
- [OFFICIAL / marketing] 70–500 ms end-to-end. Claimed "40x–200x faster than frontier LLMs for equivalent intelligence". The blog says Jev owns the "Pareto frontier for almost 2 orders of magnitude" on its own evals site (evals.typesafe.ai). — [TypeSafe blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- [OFFICIAL-partner] Vercel: "up to 194x faster" and "445x cheaper" than LLMs in workflow evals. — [Vercel blog](https://vercel.com/blog/ai-gateway-jev-model-launch)
- [PRESS] Real-world speedups reported by users: median about 7x (headline: 193.6x). Median cost savings about 30x. — [InfoQ](https://www.infoq.com/news/2026/10/typesafe-ai-jev-released/)
- [AGGREGATOR] OpenRouter production data: P50 0.21 s, P95 0.34 s. — [Firecrawl](https://www.firecrawl.dev/blog/openai-decisions-api-vs-jev). **Contrast:** Cloudflare's own benchmark measured Jev at 524.1 ms median. — [Developers Digest](https://www.developersdigest.tech/blog/cloudflare-clef-decision-models-2026)

**Calibration claims & limits**
- [OFFICIAL / marketing] Jev "always communicates confidence and uncertainty with every output. Calibrated: higher confidence means higher accuracy". "0% hallucination" here means the output is schema-guaranteed, not an empirical measurement. No standard public benchmark (e.g., MMLU) appears in the launch blog. — [TypeSafe blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- [OFFICIAL] Known limitations of jev-1.13 (from the known-limitations page):
  - "Jev is not a calculator"; counting, arithmetic and date comparisons are unreliable.
  - Large or noisy state hurts accuracy.
  - Vulnerable to prompt injection and adversarial content.
  - Sensitive to option order in Choice questions; can be overly literal.
  - Score levels are weakly calibrated numerically and should not be interpolated. — [jev-1.13 limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13.md)
- [COMMUNITY/independent test] Ryan Porter ran ProofWriter logic problems through Jev. At ≥99% stated confidence, Jev was correct 98.9% of the time (compared with Luna in §2). This is the author's own test, not peer reviewed. — [anth.us](https://anth.us/blog/openai-decisions-api-preview/)
- [PRESS] Developer critique: Jev "can still emit a completely wrong valid value". — [InfoQ](https://www.infoq.com/news/2026/10/typesafe-ai-jev-released/)
- [AGGREGATOR] Cloudflare's "Decision Index" benchmark:
  - Jev leads on GPQA Diamond (78.3 vs Clef 48.0), MMLU-Pro (82.7 vs 65.9) and When2Call (81.0 vs 72.4).
  - Clef leads on BANKING77 (94.2 vs 79.7), BFCL (98.5 vs 95.8) and CLINC150+OOS (97.4 vs 89.3). These are vendor-run numbers (Cloudflare). — [Developers Digest](https://www.developersdigest.tech/blog/cloudflare-clef-decision-models-2026)

**Distribution / adoption signals**
- [OFFICIAL-partner] Vercel AI Gateway: "By hour 24, nearly 13% of paid teams were using it". That is 2x the GPT-5.6 family and 6x Fable 5.1, and 10% of teams within 18 h. Vercel calls it the "fastest-adopted model in AI Gateway history". — [Vercel blog](https://vercel.com/blog/ai-gateway-jev-model-launch); [Vercel on X](https://x.com/vercel/status/2101077346203971900)
- [OFFICIAL-partner] OpenRouter serves `typesafe/jev-1.13` (alias `~typesafe/jev-latest`) through two surfaces: the OpenRouter **Decisions API** `POST https://openrouter.ai/api/alpha/decisions` and a **System One API** `POST https://openrouter.ai/api/v1/systemone`. Billing goes through the OpenRouter account; output is free; 32K context. — [OpenRouter docs](https://openrouter.ai/docs/guides/community/jev)
- [OFFICIAL-partner] Runware hosts Jev (`typesafe:jev@latest`) and its own Laya (`runware:laya@1`) on a `/v1/systemone` endpoint (post dated 2026-09-28). Pricing:
  - Jev: $0.042/M input.
  - Laya: $0.020/M input, free through 2026-10-12. — [Runware blog](https://runware.ai/blog/jev-laya-and-the-emerging-role-of-decision-models)
- [AGGREGATOR] Cloudflare listed Jev on Workers AI by 2026-09-21 (32K context). Revenue terms were not disclosed. — [ts2.tech](https://ts2.tech/en/jev-reaches-13-of-vercel-paid-teams-as-cloudflare-adds-typesafes-model/)
- [COMMUNITY/official-partner forum] **Last-week item:** on **2026-09-30**, n8n shipped a "TypeSafe AI" node ("Route item by System One question"). It is free on n8n Cloud via Gateway credits until 2026-10-10 23:59 UTC. The post repeats TypeSafe's claim of "238x lower cost than Claude Fable 5.1". — [n8n community](https://community.n8n.io/t/typesafes-jev-is-now-in-n8n-free-on-cloud-via-gateway-credits-until-october-10/317957)
- [PRESS] Netlify, LangChain (`TypeSafeClassifier`) and five Elixir clients integrated Jev. — [InfoQ](https://www.infoq.com/news/2026/10/typesafe-ai-jev-released/). [AGGREGATOR] Vercel, Cloudflare, LangChain and Langfuse integrated within three days of launch. — [search snippet, aiweekly/zurb radar](https://aiweekly.co/alerts/typesafes-jev-hits-13-of-vercel-paid-teams-in-24-hours)
- [PRESS] TechCrunch case study: Shapor Naghibzadeh's QueryStory uses Jev for agent action monitoring, at $2.94 vs $372 with frontier LLMs (~99% savings). — [TechCrunch 09-30](https://techcrunch.com/2026/09/30/openais-jev-clone-could-help-the-frontier-lab-stop-its-swarming-agents/)
- [AGGREGATOR] Funding: $40M seed led by DCVC, announced at launch. — [KuCoin](https://www.kucoin.com/news/insight/BTC/6ab0f7ee74fd460007c47b1e); [Startup Fortune](https://startupfortune.com/amazon-releases-its-own-jev-clone-as-the-ai-decision-model-race-turns-into-a-pile-up/). Startup Fortune also reports a "$10 billion" valuation. That is **unverified and implausible on its face** for a $40M seed, and no primary source was found. A separate headline says investors are discussing a higher valuation. — [runtimewire](https://runtimewire.com/article/typesafe-investors-discuss-a-higher-valuation-after-jev-reaches-nearly-13-of-one)
- [AGGREGATOR] Founder on pricing sustainability: "We can't prove it isn't subsidized; we'll need the long-term to prove the sustainability of our pricing." — [ts2.tech](https://ts2.tech/en/jev-reaches-13-of-vercel-paid-teams-as-cloudflare-adds-typesafes-model/)

### Inferences
- Jev is the only product in this category with a fully documented public contract: limits, error codes, rate limits, versioned aliases and SDK changelogs. Every other hosted entrant either copies its wire format (`/v1/systemone`) or has no published schema (OpenAI).
- The context-window discrepancy is probably definitional rather than contradictory. Docs say 64k total per request, with state plus the longest question capped at 32k; resellers advertise the 32k figure.
- The last week brought ecosystem work (n8n, SDK HTTP/2, OpenRouter's "Decisions API" naming) rather than a model update. jev-1.13 has been the current model since at least 09-18.

### Gaps
- No official release date for jev-1.13 or its predecessors. The models page lists no dates or deprecation timeline.
- Max questions per call and the maximum state size in bytes are not documented on the API page. Clef documents 1–64 questions; Jev does not.
- No independent, reproducible calibration metric (ECE/Brier) is published by TypeSafe. "Calibrated" is a vendor claim. The only independent number found is one blogger's ProofWriter test.
- The $40M/DCVC seed comes only from aggregators in this pass; no official TypeSafe funding post or DCVC release was fetched.
- No named paying enterprise customers found. Adoption figures are partner-reported (Vercel) and cover usage share, not revenue.

---

## 2. OpenAI Decisions API (GPT-6 Luna) — what was officially said, availability, shape, pricing, latency, follow-ups

### Takeaway
OpenAI announced the Decisions API at DevDay on 2026-09-29: a constrained "version of GPT-6 Luna" that answers user-defined questions with finite predefined answers, takes text or image context, and is shown at ~150 ms vs ~1.6 s through the regular API. It is in **limited preview**, with broad release promised "in the coming days". As of 2026-10-03 there is no public docs page, schema, pricing or confirmed confidence output, and the official GPT-6 Luna model page does not mention it.

### Cited Findings
- [OFFICIAL-via-secondary] DevDay recap wording: the Decisions API "enables real-time decision-making by focusing Luna's intelligence on a specific set of user-defined questions with finite pre-defined answers". Its stated uses are to "classify content, route requests, or choose an agent's next action". The openai.com recap returned 403 to direct fetch; the quote comes via [modelsystem.one](https://modelsystem.one/news/openai-decisions-api-preview/) and [search snippets](https://jevmodel.org/openai-decisions-api/). Recap URL: https://openai.com/index/devday-2026-recap/
- [OFFICIAL-via-secondary] @OpenAIDevs on X: "powered by GPT-6 Luna", "available in limited preview", broad release "in the coming days". — [modelsystem.one](https://modelsystem.one/news/openai-decisions-api-preview/); [InfoQ DevDay recap, 2026-10-02](https://www.infoq.com/news/2026/10/openai-devday-2026/)
- [OFFICIAL-via-secondary] Sam Altman, on stage: "By focusing the model on that choice, we can make it extremely fast while keeping capabilities like image understanding, broad language support, and safety protections." — [TechCrunch 2026-09-30](https://techcrunch.com/2026/09/30/openais-jev-clone-could-help-the-frontier-lab-stop-its-swarming-agents/). He showed it driving a computer-use agent. — [search snippet / gazetaexpress](https://www.gazetaexpress.com/en/OpenAI-introduces-Decisions-API--a-tool-that-can-make-AI-agents-faster-and-more-secure/)
- [OFFICIAL-via-secondary] Thibault Sottiaux (OpenAI): it "supports visual inputs" and is "tuned to be able to make decisions in less than a few hundreds of milliseconds". — [modelsystem.one](https://modelsystem.one/news/openai-decisions-api-preview/); [opentools](https://opentools.ai/news/openai-decisions-api-luna-classification-routing-preview)
- [PRESS] The Decoder (2026-09-29) on latency: OpenAI says the API decides "ten times faster than GPT-6 Luna does through the regular API", with 150 ms vs 1.6 s in OpenAI's benchmark chart. — [The Decoder](https://the-decoder.com/openai-expands-codex-and-its-api-at-devday-with-security-scans-a-decisions-api-and-ultrafast/)
- [AGGREGATOR] Context for the 150 ms figure: the demo routed 10,000 customer requests and the launch video ran at 15x realtime. No p50/p99, regions or SLA have been published. — [modelsystem.one](https://modelsystem.one/news/openai-decisions-api-preview/)
- [OFFICIAL] The GPT-6 Luna model page lists $0.10/M input, $0.50/M output, $0.01 cached input, 1.05M context and 128K max output, with **no mention of a Decisions API or endpoint** (fetched 2026-10-03). — [developers.openai.com GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)
- [AGGREGATOR] Pricing has not been announced. Opentools warns that "Luna's token prices should not be assumed as substitute rates". Firecrawl's table uses Luna rates ($0.10/$0.50) only as a proxy. — [opentools](https://opentools.ai/news/openai-decisions-api-luna-classification-routing-preview); [Firecrawl](https://www.firecrawl.dev/blog/openai-decisions-api-vs-jev)
- **Confidence outputs, conflicting reports:**
  - [PRESS] The New Stack reportedly says it returns "predefined answers with confidence scores". The article is paywalled; the claim is quoted in a search snippet. — [The New Stack 2026-09-29](https://thenewstack.io/openai-decision-api-luna/)
  - [PRESS] TechCrunch says it outputs probabilities. — [TechCrunch](https://techcrunch.com/2026/09/30/openais-jev-clone-could-help-the-frontier-lab-stop-its-swarming-agents/)
  - [PRESS] The Decoder mentions no confidence outputs. — [The Decoder](https://the-decoder.com/openai-expands-codex-and-its-api-at-devday-with-security-scans-a-decisions-api-and-ultrafast/)
  - [AGGREGATOR] Confidence scores appear "in press, not OpenAI's official language". — [modelsystem.one runtime page](https://modelsystem.one/runtimes/openai-decisions-api/)
- [COMMUNITY/independent test] Ryan Porter (2026-10-01) ran ProofWriter problems through regular Luna. When Luna said it was ≥99% sure (2,672 of 3,600 problems), it was correct only 68% of the time, versus Jev at 98.9%. This tested Luna through the standard API, **not** the Decisions API, which the author could not access or confirm returns confidences. — [anth.us](https://anth.us/blog/openai-decisions-api-preview/)
- [AGGREGATOR] Docs status: no guide, API reference, changelog entry, endpoint on the Luna page, request/response schema, max answers per question, context limit, regions or data-handling terms. OpenAI says details will come "at broad rollout". — [modelsystem.one](https://modelsystem.one/news/openai-decisions-api-preview/); [opentools](https://opentools.ai/news/openai-decisions-api-luna-classification-routing-preview)
- [AGGREGATOR, unattributed snippet — UNVERIFIED] "As of October 2, 2026, a standard API key still got a 403 'Decision API is not enabled for this user' error, and there's no docs page yet." This appeared in a search-result summary for "developers.openai.com decisions API" that drew on aggregator pages. The modelsystem.one page I fetched does not contain it. — [search results incl. orcarouter](https://www.orcarouter.ai/blog/openai-decisions-api-gpt-6-luna)
- [AGGREGATOR] Input modalities: text or images; outputs are finite, constrained decisions. No versioned model ID published. — [opentools](https://opentools.ai/news/openai-decisions-api-luna-classification-routing-preview); [Firecrawl](https://www.firecrawl.dev/blog/openai-decisions-api-vs-jev)
- [AGGREGATOR] Community reception: the Decisions API HN submission got 6 points, versus 691 for a "Jev in 25 Lines" post. — [Firecrawl](https://www.firecrawl.dev/blog/openai-decisions-api-vs-jev) (HN counts not verified directly)
- [PRESS] InfoQ's DevDay recap (2026-10-02) lists the Decisions API alongside GPT-6.1 Sol, the Agents API with computer use, and ChatGPT plugin extensions. It gives no pricing or latency. — [InfoQ](https://www.infoq.com/news/2026/10/openai-devday-2026/)
- [AGGREGATOR] Date conflict: Startup Fortune lists the OpenAI launch as Sept 30. All primary-adjacent sources say DevDay was 2026-09-29. — [Startup Fortune](https://startupfortune.com/amazon-releases-its-own-jev-clone-as-the-ai-decision-model-race-turns-into-a-pile-up/)

### Inferences
- The 150 ms vs 1.6 s comparison is OpenAI's own demo chart. Nobody has published independent latency numbers because preview access is restricted.
- Whether OpenAI returns calibrated per-option probabilities, the core System One property, is the biggest open question. Press claims it does; OpenAI's own words only say "decisions". Porter's test shows stock Luna's verbalized confidence is badly overconfident, though the Decisions API may expose token logprobs or a dedicated head instead.
- Up to five days after DevDay, the promised "coming days" broad release had not shown up in any official docs I could fetch.

### Gaps
- No public endpoint path, request/response schema, max options, context limit, pricing, data-retention terms or region info.
- No OpenAI statement found on calibration methodology.
- Could not fetch openai.com directly (403). I also did not find any X post by OpenAI after 09-29 announcing GA.
- It is unclear whether "a version of GPT-6 Luna" means decision-specific weights or a head, or stock Luna with constrained decoding.

---

## 3. Other vendors' competing decision / classification APIs (last week + recent)

### Takeaway
Within about 17 days of Jev's launch, two major infrastructure vendors shipped direct competitors on **2026-10-01**. **Cloudflare Clef / Clef-flash** is hosted and GA on Workers AI, Jev-API-compatible, with Apache-2.0 open weights. **AWS Strands Decider 2B** is open source and local-only, with no hosted Bedrock endpoint. Hosted resale surfaces also proliferated: OpenRouter's "Decisions API", Runware's `/v1/systemone`, Vercel AI Gateway and Cloudflare Workers AI hosting Jev. **No evidence** turned up of Google/Gemini, Anthropic, Microsoft/Azure, Cohere, Mistral, Groq, Fireworks, Together or Cerebras launching a decision-model API.

### Cited Findings
**Cloudflare Clef / Clef-flash (hosted, GA, 2026-10-01)**
- [OFFICIAL] Cloudflare blog (2026-10-01, Michelle Chen), "Introducing Clef: our open-source decision models, and new RL fine-tuning platform". Key points:
  - Two models: Clef, on a Qwen 27B base, and Clef-flash, on a Qwen 9B base; both have 64k context.
  - Hosted on Workers AI and generally available; weights are Apache-2.0 on Hugging Face.
  - Question types: noul, choice and score. The models are "fully API-compatible" with Jev.
  - Calibration uses "label-smoothed cross-entropy for valid schema outputs paired with a Brier loss". No ECE figures are published.
  - Median latency: Clef 209.3 ms, Clef-flash 38.8 ms. p95: 238.6 ms and 122.4 ms.
  - The RL fine-tuning platform is available as a hands-on FDE engagement now, with self-serve planned and pricing undisclosed. — [Cloudflare blog](https://blog.cloudflare.com/clef-decision-models/)
- [OFFICIAL] Workers AI model page: `@cf/cloudflare/clef` (plus `@cf/cloudflare/clef-flash`).
  - Price: **$0.24/M input tokens** (Clef).
  - Context: 65,536 tokens. Input can be text, JSON, images or video, with at most 4 images.
  - Limits: **1–64 questions per request**, question ID ≤100 chars, request body ≤13 MiB. — [Workers AI docs](https://developers.cloudflare.com/workers-ai/models/clef/)
- [AGGREGATOR] Clef-flash is priced at $0.09/M input; neither model charges for output. This figure is attributed to Workers AI docs but was not independently verified here. — [Developers Digest](https://www.developersdigest.tech/blog/cloudflare-clef-decision-models-2026)
- [AGGREGATOR] **Pricing conflict:** Startup Fortune calls Clef "free". That is true only of the open weights; hosted inference is $0.24/M. — [Startup Fortune](https://startupfortune.com/amazon-releases-its-own-jev-clone-as-the-ai-decision-model-race-turns-into-a-pile-up/)
- [AGGREGATOR] Benchmark claims: BANKING77 macro-F1 94.2 (Jev 79.7); median 209.3 ms (Jev 524.1 ms); "2.5x–13x faster than Jev". These come from Cloudflare's own benchmark runs. — [Market Intelligence Research 2026-10-02](https://marketintelligenceresearch.com/blog/three-jev-alternates-clef-jev-27b-vl-open-decision-model-family/); [Startup Fortune](https://startupfortune.com/amazon-releases-its-own-jev-clone-as-the-ai-decision-model-race-turns-into-a-pile-up/)

**AWS Strands Decider 2B (open source, local, 2026-10-01) — not a hosted API**
- [OFFICIAL] Strands blog (2026-10-01; Marc Brooker, Mike Chambers, Fabio Nonato de Paula). Key points:
  - Architecture: a Qwen3.5-2B torso, a ~1M-parameter pointer head and a rank-16 LoRA. Code is open source on GitHub; weights are on Hugging Face.
  - It runs on a local CPU or GPU. The blog mentions no Bedrock or SageMaker hosting.
  - Median latency is ~115 ms on an RTX 3090 and ~153 ms on an M3 MacBook, growing roughly linearly with task size.
  - It supports yes/no and choice questions.
  - Calibration is measured by Brier score. On JevBench's public set it ranks "3rd of 33 in the 2B class" for accuracy and calibration.
  - The blog does not mention `/v1/systemone` compatibility. — [Strands blog](https://strandsagents.com/blog/introducing-strands-decider/)
- [PRESS] TechCrunch (2026-10-01, Tim Fernholz), "Amazon releases its own Jev clone as decision models flood the web": Strands Decider is Apache-licensed and "fully available now". Diogo Almeida: "I get that people think it's a gold rush, but they might be underestimating the difficulty." — [TechCrunch](https://techcrunch.com/2026/10/01/amazon-releases-its-own-jev-clone-as-decision-models-flood-the-web/)
- [AGGREGATOR] In AWS's example pipeline, Decider gates locally and generative calls still go to Bedrock. — [search snippet / strands-decider README](https://github.com/strands-labs/strands-decider/blob/main/examples/strands/README.md); [The New Stack](https://thenewstack.io/aws-strands-decider-model/)
- [AGGREGATOR] Reported as 1.9B params, 72% accuracy on JevBench and 106–115 ms latency. — [Startup Fortune](https://startupfortune.com/amazon-releases-its-own-jev-clone-as-the-ai-decision-model-race-turns-into-a-pile-up/)

**Hosted resellers / gateways exposing decision APIs**
- [OFFICIAL] **OpenRouter "Decisions API"**: `POST https://openrouter.ai/api/alpha/decisions` (alpha) plus `POST /api/v1/systemone`. It currently serves Jev. The name collides with OpenAI's product. — [OpenRouter docs](https://openrouter.ai/docs/guides/community/jev); [Firecrawl](https://www.firecrawl.dev/blog/openai-decisions-api-vs-jev)
- [OFFICIAL] **Runware**: `/v1/systemone` serving Jev ($0.042/M) and Runware's Laya ($0.020/M, free until 2026-10-12). Its stated latencies for Laya (39.5 ms for one question, 158.6 ms for ten) are from local GPU runs. Runware cautions that "a probability is useful only when its relationship to actual outcomes has been checked." — [Runware blog 2026-09-28](https://runware.ai/blog/jev-laya-and-the-emerging-role-of-decision-models)
- [OFFICIAL-partner] **Vercel AI Gateway** has hosted Jev since 2026-09-15. — [Vercel blog](https://vercel.com/blog/ai-gateway-jev-model-launch)
- [AGGREGATOR] **Cloudflare Workers AI** also lists Jev (by 09-21). — [ts2.tech](https://ts2.tech/en/jev-reaches-13-of-vercel-paid-teams-as-cloudflare-adds-typesafes-model/)
- [COMMUNITY] **n8n Cloud** has had a TypeSafe AI node since 2026-09-30. — [n8n community](https://community.n8n.io/t/typesafes-jev-is-now-in-n8n-free-on-cloud-via-gateway-credits-until-october-10/317957)

**Other / adjacent entrants (mostly open-weight, not hosted commercial APIs)**
- [AGGREGATOR] **AutoTrust AI JEV-27B-VL**: vision-enabled, up to 256 options zero-shot. Self-reported metrics include ECE 0.0009 and yes/no AUROC 0.995. Hosting and license are unclear; its source is listed as a Hugging Face repo. — [Market Intelligence Research](https://marketintelligenceresearch.com/blog/three-jev-alternates-clef-jev-27b-vl-open-decision-model-family/); [HF autotrust/JEV-27B-VL](https://huggingface.co/autotrust/JEV-27B-VL)
- [OFFICIAL-third-party] **Red Hat / vLLM**: a guide (2026-09-28) to running decision models via DiffusionGemma on vLLM and Red Hat AI. DiffusionGemma support reportedly merged into vLLM mainline on 09-22. — [Red Hat Developers](https://developers.redhat.com/articles/2026/09/28/run-decision-model-vllm-and-red-hat-ai); [Market Intelligence Research](https://marketintelligenceresearch.com/blog/three-jev-alternates-clef-jev-27b-vl-open-decision-model-family/)
- [COMMUNITY] Open, self-hosted Jev-compatible servers and models:
  - Laya, which Unsloth serves through a TypeSafe-compatible API. — [Unsloth docs](https://unsloth.ai/docs/models/decision-laya)
  - Kev (Qwen LoRA adapters; claims to serve `/v1/systemone`).
  - OpenJev (DiffusionGemma). — [GitHub openjev](https://github.com/razorback16/openjev)
  - Decis (chaitin; self-hosted `/v1/systemone`). — [GitHub Decis](https://github.com/chaitin/Decis)
  - The `systemone` CLI, which routes to hosted Jev through Vercel or OpenRouter. — [GitHub codesoda/systemone](https://github.com/codesoda/systemone)
  - A tool to distill Jev for local use. — [The Register 2026-09-29](https://theregister.com/ai-and-ml/2026/09/29/open-source-tool-distills-jev-so-you-can-run-it-locally/5299856)
  - "Six clones in two days" counted by AINews. — [explainx](https://www.explainx.ai/blog/six-jev-clones-two-days-2026)
- [AGGREGATOR] **Decitron** (Zhongke Wenge, China, launched June 2026) is a different category: a world-model and multi-agent simulation "decision engine", not a typed-question classifier. No API, pricing or latency info. — [KuCoin](https://www.kucoin.com/news/flash/jev-vs-decitron-different-approaches-to-decision-making-ai)

**Big labs and inference clouds: no evidence found**
- Searches covering Google/Gemini, Anthropic, Microsoft/Azure, Mistral, Cohere, Groq, Fireworks, Together and Cerebras turned up no decision-model or System One API launch. Background: Gemini 3.8 Flash launched 09-02; Grok 4.7 arrived on Bedrock. — [digitalapplied Sept 2026 tracker](https://www.digitalapplied.com/blog/ai-model-releases-september-2026-tracker). Startup Fortune explicitly mentions no Google, Anthropic or Microsoft entrant. — [Startup Fortune](https://startupfortune.com/amazon-releases-its-own-jev-clone-as-the-ai-decision-model-race-turns-into-a-pile-up/). TechCrunch says "other startups" are rolling out similar models without naming them. — [TechCrunch 09-30](https://techcrunch.com/2026/09/30/openais-jev-clone-could-help-the-frontier-lab-stop-its-swarming-agents/)

### Inferences
- Jev's `POST /v1/systemone` wire format (Choice/Score/Noul) is becoming a de facto standard. Cloudflare Clef, OpenRouter, Runware and several OSS servers all adopt it, so switching vendors can be just a base-URL change. OpenAI is the notable exception with an undocumented, proprietary shape.
- Commercially, there are three hosted first-party decision models today: TypeSafe Jev, Cloudflare Clef/Clef-flash, and OpenAI Decisions API (preview only). AWS chose an open, local-only release instead of a Bedrock API.
- Cloudflare's per-token price ($0.24/M for Clef) is about 6x Jev's. Its pitch is open weights, vision input, edge latency (Clef-flash ~39 ms median) and fine-tuning, not price.

### Gaps
- No primary-source confirmation of Clef-flash pricing ($0.09/M) or of Jev's Workers AI price.
- Unknown whether AWS plans a hosted Bedrock or SageMaker endpoint for Strands Decider.
- No information found on Google, Anthropic, Microsoft or Cohere responses. It is possible announcements exist that search did not surface; absence of evidence is not conclusive.
- AutoTrust JEV-27B-VL metrics are self-reported; hosting and commercial terms are unknown.

---

## 4. Third-party coverage & commentary of the "explosion"; founder statements on competition

### Takeaway
Mainstream tech press frames 09-29..10-01 as a "Jev clone" pile-up: OpenAI (09-29), then Cloudflare and AWS (10-01). Founder Diogo Almeida responded publicly by welcoming the validation while arguing that intelligence-per-dollar, not speed, is the moat. Community reception was split: strong uptake on one side; skepticism of the launch rhetoric ("can't hallucinate") and "25 lines of Python" counter-posts on the other.

### Cited Findings
- [PRESS] TechCrunch, 2026-09-30, Tim Fernholz, "OpenAI's Jev clone could help the frontier lab stop its swarming agents". Quotes Altman. Almeida joked about "the beginning of the clone wars" and said: "Fast and cheap is very easy, you know… If you want it really fast and cheap, use dice, right? Intelligence is the hard part, and my North Star is always pushing the intelligence-per-dollar Pareto curve." TechCrunch describes Almeida as a former OpenAI engineer and "reinforcement learning co-inventor"; that characterization is the publication's and is not verified. — [TechCrunch](https://techcrunch.com/2026/09/30/openais-jev-clone-could-help-the-frontier-lab-stop-its-swarming-agents/)
- [COMMUNITY/primary] Diogo Almeida on X (@CompleteSkeptic): "begun, the clone war has jk, I love openai and think more competition and validation is great for developers! (assuming the model is good - plz make it good!) hopefully this is a sign for the future that building in a system one compatible way is the future". — [X post](https://x.com/CompleteSkeptic/status/2105000685209313736). Firecrawl reports the post got 647 likes within 90 minutes of the keynote. — [Firecrawl](https://www.firecrawl.dev/blog/openai-decisions-api-vs-jev). The same day he pointed developers to TypeSafe's MIT-licensed `system-one-adapter-python` for comparing models. — [modelsystem.one](https://modelsystem.one/news/openai-decisions-api-preview/)
- [AGGREGATOR] Almeida says the company's moat is its ability to generate synthetic data that produces statistically meaningful outputs. — [search snippet summarizing TechCrunch/yahoo syndication](https://tech.yahoo.com/ai/chatgpt/articles/openai-jev-clone-could-help-190057161.html)
- [PRESS] TechCrunch, 2026-10-01: "Amazon releases its own Jev clone as decision models flood the web". Almeida: "I get that people think it's a gold rush, but they might be underestimating the difficulty." — [TechCrunch](https://techcrunch.com/2026/10/01/amazon-releases-its-own-jev-clone-as-decision-models-flood-the-web/)
- [PRESS] The New Stack, 2026-09-29, Frederic Lardinois: "OpenAI answers TypeSafe's Jev with a Decision API built on Luna" (paywalled). Also "AWS launches a local answer to TypeSafe's Jev decision model". — [TNS OpenAI](https://thenewstack.io/openai-decision-api-luna/); [TNS AWS](https://thenewstack.io/aws-strands-decider-model/)
- [PRESS] The Decoder (2026-09-29) explicitly references Jev launching in mid-September and says "pairing a stronger model as an orchestrator with a fast decision model looks promising", citing a Minecraft agent that uses Jev for action selection. — [The Decoder](https://the-decoder.com/openai-expands-codex-and-its-api-at-devday-with-security-scans-a-decisions-api-and-ultrafast/)
- [PRESS] InfoQ (2026-10-01, Jev; 2026-10-02, DevDay). The Jev piece notes real-world median speedups of about 7x versus the 193.6x headline, and the "wrong valid value" critique. — [InfoQ Jev](https://www.infoq.com/news/2026/10/typesafe-ai-jev-released/); [InfoQ DevDay](https://www.infoq.com/news/2026/10/openai-devday-2026/)
- [PRESS] Background coverage:
  - MarkTechPost (2026-09-19). — [MarkTechPost](https://www.marktechpost.com/2026/09/19/typesafe-ai-releases-jev/)
  - Tom's Hardware ("193x faster and 445x cheaper"). — [Tom's Hardware](https://www.tomshardware.com/tech-industry/artificial-intelligence/typesafe-ais-jev-offers-an-alternative-to-llms-that-claims-to-be-193x-faster-and-445x-cheaper-system-one-type-model-is-bespoke-for-probabilistic-decision-making)
  - The Register (2026-09-29, distillation tool). — [The Register](https://theregister.com/ai-and-ml/2026/09/29/open-source-tool-distills-jev-so-you-can-run-it-locally/5299856)
- [PRESS, non-US] Digital Today (Korea): "OpenAI unveils 'Decisions API' to speed up choice-based judgments, targeting software automation". — [digitaltoday.co.kr](https://www.digitaltoday.co.kr/en/view/109365/openai-unveils-decisions-api-to-speed-up-choice-based-judgments-targeting-software-automation)
- [AGGREGATOR] daily.dev reposts in the window: "Cloudflare releases Clef, open-weight decision models, and an RL fine-tuning service"; "AWS releases Strands Decider 2B, an open decision model modeled on TypeSafe's Jev"; and the TechCrunch OpenAI piece. — [daily.dev Clef](https://daily.dev/posts/cloudflare-releases-clef-open-weight-decision-models-and-an-rl-fine-tuning-service-q5kwww262); [daily.dev AWS](https://daily.dev/posts/aws-releases-strands-decider-2b-an-open-decision-model-modeled-on-typesafe-s-jev-w1ctygq0t); [daily.dev OpenAI](https://daily.dev/posts/openai-s-jev-clone-could-help-the-frontier-lab-stop-its-swarming-agents-wvu5oykej)
- [AGGREGATOR] KuCoin News ran many Jev and Decisions API flash items, including "Jev AI Model … Potential Impact on U.S. Semiconductor Stocks" and "OpenAI Launches Decisions API to Improve AI Agent Safety and Efficiency". — [KuCoin search results](https://www.kucoin.com/news/flash/openai-unveils-decisions-api-to-enhance-ai-agent-safety-and-efficiency)
- [AGGREGATOR] Startup Fortune (10-02/03) gives a vendor timeline. Jev 09-15; OpenAI "09-30" (sic); Cloudflare 10-01; Amazon 10-01. It calls big-cloud entries "commoditization by subsidy" rather than "competition on quality". — [Startup Fortune](https://startupfortune.com/amazon-releases-its-own-jev-clone-as-the-ai-decision-model-race-turns-into-a-pile-up/)
- [COMMUNITY] Hacker News:
  - Launch thread "Introducing System One Models and Jev". — [HN 49717558](https://news.ycombinator.com/item?id=49717558)
  - A commenter: "the main gripe that people had with Jev and Typesafe was the language used when they launched, which seemed like a parody/con/shady at first". — [HN 49767192](https://news.ycombinator.com/item?id=49767192)
  - A commenter quotes TypeSafe's own caveat that "Jev doesn't have deep knowledge of niche…" topics. — [HN 49770857](https://news.ycombinator.com/item?id=49770857)
  - [COMMUNITY] DEV post: "TypeSafe's Jev Costs 400x Less Than an LLM. These 25 Lines of Python Do the Same Job for Free." — [dev.to](https://dev.to/jamilxt/typesafes-jev-costs-400x-less-than-an-llm-these-25-lines-of-python-do-the-same-job-for-free-3ddd)
- [COMMUNITY] Simon Willison (09-21) worried about "black box" outputs with no reasoning, which make bias hard to detect. In his test, rating cities, Cupertino came out highest and East Palo Alto lowest. He argued cheap pricing makes extensive evaluation feasible. — [simonw substack](https://simonw.substack.com/p/jev-introduces-a-new-shape-of-llm)
- [COMMUNITY] Ryan Porter (anth.us, 10-01), "The OpenAI Decisions API Needs a Confidence You Can Trust", gives the Luna-overconfidence data in §2. — [anth.us](https://anth.us/blog/openai-decisions-api-preview/)
- [AGGREGATOR] X trending topic: "Jev Model Speeds Up AI Agents with Fast Decisions". — [X trending](https://x.com/i/trending/2105154696566501872)
- Note: I found **no** pasqualepillitteri.it coverage in search results.

### Inferences
- The press consensus is that the category was validated within about two weeks. The recurring framing is "clone" (TechCrunch's headline wording), which favors TypeSafe's first-mover narrative.
- Commentary is shifting from speed and cost to **calibration trustworthiness**: Porter's test, Runware's caveat, and Willison's black-box concern. That is the axis on which hosted entrants are least documented.
- Much of the "explosion" content is SEO and aggregator material (jevmodel.org, jev-ai.org, jevaiguide.com, huggingface.co/blog/sora-2/*, lmspedia, eesel). Many of these sites re-quote each other and should not be treated as independent confirmation.

### Gaps
- Exact HN points and comment counts for the Decisions API and "Jev in 25 Lines" threads were not verified directly. Firecrawl is the only source.
- No pasqualepillitteri.it article found. The Digital Today article body was not fetched.
- No official X post from Sam Altman's own account on the Decisions API was located; the quotes are from the keynote via TechCrunch.

---

## 5. Per-product inventory: status, pricing, latency, calibration, limits, verification level

### Takeaway
Hosted, first-party decision-model APIs as of 2026-10-03:
- **TypeSafe Jev**: GA, fully documented.
- **Cloudflare Clef / Clef-flash**: GA, documented, Jev-compatible.
- **OpenAI Decisions API**: limited preview, undocumented.

Resale surfaces: OpenRouter, Vercel AI Gateway, Runware, Cloudflare Workers AI (Jev) and n8n. AWS Strands Decider is open and local-only.

### Cited Findings
| Product | Vendor | Status (as of 10-03) | Price | Latency | Calibration / confidence | Notable limits | Verification |
|---|---|---|---|---|---|---|---|
| Jev (`jev-1.13.0`, alias `jev-latest`) | TypeSafe | GA (launched 09-15; waitlist dropped ~09-21) | $0.042/M input; output free | 70–500 ms (vendor); OpenRouter P50 0.21 s / P95 0.34 s (secondary); Cloudflare-measured median 524 ms | Per-option probabilities + `confidence`; "calibrated" claim; RLCD training; no published ECE | Text only; Choice ≤255 options; Score 2–10 levels; 64k/request (32k state+longest question); 100K tok/s, 80 rps | OFFICIAL docs — [models](https://docs.typesafe.ai/models.md), [api](https://docs.typesafe.ai/api.md), [blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev) |
| Decisions API (GPT-6 Luna variant) | OpenAI | Limited preview (announced 09-29); broad release "coming days" | Unpublished (Luna base: $0.10 in / $0.50 out per M — proxy only) | ~150 ms vs 1.6 s regular Luna (OpenAI demo chart) | Unconfirmed officially; press says confidence scores | Text + images; schema, max options, context unpublished | OFFICIAL-via-secondary + PRESS — [The Decoder](https://the-decoder.com/openai-expands-codex-and-its-api-at-devday-with-security-scans-a-decisions-api-and-ultrafast/), [TechCrunch](https://techcrunch.com/2026/09/30/openais-jev-clone-could-help-the-frontier-lab-stop-its-swarming-agents/), [Luna page](https://developers.openai.com/api/docs/models/gpt-6-luna) |
| Clef (27B) / Clef-flash (9B) | Cloudflare | GA on Workers AI (10-01); Apache-2.0 weights | Clef $0.24/M input (official); Clef-flash $0.09/M (secondary); output free | Median 209.3 / 38.8 ms; p95 238.6 / 122.4 ms (vendor) | Probabilities for all options; Brier + label-smoothed CE training; no ECE published | 64k context; 1–64 questions/request; ≤4 images; ≤13 MiB body; Jev-API-compatible | OFFICIAL — [blog](https://blog.cloudflare.com/clef-decision-models/), [Workers AI docs](https://developers.cloudflare.com/workers-ai/models/clef/) |
| Strands Decider 2B | AWS (Strands Labs) | Open source, local only (10-01); no hosted API | Free (self-host) | ~115 ms median RTX 3090; ~153 ms M3 | Confidence scores; Brier-measured; "3rd of 33" in 2B class on JevBench | Yes/no + choice; Qwen3.5-2B base | OFFICIAL — [Strands blog](https://strandsagents.com/blog/introducing-strands-decider/) |
| OpenRouter Decisions API / System One API | OpenRouter (serving Jev) | Alpha endpoint live | Jev price pass-through; `usage.cost` returned | n/a | Passes through Jev probabilities | 32K context | OFFICIAL — [OpenRouter docs](https://openrouter.ai/docs/guides/community/jev) |
| Runware `/v1/systemone` | Runware (Jev + Laya) | Live (post 09-28) | Jev $0.042/M; Laya $0.020/M (free to 10-12) | Laya 39.5–158.6 ms (local GPU figures) | Warns probabilities need validation | — | OFFICIAL — [Runware blog](https://runware.ai/blog/jev-laya-and-the-emerging-role-of-decision-models) |
| Jev on Vercel AI Gateway | Vercel | Live since 09-15 | TypeSafe pricing | — | — | — | OFFICIAL-partner — [Vercel](https://vercel.com/blog/ai-gateway-jev-model-launch) |
| TypeSafe AI node | n8n | Live 09-30; free on Cloud until 10-10 | Gateway credits | — | — | — | COMMUNITY forum (n8n staff) — [n8n](https://community.n8n.io/t/typesafes-jev-is-now-in-n8n-free-on-cloud-via-gateway-credits-until-october-10/317957) |
| JEV-27B-VL | AutoTrust AI | Open weights on HF (hosting unclear) | Unknown | ~46–150 ms (self-reported, game demos) | Self-reported ECE 0.0009, AUROC 0.995 | Up to 256 options; vision | AGGREGATOR — [MIR](https://marketintelligenceresearch.com/blog/three-jev-alternates-clef-jev-27b-vl-open-decision-model-family/) |

### Inferences
- For a guardrail use case (this repo's context), the only production-ready hosted options with documented calibration outputs and limits are Jev and Clef. Both share the same `/v1/systemone` request shape, so a client adapter can target either. OpenAI's preview cannot yet be evaluated.
- Jev is cheapest per input token ($0.042/M vs Clef $0.24/M). Clef-flash claims the lowest hosted latency (~39 ms median), and only Clef and OpenAI accept images.

### Gaps
- No vendor in the category publishes independent, third-party-audited calibration metrics (ECE/Brier) for hosted endpoints.
- OpenAI pricing, schema and GA date are unknown as of 2026-10-03.
- Workers AI pricing for hosted Jev, and any Bedrock or SageMaker hosting plans for Strands Decider, were not found.

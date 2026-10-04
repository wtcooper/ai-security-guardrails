# AI-Security Guardrail and Safety-Classifier Releases, 2026-09-26 to 2026-10-03 (with context)

Research date: 2026-10-03. Window = 2026-09-26..2026-10-03. Anything dated earlier is marked **[CONTEXT]**. Release dates come from the Hugging Face API `createdAt`/`lastModified` fields (queried 2026-10-03) unless stated otherwise. "Evidence quality" ratings: **A** = independent/third-party or peer-reviewable with methods; **B** = self-reported model card with held-out/external sets and methods disclosed; **C** = self-reported, small n, in-distribution or synthetic-only; **D** = marketing/press claim, or a repackage with no new eval.

Method: HF API searches (`sort=createdAt`, `direction=-1`) for prompt-injection, jailbreak, guard, safeguard, guardrail, safety-classifier, injection, agent-guard, tool-call, mcp, shield, moderation, laya, firewall; per-org `lastModified` scans for meta-llama, ibm-granite, nvidia, protectai, Qwen, google, openai, allenai and others; README reads for every security-relevant hit; arXiv API (cs.CR-style keyword queries sorted by submittedDate); web search plus vendor changelogs.

---

## 1. New open-weight guardrail and safety classifiers on Hugging Face (2026-09-26..10-03)

### Takeaway
No major lab (Meta, IBM, NVIDIA, Google, OpenAI, AllenAI, ProtectAI, Qwen) shipped a new guard model this week. All of the in-window activity comes from small orgs and individuals. The most substantive releases are **ZeroLeaks Shield Small** (118M, 10-02, non-commercial license), **Horizon-Labs' Apache-2.0 mmBERT guard family** (prompt-injection guard base v2.2 on 10-02; content-safety guard base and small on 09-26 and 09-27), **HS-Guard v10** (a 754.5M streaming safety classifier, non-commercial), and a burst of **Laya-based injection guards** (covered in Q2). Most other hits are hobby fine-tunes or repackages with weak or no evaluation.

### Cited Findings

**Substantive in-window releases (encoder and small classifiers)**

- **ZeroLeaks/shield-small**: created 2026-10-02, release "S15e, October 2, 2026". 118M-parameter 12-layer BERT fine-tuned from `intfloat/multilingual-e5-small`, shipped as int8 ONNX (118,445,560 bytes). Labels BENIGN/INJECTION. 256-token windows with stride 192, max 32 windows. Intended for retrieved documents, tool results, web pages, messages and **tool descriptions**, which makes it relevant to MCP tool poisoning. These are the same weights as the hosted `shield` tier. License **CC BY-NC 4.0**; commercial use needs a separate license. The card says the score "is not a calibrated probability". — [HF card](https://huggingface.co/ZeroLeaks/shield-small)
  - Reported metrics are for "Small + Shield rules v2" as a system, not the model alone: mean category-balanced accuracy 84.3%, attack recall 71.8%, FPR 7.2%, across 35 public datasets. The card says this "informed development and is not an unseen evaluation". **Evidence: C** (vendor-run, not held out). — [HF card](https://huggingface.co/ZeroLeaks/shield-small); release post [zeroleaks.ai/blog/shield](https://zeroleaks.ai/blog/shield) (not fetched)
- **Horizon-Labs/prompt-injection-guard-base v2.2**: updated 2026-10-02. v1, v2 and v2.1 are all dated 2026-09-23, just before the window. 307.5M params, `jhu-clsp/mmBERT-base` backbone, Apache-2.0, ungated, 8k context, ONNX (fp32 and int8) and transformers.js builds. Labels SAFE/INJECTION, the same convention as `protectai/deberta-v3-base-prompt-injection-v2`, so it works as a drop-in replacement for LLM Guard. It targets direct and **indirect** injection in emails, web pages, RAG chunks and tool/API outputs. v2.2 was distilled from large v2.1 plus a Qwen3.8-27B judge, and the macro average over external sets rose from .877 to .887. — [HF card](https://huggingface.co/Horizon-Labs/prompt-injection-guard-base); [API](https://huggingface.co/api/models/Horizon-Labs/prompt-injection-guard-base)
  - Self-run comparison at threshold 0.5 against ProtectAI v2, deepset, PIGuard, Prompt Guard 2 86M/22M, Wolf Defender and NeuralTrust small:
    - Macro average over external sets: **0.887** (this model), versus PIGuard 0.793, ProtectAI v2 0.637, Prompt Guard 2 86M 0.540 and Prompt Guard 2 22M 0.380.
    - Over-defense: NotInject 0.944, OR-Bench-hard 0.994.
    - Indirect injection: PIArena F1 0.969, BIPIA F1 0.628 (PIGuard 0.963, though PIGuard was trained on BIPIA), LLMail-Inject phase-2 recall 0.998.
    - The card notes that baselines use different definitions of "injection". **Evidence: B** (external sets and methods disclosed, but self-run).
    - Interactive [leaderboard](https://huggingface.co/spaces/Horizon-Labs/prompt-injection-leaderboard) and [eval-suite dataset](https://huggingface.co/datasets/Horizon-Labs/prompt-injection-eval-suite). — [HF card](https://huggingface.co/Horizon-Labs/prompt-injection-guard-base)
- **Horizon-Labs/prompt-injection-guard-large v2.1** **[CONTEXT, 2026-09-25]**: 567.8M, `BAAI/bge-m3` backbone, Apache-2.0. Macro average 0.884. Changelog: "large v2.1 (2026-09-25): first release of the large size". The small model (140.6M) also stays at v2.1. — [HF card](https://huggingface.co/Horizon-Labs/prompt-injection-guard-large)
- **Horizon-Labs/content-safety-guard-base** (created 2026-09-26, 307.5M) and **-small** (created 2026-09-27, 140.6M): mmBERT encoders, Apache-2.0, multilingual content moderation for prompts and responses, runnable on CPU or in the browser.
  - Small reports F1 for the unsafe class at threshold 0.5: PolyGuard prompts 0.771 (17 languages), PolyGuard responses 0.709, ToxicChat 0.776, OpenAI moderation set 0.762, XSTest 0.811.
  - The teacher Qwen3Guard-Gen-8B scores 0.846, 0.801, 0.638, 0.685 and 0.908 on the same sets. Qwen3Guard-Gen-0.6B strict scores 0.821, 0.748, 0.588, 0.660 and 0.853.
  - **Evidence: B** (benchmarks not used for training; self-run). — [small card](https://huggingface.co/Horizon-Labs/content-safety-guard-small); [base card](https://huggingface.co/Horizon-Labs/content-safety-guard-base)
- **KrisLiu16/HS-Guard-v10**: created 2026-09-28. 754.5M "hybrid-state" safety classifier (18 gated-delta layers plus 6 windowed-attention layers) on Qwen3.5-0.8B-Base, with separate prompt and response heads. It scores without generating text and supports **streaming response cut-off**. License **CC BY-NC 4.0**. Requires its own `hs-guard` package and a CUDA GPU.
  - Versus Qwen3Guard-Stream-0.6B on the same examples:
    - response red-line recall 98.25% vs 92.11% (n=114)
    - safe-response FPR 14.78% vs 22.17% (n=203)
    - ToxicChat F1 74.16 vs 70.51
    - Aegis 2.0 response F1 81.65 vs 78.95
  - Streaming engine: about 2.38 ms single-token median latency on one L20.
  - **Evidence: B/C** (small red-line sets; the policy is project-specific and includes selected political/public-order content). — [HF card](https://huggingface.co/KrisLiu16/HS-Guard-v10)
- **QuantumNous/astrlink-guard**: created 2026-09-30. Token-classification **PII and secret detection** (zh/en), on `microsoft/Multilingual-MiniLM-L12-H384`, ONNX, Apache-2.0. It is aimed at data leakage. — [API](https://huggingface.co/api/models/QuantumNous/astrlink-guard); [HF](https://huggingface.co/QuantumNous/astrlink-guard)

**Generative and agent-trajectory guards (in window)**

- **Kodjaoglanian/Athenas-Guard-9B**: created 2026-09-29. A LoRA merged into Qwen3.5-9B. It emits JSON `{verdict, category, action, reason}` with categories safe_query, frustrated_user, bot_harassment, prompt_injection and illicit_activity. It targets Brazilian-Portuguese customer service. Its evaluation is "a stratified adversarial stress suite comprising 60 isolated test vectors". **Evidence: C**. — [HF card](https://huggingface.co/Kodjaoglanian/Athenas-Guard-9B)
- **Jazhyc/Gleipnir-4B- and -9B-ToolTrajectories-InjectionAware**: created 2026-10-02. Research LoRA "AI-control monitors" on Qwen3.5-4B (and 9B), MIT license. They were trained for one epoch on 8,688 tool trajectories with Kimi K3 soft labels. Each classifies an agent trajectory as problematic or not (risk = sigmoid(logprob_1 − logprob_0)), and the instructions are hardened against injected content addressing the monitor. The card calls it "an uncalibrated research artifact" and publishes no metrics. **Evidence: D** (no eval). — [HF card](https://huggingface.co/Jazhyc/Gleipnir-4B-ToolTrajectories-InjectionAware)

**Repackages, quantizations and low-signal hobby uploads (in window; listed for completeness)**

- `OpenFlowLM/GPT-OSS-Safeguard-20B-NPU2` (10-02): an NPU repackage of `openai/gpt-oss-safeguard-20b`. — [API](https://huggingface.co/api/models/OpenFlowLM/GPT-OSS-Safeguard-20B-NPU2)
- `zgpu-ai/zlm-v1-moderation-edge` (09-29): a quantized ONNX build of `KoalaAI/Text-Moderation` (deberta, openrail). — [API](https://huggingface.co/api/models/zgpu-ai/zlm-v1-moderation-edge)
- Small injection classifiers with minimal cards. — [HF search](https://huggingface.co/api/models?search=prompt-injection&sort=createdAt&direction=-1&limit=40)
  - `edithngalame/mdeberta-v3-prompt-injection-en-es` (09-27)
  - `nodd-repo/prompt-injection` (09-28)
  - `thealper2/qwen3-0.6b-prompt-injection-detector` (09-26)
  - `KrishnikaKamaraj/sentinelAI-xlmr-prompt-injection` (10-02)
- Other guards. — [HF search](https://huggingface.co/api/models?search=guard&sort=createdAt&direction=-1&limit=40)
  - `Mihirbarve/agentguard-qlora` (09-28, Qwen2.5-3B, empty template card)
  - `InnoLabTeam/safety-classifier-v1` (09-29)
  - `aaaa47080/CryptoMind-Guard-0.6B` (10-03)
  - `RomanKudriavskii/jeff-guard-multilang` (10-02)
  - `Tulifo/chittu-guard-v0-4b` (09-27, child safety, en/ta)
  - `Fibogacci/muszka-guard-0.1b-v1.1` (09-26)

**Major-vendor check (none released in window)**

- No guard or safety-classifier model from meta-llama, ibm-granite, nvidia, protectai, google, openai or allenai was created in the window. The recent nvidia/ibm-granite/allenai updates are non-safety models (speech, forecasting, Kumo, etc.). — HF API author scans: [nvidia](https://huggingface.co/api/models?author=nvidia&sort=lastModified&direction=-1&limit=30), [ibm-granite](https://huggingface.co/api/models?author=ibm-granite&sort=lastModified&direction=-1&limit=30)
- **Qwen3Guard-Stream-0.6B, -4B and -8B** have `lastModified` = 2026-09-27, but were created 2025-09-23. The nature of the change was not determined (likely a card or config edit, not a new model). — [API](https://huggingface.co/api/models/Qwen/Qwen3Guard-Stream-4B)
- Meta's Prompt Guard 2 and Llama Guard 4 were last modified 2025-04-29. — [API](https://huggingface.co/api/models/meta-llama/Llama-Prompt-Guard-2-86M)

### Inferences
- **OWASP mapping (inferred; no in-window model card cites OWASP)**:
  - Injection and jailbreak classifiers (Shield Small, Horizon PI guard, the Laya guards) map to **LLM01 Prompt Injection**, and in agent settings to OWASP Agentic **Agent Goal Hijack**.
  - Tool-description scanning (Shield Small) addresses **MCP tool poisoning**.
  - astrlink-guard maps to **LLM02 Sensitive Information Disclosure**.
  - The content-safety guards (Horizon, HS-Guard) cover harmful-content output risks rather than security per se.
  - The trajectory monitors (Gleipnir, AdaGuard in Q4) map to **LLM06 Excessive Agency** and Agentic **Tool Misuse**.
- The practical "best open, commercially usable, fast" newcomer this week is the Horizon-Labs PI guard (Apache-2.0, ONNX, LLM Guard drop-in). Its self-reported numbers beat Prompt Guard 2 and ProtectAI v2 by a wide margin on indirect-injection sets. ZeroLeaks and HS-Guard are non-commercial.
- Encoder classifiers (100–600M) remain the dominant shape for new security guards. LLM-based guards this week are either single-domain (Athenas) or research monitors (Gleipnir).

### Gaps
- Download counts are tiny (mostly under 700) for every in-window model, so there is no adoption signal yet.
- None of these models has independent third-party evaluation.
- The ZeroLeaks full model card PDF and release blog were not fetched, so data sources and per-dataset numbers are unverified.
- What changed in the Qwen3Guard-Stream 2026-09-27 modification is unknown.
- Gated meta-llama repos may hide unlisted private updates. The public API showed none.
- A HF search for "mcp" and "firewall" returned no MCP-specific guard model in the window.

---

## 2. Guardrail models built on decision ("System One") models: Laya, Jev, Decider, Jeff, OpenAI Decisions API

### Takeaway
Yes, and this is the most active area of the week. Within about two weeks of Laya's open release (HF 2026-09-18/19), the community published at least six Laya-based security guards on HF in or just before the window. Two LoRA guards sit on other open decision models: Decider-2B (tool-call CONTINUE/ASK/BLOCK) and Jeff-0.8B (injection-type classification). OpenAI announced a Decisions API (2026-09-29, limited preview), but has published no security-specific docs or metrics. No guardrail model built on Jev or OpenAI Decisions was released. Jev is closed and hosted, and serves as the "SOTA reference" that the Laya guards benchmark against.

### Cited Findings

**Base decision models [CONTEXT; released just before the window]**

- **Laya** (Convai Innovations / Nandha Kishor M): HF created 2026-09-18 (`laya`, `laya-typed-decisions`) and 2026-09-19 (`laya-multilingual`), Apache-2.0.
  - Checkpoints: 421M ModernBERT-large (English, 512 ctx, card says "best at… guardrails"); 322M mmBERT-base multilingual (1k context, up to 8k); 421M typed-decisions.
  - Non-autoregressive. Returns typed answers (choice/score/noul) with calibrated probabilities in one forward pass, about 33 ms. Trained with RLCD (RL against proper scoring rules).
  - `laya-serve` exposes the same `POST /v1/systemone` shape as TypeSafe Jev.
  - Latency on a T4: 39.5 ms (English) and 32.8 ms (multilingual) for one question.
  - — [HF card](https://huggingface.co/convaiinnovations/laya); [API](https://huggingface.co/api/models/convaiinnovations/laya)
- **Jev** (TypeSafe AI): closed, hosted-only. "TypeSafe has not published weights, a parameter count, or a self-hosting option." Latency 70–500 ms, $42 per billion input tokens, output free. Primitives are Choice, Score and Noul. MarkTechPost notes the main benchmarks are vendor-run. — [MarkTechPost, 2026-09-19](https://www.marktechpost.com/2026/09/19/typesafe-ai-releases-jev/)
  - Release date conflict: MarkTechPost dates the release **2026-09-19**; another outlet says Jev launched **September 15**. — [pasqualepillitteri.it](https://pasqualepillitteri.it/en/news/19372/openai-decisions-api-jev)
  - `huggingface.co/typesafe/jev` (linked from safe-laya's card) returned an auth error from the HF API, so there are no public weights. — [API](https://huggingface.co/api/models/typesafe/jev)
- **TypeSafe "LLM guardrails" cookbook** **[CONTEXT]**: uses `jev-1.12` via `system_one()`. It screens five hazards (jailbreak/instruction override, harmful requests, medical advice, self-harm, output policy violations) with noul questions plus a 0–3 severity score. Example policies:
  - strict: "review >= 0.35, action >= 0.70, severity blocks at 2.0"
  - permissive: action >= 0.85
  - Actions are pass, human review, block, or route-to-support. Numbers are dated 2026-08-15. — [TypeSafe docs](https://docs.typesafe.ai/cookbooks/llm_guardrails.md)
  - The fetch summarizer also reported an OWASP "A07:2024" mapping. That is a web-app Top 10 ID, not an LLM one, and is likely a summarizer artifact. Treat it as **unverified**.
- **Decider-2B** (`Mapika/decider-2b`): HF created 2026-09-16, 1.88B, Apache-2.0, built on Qwen3.5-2B-Base. It scores enumerated options via answer-slot logits and had 285,776 downloads at query time. — [API](https://huggingface.co/api/models/Mapika/decider-2b)
- **Jeff-Qwen3.5-0.8B** (mstrasser): HF created 2026-09-28. "Community preview v1.2 (1 October 2026), with nine LoRA adapters". A v1.3 LTS base is "due in about 36 hours". — [HF card](https://huggingface.co/mstrasser/Jeff-Qwen3.5-0.8B)
- **OpenAI Decisions API**: announced at DevDay on **2026-09-29**, built on GPT-6 Luna, in limited preview with "broad release planned in the coming days". It picks among developer-defined answers and returns a confidence score. — [OpenAI DevDay 2026 recap](https://openai.com/index/devday-2026-recap/) (403 on direct fetch; content via search snippet); [ModelSystem.One](https://modelsystem.one/news/openai-decisions-api-preview/)
  - The launch video showed 150 ms per request against 1.6 s on the Responses API. Pricing is unpublished. ModelSystem.One reports "no public documentation: no guide, no API reference, no changelog entry". — [ModelSystem.One](https://modelsystem.one/news/openai-decisions-api-preview/)
  - Security use (e.g., asking "does this text contain instructions aimed at the agent" of scraped pages) appears only in **third-party** guides, not in OpenAI material. — [HF community blog](https://huggingface.co/blog/sora-2/what-is-openai-decisions-api-a-practical-guide-to); [Firecrawl](https://www.firecrawl.dev/blog/openai-decisions-api-vs-jev)

**Laya-based security guards (in window unless marked)**

| Model | Date (HF created) | Base / size | License | Risks | Key reported metrics | Evidence |
|---|---|---|---|---|---|---|
| [ottosulin/safe-laya](https://huggingface.co/ottosulin/safe-laya) | 2026-10-02 | laya 421M full FT | Apache-2.0 | 4-way BENIGN / PROMPT_INJECTION / JAILBREAK / HARMFUL_REQUEST on user prompts, retrieved docs, tool outputs | In-dist acc 0.903 (n=1378). TrustAIRLab in-the-wild any-attack recall 0.749. NotInject FPR 0.077 @0.30. **XSTest-safe FPR 0.80**. Head-to-head vs **Jev** on identical OOD sets: recall 0.749 vs 0.893, NotInject acc 0.655 vs 0.979, XSTest acc 0.658 vs 0.936. Latency about 30 ms GPU, about 9 rows/s laptop CPU. Ships a CycloneDX 1.6 AI-BOM. 11,314 training items, ~$2 of A10G | B (honest, publishes Jev gap) |
| [OidoStudio/laya-mm-guard-v3-gguf](https://huggingface.co/OidoStudio/laya-mm-guard-v3-gguf) | 2026-10-01 | laya-multilingual (mmBERT-base) full FT, GGUF F16 629 MB | Apache-2.0 | Direct jailbreak plus **indirect** injection in emails, invoices, web pages, tickets, tool output, code, resumes; multilingual | Public test splits F1 0.949 (n=12,013). LLMail-Inject F1 0.849. Independent hand-written gold set (n=89): F1 0.907, recall 0.93, FPR 0.106, AUROC 0.967. Calibration T=2.92, ECE 0.022→0.006. About 85 ms per question on CPU via [laya-go-server](https://github.com/Djancyp/laya-go-server) (Go + llama.cpp, `/v1/systemone`-compatible). Known misses: white-text resume instructions, markdown-image exfiltration, "@reviewer approve and merge" | B |
| [Dipto084/safe_laya](https://huggingface.co/Dipto084/safe_laya) | 2026-10-03 | laya-typed-decisions 421M | Apache-2.0 | ALLOW/DECLINE input jailbreak filter, multi-turn, from TRACE rubric ([arXiv:2608.15594](https://arxiv.org/abs/2608.15594)) | Held-out acc 0.879, AUROC 0.944, ECE 0.050, FPR 0.107. As an input filter vs AutoDAN-Turbo on Llama-3.1-8B: jailbroken 103/120 → 15/120 (stock laya 39/120). **Over-refusal rate not measured** | B/C |
| [mnjkshrm/sentrygate-laya](https://huggingface.co/mnjkshrm/sentrygate-laya) | 2026-10-03 | int8 ONNX export of base laya (not fine-tuned), about 440 MB | Apache-2.0 | Prompt override and bypass, for the [sentrygate](https://github.com/Manojython/sentrygate) on-device guard | deepset/prompt-injections (662 rows), 4-question MAX: ROC-AUC 0.869 (fp32 0.874). About 1.1 GB RAM on CPU | C |
| [GoatHerder/Ariadne-Laya-Injection](https://huggingface.co/GoatHerder/Ariadne-Laya-Injection) | 2026-09-28 | 4.2 MB "specialist interface" (1.05M params) on frozen laya 421M | Apache-2.0 | Binary injection | n=116 deepset test: acc 88.79% (base laya 57.76%, deepset deberta 99.14%). Scores not recalibrated | C |
| [Jojoarumugam/laya-agentguard](https://huggingface.co/Jojoarumugam/laya-agentguard) **[CONTEXT 09-23]** | 2026-09-23 | laya 421M | Apache-2.0 | **Destructive tool call** plus **injection in third-party content** | "**It failed its own quality gate**" (target 0.85 acc / 0.10 ECE). Injection acc 0.804 (n=51), destructive acc 0.796 (n=49). Fitted allow/escalate/block thresholds via [laya-forge](https://github.com/devjothish/laya-forge) | C (self-flagged) |
| [16sulphur/laya-prompt-guard](https://huggingface.co/16sulphur/laya-prompt-guard) **[CONTEXT 09-24]** | 2026-09-24 | laya 421M | Apache-2.0 | Injection and jailbreak ([gutcheck](https://github.com/16SULPHUR/gutcheck) pack) | Held-out (in-dist) acc: injection 0.954 (n=109), jailbreak 0.994 (n=320) | C |

Also seen but not analysed (Laya, security-adjacent):
- `hxrikp/laya-session-guard-followup-original` (09-26) and `hxrikp/laya-session-guard-pilot` (09-22)
- `GoatHerder/Ariadne-Laya-Moderation` (09-28)
- `Vinay57/laya-jigsaw-moderation` (09-24)

— [HF search "laya"](https://huggingface.co/api/models?search=laya&sort=createdAt&direction=-1&limit=40)

**Guards on other open decision models (in window)**

- **johannhartmann/decider-2b-toolcall-guard-lora**: created 2026-09-29. LoRA (r=16) on Decider-2B, Apache-2.0. Sits between an agent and its tools and answers CONTINUE / ASK / BLOCK given policy, goal, history (including raw tool outputs) and the proposed call. Trained on 3,141 decisions from AgentDojo and ToolEmu, with labels from Claude Haiku 4.5 and a Claude Sonnet 5 judge ([dataset](https://huggingface.co/datasets/johannhartmann/toolcall-guard-v1), MIT). — [HF card](https://huggingface.co/johannhartmann/decider-2b-toolcall-guard-lora)
  - Accuracy 0.80 on seen tools and 0.78 on unseen tools. False CONTINUE 0.11/0.12.
  - On the human-labelled ASSEBench (n=1,032): acc 0.65 and "unsafe let through" 0.53, versus Claude Sonnet 5 as guard at 0.79 / 0.30.
  - Latency 206 ms, versus 1,806 ms for Sonnet 5.
  - The card says it is "**Not a security boundary**… still lets about half of the unsafe actions through". **Evidence: B** (external human-labelled set included).
- **mstrasser/Jeff-Qwen3.5-0.8B-guard**: created 2026-10-01. LoRA on Jeff v1.2. Answers two questions in one pass: attack yes/no, and kind (benign / direct injection / indirect injection / jailbreak / **exfiltration**). Trained on deepset, Lakera gandalf, mosscap and TrustAIRLab data. — [HF card](https://huggingface.co/mstrasser/Jeff-Qwen3.5-0.8B-guard)
  - Held-out generated-application test (6,552 rows): acc 98.4%, ECE 0.004, versus 46.9% for Jeff alone.
  - Versus Qwen3.8-27B (300-row sample): 98.0% vs 84.0%, at 103 ms vs 3.92 s.
  - Latency about 25–31 ms p50 on an RTX PRO 6000.
  - Public-benchmark tests (deepset, JailbreakBench, LLMail, benign FP) are "**Not measured yet**". **Evidence: C** (synthetic in-distribution).

### Inferences
- The decision-model guard pattern has converged on three ingredients: typed noul/choice questions with fixed verbatim criteria wording, post-hoc temperature calibration, and three-zone allow/review/block thresholds. That matches the TypeSafe cookbook design. The calibrated-probability claim is the main differentiator over classic SAFE/INJECTION classifiers.
- Evidence so far says **fine-tuned Laya guards trail hosted Jev on benign accuracy and over-defense**: safe-laya's NotInject acc is 0.655 vs Jev's 0.979, and its XSTest FPR is 0.80. Purpose-built encoders such as the Horizon PI guard (NotInject 0.944) look stronger on over-defense than Laya fine-tunes.
- Agent action guards (decider tool-call guard, laya-agentguard "destructive" question) are the newest and weakest category. Both cards self-report failing gates, or letting about half of unsafe actions through on human-labelled data.
- OWASP mapping (inferred):
  - decider tool-call guard and laya-agentguard → LLM06 Excessive Agency, Agentic Tool Misuse / Goal Hijack
  - Jeff guard "exfiltration" class → LLM02 Sensitive Information Disclosure
  - all injection guards → LLM01

### Gaps
- No public Jev-based or OpenAI-Decisions-based guardrail *model* exists. Jev is API-only, and the Decisions API has no public docs, pricing or security metrics.
- I found no guard-specific TypeSafe product release in the window. The cookbook predates it (numbers dated 2026-08-15).
- None of the Laya guards was independently evaluated except via the arXiv System One evaluation in Q4, which covers base Laya, Jev, Decider and Bespoke Nimble, not these specific fine-tunes.
- The Jev release date conflicts between sources (09-15 vs 09-19).

---

## 3. Commercial guardrail product updates (2026-09-26..10-03)

### Takeaway
It was a quiet week for classic guardrail APIs. Changelogs for AWS Bedrock Guardrails, Azure Prompt Shields, Lakera, Cloudflare and Google Model Armor showed **no verifiable in-window feature releases**. The notable commercial items are adjacent:
- the **OpenAI Decisions API** preview (09-29)
- **NVIDIA's Open Agent Safety Platform** (09-28), a runtime/sandbox and in-silicon monitoring stack with no classifier models named
- **BlackFog ADX Vision 2.0** (marketing-level prompt-injection claims)
- **LiteLLM v1.103.0** (09-27, gateway hardening)

### Cited Findings
- **OpenAI Decisions API** (2026-09-29, limited preview). See Q2. — [OpenAI DevDay recap](https://openai.com/index/devday-2026-recap/); [ModelSystem.One](https://modelsystem.one/news/openai-decisions-api-preview/)
- **NVIDIA Open Agent Safety Platform** (2026-09-28). OpenShell is an Apache-2.0 runtime that "puts every agent in a deny-by-default sandbox and enforces policy from outside the agent's process". Sentry provides "out-of-band, in-silicon telemetry… quarantine agents in milliseconds". It is optimized for Vera CPU and BlueField DPU. — [NVIDIA dev blog](https://developer.nvidia.com/blog/nvidia-open-agent-safety-platform-a-reference-for-continuous-in-silicon-agent-monitoring/); [Help Net Security](https://www.helpnetsecurity.com/2026/09/28/nvidia-open-agent-safety-platform/); [CNBC](https://www.cnbc.com/2026/09/28/nvidia-releases.html)
  - The dev blog names **no classifier or guardrail models** (no NemoGuard or Nemotron safety models). — [NVIDIA dev blog](https://developer.nvidia.com/blog/nvidia-open-agent-safety-platform-a-reference-for-continuous-in-silicon-agent-monitoring/)
- **BlackFog ADX Vision 2.0** (Help Net Security products roundup, 2026-10-02): "seven layers of protection designed to identify prompt injection attempts" for generative and agentic AI governance. **Evidence: D** (marketing only). — [Help Net Security](https://helpnetsecurity.com/2026/10/02/new-infosec-products-of-the-week-october-2-2026)
- Same roundup: **Genea MCP**, an MCP server for access-control provisioning. It is not a guard. — [Help Net Security](https://helpnetsecurity.com/2026/10/02/new-infosec-products-of-the-week-october-2-2026)
- **LiteLLM**:
  - v1.103.0 (2026-09-27): "Config file ownership, Fuse and Capability routing, gateway hardening".
  - **[CONTEXT]** v1.102.0 (2026-09-19) runs post_call guardrail pipelines on streaming responses, so text and tool-call rewrites apply mid-stream.
  - — [LiteLLM release notes](https://docs.litellm.ai/release_notes/); [ai-tldr](https://ai-tldr.dev/releases/litellm-v1-102-0/)
- **DeepKeep "AI Lens for Developers"** and **Classie "Supervise"** (agent monitoring/control) were listed 2026-10-02 in an aggregator. **Evidence: D**. — [AI Agents Directory brief](https://aiagentsdirectory.com/news/ai-agents-news-brief-october-2-2026)
- **No in-window changes verified for:**
  - **Azure AI Content Safety**: the what's-new page was updated 2026-10-01, but its newest entry is Nov 2025 (Task Adherence public preview: detects misaligned tool invocations and improper tool input/output). — [Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/whats-new)
  - **Lakera**: the changelog has no dates. The latest container is 2.0.493 (audio debugging). The prior 2.0.474 notes "quality improvements across prompt injection and content moderation detection". — [Lakera changelog](https://docs.lakera.ai/changelog.md)
  - **Google Model Armor**: the release-notes URL returned 404. — [docs.cloud.google.com](https://docs.cloud.google.com/model-armor/docs/release-notes)
  - **Cloudflare**: nothing newer than Feb 2025 surfaced. — [Cloudflare changelog](https://developers.cloudflare.com/changelog/2025-02-26-guardrails/)
  - **AWS Bedrock Guardrails**: no AWS primary source in window. — [Mantel Group summary](https://community.mantelgroup.com.au/articles/post/what-s-new-in-amazon-bedrock-guardrails-in-2026-Hhk2P5WExiHLFg1)
- **[CONTEXT] recent commercial moves (before the window):**
  - HiddenLayer: $100M Series B and **Agent Harness Security** for coding agents (2026-09-02). — [PR Newswire](https://www.prnewswire.com/news-releases/hiddenlayer-unveils-agent-harness-security-to-protect-ai-powered-software-development-at-runtime-302841271.html); [KuCoin summary](https://www.kucoin.com/blog/hiddenlayer-100m-ai-agent-runtime-security)
  - AIR Security exited stealth with $50M for an inline "AI agent firewall" that inspects prompts, retrieved docs, tool outputs and **tool definitions** (2026-09-01). — [AI Learning Guides](https://ailearningguides.com/air-security-ai-agent-firewall-explained/)
  - Rubrik MCP support with "OWASP MCP Top 10-aligned guardrails" (2026-09-15). — [Futurum](https://futurumgroup.com/insights/rubriks-mcp-launch-bets-on-agentic-ai-as-cyber-resiliences-next-layer/)
  - Palo Alto Prisma AIRS 3.0 (RSAC 2026), plus a July 2026 "Tool Chaining" red-team category. — [PR Newswire](https://www.prnewswire.com/news-releases/palo-alto-networks-secures-agentic-ai-with-prisma-airs-3-0--302722579.html); [PANW docs](https://docs.paloaltonetworks.com/ai-runtime-security/new-features/by-date/prisma-airs/july-2026)
  - Lakera Guard returned a five-tier confidence breakdown per detector (Aug 2026, per a secondary source). — [tech-insider](https://tech-insider.org/lakera-vs-prisma-airs-vs-cisco-ai-defense-2026/)
  - Cisco AI Defense agentic guardrails, including a "Tool Exploitation guardrail" (date not verified). — [Cisco blog](https://blogs.cisco.com/ai/security-for-the-agentic-era-cisco-ai-defense-breaks-new-ground)
  - CrowdStrike Falcon AIDR "MCP proxy" (secondary comparison source, date not verified). — [aisecurityandsafety.org](https://aisecurityandsafety.org/en/compare/hiddenlayer-aisec-vs-crowdstrike-ai-security-tool/)
- **Threat context in window**:
  - Zscaler found two in-the-wild indirect-prompt-injection campaigns (SEO poisoning, hidden prompts) tricking agents into crypto payments. — [SecurityWeek](https://www.securityweek.com/prompt-injection-attacks-trick-ai-agents-into-making-crypto-payments/)
  - The Register on self-replicating prompt injections (2026-09-29). — [The Register](https://theregister.com/security/2026/09/29/add-one-more-ai-worry-to-the-nightmare-scenario-self-replicating-prompt-injections/5299922)

### Inferences
- Commercial momentum has shifted from prompt classifiers to **agent runtime control**: sandboxing, tool-call mediation, MCP proxies and identity. This week's NVIDIA launch fits that pattern. Classifier-style guards are becoming one component, often open-weight, inside these stacks.
- The OpenAI Decisions API, if it reaches GA with low latency and price, is the most likely commercial entrant to compete directly with Jev and Laya for guardrail checks. As of 10-03 there is no security documentation or benchmark for it.

### Gaps
- No primary-source in-window changelog entries were found for AWS Bedrock Guardrails, Google Model Armor (URL 404), Azure Prompt Shields, Cloudflare Firewall for AI / AI Security for Apps, Protect AI, CrowdStrike, Zscaler AI Guard or Cisco. Absence of evidence is not proof of no release; vendor blogs and X/LinkedIn were not exhaustively checked.
- The OpenAI DevDay recap returned 403, so Decisions API details rely on search snippets and secondary sources.
- The BlackFog claims are unverifiable marketing.

---

## 4. New benchmarks and evaluations for guardrail models (2026-09-26..10-03)

### Takeaway
There is a cluster of directly relevant evaluations:
- **Red Hat (10-02)** and the **guardrail-showdown** repo (10-01) benchmark Jev and Laya against classic guards. Both find that cheap pre-trained classifiers (DeBERTa PI v2) remain as accurate as decision models on prompt injection at a fraction of the latency.
- **arXiv 2609.33401 (09-27)** is the first paper evaluating System One models (Jev, Laya, Decider, Bespoke Nimble) specifically for agent-security decisions. It finds high-confidence failures concentrated in particular attack groups.
- Several calibration papers (overconfident guards; LLaDA-Guard) and agent-IPI harness papers (Silent Failures, pikit, AdaGuard) also appeared.
- No new OWASP-aligned eval suite was found.

### Cited Findings

**Industry and third-party benchmarks**

- **Red Hat Developers, "Benchmarking AI decision models against traditional guardrails"** (2026-10-02; Rob Geada, Mac Misiura, Shelton Cyril). Nine guardrails on NeMo Guardrails-derived class-balanced PI and toxicity benchmarks (EvalHub). — [Red Hat](https://developers.redhat.com/articles/2026/10/02/benchmarking-ai-decision-models-against-traditional-guardrails)

  | Model | PI accuracy | PI median latency | Content-safety accuracy | Content-safety latency |
  |---|---|---|---|---|
  | Qwen3.6-35B | 89.31% | 312.5 ms | 85.47% | — |
  | deberta-v3-base PI v2 | 89.01% | **54.1 ms** (CPU) | — | — |
  | DiffusionGemma | 87.72% | — | 85.53% | — |
  | Jev-1.13.0 | 86.35% | 348.1 ms | **86.20%** | 360.4 ms |
  | Laya | 85.44% | 119.3 ms | **57.87%** | — |
  | Nemotron-3.5 (custom) | 84.84% | — | 85.07% | — |
  | Shieldstral-1.0 | 72.02% | — | — | — |
  | BART-mnli | 61.49% | — | — | — |
  | granite-guardian-hap-125m | — | — | 80.27% | 33.2 ms |

  - Tuned policies raised Laya's accuracy by 17.83 points but cut Jev's by 3.67.
  - Conclusion: decision models "do not reliably outperform LLM-as-a-judge, pre-trained predictive models, or open source decision models in speed or accuracy".
  - **Evidence: A−**. It is a third party relative to TypeSafe and Convai, but the authors publish the RedHatAI deberta and granite-hap models that rank well (possible bias). The Jev latency includes about 56 ms of trans-Atlantic network.
- **AjeyDS/guardrail-showdown** (GitHub; results snapshot 2026-10-01). PI test of Regex, ProtectAI, Jev, GPT-6 Luna (via OpenRouter) and Lakera. — [GitHub](https://github.com/AjeyDS/guardrail-showdown)
  - Main set (942 prompts):

    | Model | Detection (default) | FP | Detection (tuned) | Latency | Cost per 1M |
    |---|---|---|---|---|---|
    | ProtectAI | 86.4% | 2.8% | 92.4% | 15.5 ms | free |
    | Jev | 79.3% | 3.6% | **94.6%** | 258 ms | $20.21 |
    | Luna | 83.9% | 2.1% | 86.6% | 1,042 ms | $44.07 |

  - Hard set (156 prompts), detection at default → tuned: Jev 66.2% → 80.0% with 0% FP; ProtectAI 42.5% → 52.5%.
  - Lakera partial results (390 checks before quota ran out): 89.6% detection, **32.1% FP**.
  - **Evidence: B−** (individual, small hard set).

**arXiv preprints**

- **arXiv 2609.33401, "Evaluating System One Models for Agent Security Decisions: Reliability, Calibration, and Selective Automation"** (2026-09-27, Yixuan Liu). Evaluates **Jev, Laya, Decider, Bespoke Nimble** against specialized classifiers and LLM judges. — [arXiv](https://arxiv.org/abs/2609.33401)
  - Strong aggregate calibration can hide "attacks classified as safe with high confidence" in particular attack groups.
  - Adapted configurations "do not consistently improve classification over their base models".
  - Under strict error limits, few inputs are auto-allowed, and separate allow/block thresholds increase automation "mainly through more blocks".
  - Judges share high-confidence errors.
  - **Evidence: A−** (preprint).
- **arXiv 2609.33671, COGNIT-Guard** (2026-09-27). CPU fast gatekeeper plus confidence-gated escalation to **Laya-322M** on Huawei Ascend 910C NPU. — [arXiv](https://arxiv.org/abs/2609.33671)
  - DUCS-Bench (n=607): 98.85% acc, benign FPR 0.42%, ECE 1.12%.
  - NPU-only latency 21.77 ms. Cascade 41.63 ms mean.
  - OOD SafetyBench-ZH accuracy 56.81–65.05%. **Evidence: B** (single author; custom benchmark).
- **arXiv 2609.36477, "Guard Models Are Overconfident Where Base Models Are Uncertain"** (2026-09-29). Five guard models. Adversarial attacks degrade calibration "by an order of magnitude", turning false negatives into high-confidence errors. Base LMs often remain uncertain on the same inputs. — [arXiv](https://arxiv.org/abs/2609.36477)
- **arXiv 2609.33634, LLaDA-Guard** (2026-09-27; Pin-Yu Chen et al.). Masked-diffusion guard via class-conditional reconstruction on LLaDA-8B. It leads on average rank across seven held-out safety benchmarks, with ECE 0.0875 vs 0.1384 for Qwen3Guard and token-level risk localization. — [arXiv](https://arxiv.org/abs/2609.33634)
- **arXiv 2609.34241, AdaGuard** (2026-09-28). 0.6B, 4B and 8B guard models that judge **agent trajectories under user-defined policies** (1–100 rules), with the new AdaptiveSafety dataset (10,939 train / 1,000 test). The 4B model reaches 89.30% on AdaptiveSafety and 71.82% on DynaBench. — [arXiv](https://arxiv.org/abs/2609.34241); [GitHub](https://github.com/Yunhao-Feng/AdaGuard)
- **arXiv 2609.32691, "Silent Failures in Agentic Security Evaluation"** (2026-09-26). An audit of an IPI benchmark harness. The tool-identity scorer reports 21.7% attack success where the true argument-level rate is 1.2%, and a model reported at 62.8% scores 0% under the corrected harness. It releases a validated tool-call-mediation harness. — [arXiv](https://arxiv.org/abs/2609.32691)
- **arXiv 2609.36817, pikit** (2026-09-29, Tencent). IPI toolkit with 13 attacks, 16 channels, 9 prevention strategies and 3 offline detectors. Defenses give a 71.8% relative ASR reduction. Offline detectors show "perfect precision but low recall". — [arXiv](https://arxiv.org/abs/2609.36817); [GitHub](https://github.com/Tencent/AI-Infra-Guard/tree/main/Research/pikit)
- **arXiv 2609.38357** (2026-09-29). Safe-response rate falls from 85–100% at turn 1 to 15–44% by depth 101 in long adversarial conversations. It argues for conversation-level safeguards. — [arXiv](https://arxiv.org/abs/2609.38357)
- **[CONTEXT] arXiv 2609.30657** (2026-09-25). Email-agent PI detection via attack-chain modeling: mean F1 0.406 vs 0.216 for the best of five pretrained detectors. — [arXiv](https://arxiv.org/abs/2609.30657)
- Other in-window cs.CR titles, **abstracts not read** (titles only, from the arXiv API). — [arXiv API query](https://export.arxiv.org/api/query?search_query=abs:%22prompt%20injection%22&sortBy=submittedDate&sortOrder=descending&max_results=40)
  - ToolFence, fine-grained authorization for tool-using agents ([2609.37196](https://arxiv.org/abs/2609.37196))
  - CounterSteer, activation steering against IPI ([2609.36570](https://arxiv.org/abs/2609.36570))
  - Render Before Reading ([2609.36121](https://arxiv.org/abs/2609.36121))
  - CoDeL ([2609.34463](https://arxiv.org/abs/2609.34463))
  - ORBIT, a multi-agent safety/security eval framework ([2609.33102](https://arxiv.org/abs/2609.33102))
  - Agent Safety From Within, internal-state harmful-trajectory detection ([2609.33039](https://arxiv.org/abs/2609.33039))
  - PlanGuard ([2609.32801](https://arxiv.org/abs/2609.32801))
  - PROACT-Agent ([2609.34415](https://arxiv.org/abs/2609.34415))
  - Divide and Inject ([2609.36576](https://arxiv.org/abs/2609.36576))
  - Memetic Trojans ([2610.00430](https://arxiv.org/abs/2610.00430))
  - A2A envelope-layer defense ([2610.00392](https://arxiv.org/abs/2610.00392))
  - The Innocent Courier, covert exfiltration via LLM web fetching ([2610.01768](https://arxiv.org/abs/2610.01768))

**Eval artifacts shipped with models (in window)**

- Horizon-Labs prompt-injection leaderboard and eval suite. — [Space](https://huggingface.co/spaces/Horizon-Labs/prompt-injection-leaderboard); [dataset](https://huggingface.co/datasets/Horizon-Labs/prompt-injection-eval-suite)
- `johannhartmann/toolcall-guard-v1` (MIT; tool-call CONTINUE/ASK/BLOCK decisions from AgentDojo and ToolEmu). — [dataset](https://huggingface.co/datasets/johannhartmann/toolcall-guard-v1)

### Inferences
- The two independent PI benchmarks this week agree. A 184M DeBERTa classifier (ProtectAI / RedHatAI v2) matches or beats Jev and Laya on default settings at about 15–55 ms. Jev's edge shows up mainly after threshold tuning and on hard or novel attacks.
- Laya's content-safety accuracy (57.87%) suggests it needs fine-tuning for that task. That is consistent with the wave of Laya fine-tunes.
- The calibration-under-attack results (2609.36477, 2609.33401) directly undercut a core System One selling point. "Calibrated probabilities" on clean data do not mean calibrated under adversarial inputs, so three-zone thresholds need per-attack-group validation.
- The Silent Failures paper implies that many published agent-IPI ASR numbers, including those used to market guards, may be inflated by harness defects.

### Gaps
- No new OWASP LLM / Agentic / MCP Top 10-aligned benchmark was found in the window.
- No public benchmark of the OpenAI Decisions API for security tasks exists yet.
- Full-paper numbers for 2609.33401 (per-model accuracy and ECE) were not extracted; only the abstract was read.
- Whether a "2026" edition of the OWASP LLM Top 10 exists was not verified in this session. The OWASP mappings above use the 2025 LLM Top 10 IDs and the Agentic Top 10 category names from memory, and should be checked.

---

## 5. Established guardrail models for comparison [CONTEXT; all outside the window]

### Takeaway
The incumbent baselines that this week's releases compare against are mostly 2024–2025 vintage plus a few 2026 NVIDIA and IBM updates. The ones most often cited in this week's model cards are ProtectAI DeBERTa v2, Meta Prompt Guard 2, PIGuard and Qwen3Guard.

### Cited Findings (HF createdAt / lastModified, license, params)
- **protectai/deberta-v3-base-prompt-injection-v2**: created 2024-04-20, modified 2026-07-09. Apache-2.0, 184M, 760,832 downloads. Still the de facto PI baseline (Red Hat benchmark: 89.01% at 54 ms). — [API](https://huggingface.co/api/models/protectai/deberta-v3-base-prompt-injection-v2); [Red Hat](https://developers.redhat.com/articles/2026/10/02/benchmarking-ai-decision-models-against-traditional-guardrails)
- **meta-llama/Llama-Prompt-Guard-2-86M / -22M**: created 2025-04-28. Llama license (gated). 279M / 71M params per HF safetensors total. — [API](https://huggingface.co/api/models/meta-llama/Llama-Prompt-Guard-2-86M)
- **meta-llama/Llama-Guard-4-12B**: created 2025-04-23, 12B, gated. — [API](https://huggingface.co/api/models/meta-llama/Llama-Guard-4-12B)
- **Meta LlamaFirewall** (agent guardrail system). — [Meta AI](https://ai.meta.com/research/publications/llamafirewall-an-open-source-guardrail-system-for-building-secure-ai-agents/)
- **leolee99/PIGuard**: created 2025-04-20, MIT, 184M. Over-defense-focused PI guard. — [API](https://huggingface.co/api/models/leolee99/PIGuard); [project](https://injecguard.github.io/)
- **qualifire/prompt-injection-sentinel**: created 2025-05-28, 396M, gated. — [API](https://huggingface.co/api/models/qualifire/prompt-injection-sentinel)
- **Qwen3Guard-Gen-0.6B / 8B and Qwen3Guard-Stream-0.6B / 4B / 8B**: created 2025-09-23, Apache-2.0 ([arXiv 2510.14276](https://arxiv.org/abs/2510.14276)). Stream variants modified 2026-09-27. — [API](https://huggingface.co/api/models/Qwen/Qwen3Guard-Gen-8B)
- **openai/gpt-oss-safeguard-20b / 120b**: created 2025-09-18, Apache-2.0, policy-following reasoning safety models (21.5B / 120.4B). — [API](https://huggingface.co/api/models/openai/gpt-oss-safeguard-20b)
- **IBM Granite Guardian**:
  - 3.3-8b (2025-06-03, Apache-2.0) and 4.1-8b (2026-04-16; GGUF 2026-05-26). — [API search](https://huggingface.co/api/models?author=ibm-granite&search=guardian&sort=createdAt&direction=-1&limit=5); [3.3 API](https://huggingface.co/api/models/ibm-granite/granite-guardian-3.3-8b)
  - granite-guardian-hap-125m: 80.27% content safety at 33 ms in the Red Hat benchmark. — [Red Hat](https://developers.redhat.com/articles/2026/10/02/benchmarking-ai-decision-models-against-traditional-guardrails)
- **NVIDIA**:
  - Nemotron-3.5-Content-Safety (2026-05-22), Nemotron-3-Content-Safety (2026-03-06), Nemotron-Content-Safety-Reasoning-4B (2025-11-26), Llama-3.1-Nemotron-Safety-Guard-8B-v3 (2025-08-20), llama-3.1-nemoguard-8b-content-safety (2025-01-15). — [API search](https://huggingface.co/api/models?author=nvidia&search=safety&sort=createdAt&direction=-1&limit=6)
  - Nemotron-3.5 scored 84.84% (custom policy) on PI in the Red Hat benchmark. — [Red Hat](https://developers.redhat.com/articles/2026/10/02/benchmarking-ai-decision-models-against-traditional-guardrails)
- **google/shieldgemma-2-4b-it**: created 2025-03-04. ShieldGemma 2B / 9B / 27B created 2024-07-16. Gemma license. — [API](https://huggingface.co/api/models?author=google&search=shieldgemma&sort=createdAt&direction=-1&limit=4)
- **allenai/wildguard**: created 2024-06-15, Apache-2.0, 7.2B. — [API](https://huggingface.co/api/models/allenai/wildguard)
- **Recent near-window encoders cited as baselines**: `vllm-sr/Vela-1.0-Encoder-307M-Shield` (2026-09-22), `AWuhrmann/tripwire-prompt-injection-base` (2026-09-23), and "Wolf Defender" and "NeuralTrust small" (named in the Horizon-Labs card). — [HF search](https://huggingface.co/api/models?search=shield&sort=createdAt&direction=-1&limit=40); [Horizon card](https://huggingface.co/Horizon-Labs/prompt-injection-guard-base)
- **Commercial incumbents**:
  - Azure Prompt Shields (GA Aug 2024; Task Adherence preview Nov 2025). — [Microsoft Learn](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/whats-new)
  - Lakera Guard. — [Lakera changelog](https://docs.lakera.ai/changelog.md)
  - Prisma AIRS 3.0. — [PR Newswire](https://www.prnewswire.com/news-releases/palo-alto-networks-secures-agentic-ai-with-prisma-airs-3-0--302722579.html)
  - Cisco AI Defense. — [Cisco blog](https://blogs.cisco.com/ai/security-for-the-agentic-era-cisco-ai-defense-breaks-new-ground)
  - Cloudflare AI Gateway Guardrails, which use Llama Guard; PI detection is a separate Enterprise WAF add-on. — [Cloudflare changelog](https://developers.cloudflare.com/changelog/2025-02-26-guardrails/); [Senthex](https://senthex.com/en/cloudflare-ai-gateway-alternatives/)
  - OpenAI Guardrails framework: launched Oct 6 (2025, per the HiddenLayer research timeline) and bypassed by HiddenLayer via judge manipulation. — [HiddenLayer](https://www.hiddenlayer.com/research/same-model-different-hat); [Hackread](https://hackread.com/openai-guardrails-bypass-prompt-injection-attack/)

### Inferences
- Meta Prompt Guard 2 (April 2025) is now the stalest major-lab PI baseline. New open guards routinely report beating it by large margins on indirect-injection sets (Horizon card: PIArena F1 0.150 vs 0.969). A Meta refresh would be a notable event to watch for.
- The commercial classifier-API incumbents (Azure, Lakera, Model Armor, Bedrock) have not visibly responded to the decision-model wave with typed or calibrated outputs. Lakera's per-detector confidence tiers (Aug 2026, secondary source) are the closest analogue.

### Gaps
- Parameter counts above are HF safetensors totals; they may differ from marketing sizes (e.g., Prompt Guard 2 "86M" shows 279M).
- Dates for the Cisco AI Defense agentic guardrails and the CrowdStrike Falcon AIDR MCP proxy were not verified from primary sources.

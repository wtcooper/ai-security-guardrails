# Gateway-layer and hosted guardrail designs for agentic tool-calling loops (as of 2026-10-08)

Scope: where checks run (request, response, tool calls, tool results, MCP), actions (block, redact/mask, rewrite, flag), how blocks reach the client, streaming, latency, fail-open vs fail-closed. Cyber and agent-security focus only. Pages were fetched 2026-10-08. Doc "last updated" dates are given where the page showed one. Most fetches went through a summarising tool, so quoted text is close to the source but should be spot-checked before it is quoted verbatim in a final report.

## Portkey AI Gateway (now being acquired by Palo Alto Networks): deny vs flag, 446/246, hooks, MCP

### Takeaway
Portkey runs guardrails as `before_request_hooks` (input) and `after_request_hooks` (output). They run async (log only, the default) or sync. In sync mode a failed check returns HTTP **446** when `deny=true` (the request is killed) or **246** when `deny=false` (the request still goes through and is flagged). Its MCP Gateway applies guardrails to `tools/call` arguments and tool results and returns a JSON-RPC error with code **-32446**. The LLM-specific and partner checks (moderation, PII, third-party providers) are not available for MCP tool calls.

### Cited Findings
- Hook points: input checks via `before_request_hooks` / `input_guardrails` run before the request goes to the LLM; output checks via `after_request_hooks` / `output_guardrails` run after the response comes back — [Portkey Guardrails docs](https://portkey.ai/docs/product/guardrails)
- "Portkey only evaluates the last message in the request body when running guardrails checks." — [Portkey Guardrails docs](https://portkey.ai/docs/product/guardrails)
- Async mode (`async=true`, the default) runs the guardrails alongside the LLM call with no added latency. It returns the provider's normal status (200) and only logs results, with no orchestration. Sync mode (`async=false`) blocks before and after the call, allows retry or fallback on failure, and adds latency — [Portkey Guardrails docs](https://portkey.ai/docs/product/guardrails)
- Status codes: a FAIL verdict with `deny=false` gives **246**: "Request will STILL be sent, but with a 246 status code". A FAIL verdict with `deny=true` gives **446**: "Request will be killed with a 446 status code". PASS gives 200 — [Portkey Guardrails docs](https://portkey.ai/docs/product/guardrails)
- Body shape: in sync mode the response carries `hook_results.{before_request_hooks[], after_request_hooks[]}`. Each entry has `verdict`, `id`, a `checks[]` array (with per-check `error` and execution time), `feedback` (counts of successful, failed and errored checks), `execution_time` in ms, and the `deny` and `async` flags — [Portkey Guardrails docs](https://portkey.ai/docs/product/guardrails)
- Streaming: input guardrails run before the stream starts. Output guardrails run after the stream completes and arrive as an extra SSE chunk. "No action is taken for output guardrails on streaming — fallback and retry are not triggered". Clients must send `x-portkey-strict-open-ai-compliance: false` to see `hook_results` — [Portkey Guardrails docs](https://portkey.ai/docs/product/guardrails)
- MCP Gateway guardrails: they intercept `tools/call` at two stages, input ("the arguments sent to the MCP tool") and output ("the result returned from the MCP tool"). The guardrail is created with `target: "mcp_tools"` and mapped per workspace or per server with `run_on: ["input"|"output"]`. It can be narrowed to individual tools with `mcp_integration_capability_ids` — [Portkey MCP Guardrails](https://portkey.ai/docs/aigw/product/mcp-gateway/guardrails)
- An MCP block is returned as a JSON-RPC error: `{"jsonrpc":"2.0","id":1,"error":{"code":-32446,"message":"Request blocked by guardrail","data":{"guardrail_id":"default.regexMatch","reason":"Input matched restricted pattern"}}}`. The documented example uses `"on_fail": "deny"` — [Portkey MCP Guardrails](https://portkey.ai/docs/aigw/product/mcp-gateway/guardrails)
- "LLM-specific checks (PII detection, content moderation, language checks, and third-party provider checks...) are not available for MCP tool calls." — [Portkey MCP Guardrails](https://portkey.ai/docs/aigw/product/mcp-gateway/guardrails)
- Corporate status: Palo Alto Networks announced its intent to acquire Portkey on **2026-05-04**, with closing expected in PANW fiscal Q4 2026. Portkey is to become the AI Gateway for Prisma AIRS. Analyst caveat: whether developer simplicity survives integration into the platform is an open question — [NAND Research](https://nand-research.com/palo-alto-networks-portkey-acquisition-anchors-its-agentic-security-stack/); [Pulse2](https://pulse2.com/palo-alto-networks-to-acquire-portkey-to-establish-ai-gateway-as-control-plane-for-autonomous-enterprise-agents/). Marketing claims in the coverage (99.99% uptime, "trillions of tokens per month") are vendor statements and are not independently verified.

### Inferences
- 246 is a "flag but continue" signal sent in-band on a success-range code. 446 is a non-standard 4xx. Clients built on the OpenAI SDK treat 446 as a generic API error, so the agent loop sees an exception rather than a refusal message.
- The rule that only the last message is evaluated matters in agent loops. When the request ends with a `tool` message, that tool result is probably what gets checked, and earlier injected tool results in the history are not re-checked. The docs do not state this explicitly.
- For prompt-injection detection on tool results in Portkey's MCP path, the documented checks are deterministic (regex and similar). Partner detectors are excluded for MCP, so injection screening of tool output would need the LLM-path guardrails or a webhook.

### Gaps
- Fail-open vs fail-closed when a guardrail check errors or times out is not documented on the fetched pages. Each check has an `error` field, but the verdict policy on error is not stated.
- No published latency figures for sync mode.
- It is unclear whether MCP guardrails support flag or async modes as well as deny.
- Post-acquisition branding and doc changes (for example "Prisma AIRS AI Gateway") were not confirmed in Portkey's docs.

## Kong AI Gateway: AI Prompt Guard, AI Semantic Prompt Guard, AI Sanitizer, cloud guardrail plugins, MCP

### Takeaway
Kong's guardrails are per-route plugins on AI Proxy traffic. Regex Prompt Guard returns **400**. Semantic Prompt Guard returns **403**. The vendor plugins (Lakera, Azure Content Safety, AWS Guardrails, GCP Model Armor, Custom Guardrail) inspect the request and optionally the response, including streamed responses frame by frame for Lakera. Kong's documented MCP security is identity, ACL and tool-visibility control (AI MCP Proxy and MCP OAuth2): an ACL denial is a JSON-RPC **-32602** error. Content guardrails on MCP tool arguments or results are not documented.

### Cited Findings
- AI Prompt Guard (Gateway 3.6+): PCRE allow and deny lists. For chat it scans "chat messages where the role is `user`", by default only the trailing user message. A match returns **400 Bad Request**, and deny takes precedence over allow. Response scanning is not documented — [Kong AI Prompt Guard](https://developer.konghq.com/plugins/ai-prompt-guard/)
- AI Semantic Prompt Guard (Gateway 3.8+, Enterprise): embedding similarity against allow and deny prompt lists stored in a vector DB (Redis, pgvector, Valkey 3.14+). A deny match, or failing the allow list, returns **403**. Prompt only — [Kong AI Semantic Prompt Guard](https://developer.konghq.com/plugins/ai-semantic-prompt-guard/)
- AI Lakera Guard (Gateway 3.13+, Enterprise) inspects at three points: request ("before any data leaves the gateway toward the target LLM"), buffered response ("before any byte is transmitted back toward the client"), and streaming response per frame ("buffering each frame in memory as it arrives"). By default the client is not told why it was blocked. `reveal_failure_categories: true` returns a JSON `breakdown` array with `detector_type`. Logging examples show `input_processing_latency` of about 72–78 ms. These are illustrative log values, not an SLA — [Kong AI Lakera Guard](https://developer.konghq.com/plugins/ai-lakera-guard/)
- The Lakera plugin extracts text from `/chat/completions`, `/responses`, `/images/generations` and `/embeddings`. Separate extraction of tool calls or tool results is not specified — [Kong AI Lakera Guard](https://developer.konghq.com/plugins/ai-lakera-guard/)
- AI Azure Content Safety (Gateway 3.7+, response checks from 3.12+) can send "all chat history, or just the 'user' content" to Azure Content Safety. Status code, Prompt Shields use and failure behaviour are not stated on the page — [Kong AI Azure Content Safety](https://developer.konghq.com/plugins/ai-azure-content-safety/)
- AI Custom Guardrail (Gateway 3.14+) calls any HTTP guardrail service in an INPUT phase (request body) and an OUTPUT phase (response body). It is configured with `config.response.block` and `block_message`. Other guardrail plugins in the same family are AI Sanitizer, AI AWS Guardrails, AI Azure Content Safety and AI GCP Model Armor — [Kong AI Custom Guardrail](https://developer.konghq.com/plugins/ai-custom-guardrail/)
- MCP: the AI MCP Proxy plugin bridges MCP and HTTP. It can proxy MCP, convert REST APIs into MCP tools, or expose grouped tools as an MCP server, and brings Kong's authentication, rate limiting and observability to MCP endpoints — [Kong AI MCP Proxy](https://developer.konghq.com/plugins/ai-mcp-proxy/)
- The MCP security cookbook (Gateway 3.14+) uses AI MCP OAuth2 plus per-tool ACLs in AI MCP Proxy. Tools are hidden from `tools/list`, and unauthorized calls are rejected "with `INVALID_PARAMS (-32602)` before the request leaves Kong". The recipe does not inspect tool arguments or results for content — [Kong Secure Internal MCP Gateway cookbook](https://developer.konghq.com/cookbooks/secure-internal-mcp-gateway/)
- Kong's April 2025 MCP blog names prompt guard, semantic guard, Azure Content Safety and PII sanitizer as "security layers" for MCP architectures but does not say they inspect MCP tool calls or results. "Trust layer" is positioning language — [Kong blog, 2025-04-24](https://konghq.com/blog/product-releases/securing-observing-governing-mcp-servers-with-ai-gateway)
- Kong AI Gateway 2.2 went GA on **2026-09-30**. It adds "MCP Server Bundling" (one route that shows each caller only the tools it is authorized to see and execute) and identity-aware AI policies. The press release names no new content-guardrail capability for MCP — [Kong press release](https://konghq.com/company/press-room/press-release/kong-ai-gateway-expands-with-new-capabilities-bringing-enterprise-governance-to-the-agentic-ai-era)

### Inferences
- Kong is an "authorize the tool" design for MCP plus "inspect the LLM payload" for chat. Injected content in tool results would reach the guardrail only when it re-enters the next `/chat/completions` request, and only if the plugin inspects non-user roles: Prompt Guard defaults to user role only, and Azure can be set to all history.
- Status codes differ across Kong plugins (400 for regex, 403 for semantic), so client handling has to be per plugin.

### Gaps
- Block status code and body for the Lakera, AWS Guardrails, Model Armor and Custom Guardrail plugins were not shown on the fetched pages.
- Fail-open or fail-closed on vendor timeouts or errors is not documented for any Kong guardrail plugin fetched.
- AI Sanitizer details (redact and restore of PII) were not fetched.
- No documented Kong guardrail inspects MCP `tools/call` results for prompt injection as of 2026-10-08.

## Cloudflare: AI Gateway Guardrails and Firewall for AI (now "AI Security for Apps")

### Takeaway
AI Gateway Guardrails classify prompts and responses with Llama Guard 3 8B, plus Prompt Guard 2 86M for prompt injection (category P1). Each hazard category is set to Flag, Ignore or Block. Blocks return error **2016** (prompt) or **2017** (response). Guardrails add roughly 500 ms. When any category is set to block, they fail closed if Workers AI is unreachable. The separate WAF product (AI Security for Apps, formerly Firewall for AI) scores inbound JSON requests on `cf-llm` endpoints, and blocks happen through WAF custom rules. Neither product documents tool-call or tool-result awareness.

### Cited Findings
- Guardrails check user prompts and model responses. Flag logs the content and Block prevents it from proceeding. Supported providers include OpenAI, Anthropic, DeepSeek and others. Page last updated 2026-09-30 — [Cloudflare AI Gateway Guardrails](https://developers.cloudflare.com/ai-gateway/features/guardrails/)
- Models: Llama Guard 3 8B (`@cf/meta/llama-guard-3-8b`) and a prompt-injection detector (`@cf/meta/prompt-guard-2-86m`) on Workers AI. "Evaluations using Llama Guard 3 8B on Workers AI add approximately 500 milliseconds per request". Longer content is split into chunks, which adds latency — [Cloudflare Guardrails usage considerations](https://developers.cloudflare.com/ai-gateway/features/guardrails/usage-considerations/)
- Fail behaviour: "If at least one hazard category is set to `block`, but AI Gateway is unable to receive a response from Workers AI, the request will be blocked", and if a category is set to `flag` and no response is obtained, "the request will proceed without evaluation" — [Cloudflare Guardrails usage considerations](https://developers.cloudflare.com/ai-gateway/features/guardrails/usage-considerations/)
- Streaming: on the REST API path Guardrails "evaluates the response and logs the result, but does not enforce it". On gateway endpoints Guardrails "buffers the full response, evaluates it, and returns a single non-streamed payload" — [Cloudflare Guardrails usage considerations](https://developers.cloudflare.com/ai-gateway/features/guardrails/usage-considerations/)
- Configuration is per category (for example `"P1": "BLOCK"` for prompt injection), with options Flag, Ignore or Block. A blocked prompt returns error code `2016` "Prompt blocked due to security configurations". A blocked response returns `2017` "Response blocked due to security configurations". Logs are written for all requests, linked by eventID — [Cloudflare Set up Guardrails](https://developers.cloudflare.com/ai-gateway/features/guardrails/set-up-guardrail/)
- AI Security for Apps (formerly Firewall for AI) scans "incoming requests to endpoints labeled `cf-llm`" and "only handles requests with a JSON content type". Detections cover PII, unsafe and custom topics, and prompt injection. Mitigation is through custom rules or rate-limiting rules that block or challenge. The detection fields are an Enterprise paid add-on. Page last updated 2026-09-08 — [Cloudflare AI Security for Apps](https://developers.cloudflare.com/waf/detections/ai-security-for-apps/)
- Prompt injection score `cf.llm.prompt.injection_score` runs 1–99, where 1–19 means a high likelihood of injection. The example rule is `(cf.llm.prompt.injection_score < 20)` with action Block — [Cloudflare prompt injection detection](https://developers.cloudflare.com/waf/detections/ai-security-for-apps/prompt-injection)

### Inferences
- Cloudflare is a request/response classifier gateway with no agent semantics. A tool result is screened only as part of the next prompt payload. Which message roles are classified is undocumented.
- The block → 2016/2017 error means an agent sees a gateway error, not an in-band refusal, which ends the turn.
- The AI Security for Apps block uses the WAF block action. Its HTTP status (403 by default for WAF blocks) is not stated on the fetched pages.

### Gaps
- Which messages (last user, all roles, tool messages) Guardrails classify is not documented.
- The HTTP status that accompanies 2016/2017 was not shown.
- Whether AI Security for Apps inspects responses is not stated on the fetched page.
- Neither product documents MCP guardrails.

## Microsoft Azure: Prompt Shields, Foundry agent guardrails, APIM `llm-content-safety`, indirect-injection guidance

### Takeaway
Microsoft has the most agent-aware first-party design. Foundry guardrails have four intervention points: user input, **tool call** (preview), **tool response** (preview) and output. The only action available for agents is "annotate and block": an indirect attack found in a tool response **stops the agent run**, so it is blocked, not sanitised. This adds about 50–100 ms per intervention point and covers only Microsoft-hosted tool types. APIM's `llm-content-safety` policy returns **403** and now also covers MCP tools and A2A APIs. For streams, APIM silently stops forwarding instead of returning 403. Microsoft's guidance for indirect injection layers spotlighting, Prompt Shields, deterministic exfiltration blocks and human consent.

### Cited Findings
- Prompt Shields detects **user prompt attacks**, scanned at the user-input intervention point, and **document attacks**: "hidden instructions in third-party content… In Foundry, the system scans for these attacks at the **user input** and **tool response** intervention points." The standalone API analyzes a `userPrompt` and up to five `documents` and returns `attackDetected` for each. Page updated 2026-09-18 — [Prompt Shields concept](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection)
- Document-attack subtypes include manipulated content, access to system infrastructure, information gathering (delete, modify or steal data), availability, fraud, malware, plus the user-attack classes — [Prompt Shields concept](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection)
- Spotlighting (preview) "tags input documents with special formatting that identifies them as lower-trust content… transforms the document content by using base64 encoding". It is off by default, works only with Chat Completions, and raises token counts. The troubleshooting advice for false positives is to switch "from **block** to **annotate** mode" and to consider "exempting trusted input sources from document attack scanning" — [Prompt Shields concept](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection)
- Foundry intervention points are User input, Tool call (Preview, agents only), Tool response (Preview, agents only) and Output. Agent guardrails are in preview. An agent's guardrail fully overrides the model deployment's guardrail. Doc updated 2026-08-18 — [Foundry guardrails overview](https://learn.microsoft.com/en-us/azure/foundry/guardrails/guardrails-overview)
- Actions: models support "Annotate" and "Annotate and block". Agents support **only "Annotate and block"**. Spotlighting and Groundedness are not supported for agents — [Foundry guardrails overview](https://learn.microsoft.com/en-us/azure/foundry/guardrails/guardrails-overview)
- Block semantics. Tool call: "the tool call won't be executed, and the agent stops functioning until there is another user input." Tool response with an indirect attack: "the full payload sent back from each tool to this agent is scanned… If detected, the agent stops operating immediately, and prevents the malicious content from being saved by the agent" — [Foundry intervention points](https://learn.microsoft.com/en-us/azure/foundry/guardrails/intervention-points)
- Latency: "Guardrail processing at each intervention point adds approximately 50-100ms of latency", varying with content length and the number of controls — [Foundry intervention points](https://learn.microsoft.com/en-us/azure/foundry/guardrails/intervention-points)
- Tool coverage: tool call and tool response moderation "require moderation support from the tool itself". The supported tools are Azure AI Search, Azure Functions, OpenAPI, SharePoint Grounding, Fabric Data Agent, Bing Grounding, Bing Custom Search and Browser Automation. Controls do not take effect for other tools. MCP is not on the list — [Foundry intervention points](https://learn.microsoft.com/en-us/azure/foundry/guardrails/intervention-points)
- Annotation shape: `prompt_filter_results[].content_filter_results.jailbreak.{filtered, detected}` — [Prompt Shields concept](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection)
- APIM `llm-content-safety`: it checks LLM prompts or completions through Azure AI Content Safety and "can also enforce content safety checks on requests or responses for MCP tools or A2A Agent APIs managed in API Management". On detection, "API Management blocks the request or response and returns a `403` error code". `shield-prompt="true"` enables Prompt Shields (default false). It is placed in the inbound and/or outbound section, and `enforce-on-completions` is available. Doc dated 2026-08-18 — [APIM llm-content-safety](https://learn.microsoft.com/en-us/azure/api-management/llm-content-safety-policy)
- APIM streaming: "the stream handler buffers events in a sliding window and, if a content safety violation is detected, stops forwarding further events to the client. A `403` error isn't returned in this case." The prompt window is fixed at 10,000 characters. The response window defaults to 1,000 characters, configurable with overlap. Oversized content returns 403 — [APIM llm-content-safety](https://learn.microsoft.com/en-us/azure/api-management/llm-content-safety-policy)
- MSRC guidance (Andrew Paverd, 2025-07-29) has three layers. Prevention: hardened system prompts plus Spotlighting in three modes (delimiting, datamarking, encoding with base64 or ROT13). Detection: Prompt Shields, "a probabilistic classifier-based approach", integrated with Defender for Cloud. Impact mitigation: data governance, deterministic blocking of exfiltration such as markdown image injection and untrusted links, and explicit user consent. On detection the app "must either block the prompt completely or take some other type of defensive action" — [MSRC blog](https://www.microsoft.com/msrc/blog/2025/07/how-microsoft-defends-against-indirect-prompt-injection-attacks)

### Inferences
- Microsoft's documented default for injected tool output is to **halt the run**: block the turn, not redact and continue. Spotlighting is the "continue safely" alternative. It transforms rather than removes the content, and it is not available for agents.
- APIM's streaming behaviour (silent truncation with no error) is a client-visible difference. An agent harness may see a truncated stream rather than an error.

### Gaps
- What a Foundry agent run returns to the caller when a tool response is blocked (run status, error code, message) was not shown.
- Prompt Shields standalone API latency and character limits were not captured in this pass.
- APIM behaviour when Content Safety is unreachable (fail-open or fail-closed) is not documented on the policy page.
- It is unclear whether the APIM policy on MCP inspects `tools/call` arguments, results or both.

## AWS: Bedrock Guardrails (ApplyGuardrail, input tags, prompt attack filter), Bedrock Agents, AgentCore Policy

### Takeaway
Bedrock's prompt-attack filter is **input-only and tag-dependent**, and AWS states it **does not evaluate tool results** (`toolResult`) or tool definitions in Converse. To screen tool output, the documented route is to call `ApplyGuardrail` yourself. A newer gateway-native option (GA 2026-06-17) is **AgentCore Policy**: Cedar policies call Bedrock Guardrails on MCP `tools/call`, HTTP runtime and inference targets. `forbid` denies inputs and `suppressOutput` suppresses tool, agent or model outputs. A `LOG_ONLY` mode is available for threshold tuning.

### Cited Findings
- `ApplyGuardrail` assesses any text against a configured guardrail without invoking a model, with `source: INPUT|OUTPUT`. The response has `action: GUARDRAIL_INTERVENED|NONE`. `outputs[]` holds masked text when content was masked, "a single text with canned message" when blocked, and is empty when the guardrail did not intervene. Assessments include `PROMPT_ATTACK` filter results and `invocationMetrics.guardrailProcessingLatency`. The docs frame it as usable "anywhere in your application flow", for example evaluating input before RAG retrieval — [ApplyGuardrail docs](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-independent-api.html)
- Sensitive-information findings carry `action: BLOCKED | ANONYMIZED`, so masking and continuing is a native outcome for PII and regex matches — [ApplyGuardrail docs](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-independent-api.html)
- The prompt attack filter covers jailbreaks, prompt injection, and prompt leakage (Standard tier only). It is configured with `inputStrength`/`inputAction: BLOCK | NONE`, where NONE is "Detect (no action)" — [Bedrock prompt attack filter](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-prompt-attack.html)
- **"The prompt attack filter does not evaluate tool results. Content in `messages[].content[].toolResult` is not assessed for prompt attacks, and neither are the tool definitions in `toolConfig.tools[].toolSpec`."** — [Bedrock prompt attack filter](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-prompt-attack.html)
- With InvokeModel or InvokeModelWithResponseStream you "must always use input tags… If there are no tags, prompt attacks for those use cases will not be filtered" — [Bedrock prompt attack filter](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-prompt-attack.html)
- Input tags are `<amazon-bedrock-guardrails-guardContent_{suffix}>`. AWS recommends "a new, random string as the `tagSuffix` for every request" because a static tag lets a malicious user close it and inject. Untagged content is not processed, except that with no tags at all the whole prompt is processed, apart from the prompt-attack filter, which still needs tags. Converse uses `guardrailConfiguration` / guardContent blocks instead of XML tags — [Bedrock input tagging](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-tagging.html)
- Bedrock Agents: a guardrail is attached with `GuardrailConfiguration` on CreateAgent or UpdateAgent. The page does not say which orchestration steps (action-group outputs, KB results) are evaluated — [Bedrock Agents guardrail](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-guardrail.html)
- AgentCore Policy with Guardrails: policies can use the `ContentFilter`, `PromptAttack` (JAILBREAK, PROMPT_INJECTION, PROMPT_LEAKAGE) and `SensitiveInformation` safeguards, each scored 0–1 in steps of 0.2. Guardrails run on "MCP targets — `POST /mcp` (JSON-RPC `tools/call`)", HTTP runtime targets and HTTP inference targets. The evaluator extracts the configured `dataPath`, calls `InvokeGuardrailChecks`, and returns ALLOW or DENY — [AgentCore guardrails in policies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-guardrails-in-policies.html)
- Effects: `permit`/`forbid` govern authorization of the request (input). `suppressOutput` "operates on the data an action returns. After an authorized action is completed, it evaluates the outputs against the guardrail and suppresses the output when the guardrail is violated" — [AgentCore guardrails in policies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-guardrails-in-policies.html)
- Default thresholds: Content Filter 0.2, Prompt Attack 0.4, Sensitive Info 0.2. AWS recommends tuning in `LOG_ONLY` mode against a golden set, or against production traffic labelled by an LLM judge, then building confusion matrices. "Guardrails are non-deterministic… Policies, however, are deterministic." Regex is not supported, and Cedar conditions cannot be mixed with guardrail conditions — [AgentCore guardrails in policies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-guardrails-in-policies.html)
- GA on 2026-06-17 (AWS NY Summit). Secondary coverage describes Cedar as default-deny — [Classmethod](https://dev.classmethod.jp/en/articles/20260617-amazon-bedrock-agentcore-policy-guardrails/)
- A CSA research note (2026-08-06, "CoreBreak") reports that agent harnesses, including AgentCore's InvokeHarness, dispatched attacker-supplied tool-use blocks without the model running, which bypasses model-level guardrails. It recommends verifying that tool calls came from real model completions. The CVE IDs are from that note and were not independently verified — [CSA research note](https://labs.cloudsecurityalliance.org/research/csa-research-note-agent-infra-guardrail-bypass-20260806-csa/)

### Inferences
- In AWS's model, tool output from a Bedrock-native Converse loop is not screened for injection unless the developer calls `ApplyGuardrail` on it, or routes the tool through AgentCore Gateway with a `suppressOutput` PromptAttack policy on the output path.
- `suppressOutput` is an output-withholding action (suppress and continue?), not a turn-kill. What the agent receives in place of the output is undocumented.
- CoreBreak argues for checking tool calls at the dispatch or gateway layer, not only at model input and output.

### Gaps
- What `suppressOutput` returns to the MCP client or agent (empty result, JSON-RPC error, or placeholder text) is not documented on the fetched page.
- AgentCore fail behaviour when `InvokeGuardrailChecks` errors or times out was not stated in the fetched content. Only secondary sources say Cedar is default-deny.
- ApplyGuardrail latency SLOs are not documented (only a per-call `guardrailProcessingLatency` metric).
- Bedrock Agents' per-step guardrail coverage is undocumented on the page fetched.
- Streaming (sync vs async guardrail modes for ConverseStream) was not captured in this pass.

## Google Cloud Model Armor: sanitizeUserPrompt / sanitizeModelResponse, Apigee, Vertex / Agent Platform, Agent Gateway, MCP

### Takeaway
Model Armor is a stateless, single-turn screening API (`sanitizeUserPrompt` / `sanitizeModelResponse`). The caller acts on `filterMatchState`. Integrations (Vertex / Gemini Enterprise Agent Platform, Apigee, Agent Gateway, Google MCP servers) enforce **INSPECT_ONLY** or **INSPECT_AND_BLOCK** through templates or floor settings. Model Armor screens Google MCP servers' `tools/call` requests and responses. Agent Gateway screens ingress, agent-to-LLM, agent-to-MCP and A2A traffic. The Vertex integration is explicitly **fail-open** when Model Armor is unavailable.

### Cited Findings
- Filters: RAI (hate, harassment, sexual, dangerous, CSAM), prompt injection and jailbreak, Sensitive Data Protection (basic or advanced, with de-identify), and malicious URLs (up to 256 per request). Enforcement is "Inspect only" (log) or "Inspect and block". Model Armor is stateless and single-turn, does not decode Base64, hex or URL-encoded content, and is limited to 4 MB documents. Prompt injection needs at least 3 words, otherwise it returns `NO_MATCH_FOUND`. Updated 2026-10-06 — [Model Armor overview](https://docs.cloud.google.com/security-command-center/docs/model-armor-overview)
- API response: `sanitizationResult.filterMatchState` (MATCH_FOUND or NO_MATCH_FOUND), `invocationResult`, and `filterResults.pi_and_jailbreak.piAndJailbreakFilterResult.{matchState, confidence_level}`, plus `sdp` inspect or redact results. The guidance is to "Sanitize each user input separately" and "Don't include conversation history". The caller implements blocking — [Model Armor sanitize prompts/responses](https://docs.cloud.google.com/model-armor/sanitize-prompts-responses)
- MCP: Model Armor sanitizes "'tools/call' request and response" and "'prompts/get' request and response", plus tool execution errors. `tools/list` and `resources/*` are not scanned. It is enabled through floor settings (`--add-integrated-services=GOOGLE_MCP_SERVER`) with INSPECT_AND_BLOCK. When blocked, "Depending on the MCP server and client, you might receive an error or an empty response". Applies to Google and Google Cloud MCP servers. Updated 2026-10-06 — [Model Armor MCP integration](https://docs.cloud.google.com/model-armor/model-armor-mcp-google-cloud-integration)
- Agent Gateway (part of Gemini Enterprise Agent Platform) has Model Armor checks at client-to-agent ingress, agent-to-external-LLM (OpenAI API format), agent-to-MCP and agent-to-agent (A2A v1). It can "either block and redact content… or to only inspect content and log". On an ingress block "the client receives an error". On egress violations "the connection is terminated". Streaming sanitization is supported only via `streamQuery` for ADK agents. Updated 2026-10-06 — [Model Armor + Agent Gateway](https://docs.cloud.google.com/model-armor/model-armor-agent-gateway-integration)
- Vertex / Agent Platform: per-request templates via `modelArmorConfig` (`promptTemplateName`, `responseTemplateName`) or project floor settings. Blocks return `"blockReason": "MODEL_ARMOR"` with `blockReasonMessage`. **Fail-open**: the platform "skips the Model Armor sanitization step and continues processing the request" when Model Armor is unavailable, though configuration errors in INSPECT_AND_BLOCK still surface. Documents and file uploads are not sanitized in this integration — [Model Armor + Vertex](https://docs.cloud.google.com/model-armor/model-armor-vertex-integration)
- Apigee: the `SanitizeUserPrompt` policy goes in the request flow and `SanitizeModelResponse` in the response flow. "Apigee allows, blocks, or redacts the request or response". Redacted data can be passed on through flow variables — [Model Armor + Apigee](https://docs.cloud.google.com/model-armor/model-armor-apigee-integration)
- Other listed integrations: Cloud Networking Services and LangChain — [Model Armor overview](https://docs.cloud.google.com/security-command-center/docs/model-armor-overview)

### Inferences
- Google is the only vendor here that documents block-or-redact for MCP and A2A at a managed agent gateway, but MCP coverage is limited to Google-hosted MCP servers (via floor setting) or traffic routed through Agent Gateway.
- The advice to send single-turn input without history implies that tool results should be sanitized individually (as `sanitizeUserPrompt`-style inputs) rather than inside the full conversation.

### Gaps
- Model Armor latency figures are not published on the fetched pages.
- Fail-open or fail-closed for the Agent Gateway, MCP and Apigee integrations is undocumented (only Vertex is explicitly fail-open).
- Apigee fault codes and HTTP status on block were not shown.
- Whether Agent Gateway's "redact" applies to prompt-injection findings or only to SDP findings is unclear.

## Lakera Guard

### Takeaway
Lakera documents the most explicit agent-loop screening model: call `/v2/guard` at **every step** with the full history. Only the **last interaction** is re-screened. Tool results (`tool::content`) are treated as untrusted. Tool calls (`assistant::tool_call`) get DLP, a "Dangerous Deviation" detector and tool allow/deny lists. Tool definitions are screened every time they are sent. The application decides the action (block, or mask with `payload: true`).

### Cited Findings
- Screening locations: system and developer messages are trusted and not screened. `user::content` gets Prompt Defense, moderation, DLP, malicious links and custom checks. `assistant::content` is screened. `assistant::tool_call` gets "Data Leakage Prevention on the arguments, Dangerous Deviation detector, Tool Allow/Deny List". `tool::content`: "Tool results are untrusted: a compromised or poisoned tool can leak data or carry an indirect prompt injection". `tool_definition::content` is screened "each time they are sent" when bound to Prompt Defense — [Lakera screening agent conversations](https://docs.lakera.ai/docs/api/screening-roles)
- "AI Guardrails screens the **last interaction** in the `messages` array" and "Call the Guard API at every step of the agent loop so each interaction is screened as it occurs." Tool-call screening needs the conversation history ("the detector judges the call against the user's request"), the tool call in the final assistant message, and tool definitions in a top-level `tools` field — [Lakera screening agent conversations](https://docs.lakera.ai/docs/api/screening-roles)
- Response: `{"flagged": true, "breakdown": [{"detector_type": "prompt_attack", "detector_id": "...", "detected": true, "result": "l1_confident", "message_id": 1}]}`. Tool-call detections carry a `source` index. "To mask detected content rather than block the interaction, request `"payload": true`" to get match locations — [Lakera screening agent conversations](https://docs.lakera.ai/docs/api/screening-roles)
- Quickstart guidance: "If AI Guardrails detects any threats, do not call the LLM!" The demo app runs in monitoring mode by default — [Lakera quickstart](https://docs.lakera.ai/docs/quickstart)
- An example Lakera call latency of about 72–78 ms appears in Kong plugin log examples. Treat it as illustrative — [Kong AI Lakera Guard](https://developer.konghq.com/plugins/ai-lakera-guard/)

### Inferences
- Lakera's design (incremental last-interaction screening with full history for context) maps directly onto a gateway that sees every agent turn. It is designed to catch both injected tool output and deviating tool calls before execution.

### Gaps
- No Lakera-published latency SLO or fail-open/closed recommendation was found on the fetched pages.
- Lakera's ownership and branding changes (it is reportedly part of Check Point) were not verified in this pass.

## Palo Alto Networks Prisma AIRS (AI Runtime Security API intercept), MCP and agent protections

### Takeaway
The Prisma AIRS Scan API (sync and async) accepts a `tool_event` content type that carries MCP metadata plus tool `input` and `output`. It applies prompt injection, AI Agent Protection, DLP, URL, malicious code, DB security and toxic content detections, and returns `action: allow|block` with a verdict and category. Enforcement is left to the calling app or gateway. Portkey is set to become Prisma AIRS's AI gateway.

### Cited Findings
- MCP tool scanning was added to the existing sync and async scan APIs. The payload is `tool_event: {metadata: {ecosystem: "mcp", method: "tools/call", server_name, tool_invoked}, input, output}`. It validates "tool definitions, inputs and outputs using multiple detection services" (prompt injection, toxic content, AI agent protection, database security, custom topics, URL, malicious code, DLP). The response has `action` ("block"/"allow"), `verdict` and `category`, with `input_detected` and `output_detected` breakdowns. Updated October 2026 — [Prisma AIRS Detect MCP Threats](https://docs.paloaltonetworks.com/ai-runtime-security/administration/api-intercept-create-configure-security-profile/detect-mcp-threats)
- The targeted threats are context poisoning via tool-description manipulation and credential leakage in tool output — [Prisma AIRS Detect MCP Threats](https://docs.paloaltonetworks.com/ai-runtime-security/administration/api-intercept-create-configure-security-profile/detect-mcp-threats)
- API intercept limits: 2 MB per sync scan and 5 MB per async scan (max 25 batched). API keys are region-locked. Updated 2026-10-01 — [Prisma AIRS API intercept overview](https://docs.paloaltonetworks.com/prisma-airs/ai-runtime-security/airs-api/ai-runtime-security-api-intercept-overview)
- Rate limits return HTTP 429, and "callers (apps, gateways, agents) need to handle this gracefully" (search-result summary of PANW docs) — [Prisma AIRS API intercept overview](https://docs.paloaltonetworks.com/prisma-airs/ai-runtime-security/airs-api/ai-runtime-security-api-intercept-overview)

### Inferences
- Prisma AIRS is a decision API. Whether a block kills the turn or drops the tool result is the integrator's choice. The acquisition implies Portkey's 446/-32446 semantics will be the likely enforcement surface.

### Gaps
- Latency SLOs, fail-open guidance and client-behaviour recommendations on block are not documented on the fetched pages.
- AI Agent Protection detector semantics (for example tool misuse or goal deviation) were not detailed.

## Other gateways with documented agent/tool guardrails (TrueFoundry, agentgateway, Envoy AI Gateway → Agent Router, CrowdStrike/Pangea)

### Takeaway
TrueFoundry and agentgateway both document guardrails on MCP tool pre-invoke and post-invoke. TrueFoundry adds validate vs mutate modes and an explicit fail-open option. agentgateway uses external gRPC policy servers with pass, mutate or deny and **failClosed by default**. Envoy AI Gateway (renamed Agent Router) documents MCP authorization and tool filtering but no content guardrails on tool traffic.

### Cited Findings
- TrueFoundry has four hooks: LLM Input, LLM Output, MCP Pre Tool and MCP Post Tool. **Validate** blocks without changing data. **Mutate** rewrites (for example PII redaction) and can also block — [TrueFoundry guardrails overview](https://truefoundry.com/docs/ai-gateway/guardrails-overview)
- TrueFoundry enforcement strategies: **Enforce** (block on violation and on guardrail error), **Enforce But Ignore On Error** ("graceful degradation on guardrail outage"), and **Audit** (log only) — [TrueFoundry guardrails overview](https://truefoundry.com/docs/ai-gateway/guardrails-overview)
- TrueFoundry execution: LLM input validation runs in the background while the model request is in flight, and on failure "the AI Gateway cancels the model request". Output guardrails "are not applied when the response is streamed". "All MCP guardrails run synchronously — pre-tool guardrails block before the tool executes, and post-tool guardrails block after." Providers include Bedrock Guardrails, Azure Content Safety and Prompt Shield, Prisma AIRS, Model Armor, CrowdStrike (formerly Pangea), Cisco AI Defense, F5 and others — [TrueFoundry guardrails overview](https://truefoundry.com/docs/ai-gateway/guardrails-overview)
- CrowdStrike AIDR can run on MCP tool calls and tool outputs through TrueFoundry, with arguments and results sent as text (search-result summary) — [TrueFoundry CrowdStrike integration](https://www.truefoundry.com/docs/ai-gateway/crowdstrike)
- agentgateway MCP guardrails apply to `tools/call`, `tools/list`, `prompts/get`, `resources/read` and wildcards. Outcomes are Pass, mutate parameters or results, or "Deny: Reject the call with a JSON-RPC error". The external gRPC server receives "a structured, MCP-native payload, including the JSON-RPC method name, the target backend, the request or response parameters". Phases are `request`, `response` and `full`. Failure mode is **`failClosed` (default)** or `failOpen` — [agentgateway MCP guardrails](https://agentgateway.dev/docs/standalone/main/documentation/mcp/guardrails/about/)
- Envoy AI Gateway is now "Agent Router": "Formerly Envoy AI Gateway — now an Agentic AI Foundation project. Same code, same maintainers." aigateway.envoyproxy.io redirects there. Its MCP docs cover OAuth, `toolSelector` filtering, multiplexing and CEL authorization, but no tool-content guardrails — [Agent Router MCP docs](https://theagentrouter.ai/docs/capabilities/mcp/)
- Pangea (now CrowdStrike) blog: its MCP server routes user prompts and tool or data-source outputs through AI Guard for injection detection and redaction (vendor blog, not verified beyond the search snippet) — [Pangea blog](https://pangea.cloud/blog/secure-mcp-servers-with-ai-guardrails/)

### Inferences
- TrueFoundry's note that a post-tool check "cannot undo a side effect the tool already committed" ([TrueFoundry blog](https://www.truefoundry.com/blog/truefoundry-ai-gateway-guardrails-explained), seen only as a search snippet) shows why pre-tool checks on arguments matter as much as post-tool checks on results.

### Gaps
- Noma, Lasso, HiddenLayer and Protect AI (now part of Prisma AIRS) were **not researched** in this pass because of tool-call budget. Their agent-loop recommendations are unknown here.
- Helicone and Traefik were not checked.
- agentgateway's built-in LLM prompt guards (regex, moderation, Bedrock, Model Armor) were not covered on the fetched MCP page.

## Cross-cutting: redact-and-continue vs block, fail-open vs fail-closed, latency budgets

### Takeaway
For **prompt injection found in tool output**, documented first-party behaviour is overwhelmingly **block or halt**, not "strip the injection and continue". Azure Foundry stops the agent, Portkey denies with -32446, Model Armor errors or returns an empty response, and agentgateway denies with a JSON-RPC error. **Redaction or masking** is offered for PII, secrets and SDP (Bedrock `ANONYMIZED`, Model Armor/Apigee redact, TrueFoundry Mutate, Lakera `payload` masking, AgentCore `suppressOutput`). The only "transform and continue" injection defence is Microsoft's spotlighting, which is not supported for agents. Fail-open vs fail-closed is inconsistent and often undocumented. Published latency is about 50–100 ms per check (Azure) up to about 500 ms (Cloudflare Llama Guard), with async or parallel modes used to hide it.

### Cited Findings
- Block or halt on injected tool output. Azure: "the agent stops operating immediately" — [Foundry intervention points](https://learn.microsoft.com/en-us/azure/foundry/guardrails/intervention-points). MSRC: the app "must either block the prompt completely or take some other type of defensive action" — [MSRC blog](https://www.microsoft.com/msrc/blog/2025/07/how-microsoft-defends-against-indirect-prompt-injection-attacks). Portkey MCP deny returns JSON-RPC -32446 — [Portkey MCP Guardrails](https://portkey.ai/docs/aigw/product/mcp-gateway/guardrails). Model Armor MCP gives "an error or an empty response" — [Model Armor MCP](https://docs.cloud.google.com/model-armor/model-armor-mcp-google-cloud-integration)
- Redaction for data, not injections: Bedrock PII `ANONYMIZED` returns masked text in `outputs` — [ApplyGuardrail](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-independent-api.html). Apigee "allows, blocks, or redacts" — [Model Armor + Apigee](https://docs.cloud.google.com/model-armor/model-armor-apigee-integration). TrueFoundry Mutate (for example PII redaction) — [TrueFoundry](https://truefoundry.com/docs/ai-gateway/guardrails-overview). Lakera masking via `payload: true` — [Lakera](https://docs.lakera.ai/docs/api/screening-roles). AgentCore `suppressOutput` suppresses violating tool, agent or model outputs — [AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-guardrails-in-policies.html)
- Flag-only modes are common and recommended for tuning: Portkey async (default) and 246; Cloudflare Flag; Azure Annotate (models only); Bedrock `NONE` ("Detect"); Model Armor INSPECT_ONLY; TrueFoundry Audit; AgentCore LOG_ONLY, which AWS explicitly recommends for threshold calibration — sources in the product sections above, especially [AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-guardrails-in-policies.html)
- Fail-closed by default: Cloudflare when any category is set to Block ("the request will be blocked") — [Cloudflare](https://developers.cloudflare.com/ai-gateway/features/guardrails/usage-considerations/); agentgateway `failClosed` default — [agentgateway](https://agentgateway.dev/docs/standalone/main/documentation/mcp/guardrails/about/); TrueFoundry "Enforce" blocks on guardrail error — [TrueFoundry](https://truefoundry.com/docs/ai-gateway/guardrails-overview); APIM returns 403 when content exceeds Content Safety limits — [APIM](https://learn.microsoft.com/en-us/azure/api-management/llm-content-safety-policy)
- Fail-open: Vertex + Model Armor "skips the Model Armor sanitization step and continues" when unavailable — [Model Armor + Vertex](https://docs.cloud.google.com/model-armor/model-armor-vertex-integration); Cloudflare in Flag mode "will proceed without evaluation" — [Cloudflare](https://developers.cloudflare.com/ai-gateway/features/guardrails/usage-considerations/); TrueFoundry "Enforce But Ignore On Error" as an opt-in — [TrueFoundry](https://truefoundry.com/docs/ai-gateway/guardrails-overview)
- Latency: Azure Foundry about 50–100 ms per intervention point — [Foundry intervention points](https://learn.microsoft.com/en-us/azure/foundry/guardrails/intervention-points); Cloudflare Llama Guard about 500 ms per request — [Cloudflare](https://developers.cloudflare.com/ai-gateway/features/guardrails/usage-considerations/); Lakera about 72–78 ms in example logs — [Kong Lakera plugin](https://developer.konghq.com/plugins/ai-lakera-guard/); Portkey async adds no latency — [Portkey](https://portkey.ai/docs/product/guardrails); TrueFoundry runs input validation in parallel with the model call and cancels it on failure — [TrueFoundry](https://truefoundry.com/docs/ai-gateway/guardrails-overview)
- Streaming is commonly weakened. Portkey takes no action on output guardrails for streams. TrueFoundry does not apply output guardrails to streams. Cloudflare buffers the whole response (gateway) or only logs (REST). APIM stops forwarding without a 403. Kong Lakera buffers per frame. Model Armor streaming works only via ADK `streamQuery` — sources in the product sections above.
- Block return shapes vary widely:
  - HTTP 446/246: [Portkey](https://portkey.ai/docs/product/guardrails)
  - HTTP 400 and 403: [Kong Prompt Guard](https://developer.konghq.com/plugins/ai-prompt-guard/) / [Kong Semantic](https://developer.konghq.com/plugins/ai-semantic-prompt-guard/)
  - HTTP 403: [APIM](https://learn.microsoft.com/en-us/azure/api-management/llm-content-safety-policy)
  - error codes 2016/2017: [Cloudflare](https://developers.cloudflare.com/ai-gateway/features/guardrails/set-up-guardrail/)
  - `blockReason: MODEL_ARMOR`: [Vertex](https://docs.cloud.google.com/model-armor/model-armor-vertex-integration)
  - in-band canned message in `outputs`: [Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-independent-api.html)
  - annotations `filtered`/`detected`: [Azure](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection)
  - JSON-RPC errors on MCP: -32446 [Portkey](https://portkey.ai/docs/aigw/product/mcp-gateway/guardrails), -32602 for ACL [Kong](https://developer.konghq.com/cookbooks/secure-internal-mcp-gateway/), [agentgateway](https://agentgateway.dev/docs/standalone/main/documentation/mcp/guardrails/about/)

### Inferences
- Synthesis of the sources above, by product:

| Product | Tool call checked | Tool result checked | Injection action | Block return | Default on guard failure |
|---|---|---|---|---|---|
| Portkey | MCP input | MCP output (regex-type only) | deny / flag (246) | 446 / JSON-RPC -32446 | undocumented |
| Kong | ACL only (MCP) | not documented | block | 400 / 403 / JSON-RPC -32602 | undocumented |
| Cloudflare AI GW | no | only as next prompt | block / flag | err 2016 / 2017 | closed (block categories), open (flag) |
| Azure Foundry agents | yes (preview) | yes (preview, MS tools only) | halt run | annotation + stop | undocumented |
| Azure APIM | MCP / A2A (unspecified) | MCP / A2A (unspecified) | block | 403; silent stream cut | undocumented |
| AWS Bedrock (Converse) | no | **no** (prompt attack excludes toolResult) | block / mask | canned message | n/a |
| AWS AgentCore Policy | yes (forbid) | yes (suppressOutput) | deny / suppress | undocumented | default-deny (secondary source) |
| Google Model Armor | MCP `tools/call` request | MCP `tools/call` response | block / redact | error or empty (MCP); MODEL_ARMOR | open (Vertex) |
| Lakera | `assistant::tool_call` | `tool::content` | app decides; mask option | `flagged` + breakdown | undocumented |
| Prisma AIRS | `tool_event.input` | `tool_event.output` | allow / block verdict | app decides | undocumented |
| TrueFoundry | MCP pre-tool | MCP post-tool | validate / mutate | undocumented | configurable (Enforce = closed) |
| agentgateway | ext server, request | ext server, response | pass / mutate / deny | JSON-RPC error | closed (default) |

- The common design is "detect at each hop, then kill the turn on injection, redact on sensitive data, and flag-only during tuning". No major vendor documents removing just the injected span from a tool result and continuing as a recommended practice.
- For a drop-in gateway guardrail, the closest documented precedents are Portkey and Kong (status-code blocks on the LLM path) and Lakera (last-interaction screening with full history). Azure Foundry's tool-response "halt" is the precedent for blocking on tool output.

### Gaps
- None of the products publish a guardrail latency SLO. The figures above come from usage notes or examples.
- Fail-open vs fail-closed is undocumented for Portkey, Kong, Azure (Foundry and APIM), Prisma AIRS, Lakera, and the Model Armor MCP, Apigee and Agent Gateway integrations.
- No independent benchmark compares these products on detecting injection in tool results. The CSA CoreBreak note is the only third-party agent-guardrail bypass analysis found.

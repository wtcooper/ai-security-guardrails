# Our LiteLLM gateway guardrail implementation: what is standard LiteLLM and what is ours

Audit of the repository at commit 336bd9f against the installed LiteLLM **1.103.2**. Link paths are relative to the repo root.
`LL/` stands for `.venv/lib/python3.12/site-packages/litellm/`. Every line number below was read from the files themselves.
Classification labels used throughout:
**STANDARD** = a documented LiteLLM feature; **BUILT-IN, UNDOCUMENTED** = public LiteLLM code that the docs page does not
describe; **INTERNAL** = we depend on LiteLLM internals (a likely break point on upgrade); **OURS** = entirely our code.

## Q1. Which LiteLLM hooks, modes and mechanisms does agentic-security use, and how is each classified?

### Takeaway
agentic-security is a `CustomGuardrail` that overrides only the unified `apply_guardrail` method and runs in
`mode: [pre_call, post_call]`. It uses no `during_call` and no MCP hooks. The hook plumbing, the `structured_messages`
write-back and the 200 "passthrough" refusal are LiteLLM's. Everything that decides (window, judge, hedging, deadline,
fail-open, surgical cuts) is ours. Four things depend on LiteLLM internals: the post-call in-place reply rewrite, the
`streaming_buffer_until_moderated` attribute, the `llm_router` module global, and spend attribution through
`metadata.user_api_key_*`.

### Cited Findings

**Mechanism-by-mechanism classification (agentic-security)**

| Mechanism | Our code | Class | LiteLLM evidence |
|---|---|---|---|
| Subclass `CustomGuardrail`, loaded by `guardrail: agentic_security.AgenticSecurity`; `mode`, `default_on`, per-request `"guardrails": [...]` | [agentic_security.py:55, 312-318](/deploy/agentic-security/agentic_security.py#L312); [litellm_config.example.yaml:3-8](/deploy/agentic-security/litellm_config.example.yaml#L3) | STANDARD | `default_on` at [LL/integrations/custom_guardrail.py:163,208](/.venv/lib/python3.12/site-packages/litellm/integrations/custom_guardrail.py#L163); `should_run_guardrail` at [:991](/.venv/lib/python3.12/site-packages/litellm/integrations/custom_guardrail.py#L991); documented in the [quick start](https://docs.litellm.ai/docs/proxy/guardrails/quick_start) |
| Unified `apply_guardrail(inputs, request_data, input_type, logging_obj)` | [agentic_security.py:329-359](/deploy/agentic-security/agentic_security.py#L329) | STANDARD | base method [custom_guardrail.py:1245-1268](/.venv/lib/python3.12/site-packages/litellm/integrations/custom_guardrail.py#L1245); documented in the [custom guardrail docs](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail) |
| Routing to the unified path | (implicit) | STANDARD, with a caveat | The proxy routes to `unified_guardrail` only if `"apply_guardrail" in type(callback).__dict__` ([LL/proxy/utils.py:1668-1676](/.venv/lib/python3.12/site-packages/litellm/proxy/utils.py#L1668)). A subclass of `AgenticSecurity` that does not redefine `apply_guardrail` would fall back to the native hooks, which do nothing. The deployment-level check uses `type(self).apply_guardrail is not CustomGuardrail.apply_guardrail` instead ([custom_guardrail.py:775-776](/.venv/lib/python3.12/site-packages/litellm/integrations/custom_guardrail.py#L775)) |
| Reads `inputs["structured_messages"]`, `inputs["tools"]`, `inputs["texts"]` (pre-call) and `inputs["tool_calls"]`, `inputs["texts"]` (post-call) | [agentic_security.py:374-386](/deploy/agentic-security/agentic_security.py#L374) | STANDARD | `GenericGuardrailAPIInputs` at [LL/types/utils.py:4538-4549](/.venv/lib/python3.12/site-packages/litellm/types/utils.py#L4538); the docs list texts/images/tools/tool_calls/structured_messages/model ([docs](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail)) |
| Withholding: returns a **new** `structured_messages` list | [agentic_security.py:410-419](/deploy/agentic-security/agentic_security.py#L410) | STANDARD | The docs say that for `structured_messages` you must "replace the list with a new one". The chat handler writes it back only when `guardrailed_structured_messages is not original_structured_messages` ([LL/llms/openai/chat/guardrail_translation/handler.py:184-198](/.venv/lib/python3.12/site-packages/litellm/llms/openai/chat/guardrail_translation/handler.py#L184)). Anthropic: [LL/llms/anthropic/chat/guardrail_translation/handler.py:663-677](/.venv/lib/python3.12/site-packages/litellm/llms/anthropic/chat/guardrail_translation/handler.py#L663). Responses: [LL/llms/openai/responses/guardrail_translation/handler.py:491-497](/.venv/lib/python3.12/site-packages/litellm/llms/openai/responses/guardrail_translation/handler.py#L491) |
| Pre-call block and streamed post-call block via `self.raise_passthrough_exception(...)`, which raises `ModifyResponseException` | [agentic_security.py:421-429](/deploy/agentic-security/agentic_security.py#L421) | BUILT-IN, UNDOCUMENTED | A public helper with a docstring at [custom_guardrail.py:256-304](/.venv/lib/python3.12/site-packages/litellm/integrations/custom_guardrail.py#L256), class at [LL/exceptions.py:1196-1229](/.venv/lib/python3.12/site-packages/litellm/exceptions.py#L1196). Used in-tree by Bedrock, Grayswan and Straiker (grep). Not mentioned on the custom-guardrail docs page, whose documented way to block is "raise an exception" ([docs](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail)) |
| Post-call (non-stream) **in-place reply rewrite**: mutates `request_data["response"].choices[*].message` (content becomes the refusal, `tool_calls=None`, `function_call=None`, `finish_reason="content_filter"`) and returns `texts=[refusal]` | [agentic_security.py:431-445](/deploy/agentic-security/agentic_security.py#L431) | **INTERNAL** | It depends on (a) the handler stashing the response in `request_data["response"]` ([chat handler.py:437-442](/.venv/lib/python3.12/site-packages/litellm/llms/openai/chat/guardrail_translation/handler.py#L437)). It also depends on (b) the tool-call write-back skipping a choice whose `tool_calls` is `None` (`if choice_tool_calls is not None` at [handler.py:1054-1086, guard at 1075](/.venv/lib/python3.12/site-packages/litellm/llms/openai/chat/guardrail_translation/handler.py#L1075)). The docs do not describe this |
| `streaming_buffer_until_moderated = True` as an instance attribute | [agentic_security.py:321-322](/deploy/agentic-security/agentic_security.py#L321) | **INTERNAL** (a documented Bedrock param, read from custom guardrails by `getattr`) | Read via `resolve_streaming_flag`: "default < guardrail attribute < guardrail_config < optional_params" ([LL/proxy/guardrails/guardrail_hooks/unified_guardrail/unified_guardrail.py:962-968, 1008-1032](/.venv/lib/python3.12/site-packages/litellm/proxy/guardrails/guardrail_hooks/unified_guardrail/unified_guardrail.py#L962)). For `apply_guardrail` guardrails the default is `False` ([LL/proxy/utils.py:3772](/.venv/lib/python3.12/site-packages/litellm/proxy/utils.py#L3772)). The field is documented only on `BedrockGuardrailStreamingParams` ([LL/types/guardrails.py:665-671](/.venv/lib/python3.12/site-packages/litellm/types/guardrails.py#L665)). The custom-guardrail docs say instead that post_call streaming guardrails "run on the fully assembled response after all chunks have been delivered to the client" ([docs](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail)) |
| Judge calls via `from litellm.proxy.proxy_server import llm_router` then `llm_router.acompletion(model=judge_model, metadata=..., timeout=judge_timeout_s, num_retries=0)` | [agentic_security.py:388-408](/deploy/agentic-security/agentic_security.py#L388) | `Router.acompletion` is public; the `llm_router` module global is **INTERNAL** (LiteLLM's own `init_guardrails.py:60` uses the same import) | [LL/proxy/guardrails/init_guardrails.py:60](/.venv/lib/python3.12/site-packages/litellm/proxy/guardrails/init_guardrails.py#L60) |
| Chargeback: copies `user_api_key*` fields from the metadata dict that holds the proxy's `UserAPIKeyAuth`, and adds tags `guardrail_stage:*` and `guardrail:<name>` | [agentic_security.py:361-372](/deploy/agentic-security/agentic_security.py#L361) | **INTERNAL** (convention) + OURS (trust rule) | The proxy writes `user_api_key_*` and the `user_api_key_auth` object into the metadata bucket ([LL/proxy/litellm_pre_call_utils.py:1644-1674](/.venv/lib/python3.12/site-packages/litellm/proxy/litellm_pre_call_utils.py#L1644)). Spend logs read `metadata.user_api_key_hash`, `user_api_key_team_id` and `metadata.tags` into `request_tags` ([LL/proxy/spend_tracking/spend_tracking_utils.py:242, 554-580, 783-791](/.venv/lib/python3.12/site-packages/litellm/proxy/spend_tracking/spend_tracking_utils.py#L554)) |
| "Router calls skip proxy guardrails" (no recursion) | docstring [agentic_security.py:389-390](/deploy/agentic-security/agentic_security.py#L389) | Holds by LiteLLM's structure, not by a documented guarantee | The deployment-level guardrail hook returns early unless `kwargs["guardrails"]` is a list ([custom_guardrail.py:795-796](/.venv/lib/python3.12/site-packages/litellm/integrations/custom_guardrail.py#L795)). Our judge call sets no `guardrails` |
| Window, judge envelope, digit scoring, review band, locate/cut, hedging, deadline, fail-open, content-hash audit log, refusal/redaction texts | [agentic_security.py:58-308, 329-359](/deploy/agentic-security/agentic_security.py#L58) | OURS | — |

**Hooks and modes**
- The configured mode is `[pre_call, post_call]` ([litellm_config.example.yaml:7](/deploy/agentic-security/litellm_config.example.yaml#L7); [gateway/litellm_config.yaml:94-113](/gateway/litellm_config.yaml#L94)). The config comment gives the reason: "pre_call (not during_call), so a block never cancels billed inference".
- LiteLLM offers more hook types: `pre_call, post_call, during_call, logging_only, pre_mcp_call, during_mcp_call, post_mcp_call, realtime_input_transcription` ([LL/types/guardrails.py:1265-1273](/.venv/lib/python3.12/site-packages/litellm/types/guardrails.py#L1265)). agentic-security uses none of the MCP ones, nor `during_call` or `logging_only`.
- Pre-call maps to `UnifiedLLMGuardrails.async_pre_call_hook` → the endpoint translation's `process_input_messages` ([unified_guardrail.py:185-241](/.venv/lib/python3.12/site-packages/litellm/proxy/guardrails/guardrail_hooks/unified_guardrail/unified_guardrail.py#L185)).
- Post-call maps to `async_post_call_success_hook` → `process_output_response`. The route resolves the call type ([unified_guardrail.py:283-379](/.venv/lib/python3.12/site-packages/litellm/proxy/guardrails/guardrail_hooks/unified_guardrail/unified_guardrail.py#L283)).
- Streaming post-call maps to `async_post_call_streaming_iterator_hook` ([unified_guardrail.py:970-1060](/.venv/lib/python3.12/site-packages/litellm/proxy/guardrails/guardrail_hooks/unified_guardrail/unified_guardrail.py#L970)).
- **Mechanisms LiteLLM offers that agentic-security does not use:**
  - `inject_advisory_message` ([custom_guardrail.py:306+](/.venv/lib/python3.12/site-packages/litellm/integrations/custom_guardrail.py#L306));
  - `scan_only_tool_results` / `skip_tool_message_in_guardrail` / `skip_system_message_in_guardrail` ([LL/llms/base_llm/guardrail_translation/utils.py:194-258](/.venv/lib/python3.12/site-packages/litellm/llms/base_llm/guardrail_translation/utils.py#L194));
  - `streaming_transform_mode: incremental_diff` ([unified_guardrail.py:1004-1007](/.venv/lib/python3.12/site-packages/litellm/proxy/guardrails/guardrail_hooks/unified_guardrail/unified_guardrail.py#L1004));
  - `violation_message_template` ([custom_guardrail.py:237-254](/.venv/lib/python3.12/site-packages/litellm/integrations/custom_guardrail.py#L237));
  - `GuardrailRaisedException` (agentic-security never raises a 400).

### Inferences
- The most upgrade-fragile piece is the post-call in-place rewrite. It writes into a response object the handler did not hand to the guardrail as an input. Chargeback correctness on post-call blocks depends on it (Q2, Q5).
- Since the chat handler copies a `"structured_messages"` key straight back into the request ([handler.py:184-198](/.venv/lib/python3.12/site-packages/litellm/llms/openai/chat/guardrail_translation/handler.py#L184)), returning a modified list as a way to *transform* input (rather than only block it) is a supported pattern, not a hack.

### Gaps
- I did not confirm whether `raise_passthrough_exception`, MCP modes or `streaming_buffer_until_moderated` for custom guardrails are documented on LiteLLM docs pages other than the [custom guardrail](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail) and [quick start](https://docs.litellm.ai/docs/proxy/guardrails/quick_start) pages.

## Q2. How is a block or a withhold returned for /chat/completions, Anthropic /v1/messages, the Responses API and streaming, and what does the agent see?

### Takeaway
On chat completions the agent always gets an HTTP 200 with the fixed refusal and `finish_reason: "content_filter"`.
Tool calls are stripped, and for post-call blocks the response keeps its real usage. On `/v1/messages` and
`/v1/responses` the post-call in-place rewrite cannot apply, because it only understands `.choices`. Every block there
goes through LiteLLM's generic passthrough. The Anthropic version reports `stop_reason: "end_turn"`, not a
refusal. The Responses version emits a non-standard output item and, on the code path I read, no SSE for a streaming
request. A flagged tool result (withhold) changes no status: the model still runs, on rewritten input.

### Cited Findings
**Decision logic (ours)**
- A flagged tool result is withheld only when *all* flagged entries are tool results. A flagged user message or tool definition, or any flagged tool call in post-call, leads to `_refuse` ([agentic_security.py:344-359](/deploy/agentic-security/agentic_security.py#L344)).
- A flagged user message beats a withholdable tool result ([tests/test_agentic_security.py:119-128](/tests/test_agentic_security.py#L119)).
- `_refuse` rewrites in place only when `input_type == "response"` and the request is not streaming. Otherwise it calls `raise_passthrough_exception` with `violation_message=refusal_message` and `detection_info={guard, hook, reason[:500]}` ([agentic_security.py:421-429](/deploy/agentic-security/agentic_security.py#L421)).
- The refusal text is "A security policy violation was detected, so this request was not completed." ([agentic_security.py:58](/deploy/agentic-security/agentic_security.py#L58)). The caller never sees the reason; it goes only to the gateway log ([agentic_security.py:353-356](/deploy/agentic-security/agentic_security.py#L353)).

**/chat/completions, non-streaming**
- **Pre-call block:** LiteLLM catches `ModifyResponseException` and calls `post_call_failure_hook`. It then builds a new `ModelResponse` with `content=e.message`, `finish_reason="content_filter"` and `usage=_blocked_response_usage(e.original_response)`, which is zero pre-call. It returns a plain 200 ([LL/proxy/proxy_server.py:11372-11410](/.venv/lib/python3.12/site-packages/litellm/proxy/proxy_server.py#L11372); usage helper [:11262-11275](/.venv/lib/python3.12/site-packages/litellm/proxy/proxy_server.py#L11262)).
- **Post-call block:** our in-place rewrite keeps the original response object, so its id, model and real usage stay. Content becomes the refusal, `tool_calls=None`, `function_call=None`, `finish_reason="content_filter"`, and the call completes as a success ([agentic_security.py:431-445](/deploy/agentic-security/agentic_security.py#L431); asserted in [tests/test_agentic_security.py:140-153](/tests/test_agentic_security.py#L140)).
- **End-to-end on chat:** the chargeback check fails a run unless blocked paths return `finish_reason == "content_filter"` with no tool calls or chunks ([evals/lab/chargeback_check.py:112-114](/evals/lab/chargeback_check.py#L112)).

**/chat/completions, streaming**
- **Pre-call block:** the same handler wraps the synthetic response in `ModelResponseIterator`/`CustomStreamWrapper` and returns an SSE `StreamingResponse` with status 200 ([proxy_server.py:11386-11407](/.venv/lib/python3.12/site-packages/litellm/proxy/proxy_server.py#L11386)).
- **Post-call:** with `streaming_buffer_until_moderated=True`, `end_of_stream_only` is forced on ([unified_guardrail.py:1033-1034](/.venv/lib/python3.12/site-packages/litellm/proxy/guardrails/guardrail_hooks/unified_guardrail/unified_guardrail.py#L1033)). The ended stream is rebuilt into a full `ModelResponse` and run through the non-streaming `process_output_response`, so tool calls are visible to the judge ([chat handler.py:642-678](/.venv/lib/python3.12/site-packages/litellm/llms/openai/chat/guardrail_translation/handler.py#L642)).
- On a streamed post-call block we raise passthrough. LiteLLM's `build_block_sse_chunks` emits a role+content chunk, then a final chunk with `finish_reason: "content_filter"` and the original call's usage ([chat handler.py:1284-1337](/.venv/lib/python3.12/site-packages/litellm/llms/openai/chat/guardrail_translation/handler.py#L1284)). The unified hook attaches `original_response` on post-call passthroughs ([unified_guardrail.py:366-373](/.venv/lib/python3.12/site-packages/litellm/proxy/guardrails/guardrail_hooks/unified_guardrail/unified_guardrail.py#L366)).

**Anthropic /v1/messages**
- **Pre-call:** request inputs are translated to OpenAI-format `structured_messages` (tool_result blocks become `role: tool`). Withholding is written back into Anthropic format ([anthropic handler.py:515-529, 663-677](/.venv/lib/python3.12/site-packages/litellm/llms/anthropic/chat/guardrail_translation/handler.py#L515)). This is tested through LiteLLM's real handler ([tests/test_agentic_security.py:183-200](/tests/test_agentic_security.py#L183)).
- **Post-call:** `request_data["response"]` holds an `AnthropicMessagesResponse` ([anthropic handler.py:1188-1194](/.venv/lib/python3.12/site-packages/litellm/llms/anthropic/chat/guardrail_translation/handler.py#L1188)), which has no `.choices`. `_refuse_in_place` therefore returns `None` and falls through to `raise_passthrough_exception` ([agentic_security.py:422-429, 434-436](/deploy/agentic-security/agentic_security.py#L422)).
- **Block body:** the endpoint returns 200 with `content=[{"type":"text","text": refusal}]`, `stop_reason="end_turn"` and usage from `original_response` ([LL/proxy/anthropic_endpoints/endpoints.py:157-201](/.venv/lib/python3.12/site-packages/litellm/proxy/anthropic_endpoints/endpoints.py#L157)).
- **Streamed block:** the `build_block_sse_chunks` path also ends with `stop_reason: "end_turn"` ([anthropic handler.py:390, 437](/.venv/lib/python3.12/site-packages/litellm/llms/anthropic/chat/guardrail_translation/handler.py#L390)).

**OpenAI Responses API**
- **Pre-call:** withholding is written back into `data["input"]` / `instructions` ([responses handler.py:491-497](/.venv/lib/python3.12/site-packages/litellm/llms/openai/responses/guardrail_translation/handler.py#L491)). This is tested ([tests/test_agentic_security.py:189-200](/tests/test_agentic_security.py#L189)).
- **Post-call:** `request_data["response"]` is a `ResponsesAPIResponse` ([responses handler.py:733-734](/.venv/lib/python3.12/site-packages/litellm/llms/openai/responses/guardrail_translation/handler.py#L733)), with no `.choices`, so this path also falls through to passthrough.
- **Block body:** the endpoint returns a `ResponsesAPIResponse` with `status="completed"` and `output=[{"content":[{"type":"text","text": violation}]}]`. That item has no `type: "message"`, no `role`, and uses `"text"` rather than `"output_text"`. The except-branch has no streaming branch: it returns this object even when `stream: true` ([LL/proxy/response_api_endpoints/endpoints.py:420-438](/.venv/lib/python3.12/site-packages/litellm/proxy/response_api_endpoints/endpoints.py#L420)).
- **Streamed post-call blocks** inside the unified hook use the Responses `build_block_sse_chunks`, which emits a full `response.created` … `response.completed` event sequence ([responses handler.py:1471-1500](/.venv/lib/python3.12/site-packages/litellm/llms/openai/responses/guardrail_translation/handler.py#L1471)).

**Withhold (any format)**
- The model runs on the rewritten input. A cut tool result shows `REMOVED_MARKER` where lines were cut; a whole-result withhold shows `REDACTION_MESSAGE` ([agentic_security.py:59-61, 69, 410-419](/deploy/agentic-security/agentic_security.py#L59)).
- The redaction text deliberately says "do not guess them … tell the user they were withheld", because "continue without it" made the model guess (comment at [agentic_security.py:61](/deploy/agentic-security/agentic_security.py#L61)).
- Nothing in the HTTP response tells the client that input was modified. The only record is a gateway warning per flagged entry with action `redacted (lines cut)` / `redacted (whole)` ([agentic_security.py:353-356](/deploy/agentic-security/agentic_security.py#L353)).

### Inferences
- **Anthropic and Responses post-call blocks** take the raise path that our chargeback doc measured as "recorded as a `failure` with $0" on chat ([docs/chargeback.md:51-55](/docs/chargeback.md#L51)). Their chargeback is therefore likely not intact. LiteLLM 1.103.2 now puts real usage in the response *body* through `original_response`, but that is not the spend log.
- **Clients on `/v1/messages`** cannot tell a guardrail refusal from a normal answer by `stop_reason`, because it is `end_turn`, not `refusal`.
- **The Responses block item's shape** may not parse in strict OpenAI SDK clients. This was not tested.

### Gaps
- **Untested formats:** no end-to-end test or eval in the repo exercises `/v1/messages` or `/v1/responses` blocks, or their chargeback. `chargeback_check.py` posts only to `/v1/chat/completions` ([evals/lab/chargeback_check.py:80-86](/evals/lab/chargeback_check.py#L80)). The agent eval uses chat completions with `stream=false` ([docs/agent-eval.md:70-72](/docs/agent-eval.md#L70)).
- **Anthropic streamed pre-call blocks:** I did not run them, so their exact SSE output is unconfirmed. The endpoint passes a single `AnthropicMessagesResponse` object to `async_sse_data_generator` ([anthropic endpoints.py:185-199](/.venv/lib/python3.12/site-packages/litellm/proxy/anthropic_endpoints/endpoints.py#L185)).

## Q3. How do agentic-security's own mechanisms work: post-call only on tool calls, the 10-message window, surgical withholding, fail-open with a deadline, hedging and chargeback?

### Takeaway
All of these are our code, built on the unified hook. Post-call returns at once unless the reply has tool calls. The
window is the last 10 non-system messages, extended to cover every new user message. One pre-call judge call rates the
new user turn, every tool result in the window, and tool definitions on a new user turn. Each hook has
`asyncio.wait_for(deadline_s)` and fails open by default. The first-pass call is hedged at 2.5 s, and the slower call
is left running so it still bills. Judge calls go through the gateway router with the caller's identity in metadata.

### Cited Findings
**Post-call only on tool calls**
- `_judge` returns `(None, [])` when `inputs["tool_calls"]` is empty, with the comment "plain-text replies are not judged" ([agentic_security.py:380-382](/deploy/agentic-security/agentic_security.py#L380)). A test confirms zero judge calls for a plain-text reply ([tests/test_agentic_security.py:143-144](/tests/test_agentic_security.py#L143)).
- LiteLLM does call the hook for tool-call-only replies, because `_has_text_content` returns True for a non-empty `tool_calls` ([chat handler.py:906-934](/.venv/lib/python3.12/site-packages/litellm/llms/openai/chat/guardrail_translation/handler.py#L906)).
- This skip is OURS. LiteLLM still invokes post-call on every response.

**Window**
- `request_lines` keeps non-system/developer messages and starts at `min(last-window start, first message after the last assistant turn)` ([agentic_security.py:127-151](/deploy/agentic-security/agentic_security.py#L127)).
- **Rated entries:** user messages after the last assistant turn; every tool result in the window, re-rated each request; tool definitions only when a new user turn starts ([agentic_security.py:140-150](/deploy/agentic-security/agentic_security.py#L140)).
- **Context-only entries:** assistant text and tool calls ([agentic_security.py:143-146](/deploy/agentic-security/agentic_security.py#L143)).
- Tool results without text parts are serialized and rated, never skipped ([agentic_security.py:147-149](/deploy/agentic-security/agentic_security.py#L147); test [:203-207](/tests/test_agentic_security.py#L203)).
- **The system prompt is excluded** unless `include_system_prompt: true` ([agentic_security.py:131-132, 151](/deploy/agentic-security/agentic_security.py#L131); test [:83-94](/tests/test_agentic_security.py#L83)).
- **Clipping:** context messages are clipped to 1,500 chars, judged entries to 24,000, the system prompt to 8,000. All of it is JSON-escaped with `<`/`>` escaped so content cannot forge tags ([agentic_security.py:63-65, 119-124, 186-203](/deploy/agentic-security/agentic_security.py#L63)).
- **Post-call context** is built from `request_data.get("messages")` ([agentic_security.py:383-385](/deploy/agentic-security/agentic_security.py#L383)), not from LiteLLM's OpenAI-normalized `structured_messages`.

**Judge and scoring**
- One first-pass call returns an "n:digit" per entry. 7-9 flags. Request-side 4-6 (or an unparseable digit) goes to one review call; tool calls send every 4-9 to review. The review returns JSON `{"reasoning","violating"}` ([agentic_security.py:228-286](/deploy/agentic-security/agentic_security.py#L228)).
- **Reasoning effort:** none for the first pass, low for review, none for locate ([agentic_security.py:232-239, 245, 278-280](/deploy/agentic-security/agentic_security.py#L232)).

**Surgical withholding**
- Each flagged result is split into lines, with lines over 400 chars split into sentences. One locate call over the cached first-pass conversation returns segment numbers (strict JSON schema). Each cut run is replaced by one marker ([agentic_security.py:70-79, 163-183, 288-308](/deploy/agentic-security/agentic_security.py#L70)).
- **Fallback to withholding the whole result** when:
  - the result is over 24,000 chars or has only one segment;
  - the locate call fails, times out or finds nothing;
  - it would cut more than 80% (`MAX_CUT_SHARE=0.8`).

  ([agentic_security.py:71, 292-307, 346-352](/deploy/agentic-security/agentic_security.py#L292); tests [:244-264](/tests/test_agentic_security.py#L244))
- **Statelessness:** the client resends the original tool result each turn, and it is re-rated and re-cut each time ([agentic_security.py:30-37](/deploy/agentic-security/agentic_security.py#L30); test [:107-116](/tests/test_agentic_security.py#L107)).

**Fail-open and deadline**
- `asyncio.wait_for(self._judge(...), self.deadline_s)` wraps the whole hook. Any exception (judge down, timeout, mapping bug) logs `"%s %s: guard failed (...); on_unavailable=%s"`. It then returns `inputs` unchanged (`allow`, the default) or refuses (`block`) ([agentic_security.py:333-341](/deploy/agentic-security/agentic_security.py#L333)). `on_unavailable` is validated to allow|block ([:319-320](/deploy/agentic-security/agentic_security.py#L319)). Tests: [:169-180](/tests/test_agentic_security.py#L169).
- **Timeouts:** each judge call has `timeout=judge_timeout_s` (default 8 s) and `num_retries=0`. One retry happens only on a BadRequest that names an output limit ([agentic_security.py:395-406](/deploy/agentic-security/agentic_security.py#L395)).
- **Locate time budget:** the locate call gets the remaining deadline, at least 0.5 s ([agentic_security.py:348-349](/deploy/agentic-security/agentic_security.py#L348)).
- **Defaults:** `deadline_s=10`, `judge_timeout_s=8`, `hedge_s=2.5` ([agentic_security.py:313-317](/deploy/agentic-security/agentic_security.py#L313); [README.md:54-66](/deploy/agentic-security/README.md#L54)).

**Hedging (OURS)**
- If the first pass has not answered within `hedge_s`, an identical second call is started and the first success wins. The slower task is not cancelled; a done-callback consumes its result so it completes and is billed ([agentic_security.py:241-263](/deploy/agentic-security/agentic_security.py#L241); test [:210-236](/tests/test_agentic_security.py#L210)).
- Only the first-pass call is hedged; the review and locate calls are not ([agentic_security.py:276-301](/deploy/agentic-security/agentic_security.py#L276)).

**Chargeback**
- **Identity:** `_meta` takes metadata only from the dict that holds an actual `UserAPIKeyAuth` instance, so a client JSON body cannot create it. It copies only `user_api_key*` scalar fields and adds tags `guardrail_stage:pre_call|post_call` and `guardrail:<name>` ([agentic_security.py:361-372](/deploy/agentic-security/agentic_security.py#L361); tests [:156-166, 276-289](/tests/test_agentic_security.py#L156)).
- **Routing:** the judge call goes through `llm_router.acompletion(... metadata=meta ...)`, using the same `model_list` deployment as inference ([agentic_security.py:388-401](/deploy/agentic-security/agentic_security.py#L388)).

**Audit**
- There is one warning per flagged entry with the guard, hook, kind, action, digits and a 12-hex sha256 of the content. Content is never logged ([agentic_security.py:353-356](/deploy/agentic-security/agentic_security.py#L353)).

### Inferences
- **LiteLLM sees fail-opens and withholds as normal successes.** `apply_guardrail` returns normally in both cases. LiteLLM's `litellm_guardrail_latency_seconds` metric records status `"success"` for any hook that does not raise, and `"error"` for one that does, including a `ModifyResponseException` block ([LL/proxy/utils.py:2538-2572](/.venv/lib/python3.12/site-packages/litellm/proxy/utils.py#L2538)). Fail-opens, withholds and post-call in-place refusals therefore all count as "success" in LiteLLM's metrics. The only signal is our gateway warning lines.
- **Post-call context is thin on Anthropic and Responses requests.** `content_text` reads only `text` parts and assistant `tool_calls` ([agentic_security.py:96-108, 146](/deploy/agentic-security/agentic_security.py#L96)). On `/v1/messages`, Anthropic `tool_use` / `tool_result` blocks and the top-level `system` are not shown to the judge. On `/v1/responses`, which carries `input` rather than `messages` (see the test fixture at [tests/test_agentic_security.py:189-192](/tests/test_agentic_security.py#L189)), the post-call judge likely sees no conversation at all. The pre-call side is unaffected because it uses LiteLLM's normalized `structured_messages`.

### Gaps
- **Built-in timeout:** I did not check whether LiteLLM 1.103.2 has its own per-guardrail timeout that could interact with `deadline_s`.
- **Responses post-call context:** I did not trace whether the proxy adds a `messages` key to Responses API request data before post-call, so "empty context" is unconfirmed.

## Q4. How do the lab integration (LabGuardrail) and gateway/litellm_config.yaml differ, including `on_block: error|refuse`?

### Takeaway
LabGuardrail is the same LiteLLM pattern: an `apply_guardrail` override, the passthrough 200 or an in-place post-call
rewrite, and the `streaming_buffer_until_moderated` attribute. It adds `on_block: error`, which raises LiteLLM's
`GuardrailRaisedException` (HTTP 400, reason in the message), and MCP hooks. It also keeps per-process state: an LRU
verdict cache plus single-flight. It splits each request into per-piece cases instead of one windowed call. Its
billing-identity code is weaker: it merges client-supplied `metadata`.

### Cited Findings
**on_block**
- `refuse` (the default) uses the same in-place post-call rewrite as agentic-security, otherwise `raise_passthrough_exception` ([src/guardlab/litellm_guardrail.py:147-177](/src/guardlab/litellm_guardrail.py#L147)).
- `error` raises `GuardrailRaisedException(guardrail_name, message=f"Blocked by {guard_id} ({input_type}): {reason}", should_wrap_with_default_message=False, blocked_content=True)` ([litellm_guardrail.py:157-159](/src/guardlab/litellm_guardrail.py#L157)). The status code is 400 by default ([LL/exceptions.py:1074-1097](/.venv/lib/python3.12/site-packages/litellm/exceptions.py#L1074)), which makes this STANDARD. The 400 carries the judge's reason to the caller.
- Values are validated to error|refuse ([litellm_guardrail.py:102-103](/src/guardlab/litellm_guardrail.py#L102)).
- **Tests:** a 400 naming the guard ([tests/test_lab_guardrail.py:31-39](/tests/test_lab_guardrail.py#L31)); a refuse-mode 200 that does not leak the reason ([:169-176](/tests/test_lab_guardrail.py#L169)); the in-place post-call rewrite ([:181-191](/tests/test_lab_guardrail.py#L181)); a streamed post-call ending the stream ([:194](/tests/test_lab_guardrail.py#L194)); buffering on by default ([:206-208](/tests/test_lab_guardrail.py#L206)); refuse as the default ([:211-212](/tests/test_lab_guardrail.py#L211)).

**Refusal construction**
- The refusal text is the same as agentic-security's ([litellm_guardrail.py:51](/src/guardlab/litellm_guardrail.py#L51)).
- Post-call non-stream: content is the refusal, `tool_calls=None`, `function_call=None`, `finish_reason="content_filter"`, `texts=[refusal]` ([litellm_guardrail.py:161-177](/src/guardlab/litellm_guardrail.py#L161)).
- Otherwise it uses the passthrough with `detection_info={guard, hook, reason[:500]}` ([:155-156](/src/guardlab/litellm_guardrail.py#L155)).

**Case mapping (OURS)**
- **Request:** each new user message (stage `input`); each new tool result; the last few user turns (`conversation`); every tool definition. **Response:** reply text (`output`, with the system prompt) and each tool call, with the system prompt, the user request and trajectory history from `task_context` ([litellm_guardrail.py:60-92](/src/guardlab/litellm_guardrail.py#L60)).
- **MCP:** a call becomes the case `tool(args)` plus the tool definitions; an MCP response becomes the case `tool_result` ([litellm_guardrail.py:62-70](/src/guardlab/litellm_guardrail.py#L62)). It reads `mcp_tool_name` and `mcp_arguments`/`arguments`, which are the fields LiteLLM's MCP translation handler reads ([LL/proxy/_experimental/mcp_server/guardrail_translation/handler.py:125-126](/.venv/lib/python3.12/site-packages/litellm/proxy/_experimental/mcp_server/guardrail_translation/handler.py#L125)).
- **Filters:** `stages` filters cases, so omitting `output` skips plain-text replies. `skip_tools` is an exact-name list ([litellm_guardrail.py:178-182, 99-109](/src/guardlab/litellm_guardrail.py#L178)).

**State (OURS; violates the drop-in "no cache/state" constraint)**
- An LRU of OK verdicts (`VERDICT_CACHE_SIZE=4096`) plus single-flight in-flight tasks, shielded from per-request deadlines ([litellm_guardrail.py:52, 111-112, 192-210](/src/guardlab/litellm_guardrail.py#L192)).

**Fail mode**
- The class default is `on_unavailable="block"` and `deadline_s=None`, so there is no deadline unless one is configured ([litellm_guardrail.py:96-107](/src/guardlab/litellm_guardrail.py#L96)).
- Per-case `unavailable`/`error` results are logged as `guard failed on <stage>` and blocked only if `on_unavailable: block` ([:131-144](/src/guardlab/litellm_guardrail.py#L131)).

**Chargeback**
- `_run` merges `{**litellm_metadata, **metadata}`, so client `metadata` wins. It copies `user_api_key*` into a ContextVar `CALLER` ([litellm_guardrail.py:183-190](/src/guardlab/litellm_guardrail.py#L183); [src/guardlab/types.py:52](/src/guardlab/types.py#L52)).
- The judge adapter calls `llm_router.acompletion(... metadata=..., num_retries=0)`. It maps Timeout, RateLimit, Connection and 5xx errors to `Unavailable` ([src/guardlab/adapters/llm_judge.py:150-181](/src/guardlab/adapters/llm_judge.py#L150)).
- The repo itself flags the metadata merge: "The lab's `LabGuardrail` … still merges both metadata fields; it is lab-only, but should get the same fix if it is ever deployed" ([docs/chargeback.md:44-47](/docs/chargeback.md#L44)).

**Gateway config entries** ([gateway/litellm_config.yaml:31-122](/gateway/litellm_config.yaml#L31))
- `s1guard`: [pre_call, post_call, pre_mcp_call, post_mcp_call].
- `cyber-guard-per-policy`: all four modes, `on_unavailable: block`, `on_block: error`. Lab only; it calls OpenAI directly, so it is not charged back.
- `cyber-guard-per-policy-gw`: all four modes, block, `refuse`.
- `cyber-guard-gw`: all four modes, block, `refuse`. It has no `deadline_s`, so there is no deadline. Its `on_block: refuse` sits at line 68, below a misplaced comment block (lines 64-67) that describes the next entry.
- `cyber-guard`: [pre_call, post_call], allow, `deadline_s: 10`, refuse, `stages` without `output`, `skip_tools: []`. This is the recommended lab placement.
- `cyber-guard-pre`: [pre_call] only.
- `agentic-security` / `agentic-security-sys`: [pre_call, post_call], allow, `deadline_s: 10`, window 10, `include_system_prompt` false/true.
- `dec-luna-emu`: all four modes, block, error. Lab only.
- `gateway/start_gateway.sh` puts `deploy/agentic-security` on `PYTHONPATH` ([gateway/start_gateway.sh:10](/gateway/start_gateway.sh#L10)).

### Inferences
- `on_block: error` exposes the judge's reason to the caller in the 400 body. The repo's own docs give hiding the reason as a reason to prefer refuse ("so the guard can't be used as an oracle", [docs/guardrail-placement.md:99-100](/docs/guardrail-placement.md#L99)).
- Leaving the LabGuardrail default `deadline_s=None` in a deployed entry would let a hung judge stall inference until the judge's own transport timeout.

### Gaps
- I did not audit `src/s1guard/litellm_guardrail.py` (the `s1guard` entry) beyond its config line.

## Q5. What measured evidence backs the design choices?

### Takeaway
There is measured evidence for most choices:
- **during_call:** $0 recorded for blocked inference.
- **Post-call refusal:** rewriting in place keeps the inference billed; raising records a $0 failure.
- **Withholding:** cutting injected lines instead of refusing lifted task success under attack from 6% (cyber-guard) or 20% (whole withholding) to 56-58%.
- **Placement:** pre-call stops 87% of injections but only 2-6% of drift.
- **Latency:** hedging cuts the pre-call p95 from 3.52 s to 2.60 s.

The claim that "200 vs 400 made no difference" compares a native 200 refusal with a 400 that the eval shim *converted into a
refusal*. It does not test how an agent handles a raw 400. All loop and chargeback evidence is on `/v1/chat/completions`.

### Cited Findings
**during_call loses inference cost (LiteLLM 1.103.2, 2026-10-05, Postgres spend DB)**
- A blocked non-streaming `during_call` ran about 2.7 s before cancellation and recorded **$0, 0 tokens**. Streaming ran about 1.8 s and also recorded $0. An allowed `during_call` recorded $0.000602 (1,200 tokens) ([docs/guardrail-placement.md:17-35](/docs/guardrail-placement.md#L17)).
- The cause is in LiteLLM's code: `_cancel_pending_gather_tasks` runs on the gathered moderation and LLM tasks ([LL/proxy/common_request_processing.py:442, 2539-2547](/.venv/lib/python3.12/site-packages/litellm/proxy/common_request_processing.py#L2539)).

**Post-call raise vs rewrite (billing)**
- "Raising at post-call, as a 400 or as LiteLLM's passthrough 200, records the inference as a `failure` with $0, although the provider charged for it" ([docs/chargeback.md:51-55](/docs/chargeback.md#L51)).
- **agentic-security: "CHARGEBACK OK on all seven paths"** (2026-10-07). The paths include a withheld tool result, a result with lines cut, and hedged calls ([docs/chargeback.md:37-42](/docs/chargeback.md#L37)).
- The check requires key spend = the sum of its rows, and team spend = the sum over its keys ([docs/chargeback.md:24-35](/docs/chargeback.md#L24)).
- **Streamed post-call block:** "inference success + judge calls … no tool-call chunk reaches the client" ([docs/chargeback.md:27-33](/docs/chargeback.md#L27)).

**200 vs 400 and task completion (cyber-guard, 2026-10-05)**
- "Returning a 200 refusal instead of a 400 doesn't change that, because the agent stops either way. Only redacting the flagged tool result and letting the agent continue would." ([README.md:334-337](/README.md#L334)).
- **Run 20261005-073721-full** (400s converted by the shim), AgentDojo attacks utility: baseline 74%, pre-call 6%, cyber-guard 6%; benign: 81 / 65 / 65%; AgentThreatBench: 79 / 12 / 21%; 0 fail-opens.
- **Run 20261005-081614-full** (native 200s): attacks 75 / 6 / 6%; benign 79 / 66 / 66%; ATB 71 / 12 / 12%; 1 fail-open, flagged in the summary as invalidating the guarded arms' attack-success numbers ([evals/results/agent/20261005-073721-full/summary.md](/evals/results/agent/20261005-073721-full/summary.md); [evals/results/agent/20261005-081614-full/summary.md](/evals/results/agent/20261005-081614-full/summary.md); [docs/agent-eval.md:99-103](/docs/agent-eval.md#L99)).
- **Caveat:** in the "400" run the agent never saw a 400. The shim turns a 400 `Blocked by …` into a 200 refusal with `finish_reason: "content_filter"` ([evals/agent/shim.py:96-100](/evals/agent/shim.py#L96); [docs/agent-eval.md:63-68](/docs/agent-eval.md#L63)).

**Withholding restores task success (2026-10-07, clean rerun `20261007-183106-full`, gpt-6-luna agent, 4 agents per arm, 0 fail-opens)** ([docs/agentic-security.md:196-204](/docs/agentic-security.md#L196))

| Arm | Under attack | Benign | ATB | Attack success (AgentDojo / ATB) | Judge calls/agent call | Judge $/1k agent calls |
|---|---|---|---|---|---|---|
| none | 73% | 78% | 79% | 0% / 8% | — | — |
| cyber-guard | 6% | 61% | 12% | 0% / 0% | 1.51 | $0.11 |
| agentic-security | 56% | 70% | 46% | 0% / 8% | 2.11 | $0.41 |
| agentic-security + system prompt | 49% | 68% | 50% | 0% / 12% | 2.11 | $0.45 |

- **Earlier run:** whole withholding scored 20% under attack versus 58% surgical. Of 477 withheld results, 268 had only their injected lines cut and 209 were withheld whole. Surgical costs about 0.36 more judge calls per agent call ([docs/agentic-security.md:188-194, 218-221](/docs/agentic-security.md#L188)).
- **Why whole withholding failed:** in 76 of 77 failed tasks, the withheld result was the one the task needed ([docs/agentic-security.md:230-232](/docs/agentic-security.md#L230)).
- **Request latency** (p50/p95): none 2.3/5.7 s; cyber-guard 2.8/5.6 s; agentic-security 4.4/9.4 s ([docs/agentic-security.md:215-216](/docs/agentic-security.md#L215)).
- **Protection with a weaker agent** (gemma4:e2b, 12 AgentDojo samples, all banking, plus 24 ATB tasks): AgentDojo attack success fell from 42% (5/12) to 0%, and ATB from 4% to 0%. Task success under attack rose from 25% to 42%. There were 22 cuts and 12 tool calls blocked ([docs/agentic-security.md:236-263](/docs/agentic-security.md#L236)).

**Surgical locate quality (116 dev tool-result attacks)**
- 105 were flagged. 93% of the multi-segment ones were cut surgically.
- A median of 87% of the text was kept.
- 77 of 78 cut results passed a fresh check.
- The locate call took 1.0 s p50 / 1.4 s p95 ([docs/agentic-security.md:170-180](/docs/agentic-security.md#L170)).

**Placement: pre-call vs action check** (1,169 toolcall-guard-v1 trajectories) ([docs/guardrail-placement.md:37-70](/docs/guardrail-placement.md#L37))
- **Injection in tool output** (n=112): pre-call stops 87%, the action check 79%.
- **Intent deviation** (n=411): pre-call 2%, the action check 81%.
- **Subtle drift** (n=272): pre-call 6%, the action check 78%.
- **False blocks:** 10-12% for the action check. Pre-call flagged 16% of safe trajectories with tool output, most of them containing real third-party instructions.

**Post-call only on tool calls**
- The justification is structural: plain replies skip the judge. Each tool-calling step adds about 0.7 s p50 for safe calls, and about 13% of safe calls plus all first-pass flags get an extra review of about 3 s ([docs/guardrail-placement.md:120-125](/docs/guardrail-placement.md#L120)).
- In the 2026-10-05 run, "Post-call added 3 blocks and no extra protection here, because pre-call stopped the attacks first" ([README.md:341](/README.md#L341)).
- **Review band trade-off** (tool-call dev slice: 154 unsafe, 86 legitimate):

  | Review band | Caught | Legit blocked | F1 | p50 / p95 |
  |---|---|---|---|---|
  | 4-9 low effort (kept) | 86% | 1.2% | 0.920 | 3.2 / 5.7 s |
  | 4-6 only | 88% | 7.0% | 0.915 | 1.1 / 3.2 s |

  ([docs/agentic-security.md:157-168](/docs/agentic-security.md#L157))

**Latency and hedging** (180 replayed AgentDojo requests; classifier time only) ([docs/agentic-security.md:140-155](/docs/agentic-security.md#L140))
- Pre-call p50/p95 went from 1.18/3.52 s to 1.35/2.60 s with hedging.
- Pre+post per step p99 went from 14.3 s to 8.3 s.
- The pre-call worst case went from 17 s to 3.2 s, for about 6% more calls.
- Pre-call prompt size was 4.4k tokens versus 50k for cyber-guard without its cache. cyber-guard without a cache made 20 judge calls (up to 36) per pre-call.

**Single-message accuracy** (agentic-security vs cyber-guard, F1) ([docs/agentic-security.md:73-86](/docs/agentic-security.md#L73))
- rep-test: 0.93 vs 0.92.
- cyber-test: 0.93 vs 0.95.
- Public benchmarks: 0.87 vs 0.86.
- Tool calls: 0.92 vs 0.93.

**Fail-open verification**
- Fail-open was verified live with a judge over budget and with a missing guard ID: both requests returned the model's answer ([docs/guardrail-placement.md:104-108](/docs/guardrail-placement.md#L104)).
- A shared rate limit once caused 16,659 fail-opens, in an earlier cyber-guard run that predates the cache ([docs/guardrail-placement.md:110-115](/docs/guardrail-placement.md#L110)).
- A slow-agent surgical run had 34 of about 1,600 checks (2%) fail open on the 10 s deadline ([docs/agentic-security.md:222-226](/docs/agentic-security.md#L222)).

### Inferences
- The 200-vs-400 conclusion holds for "refuse the turn vs refuse the turn". It does not show how real agent frameworks treat a raw HTTP 400: they may retry, raise, or surface an error. The evidence for preferring 200 is therefore billing (measured) plus convention (argued in [docs/guardrail-placement.md:94-102](/docs/guardrail-placement.md#L94)), not task completion.
- The withholding gains were measured with a gpt-6-luna agent that resisted all AgentDojo attacks even without a guardrail ([docs/agentic-security.md:206-209, 227-229](/docs/agentic-security.md#L206)). The protection evidence rests on the small Gemma run.

### Gaps
- There is no measured evidence for streaming agents, for `/v1/messages` or `/v1/responses` clients, or for MCP-executed tools.
- The 2026-10-05 200/400 comparison used cyber-guard, not agentic-security.

## Q6. What gaps and risks are visible in the code?

### Takeaway
The main risks are:
- **Format coverage:** the post-call in-place rewrite works only for chat completions. Anthropic and Responses fall back to a passthrough that is likely unbilled and has odd stop/output shapes.
- **Upgrade fragility:** several LiteLLM internals are load-bearing.
- **LiteLLM-executed MCP tools:** their results may never pass a pre-call.
- **Observability:** fail-opens and withholds look like successes to LiteLLM.
- **Known stateless-design limits:** scroll-out, tool changes mid-turn, the 24k clip.

### Cited Findings
**1. Anthropic and Responses post-call**
- `_refuse_in_place` requires `.choices` ([agentic_security.py:434-436](/deploy/agentic-security/agentic_security.py#L434)). Anthropic and Responses responses lack them (Q2), so blocks go through passthrough.
- Anthropic then reports `stop_reason: "end_turn"` ([LL/proxy/anthropic_endpoints/endpoints.py:181](/.venv/lib/python3.12/site-packages/litellm/proxy/anthropic_endpoints/endpoints.py#L181)).
- Responses returns a non-streaming body even for `stream: true` pre-call blocks ([LL/proxy/response_api_endpoints/endpoints.py:420-438](/.venv/lib/python3.12/site-packages/litellm/proxy/response_api_endpoints/endpoints.py#L420)).
- Only chat is end-to-end tested ([evals/lab/chargeback_check.py:80-86](/evals/lab/chargeback_check.py#L80)).

**2. Post-call judge context on non-chat formats**
- It is built from raw `request_data["messages"]` ([agentic_security.py:383](/deploy/agentic-security/agentic_security.py#L383)), so Anthropic tool blocks and the system prompt are not shown, and Responses `input` is not read (Q3).

**3. MCP hooks unused**
- With `[pre_call, post_call]`, tool results from MCP tools that **LiteLLM itself executes** are not covered. In the Responses-API `litellm_proxy` MCP flow, results go through `post_mcp_call_hook` ([LL/responses/mcp/litellm_proxy_mcp_handler.py:859-868](/.venv/lib/python3.12/site-packages/litellm/responses/mcp/litellm_proxy_mcp_handler.py#L859)). They are then fed to an internal SDK `aresponses` follow-up ([:1100-1108](/.venv/lib/python3.12/site-packages/litellm/responses/mcp/litellm_proxy_mcp_handler.py#L1100); import comment at [:19](/.venv/lib/python3.12/site-packages/litellm/responses/mcp/litellm_proxy_mcp_handler.py#L19)), not a new proxy request.
- The repo's "MCP hooks redundant" reasoning assumes "every tool result goes back through the gateway" ([docs/guardrail-placement.md:65-66](/docs/guardrail-placement.md#L65)).

**4. Images ignored**
- agentic-security never reads `inputs["images"]`, although LiteLLM passes them ([chat handler.py:140-141](/.venv/lib/python3.12/site-packages/litellm/llms/openai/chat/guardrail_translation/handler.py#L140); grep shows no `images` in [agentic_security.py](/deploy/agentic-security/agentic_security.py)).

**5. Global skip settings**
- If an operator sets `litellm.skip_tool_message_in_guardrail` or `skip_system_message_in_guardrail` (globally or per guardrail), tool results or the system prompt are removed from `structured_messages` before our hook sees them ([LL/llms/base_llm/guardrail_translation/utils.py:194-209, 248-258](/.venv/lib/python3.12/site-packages/litellm/llms/base_llm/guardrail_translation/utils.py#L194)). Injection screening would then be silently off.

**6. Observability of fail-open**
- Fail-open returns `inputs` with only a `verbose_proxy_logger.warning` ([agentic_security.py:336-340](/deploy/agentic-security/agentic_security.py#L336)). LiteLLM's guardrail metric marks it "success" ([LL/proxy/utils.py:2552-2572](/.venv/lib/python3.12/site-packages/litellm/proxy/utils.py#L2552)).
- The docs ask operators to alert on `guard failed` in the gateway log ([docs/guardrail-placement.md:114-115](/docs/guardrail-placement.md#L114)).
- In-place post-call refusals and withholds are also invisible to LiteLLM's guardrail status. They are not recorded as interventions; `is_guardrail_intervention` only classifies exceptions ([LL/integrations/custom_guardrail.py:74-90](/.venv/lib/python3.12/site-packages/litellm/integrations/custom_guardrail.py#L74)).

**7. Shared rate limit**
- The judge uses the same deployment and quota as inference ([gateway/litellm_config.yaml:18-20](/gateway/litellm_config.yaml#L18)), and fail-open under load has been observed (Q5).

**8. Documented stateless limits**
- **Scroll-out:** a flagged tool result older than the window reaches the model again.
- **Tool changes:** tool definitions changed within a user turn are not re-checked.
- **Long entries:** entries over 24k chars are clipped and withheld whole.
- **Delegation:** delegation false-withholds remain.

  ([docs/agentic-security.md:265-273](/docs/agentic-security.md#L265))

**9. Residual risks the repo itself documents**
- Final text replies are unchecked.
- The action check is "a filter, not a boundary": about 80% recall with 10-12% false blocks.
- "Autonomy hijack" drift in tool results is missed: ATB ah_001 and ah_003 succeeded against agentic-security.

  ([docs/guardrail-placement.md:151-161](/docs/guardrail-placement.md#L151); [docs/agentic-security.md:210-214](/docs/agentic-security.md#L210))

**10. Upgrade fragility (INTERNAL dependencies)**
- `request_data["response"]` mutation together with the tool-call write-back's `None` guard ([chat handler.py:437-442, 1075](/.venv/lib/python3.12/site-packages/litellm/llms/openai/chat/guardrail_translation/handler.py#L437)).
- The `streaming_buffer_until_moderated` attribute lookup ([unified_guardrail.py:962-968](/.venv/lib/python3.12/site-packages/litellm/proxy/guardrails/guardrail_hooks/unified_guardrail/unified_guardrail.py#L962)).
- The `litellm.proxy.proxy_server.llm_router` global.
- The `metadata.user_api_key_*` / `tags` spend-attribution convention ([spend_tracking_utils.py:554-580, 783-791](/.venv/lib/python3.12/site-packages/litellm/proxy/spend_tracking/spend_tracking_utils.py#L554)).
- The `UserAPIKeyAuth` object in the metadata bucket ([litellm_pre_call_utils.py:1674](/.venv/lib/python3.12/site-packages/litellm/proxy/litellm_pre_call_utils.py#L1674)).
- Dispatch by `"apply_guardrail" in type(callback).__dict__` ([LL/proxy/utils.py:1668-1676](/.venv/lib/python3.12/site-packages/litellm/proxy/utils.py#L1668)).

**11. Stale doc lines**
- docs/guardrail-placement.md still lists "A softer option, not yet implemented, is to replace the flagged tool result with a notice" ([docs/guardrail-placement.md:156-158](/docs/guardrail-placement.md#L156)). agentic-security implements exactly that.
- docs/chargeback.md cites a 20 s judge timeout ([docs/chargeback.md:70-71](/docs/chargeback.md#L70)). agentic-security uses 8 s ([agentic_security.py:314](/deploy/agentic-security/agentic_security.py#L314)).

**12. LabGuardrail-specific**
- It merges client metadata ([src/guardlab/litellm_guardrail.py:183](/src/guardlab/litellm_guardrail.py#L183)).
- `on_block: error` leaks the reason ([:158](/src/guardlab/litellm_guardrail.py#L158)).
- It has no deadline by default ([:107](/src/guardlab/litellm_guardrail.py#L107)), and `cyber-guard-gw` sets none ([gateway/litellm_config.yaml:57-68](/gateway/litellm_config.yaml#L57)).
- It keeps an in-process verdict cache ([:111, 192-210](/src/guardlab/litellm_guardrail.py#L192)).

### Inferences
- **Chat-completions agents** (the tested path) behave as documented. Teams whose agents use Anthropic `/v1/messages` (e.g. Claude-based coding agents) or the Responses API are exposed to findings 1-3: likely $0 post-call billing, `end_turn` refusals, and a thinner post-call context.
- **Recursion through deployment guardrails:** if an operator attaches guardrails to the judge model's deployment in `model_list` (deployment-level guardrails), the deployment hook may apply them to judge calls. Our code does nothing to prevent that. This is unverified; see Gaps.

### Gaps
- **Not run against a live gateway in this audit:** `/v1/messages` and `/v1/responses` post-call blocks, their spend rows, the Responses `stream: true` pre-call block, and whether LiteLLM-executed MCP results bypass pre-call. The findings above come from reading the source.
- **Deployment-level guardrails on the judge model:** I did not verify whether guardrails attached to the judge model's `model_list` entry would run on judge calls.

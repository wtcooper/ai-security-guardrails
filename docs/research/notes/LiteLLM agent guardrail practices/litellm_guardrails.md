# LiteLLM's guardrail framework and its guidance for agentic tool-calling loops (state as of 2026-10-08)

Method note: sources are (a) the PyPI JSON API and GitHub releases API, pulled 2026-10-08; (b) the official docs, which now live in a separate repo, BerriAI/litellm-docs, shallow-cloned at commit `1b533f8` (2026-10-08 02:58 PDT) and served at docs.litellm.ai (each URL cited below returned HTTP 200 on 2026-10-08); (c) source code: the locally installed litellm 1.103.2 (`.venv/lib/python3.12/site-packages/litellm/`) and the litellm 1.104.2 wheel (macOS arm64) downloaded to scratch and diffed against it. Source-code links point at tag `v1.104.2`. Local 1.103.2 line numbers are given where they differ. "DOC" means the claim is documented. "SRC" means it was seen only in source code.

## Q0. Which LiteLLM release is latest, and is the repo's 1.103.2 current?

### Takeaway
The latest stable release is **litellm 1.104.2**, uploaded to PyPI 2026-10-08 08:34 UTC and marked "Latest" on GitHub. The repo's 1.103.2 (2026-10-01) is one minor line behind, and its own line has since gained 1.103.3 and 1.103.4. The core guardrail framework (`CustomGuardrail`, `apply_guardrail`, the exceptions, the hook enum) is essentially identical between 1.103.2 and 1.104.2. The visible guardrail differences are the opt-in `include_guardrail_response` field, the new `/v1/decisions` endpoint, a Straiker v3 rewrite and ~20 guardrail fixes listed in the v1.104.0 notes.

### Cited Findings
- PyPI `info.version` = `1.104.2`, uploaded 2026-10-08T08:34:44Z, `requires_python >=3.10,<3.15`. Recent uploads on several parallel lines: 1.104.0 (2026-10-03), 1.104.1 (2026-10-07), 1.104.2 (2026-10-08), plus backports 1.103.3 (2026-10-03), 1.103.4 (2026-10-07), 1.102.4 and 1.101.6 (2026-10-08). Pre-releases: 1.105.0rc3 (2026-10-08 09:19) and 1.106.0.dev2 (2026-10-08 07:15) — [PyPI JSON](https://pypi.org/pypi/litellm/json)
- 1.103.2 was uploaded 2026-10-01T06:20:45Z. The local `.venv` holds `litellm-1.103.2.dist-info`, `litellm_enterprise-0.1.69.post1` and `litellm_proxy_extras-0.4.100` — [PyPI JSON](https://pypi.org/pypi/litellm/json); local site-packages listing
- GitHub marks `v1.104.2` "Latest" (published 2026-10-08T08:39:07Z). `v1.105.0-rc.3` and `v1.106.0-dev.2` are pre-releases — [GitHub releases](https://github.com/BerriAI/litellm/releases)
- The v1.104.2 notes contain one change: a backport of `/v1/systemone`, the OpenAI-format `/v1/decisions` and the OpenAI Decisions provider (PR #45190, merged 2026-10-08T05:28Z). It also carries a guardrail fix so OpenAI-format Decisions responses keep `guardrail_information` when `include_guardrail_response` is set — [v1.104.2 release](https://github.com/BerriAI/litellm/releases/tag/v1.104.2); [PR #45190](https://github.com/BerriAI/litellm/pull/45190)
- Release dates: v1.104.0 2026-10-03, v1.103.0 2026-09-28, v1.102.0 2026-09-22, v1.101.0 2026-09-15, v1.100.0 2026-09-06, v1.99.0 2026-09-01, v1.97.0 2026-08-16, v1.96.0 2026-08-10, v1.95.0 2026-08-03 — [GitHub releases API](https://github.com/BerriAI/litellm/releases)
- Diff of local 1.103.2 vs the 1.104.2 wheel (SRC):
  - `integrations/custom_guardrail.py`: identical apart from 2 typing-annotation lines.
  - `types/guardrails.py`: only `Any`→`object` / `ReadOnly` typing changes.
  - `unified_guardrail.py`, `tool_permission.py`, `guardrail_helpers.py`: byte-identical.
  - `include_guardrail_response`: present in 1.104.2 (`proxy/litellm_pre_call_utils.py:3150`, `proxy/common_request_processing.py:1414`), absent from 1.103.2.
  - `litellm/decisions/`: new in 1.104.2.
  - Source: local diff; [v1.104.2 tree](https://github.com/BerriAI/litellm/tree/v1.104.2/litellm)
- The docs no longer live in the main repo. `docs/my-website` was removed from BerriAI/litellm (commit message "docs: remove docs/my-website, point contributors to litellm-docs", 2026-04-24). Docs are now in BerriAI/litellm-docs, last pushed 2026-10-08T12:54Z — [litellm-docs repo](https://github.com/BerriAI/litellm-docs)

### Inferences
- For guardrail behaviour, 1.103.2 is a faithful proxy for 1.104.2. Upgrading matters mainly if the repo wants `include_guardrail_response` (useful for eval harnesses that read verdicts in-band) or the `/v1/decisions` route (directly relevant to the Jev / gpt-6-luna decision-API arm).
- LiteLLM ships several patch lines at once (1.101–1.104 all received patches on 2026-10-07/08). "Latest" therefore means the newest minor line, not the only maintained one.

### Gaps
- No formal LTS/support-window statement was found for the parallel 1.10x lines.

## Q1. Guardrail modes and hooks: what each sees, what it can change, and how streaming is handled

### Takeaway
**DOC.** LiteLLM has 8 event hooks (`GuardrailEventHooks`):
- `pre_call`, `during_call`, `post_call`, `logging_only`
- `pre_mcp_call`, `during_mcp_call`, `post_mcp_call`
- `realtime_input_transcription`

There is **no separate "tool-call", "agent" or "A2A" mode**. LLM tool calls and tool results flow through the ordinary `pre_call`/`post_call` translation, and MCP tool execution has its own three modes. A2A `message/send`/`message/stream` go through the normal guardrail pipeline.

Streaming:
- A plain `post_call` guardrail on a stream runs after delivery (audit-only) unless it buffers.
- `apply_guardrail`-based guardrails get a stream wrapper with tunable buffering/sampling flags.
- The docs disagree about the default: one page says buffer, another says sample every 5th chunk. Source shows the default is sample-every-5th-chunk, not buffer, except for Bedrock, Straiker and Rubrik.

### Cited Findings
- Enum `GuardrailEventHooks` = `pre_call, post_call, during_call, logging_only, pre_mcp_call, during_mcp_call, post_mcp_call, realtime_input_transcription` (SRC) — [types/guardrails.py#L1265](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/types/guardrails.py#L1265)
- DOC mode semantics:
  - `pre_call`: before the LLM call, on input.
  - `post_call`: after the call, on input & output.
  - `during_call`: same as pre_call but run in parallel with the LLM call; "Response not returned until guardrail check completes".
  - `logging_only`: scans logged input/output without changing the client response; support depends on the integration.
  - New `logging_only_scope: input|output|both` narrows the logging-only scan.
  - Source: [Guardrails Quick Start](https://docs.litellm.ai/docs/proxy/guardrails/quick_start)
- DOC custom-guardrail mode table: `pre_call` → `input_type="request"`, can mask. `during_call` → `"request"`, "Blocking only… your edits may not land before the request leaves". `post_call` → `"response"`, can mask. "If you mask or rewrite content, use `pre_call`" — [Custom Guardrail](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail)
- DOC MCP modes:
  - `pre_mcp_call`: before the MCP call, on input. Also runs on every tool returned by `tools/list`, scanning the tool description and input-schema descriptions. Blocked tools are hidden from the listing and masked ones are listed with masked text (anti tool-poisoning).
  - `during_mcp_call`: "real-time monitoring and intervention".
  - `post_mcp_call`: runs on the tool result (`CallToolResult` text blocks and string values in `structuredContent`) "before the model sees it". A mask hit on a key or a non-string value is treated as a block.
  - Source: [MCP Guardrails](https://docs.litellm.ai/docs/mcp_guardrail)
- DOC: "MCP sub-calls do not inherit the parent request's `guardrails` selection, so set `default_on: true` on the guardrail" — [MCP Guardrails](https://docs.litellm.ai/docs/mcp_guardrail)
- DOC: on a discovery scan the hook's `call_type` is `list_mcp_tools` (vs `call_mcp_tool`), with `mcp_tool_description`/`mcp_input_schema` in request data. An `apply_guardrail` guardrail receives the descriptions as extra `texts` ahead of the argument texts — [MCP Guardrails](https://docs.litellm.ai/docs/mcp_guardrail). SRC: `CallTypes.call_mcp_tool`, `list_mcp_tools`, A2A `asend_message`/`send_message` — [types/utils.py](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/types/utils.py)
- DOC: A2A "`message/send` and `message/stream` go through LiteLLM's A2A client (logging, guardrails, spend). All other methods are forwarded" — [A2A docs](https://docs.litellm.ai/docs/a2a). The OWASP page says one guardrail definition covers chat, text completion, Responses, Anthropic Messages, Google GenAI, embeddings, images, speech, transcription, video, rerank, OCR, Bedrock pass-through, A2A and MCP routes — [OWASP LLM Top 10 mapping](https://docs.litellm.ai/docs/proxy/security_owasp_llm_top10)
- DOC individual hooks on `CustomGuardrail`/`CustomLogger`:

  | Hook | Mode | Sees | Can change / block |
  |---|---|---|---|
  | `async_pre_call_hook` | pre_call | input | can modify input and fail the call |
  | `async_moderation_hook` | during_call | input | can only fail the call |
  | `async_post_call_success_hook` | post_call | input + output | can modify output and fail (non-streaming only) |
  | `async_post_call_streaming_iterator_hook` | post_call | the whole stream | can filter/block chunks in real time |

  Source: [Custom Guardrail](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail)
- DOC (custom_guardrail page): "For streaming responses, `post_call` guardrails run on the fully assembled response **after** all chunks have been delivered… audit-only… To filter or block streaming content in real-time, use `async_post_call_streaming_iterator_hook`". The same page then says built-in `apply_guardrail` guardrails "(for example Bedrock) take the opposite default on streams: LiteLLM buffers every chunk until the assembled response passes moderation" — [Custom Guardrail](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail)
- DOC (conflicting): "only Bedrock, Straiker, and Rubrik buffer by default, the rest sample every fifth chunk, and the OpenAI moderation guardrail samples rather than buffers". Streaming knobs: `streaming_buffer_until_moderated`, `streaming_sampling_rate`, `streaming_end_of_stream_only`, `streaming_transform_mode` — [OWASP LLM Top 10 mapping](https://docs.litellm.ai/docs/proxy/security_owasp_llm_top10); contradicts [Custom Guardrail](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail)
- SRC (resolves the conflict in favour of the OWASP page):
  - The unified streaming iterator defaults are `streaming_sampling_rate=5`, `streaming_end_of_stream_only=False`, `streaming_transform_mode="block_only"` (rewrites dropped on streams; `"incremental_diff"` only for OpenAI chat) and `streaming_buffer_until_moderated = buffer_until_moderated_default`, which is `False` unless the proxy routes an `override`-kind guardrail through it.
  - Buffering is force-disabled when `mask_response_content=True`, because buffered replay would leak unredacted chunks.
  - Flags resolve from the guardrail attribute, then `guardrail_config`, then callback `optional_params`.
  - Straiker and Rubrik hard-set `self.streaming_buffer_until_moderated = True`.
  - Sources: [unified_guardrail.py#L976-L1033](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/proxy/guardrails/guardrail_hooks/unified_guardrail/unified_guardrail.py#L976); [proxy/utils.py#L3965](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/proxy/utils.py#L3965) (local 1.103.2: `proxy/utils.py:3772`); local `straiker.py:321`, `integrations/rubrik.py:216`
- DOC Bedrock streaming params:
  - `streaming_buffer_until_moderated` (default True: "withhold every streamed chunk until the end-of-stream ApplyGuardrail scan passes").
  - `streaming_sampling_rate` (default 5).
  - `streaming_end_of_stream_only` (default False).
  - `streaming_buffer_release_on_scan` (default False: release withheld chunks after each passing sampled scan).
  - Source: [types/guardrails.py#L666](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/types/guardrails.py#L666); [Bedrock guardrail docs](https://docs.litellm.ai/docs/proxy/guardrails/bedrock)
- DOC LLM-as-a-judge: supports `pre_call`, `during_call` (added in v1.103.0, PR #41128) and `post_call`. "Streaming Support: Yes. A failing verdict terminates the stream" — [LLM-as-a-Judge](https://docs.litellm.ai/docs/proxy/guardrails/llm_as_a_judge); [v1.103.0 notes](https://github.com/BerriAI/litellm/releases/tag/v1.103.0)
- DOC Agentic Loop Hook (a `CustomLogger` feature, not a guardrail mode):
  - `async_should_run_agentic_loop` + `async_build_agentic_loop_plan` (or `async_build_chat_completion_agentic_loop_plan`) intercept a response, fulfil tool calls server-side and rerun.
  - `AgenticLoopPlan` supports `request_patch`, `response_override`, `terminate`.
  - Default max 3 reruns; identical tool-call fingerprints abort.
  - Streaming `/v1/messages` supported; streaming `/v1/chat/completions` does NOT trigger it.
  - Source: [Agentic Loop Hook](https://docs.litellm.ai/docs/proxy/agentic_loop_hook)

### Inferences
- For a client-side agent loop (the client executes the tools), LiteLLM sees the agent loop only as a sequence of independent LLM calls. The `pre_call` guardrail on call N+1 is where the previous tool result first becomes visible. `post_mcp_call` applies only when LiteLLM itself executes the tool (its `/mcp` gateway, or Responses-API MCP auto-execution).
- A judge-style custom guardrail that must block streamed tool calls before the client acts must set `streaming_buffer_until_moderated` (e.g. as an instance attribute, as Straiker does). Otherwise sampled scans can let early chunks, possibly including tool-call deltas, reach the client.

### Gaps
- `during_mcp_call` semantics ("real-time monitoring and intervention") are only one sentence in the docs. Whether it can block before the MCP server executes was not verified in source.
- `realtime_input_transcription` has no doc page in the guardrails folder beyond realtime_guardrails.md (not reviewed in depth).

## Q2. Custom guardrails: the `CustomGuardrail` API, `apply_guardrail`, `GenericGuardrailAPIInputs`, how tool calls and results are exposed, and masking vs blocking

### Takeaway
**DOC.** The recommended path is to subclass `CustomGuardrail` and implement one method, `async apply_guardrail(inputs, request_data, input_type, logging_obj=None) -> GenericGuardrailAPIInputs`.
- LiteLLM translates every supported API shape (OpenAI chat, Anthropic Messages, Responses, MCP, A2A, …) into `inputs`. Keys: `texts`, `images`, `tools`, `tool_calls`, `structured_messages`, `model`, `stream_holdback_chars`.
- It writes back whatever you return. **Raise to block; return modified texts or tool_calls to mask.**

On `pre_call` the guardrail sees the whole conversation:
- every message's text, including `role:"tool"` results;
- every prior assistant `tool_calls`;
- the `tools` definitions.

On `post_call` it sees only the new assistant text and tool calls, though `request_data` still carries the request.

`scan_only_tool_results` (since v1.97.0) narrows a guardrail to tool results only. This is LiteLLM's explicit knob for indirect-prompt-injection scanning in agent harnesses.

### Cited Findings
- DOC: "You only have to implement one method: `apply_guardrail`… LiteLLM pulls the content out of a request (or a response), hands it to you as `inputs`, and writes back whatever you return. Raise an exception to block the call." Register it in config.yaml as `guardrail: <module>.<Class>` — [Custom Guardrail](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail)
- DOC `inputs` keys:
  - `texts`: the text to check.
  - `images`: base64 or URLs.
  - `tools`: tool definitions sent to the LLM.
  - `tool_calls`: tool calls the LLM asked for.
  - `structured_messages`: the full messages in OpenAI format, so system vs user can be told apart.
  - `model`.
  - "To mask, edit `texts` or `tool_calls` in place; LiteLLM maps them back". `structured_messages` must be **replaced with a new list**, because in-place edits are ignored. While streaming you can set `stream_holdback_chars`.
  - Source: [Custom Guardrail](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail)
- SRC `GenericGuardrailAPIInputs(TypedDict, total=False)`:
  - `texts: list[str]`, `images: list[str]`, `tools: list[ChatCompletionToolParam]`
  - `tool_calls: list[ChatCompletionToolCallChunk] | list[ChatCompletionMessageToolCall]`
  - `structured_messages: list[AllMessageValues]`, `model: str | None`, `stream_holdback_chars: list[int]`
  - There is no dedicated `tool_results` key: tool results arrive as entries in `texts` and in `structured_messages`.
  - Source: [types/utils.py#L4493](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/types/utils.py#L4493) (local 1.103.2: L4538)
- SRC signature and default: `async def apply_guardrail(self, inputs, request_data: dict, input_type: Literal["request","response"], logging_obj=None) -> GenericGuardrailAPIInputs`. The default returns `inputs` unchanged. `__init_subclass__` auto-wraps a subclass's `apply_guardrail` with `log_guardrail_information`, so verdicts and timings are logged without decoration — [custom_guardrail.py#L1245](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/integrations/custom_guardrail.py#L1245), [#L151](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/integrations/custom_guardrail.py#L151)
- SRC `CustomGuardrail.__init__` kwargs:
  - `guardrail_name`, `supported_event_hooks`, `event_hook`, `default_on`
  - `mask_request_content`, `mask_response_content`, `violation_message_template`
  - `end_session_after_n_fails`, `on_violation`, `realtime_violation_message`
  - `on_sensitive_data` (`block`|`route`), `sensitive_data_route_to_model`, `sticky_session_routing`
  - `run_in_parallel`, `scan_raw_request`, `only_scan_new_messages`
  - Class vars `use_native_during_call_hook`, `use_native_lifecycle_hooks`, `records_own_guardrail_information`.
  - Unsupported modes raise at boot unless `LITELLM_STRICT_GUARDRAIL_MODES=false`.
  - Source: [custom_guardrail.py#L142-L235](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/integrations/custom_guardrail.py#L142)
- SRC request-side extraction (OpenAI chat translation, `process_input_messages`):
  - Iterates **all** `messages`. Each string or list-part `text` is appended to `texts`; image_url parts go to `images`; each assistant `tool_calls` entry is appended to `inputs["tool_calls"]`.
  - `structured_messages` = the in-scope messages; `tools` = request `tools`, omitted when `scan_only_tool_results`.
  - Calls `apply_guardrail(..., input_type="request")`, then maps returned `texts`/`tool_calls` back by index.
  - If the returned `texts` length mismatches, it raises `unappliable_request_rewrite` (fail-closed).
  - Source: [openai/chat/guardrail_translation/handler.py#L99-L232](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/llms/openai/chat/guardrail_translation/handler.py#L99)
- SRC response-side extraction (`process_output_response`): texts, images and tool calls from each response choice go into `inputs`. **No `structured_messages` and no `tools` are passed.** `request_data["response"]` is set to the ModelResponse; the request `messages` remain readable in `request_data` — [handler.py#L383-L460](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/llms/openai/chat/guardrail_translation/handler.py#L383). A v1.103.0 PR to give post-call scans "the scoped request conversation and tools" (#41220, merged 2026-09-17) was reverted two days later (#41986) — [v1.103.0 notes](https://github.com/BerriAI/litellm/releases/tag/v1.103.0); [PR #41986](https://github.com/BerriAI/litellm/pull/41986)
- DOC scope flags:
  - `skip_system_message_in_guardrail` and `skip_tool_message_in_guardrail` (global under `litellm_settings` or per guardrail) apply to the unified path on `/v1/chat/completions` and `/v1/messages`, and NOT to direct-hook guardrails (Aporia, DynamoAI, Javelin, Lasso, Pangea, Model Armor, Azure Content Safety, Guardrails AI, AIM, Cato, tool permission, MCP security).
  - "These flags also do not apply to other routes… (e.g. Responses API…)".
  - Source: [Guardrails Quick Start](https://docs.litellm.ai/docs/proxy/guardrails/quick_start)
- SRC/DOC `scan_only_tool_results`:
  - Description: "When True, unified guardrails only evaluate tool results, the untrusted data an agent feeds back into the model, and skip system, user, and assistant content. Intended for agent harnesses whose own prompt scaffolding is trusted but often trips prompt-attack detectors."
  - Scope rule: when set, roles other than `tool`/`function` are out of scope.
  - Added by PR #36014, merged 2026-08-06, shipped in v1.97.0.
  - It is mentioned only in passing in the docs (Gray Swan and LLM-as-a-judge pages); no dedicated section was found.
  - Sources: [types/guardrails.py#L943](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/types/guardrails.py#L943); [base_llm/guardrail_translation/utils.py#L244-L259](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/llms/base_llm/guardrail_translation/utils.py#L244); [PR #36014](https://github.com/BerriAI/litellm/pull/36014)
- SRC: `supports_scan_only_tool_results()` lets a guardrail reject that flag at init. `structured_messages_cover_full_request()` controls whether a returned `structured_messages` list replaces the full conversation or is merged into the scoped subset — [custom_guardrail.py#L951-L972](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/integrations/custom_guardrail.py#L951)
- SRC/DOC windowing options:
  - `experimental_use_latest_role_message_only` ("guardrails only receive the latest message for the relevant role").
  - `only_scan_new_messages`: per-session hash cache so only new or edited messages are sent. Needs `litellm_session_id`/`session_id` and the cache; falls back to a full scan otherwise. Added v1.95.0 (PR #33278).
  - Sources: [types/guardrails.py#L904-L921](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/types/guardrails.py#L904); [v1.95.0 notes](https://github.com/BerriAI/litellm/releases/tag/v1.95.0)
- SRC helper methods on `CustomGuardrail`:
  - `raise_passthrough_exception(violation_message, request_data, detection_info=None, original_response=None)` raises `ModifyResponseException`, an in-band 200 (see Q3).
  - `inject_advisory_message(data, message)` appends a system advisory and lets the call proceed. It returns False when it cannot land, for structured Responses `input`, "the caller must… degrade to blocking".
  - `raise_sensitive_data_route_exception(...)` reroutes to another model.
  - `get_guardrail_dynamic_request_body_params()` reads per-request `extra_body` (Enterprise per docs).
  - `should_run_guardrail(data, event_type)` handles `default_on`, opt-outs, `disable_global_guardrails` and tag-based `Mode`.
  - Sources: [custom_guardrail.py#L256-L421](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/integrations/custom_guardrail.py#L256), [#L991](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/integrations/custom_guardrail.py#L991)
- DOC: for MCP, a custom guardrail's `apply_guardrail` is called with `input_type="response"` and the tool result's text values on `post_mcp_call`. "If you override `get_supported_event_hooks`, include `post_mcp_call`" — [MCP Guardrails](https://docs.litellm.ai/docs/mcp_guardrail)
- DOC Custom Code guardrail: sandboxed Python with primitives `allow()`, `block(reason)`, `flag()` (non-blocking, added v1.101.0 PR #39728) and `modify(...)` — [custom_code_guardrail docs](https://docs.litellm.ai/docs/proxy/guardrails/custom_code_guardrail); [v1.101.0 notes](https://github.com/BerriAI/litellm/releases/tag/v1.101.0)

### Inferences
- With no window option, a `pre_call` guardrail on a long agent transcript receives every historical tool result and every prior tool call on each turn. That cost grows with the transcript, which matters for a judge with a 10-message window.
- `experimental_use_latest_role_message_only` and `only_scan_new_messages` are LiteLLM's built-in mitigations. The latter relies on a cache, which conflicts with this repo's "no cache/state" drop-in constraint.
- A drop-in judge guardrail that wants the conversation on `post_call` must read `request_data["messages"]` itself, because `inputs` does not carry it.

### Gaps
- `scan_only_tool_results` behaviour on `/v1/responses` and `/v1/messages` was not traced end-to-end in source (only the OpenAI chat handler and the shared utility were read).
- No official guidance was found on how big `texts` can get or on truncation limits for custom guardrails.

## Q3. How blocks reach the client: errors vs in-band refusals, which built-ins do which, and per-endpoint behaviour

### Takeaway
By default a block is an **error**. `HTTPException(400)` or `GuardrailRaisedException` (status 400) produce an OpenAI-style error body `{"error":{"message","type","param","code":"400",...}}`. A plain `Exception` from a custom guardrail becomes **HTTP 500**, and the docs' own example shows `"code": "500"`.

LiteLLM has an **official in-band refusal mechanism**, `ModifyResponseException`, raised via `CustomGuardrail.raise_passthrough_exception()` or the policy-pipeline `modify_response` action. The proxy returns **HTTP 200** with the violation text:

| Endpoint | In-band refusal shape (SRC) |
|---|---|
| `/chat/completions` | `finish_reason: "content_filter"` (stream and non-stream) |
| `/v1/messages` | `stop_reason: "end_turn"` (no Anthropic "refusal") |
| `/responses` | `status: "completed"` with the text as output |

The mechanism is used by built-ins only selectively: Bedrock `disable_exception_on_block`, Gray Swan / Semantic Guard `on_flagged_action: passthrough`, Straiker on the response side, Rubrik, Custom Code pre-call, Content Filter's competitor "reframe", and Block Code Execution. Most vendor integrations raise 400.

### Cited Findings
- DOC default block body (Aporia example, chat completions): `{"error":{"message":{...},"type":"None","param":"None","code":"400"}}` — [Guardrails Quick Start](https://docs.litellm.ai/docs/proxy/guardrails/quick_start). SRC: current code maps the type from status (400 → `"invalid_request_error"`, 401 → `authentication_error`, 403 → `permission_error`, 429 → `rate_limit_error`), `param` → `null`, and adds `provider_specific_fields` when the HTTPException detail is a dict. The docs' `"type":"None"` examples are therefore stale. `ProxyException.code` is serialized as a string — [common_request_processing.py#L595](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/proxy/common_request_processing.py#L595); local `proxy/common_utils/openai_error_payload.py:16-50`; local `proxy/_types.py:4101-4146`
- DOC custom guardrail blocked by plain `raise Exception(...)`: expected `{"error":{"message":"Content blocked: Policy violation","type":"None","param":"None","code":"500"}}` — [Custom Guardrail](https://docs.litellm.ai/docs/proxy/guardrails/custom_guardrail). SRC: exceptions without a 4xx/5xx `status_code` default to `HTTP_500_INTERNAL_SERVER_ERROR` — [common_request_processing.py#L3735](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/proxy/common_request_processing.py#L3735)
- SRC exception types:
  - `GuardrailRaisedException(guardrail_name, message, should_wrap_with_default_message=True, status_code=400, blocked_content=False)`. `blocked_content` separates a real verdict from a fail-closed outage.
  - `BlockedPiiEntityError` (400).
  - `ModifyResponseException(message, model, request_data, guardrail_name, detection_info, original_response)`: "should be caught by the proxy and returned with a 200 status code… allowing violation messages to be returned as successful responses rather than errors".
  - Sources: [exceptions.py#L1079](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/exceptions.py#L1079), [#L1201](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/exceptions.py#L1201)
- DOC tool_permission docs show `GuardrailRaisedException` returning `"code": "500"`. SRC: `GuardrailRaisedException.status_code` defaults to 400 and the generic handler honours `status_code`, so current builds should return 400 and the doc example looks stale. **This conflict was not runtime-verified** — [Tool Permission](https://docs.litellm.ai/docs/proxy/guardrails/tool_permission); [exceptions.py#L1079](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/exceptions.py#L1079)
- SRC chat completions in-band path: `except ModifyResponseException` calls `post_call_failure_hook` and builds a `ModelResponse` with `message.content = e.message` and `finish_reason = "content_filter"`. Usage is the blocked response's real usage on post-call blocks, zero on pre-call. When `stream=True` it returns a `StreamingResponse` with `status_code=200` — [proxy_server.py#L11746-L11785](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/proxy/proxy_server.py#L11746) (local 1.103.2: L11372-11409)
- SRC `/v1/messages` in-band path: builds `AnthropicMessagesResponse(content=[{"type":"text","text":e.message}], stop_reason="end_turn", usage=...)`. Streaming uses an SSE generator — [anthropic_endpoints/endpoints.py#L206](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/proxy/anthropic_endpoints/endpoints.py#L206) (local: L157-202). The streaming block terminator also uses `stop_reason: "end_turn"` — local `llms/anthropic/chat/guardrail_translation/handler.py:390,437`
- SRC `/responses` in-band path: returns `ResponsesAPIResponse(status="completed", output=[{"content":[{"type":"text","text":violation_text}]}])`. That output item lacks `type:"message"`/`role` and uses content type `"text"`, not `"output_text"`, so it is not a well-formed Responses output item. It is unchanged in 1.104.2. The streaming block path instead emits proper `response.created … response.completed` events with an `output_text` part. Neither sets `incomplete_details`/content_filter — [response_api_endpoints/endpoints.py#L434](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/proxy/response_api_endpoints/endpoints.py#L434); local `llms/openai/responses/guardrail_translation/handler.py:1471-1520`
- SRC streaming block terminators:
  - Chat: `build_block_sse_chunks` emits the block text plus a final chunk with `finish_reason: "content_filter"` — [openai/chat handler.py#L1296](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/llms/openai/chat/guardrail_translation/handler.py#L1296).
  - An `HTTPException` mid-stream becomes an in-stream SSE frame `data: {"error": {...}}` (OpenAI chat), or Anthropic error frames on `/v1/messages`. Fixed for valid SSE in v1.101.0 (PR #39036, merged 2026-09-02).
  - Sources: [handler.py#L720](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/llms/openai/chat/guardrail_translation/handler.py#L720); [PR #39036](https://github.com/BerriAI/litellm/pull/39036)
- SRC: the policy pipeline's `terminal_action == "modify_response"` raises `ModifyResponseException(guardrail_name=f"pipeline:{policy_name}")`. `terminal_action == "block"` raises the step's original exception, or `HTTPException(400, {"error":{"message":"Content blocked by guardrail pipeline '…'","type":"guardrail_pipeline_error","pipeline_context":{...}}})` — [proxy/utils.py#L2304](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/proxy/utils.py#L2304). DOC: Policy Flow Builder step actions `next`, `allow`, `block`, `modify_response` (with `modify_response_message`) for `on_pass`/`on_fail`/`on_error` — [Policy Flow Builder](https://docs.litellm.ai/docs/proxy/guardrails/policy_flow_builder)
- DOC Bedrock: by default "LiteLLM raises an HTTP 400 exception". `disable_exception_on_block: true` gives "a successful response containing the Bedrock guardrail's modified/blocked output", and "a block then returns HTTP 200 with `finish_reason: "content_filter"`" (motivated by OpenWebUI) — [Bedrock guardrail docs](https://docs.litellm.ai/docs/proxy/guardrails/bedrock). SRC: Bedrock builds `ModifyResponseException` when `disable_exception_on_block`, and its streaming path sets `finish_reason="content_filter"` (local `bedrock_guardrails.py:2089-2100, 2880`)
- DOC Gray Swan: `on_flagged_action`: `monitor` (log only), `block` (raise `HTTPException`), `passthrough` ("replace response content with violation message, no 400 error"). Recommendation: avoid `during_call` with block/passthrough, because the LLM is still paid for; use `pre_call` + `post_call` — [Gray Swan](https://docs.litellm.ai/docs/proxy/guardrails/grayswan)
- DOC Rubrik: "A blocked request returns the policy explanation with `finish_reason: content_filter`… If either service is unreachable… **fails open**" — [Rubrik](https://docs.litellm.ai/docs/proxy/guardrails/rubrik)
- SRC Straiker (v1.104.2): request-side block raises `GuardrailRaisedException` (400). Response-side block raises `ModifyResponseException` (200 in-band) — [straiker.py#L1149-L1170](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/proxy/guardrails/guardrail_hooks/straiker/straiker.py#L1149)
- SRC Custom Code guardrail: a pre-call `block()` uses `raise_passthrough_exception` (200 in-band). A post-call `block()` raises `HTTPException(400, {"error", "guardrail", "detection_info"})` — [custom_code_guardrail.py#L355](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/proxy/guardrails/guardrail_hooks/custom_code/custom_code_guardrail.py#L355) (local L332-366)
- SRC other in-band users: `litellm_content_filter` (only the competitor-intent "reframe" path; BLOCK raises HTTPException), `semantic_guard` (`on_flagged_action == "passthrough"`), `block_code_execution`, `grayswan` — local `content_filter.py:1708`, `semantic_guard.py:235`, `block_code_execution.py:505`, `grayswan.py:90`
- SRC tally of block mechanisms in built-in hooks (local 1.103.2):

  | Mechanism | Guardrails |
  |---|---|
  | `HTTPException(400)` | azure (Prompt Shield/Text Moderation), aporia, lakera v1/v2, model_armor, panw_prisma_airs, noma, pangea, lasso, pillar, openai moderation, cato, cisco, hiddenlayer, zscaler, crowdstrike, tool_policy, mcp_security |
  | `GuardrailRaisedException` (400) | presidio, generic_guardrail_api, tool_permission (post-call) |
  | HTTP 422 | llm_as_a_judge |
  | HTTP 502 | typesafe |

  Several also use 500/503 for provider failures. None set `finish_reason: "content_filter"` except via `ModifyResponseException`. Source: local `litellm/proxy/guardrails/guardrail_hooks/*`
- DOC Lakera v2: advisory mode (`on_flagged: inject_system_message`), which appends an advisory system message instead of blocking (v1.100.0, PR #34940). `on_flagged: block|monitor|inject_system_message` is a shared config field — [types/guardrails.py#L718](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/types/guardrails.py#L718); [v1.100.0 notes](https://github.com/BerriAI/litellm/releases/tag/v1.100.0)
- DOC tool_permission `on_disallowed_action: rewrite`: "silently strips disallowed tools from the payload… (pre-call) or rewrites the model response/tool calls… inserts error text into `message.content`/`tool_result` entries", giving 200 with `finish_reason: "stop"` in the example — [Tool Permission](https://docs.litellm.ai/docs/proxy/guardrails/tool_permission)
- DOC MCP: "On `/mcp`, a blocked result is returned as an MCP tool error (`result.isError: true`), which can arrive with HTTP 200. For `/v1/responses` MCP auto-execution, the model receives a tool error instead of the blocked content and can continue generating… A guardrail block does not by itself make the overall Responses request return HTTP 400" — [MCP Guardrails](https://docs.litellm.ai/docs/mcp_guardrail)
- SRC: `is_guardrail_intervention()` treats `ModifyResponseException`, `GuardrailRaisedException`, `BlockedPiiEntityError`, `SensitiveDataRouteException` and HTTPException with status 400/403/422 as intentional blocks (`guardrail_intervened`). Other statuses (401/408/429/…) count as `guardrail_failed_to_respond` — [custom_guardrail.py#L74-L106](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/integrations/custom_guardrail.py#L74)
- DOC/SRC header: `x-litellm-applied-guardrails` lists applied guardrails and, since v1.103.0 (PR #41583), names the blocking guardrail — [Guardrails Quick Start](https://docs.litellm.ai/docs/proxy/guardrails/quick_start); local `proxy/common_utils/callback_utils.py:488`

### Inferences
- For agent clients that treat 4xx as a fatal error (common in agent SDKs and coding agents), a custom guardrail that wants to "refuse but keep the loop alive" should call `self.raise_passthrough_exception(...)`. On chat completions this is the only first-party way to get HTTP 200 + `finish_reason: "content_filter"`.
- On `/v1/messages`, clients cannot tell a guardrail refusal from a normal answer by `stop_reason` (`end_turn`). On `/responses` the non-streaming refusal shape may not parse as standard output (SRC-only concern; worth a runtime test).
- `raise_passthrough_exception` is documented only in source docstrings, not in the docs site (grep for `raise_passthrough_exception`/`ModifyResponseException` in litellm-docs returned nothing). It is a public helper but not a documented contract.

### Gaps
- Runtime confirmation of `GuardrailRaisedException` → 400 vs the docs' "500" example was not done (no proxy started).
- Model Armor, Prisma AIRS, Noma, Pangea, Lasso, Pillar and Azure may have vendor-specific "monitor" or "mask" modes. Only their block mechanism (HTTPException 400) was tallied, not every option.
- No docs page states a cross-endpoint policy for refusal shapes. The per-endpoint shapes above come from source only.

## Q4. LiteLLM's guidance for agents, tool calling and MCP

### Takeaway
LiteLLM's agent-security guidance is spread across the OWASP LLM Top-10 (2026) mapping page, the MCP Guardrails page, the Tool Permission guardrail, Tool Policies (trust-chain) and the MCP/A2A permission controls. There is no single "guardrails for agents" page.

Explicit recommendations:
1. Scan tool results before the model sees them: `post_mcp_call`, or `scan_only_tool_results` on `pre_call`.
2. Scan tool descriptions at discovery: `pre_mcp_call` hides poisoned tools.
3. Set `default_on: true` for MCP guardrails, because sub-calls do not inherit request guardrails.
4. Constrain which tools and arguments are allowed: `tool_permission` regex rules, and Tool Policies trusted/untrusted information flow.
5. Treat guardrails as one probabilistic layer and pair them with least-privilege controls.

Fail-open/closed is per-integration rather than global:
- `unreachable_fallback` covers only some integrations.
- llm_as_a_judge and Rubrik **fail open**.
- Policy pipelines have `on_error`.

### Cited Findings
- DOC LLM01 (prompt injection): "Guardrails are classifiers, so a crafted injection can pass any of them. Treat them as one layer and pair them with the LLM03 controls, so a successful injection has little it can act on." Also "`default_on` is false", and the built-in detection callback does not cover `/v1/messages` or `/v1/responses` ("use a guardrail with `mode: pre_call` for those routes"). The page states it was checked against `main` at **v1.104.0** — [OWASP LLM Top 10 mapping](https://docs.litellm.ai/docs/proxy/security_owasp_llm_top10)
- DOC LLM03 (excessive agency):
  - Controls: MCP permission hierarchy (org/team/key), `require_key_mcp_access_defined`, tool allow/deny lists, per-entity tool permissions, toolsets, grants, client allowlist, zero-trust MCP.
  - "Put `agent_permissions` on the key or team, and send `metadata.session_id` on every call so iteration budgets can count".
  - Known limits: "MCP and A2A access is open until some level defines a list". On DB failure MCP falls back to the global list and A2A "returns unrestricted access". "There is no server-side approval step per tool call; `require_approval` on Responses API MCP tools is honored by the client". "Tool policies see only tool calls that pass through the gateway".
  - Source: [OWASP LLM Top 10 mapping](https://docs.litellm.ai/docs/proxy/security_owasp_llm_top10)
- DOC LLM10 (improper output handling): use `mode: post_call`, and set `streaming_buffer_until_moderated: true` "when a block must land before any chunk reaches the client" — [OWASP LLM Top 10 mapping](https://docs.litellm.ai/docs/proxy/security_owasp_llm_top10)
- DOC MCP tool-result scanning: "Use this mode [post_mcp_call] to block or mask PII, prompt injections, or other unsafe content coming back from a tool". Discovery scanning "is what stops tool poisoning". To refuse unapproved tools, "pin the server's tool list" — [MCP Guardrails](https://docs.litellm.ai/docs/mcp_guardrail)
- DOC Tool Permission guardrail (`guardrail: tool_permission`):
  - Regex `rules` on `tool_name`/`tool_type` with `decision: allow|deny`, plus `allowed_param_patterns` on argument paths (e.g. `"to[]": "^.+@berri\\.ai$"`).
  - `default_action: allow|deny`, `on_disallowed_action: block|rewrite`, `violation_message_template` with `{tool_name}`, `{rule_id}`, `{default_message}`.
  - Modes `pre_call`, `post_call`. Covers OpenAI `tool_calls`, Anthropic `tool_use` and MCP tools.
  - Source: [Tool Permission](https://docs.litellm.ai/docs/proxy/guardrails/tool_permission)
- DOC Tool Policies (`guardrail: tool_policy`):
  - Auto-discovered tool registry. New tools default to `input_policy: "untrusted"`, `output_policy: "untrusted"`.
  - Input policies: `untrusted`, `trusted`, `blocked`. Output policies: `untrusted`, `trusted`.
  - A `trusted`-input tool is rejected (HTTP 400) when "the conversation contains output from a tool whose output policy is untrusted" (a trust-chain / information-flow control).
  - Team/key overrides; supports pre_call/post_call/during_call.
  - Proxy-admin only, needs the DB.
  - "If the in-memory policy registry is not initialized, the guardrail returns the inputs without applying Tool Policies" (fail-open).
  - `TOOL_POLICY_CACHE_TTL_SECONDS=60`.
  - Source: [Tool Policies](https://docs.litellm.ai/docs/proxy/tool_policies)
- DOC Microsoft Agent 365 guardrail (`pre_mcp_call` only): sends every MCP tool call to Defender for allow/block under the signed-in user's Entra token (OBO); "Chat completions and other LLM routes are untouched". Added v1.103.0 (PR #38241) — [Microsoft Agent 365](https://docs.litellm.ai/docs/proxy/guardrails/microsoft_agent_365); [v1.103.0 notes](https://github.com/BerriAI/litellm/releases/tag/v1.103.0)
- DOC Lasso: "scans the whole agentic turn, not the prompt text alone… On `post_call` the guardrail sends the model's reply for each choice, which is the assistant text plus any `tool_calls`" — [Lasso](https://docs.litellm.ai/docs/proxy/guardrails/lasso_security)
- DOC Gray Swan: "Answers that contain only tool calls are scanned too. With `on_flagged_action: block` a flagged tool call returns 400 instead of reaching the client, and with `fail_open: false` a Cygnal error fails the request" — [Gray Swan](https://docs.litellm.ai/docs/proxy/guardrails/grayswan)
- DOC TypeSafe (Jev) guardrail: a **compaction** guardrail, not a safety one. It runs at `pre_call` and sends completed tool exchanges to Jev's `/v1/systemone` with a `noul` "still needed?" question, then blanks tool results scored below `relevance_threshold`. Works on chat, `/v1/messages` and `/v1/responses`. Added v1.103.0 (PR #41757) — [TypeSafe](https://docs.litellm.ai/docs/proxy/guardrails/typesafe)
- DOC agent runtime controls:
  - Agent Iteration Budgets: `max_iterations` per session gives a 429 when exceeded; `LITELLM_MAX_ITERATIONS_TTL` defaults to 3600 s.
  - Agent Kill Switch: an optional outbound webhook per agent, added v1.104.0 (PR #42841).
  - Agents can carry access groups enforced for models, MCP servers and agent calls (v1.104.0, PR #41634).
  - Sources: [Agent Iteration Budgets](https://docs.litellm.ai/docs/a2a_iteration_budgets); [Agent Kill Switch](https://docs.litellm.ai/docs/a2a_kill_switch); [v1.104.0 notes](https://github.com/BerriAI/litellm/releases/tag/v1.104.0)
- DOC/SRC fail-open/closed:
  - `unreachable_fallback: fail_closed (default) | fail_open` is implemented only by `generic_guardrail_api`, `agent_365`, `akto`, `vigil_guard`, `repelloai`, `headroom`, `compresr`, `typesafe`. Other integrations have their own flags (Gray Swan `fail_open`, CrowdStrike fail-open added v1.100.0).
  - `timeout` (seconds) is per guardrail; "Each guardrail handler chooses its own default when unset".
  - Sources: [types/guardrails.py#L1058-L1088](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/types/guardrails.py#L1058); [v1.100.0 notes](https://github.com/BerriAI/litellm/releases/tag/v1.100.0)
- DOC llm_as_a_judge: "The guardrail fails open on judge errors: if the judge call fails or returns an unparsable verdict, a warning is logged, the guardrail status is recorded as `guardrail_failed_to_respond`, and the response is returned". Blocks with HTTP 422 below `overall_threshold` (default 80). Judge calls go through the Router "with retries and standard fallbacks disabled" and "participate in that deployment's rate and cooldown accounting" — [LLM-as-a-Judge](https://docs.litellm.ai/docs/proxy/guardrails/llm_as_a_judge)
- DOC Policy Flow Builder `on_error` "applies only to error… so outages or timeouts can allow, block, go to the next step, or return a custom response without conflating them with content violations" (pipeline-level fail-open/closed) — [Policy Flow Builder](https://docs.litellm.ai/docs/proxy/guardrails/policy_flow_builder)
- DOC attachment and scoping:
  - `default_on: true` runs on every request, "even if user specifies a different guardrail or empty guardrails array".
  - Per-API-key guardrails (`/key/generate` `guardrails: [...]`) and tag-based modes (e.g. `"User-Agent: claude-cli": logging_only`) are marked Enterprise.
  - Model-level guardrails (`litellm_params.guardrails`) are Enterprise.
  - Teams can be prevented from modifying guardrails (403).
  - `[Beta] Guardrail Policies` group guardrails per team/key/model with inheritance.
  - Sources: [Guardrails Quick Start](https://docs.litellm.ai/docs/proxy/guardrails/quick_start); [Guardrail Policies](https://docs.litellm.ai/docs/proxy/guardrails/guardrail_policies)
- DOC/SRC execution controls:
  - `run_in_parallel` (block-only guardrails run concurrently, v1.95.0 PR #33770).
  - `scan_raw_request` (a pre_call guardrail always sees the pre-masking request).
  - Guardrail order is stable across edits.
  - Sources: [types/guardrails.py#L1117-L1137](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/types/guardrails.py#L1117); [Guardrails Quick Start](https://docs.litellm.ai/docs/proxy/guardrails/quick_start)
- DOC/SRC: `disable_global_guardrails` on keys/teams is gated to proxy admins (v1.104.0, PR #42699). Key/team guardrails apply to MCP tool calls (v1.102.0, PR #39629) — [v1.104.0 notes](https://github.com/BerriAI/litellm/releases/tag/v1.104.0); [v1.102.0 notes](https://github.com/BerriAI/litellm/releases/tag/v1.102.0)

### Inferences
- LiteLLM's own stance matches a defence-in-depth view: probabilistic guardrails plus deterministic least-privilege (tool allow-lists, trust-chain Tool Policies, iteration budgets).
- For a drop-in judge guardrail in a client-side loop, the nearest first-party recipe is:
  - `pre_call` with `scan_only_tool_results: true` to judge only untrusted tool output;
  - `post_call` with buffering to judge the model's tool calls;
  - `raise_passthrough_exception` for an in-band refusal.

  This is an inference; LiteLLM documents no such combined recipe.
- Masking vs blocking: the docs steer masking to `pre_call`/`post_mcp_call` (with `mask_request_content`/`mask_response_content`). Streaming masking disables buffering (SRC), so on streams masking and pre-delivery blocking are mutually exclusive for `apply_guardrail` guardrails.

### Gaps
- There is no LiteLLM-published "guardrails for agents" best-practice page beyond the OWASP mapping. No guidance was found on how to signal a tool-result block back to a client-side agent loop (e.g. rewriting the tool message vs refusing the turn).
- Default per-guardrail timeouts were not catalogued per integration.

## Q5. Billing and logging of guardrail calls

### Takeaway
Every guardrail execution is recorded as `StandardLoggingGuardrailInformation` in `guardrail_information` on the standard logging payload and spend logs, with name, provider, mode, status, response, timings and masked-entity counts. Status values are `success`, `guardrail_flagged`, `guardrail_intervened`, `guardrail_failed_to_respond` and `not_run`.

Since v1.104.0, `include_guardrail_response: true` returns those records in the response body (non-streaming only). Vendor guardrail costs (Azure Prompt Shield, Bedrock) are tracked as reporting-only estimates, not charged to key or team spend. The LLM-as-a-judge's own model call is documented only as "one extra LLM call", with its spend attribution unstated.

### Cited Findings
- DOC `StandardLoggingGuardrailInformation` fields: `guardrail_name`, `guardrail_provider`, `guardrail_mode`, `guardrail_request`, `guardrail_response`, `guardrail_status`, `start_time`, `end_time`, `duration`, `masked_entity_count`. `GuardrailStatus` = `success | guardrail_flagged | guardrail_intervened | guardrail_failed_to_respond | not_run` — [Logging spec](https://docs.litellm.ai/docs/proxy/logging_spec)
- DOC `include_guardrail_response: true`:
  - Returns `guardrail_information` as a top-level list on the response.
  - Only the JSON boolean `true` enables it, and the flag is stripped before the provider call.
  - "Streaming responses do not carry the field".
  - `keyword`/`snippet`/`match`/`regex` values are returned as `"[REDACTED]"`.
  - Added by PR #42327, merged 2026-09-22, shipped v1.104.0. Not in 1.103.2 (SRC).
  - Sources: [Guardrails Quick Start](https://docs.litellm.ai/docs/proxy/guardrails/quick_start); [PR #42327](https://github.com/BerriAI/litellm/pull/42327)
- SRC: `_summarize_guardrail_response` collapses an `apply_guardrail` return into `"allow"`/`"mask"` (comparing against a pre-hook copy) so prompts are not shipped to log sinks. A string result (a rejection message) is logged as is. `_process_error` records `guardrail_intervened` vs `guardrail_failed_to_respond` — [custom_guardrail.py#L1275-L1374](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/integrations/custom_guardrail.py#L1275)
- DOC Azure Prompt Shield cost tracking (v1.100.0, PR #38387):
  - Usage counters `requests`, `input_characters`, `text_records`; estimated cost = `text_records × price_per_1000_text_records / 1000`, exported on the guardrail OTEL span as `litellm.cost.guardrail`.
  - "Spend isolation — the guardrail cost estimate is reporting-only. It is never added to the request's `response_cost`, key/team/user spend, or budget enforcement."
  - Source: [Azure Content Safety guardrail](https://docs.litellm.ai/docs/proxy/guardrails/azure_content_guardrail)
- Release notes cost/telemetry items:
  - v1.101.0: Bedrock guardrail cost rolled up per usage counter (#39196); Guardrails Monitor UI shows usage units and cost (#39853); guardrail cost kept in spend on cache hits (#39960).
  - v1.102.0: guardrail scan ids mapped to guardrail/stage/provider (#40327); MCP failure spend log written for guardrail-blocked `/mcp-rest/tools/call` (#40555).
  - v1.103.0: blocked streaming guardrail responses logged as failures (#40191).
  - v1.104.0: masked output stored in spend logs when Presidio masks the response (#42441).
  - Sources: [v1.101.0](https://github.com/BerriAI/litellm/releases/tag/v1.101.0), [v1.102.0](https://github.com/BerriAI/litellm/releases/tag/v1.102.0), [v1.103.0](https://github.com/BerriAI/litellm/releases/tag/v1.103.0), [v1.104.0](https://github.com/BerriAI/litellm/releases/tag/v1.104.0)
- SRC: on an in-band block, the proxy still calls `post_call_failure_hook` and reports the blocked response's real token usage (`_blocked_response_usage`), so post-call blocks are not reported as zero-cost — [proxy_server.py#L11746](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/proxy/proxy_server.py#L11746)
- DOC LLM-as-a-judge: "Every judged request or response costs one extra LLM call to the judge model". With `on_failure: log` the verdict is stored in `eval_information` in request metadata, which reaches spend logs — [LLM-as-a-Judge](https://docs.litellm.ai/docs/proxy/guardrails/llm_as_a_judge)
- DOC Decisions API (`/v1/decisions`, `/v1/systemone`): cost tracked in the `x-litellm-response-cost` header and spend logs. Providers include `openai/gpt-6-luna`, `typesafe/jev-latest`, `openrouter/typesafe/jev-1.13`, Perplexity, Cloudflare Clef and self-hosted Strands Decider. "Available in `v1.104.2` and later on the 1.104.x line and in `v1.105.0-rc.3`" — [Decisions](https://docs.litellm.ai/docs/decisions)

### Inferences
- A custom judge guardrail calling a model through `litellm.acompletion` inside `apply_guardrail` is not automatically attributed to the end user's key. LiteLLM documents no mechanism for billing guardrail model calls to the caller; vendor guardrail costs are deliberately isolated from key/team spend.
- `include_guardrail_response` gives an eval harness per-request verdicts without log scraping, but only for non-streaming calls.

### Gaps
- Whether llm_as_a_judge judge-model calls create their own spend-log rows, or are attributed to the calling key, is not documented. A quick grep of the judge source found no spend/cost handling.

## Q6. Changes to the guardrail framework in 2026

### Takeaway
The 2026 trajectory: the unified `apply_guardrail` translation layer has become the default across endpoints (chat, Anthropic Messages, Responses, MCP, A2A, video). Large investment went into agent and MCP coverage (tool-result scanning, tool-description scanning, tool-call argument scanning, tool-call rewrites in streams) and into streaming buffering/rewrite correctness. No breaking API change to `CustomGuardrail`/`apply_guardrail` was found in Aug–Oct 2026. The one behaviour-hardening item to watch is strict mode validation (`LITELLM_STRICT_GUARDRAIL_MODES`, default on), and `v1.104.0` adds a startup refusal of unset or known master keys.

### Cited Findings
- v1.95.0 (2026-08-03): `only_scan_new_messages` (#33278); `run_in_parallel` (#33770) — [v1.95.0](https://github.com/BerriAI/litellm/releases/tag/v1.95.0)
- v1.96.0 (2026-08-10): "scan and mask MCP tool results via post_mcp_call guardrails" (#35155, merged 2026-07-30) — [v1.96.0](https://github.com/BerriAI/litellm/releases/tag/v1.96.0)
- v1.97.0 (2026-08-16): `scan_only_tool_results` (#36014); `litellm_content_filter` allowed on `post_mcp_call` (#35980) — [v1.97.0](https://github.com/BerriAI/litellm/releases/tag/v1.97.0)
- v1.100.0 (2026-09-06): Lakera v2 advisory (`inject_system_message`) mode (#34940); CrowdStrike AIDR fail-open (#38568); Azure Prompt Shield usage/cost (#38387); post_call scans recorded on native `/v1/messages` streams (#38713) — [v1.100.0](https://github.com/BerriAI/litellm/releases/tag/v1.100.0)
- v1.101.0 (2026-09-15):
  - `modify_response` blocks delivered as valid SSE on streaming chat and Responses (#39036).
  - Non-blocking `flag()` verdict for custom code guardrails (#39728).
  - "scan and mask MCP tool call arguments in unified guardrails" (#35142).
  - `apply_guardrail`-only providers run in `logging_only` mode (#39297).
  - Undecorated custom `apply_guardrail` overrides now record guardrail info (#39727).
  - Router fallback on Anthropic safeguard refusals (#39157).
  - Source: [v1.101.0](https://github.com/BerriAI/litellm/releases/tag/v1.101.0)
- v1.102.0 (2026-09-22):
  - post_call policy pipelines on streams (#38788, #38721).
  - Tool-call rewrites delivered into buffered chat, Responses and Messages streams (#40271).
  - Legacy post-call hooks run as streaming pipeline steps (#40284).
  - Key/team guardrails applied to MCP tool calls (#39629).
  - End-user `mcp_tool_permissions` enforced (#40865).
  - Fail closed with a named error when a Responses input rewrite cannot be applied (#40609).
  - Source: [v1.102.0](https://github.com/BerriAI/litellm/releases/tag/v1.102.0)
- v1.103.0 (2026-09-28):
  - Anthropic top-level system prompt and `tool_use` arguments scanned (#40984).
  - Buffered stream chunks released after each passing scan (#41425).
  - llm_as_a_judge `pre_call`/`during_call` (#41128).
  - Microsoft Agent 365 MCP guardrail (#38241); Singulr v2 with `pre_mcp_call`/`post_mcp_call` (#41329); TypeSafe Jev compaction guardrail (#41757).
  - `x-litellm-applied-guardrails` names the blocking guardrail (#41583).
  - Policy-engine priority ordering (#41571).
  - Post-call scoped conversation added then reverted (#41220 → #41986).
  - Source: [v1.103.0](https://github.com/BerriAI/litellm/releases/tag/v1.103.0)
- v1.104.0 (2026-10-03):
  - Opt-in `include_guardrail_response` (#42327).
  - Each choice's tool-call arguments scanned separately on n>1 streams (#40986).
  - `custom_tool_call_output` patched in place on Responses guardrail write-back (#41561).
  - Key-attached guardrails on `/v1/videos` (#42354).
  - `disable_global_guardrails` gated to proxy admins (#42699).
  - Policy default fallback attachments (#42119).
  - Straiker v3 API (#41880).
  - `mcp_tool_permissions` `["*"]` wildcard (#43108).
  - Breaking-style: "feat(proxy)!: refuse to start with an unset, empty, or publicly known master key" (#42019).
  - Source: [v1.104.0](https://github.com/BerriAI/litellm/releases/tag/v1.104.0)
- v1.105.0-rc.1 (pre-release, 2026-10-04): Straiker v3 "fails closed on a missing verdict" (#44011); Azure guardrail `get_user_prompt` dispatch restored (#44067) — [v1.105.0-rc.1](https://github.com/BerriAI/litellm/releases/tag/v1.105.0-rc.1)
- SRC: `LITELLM_STRICT_GUARDRAIL_MODES` (default true) makes an unsupported `mode` raise at startup ("pre-LIT-4226 behavior" restorable with `false`). The MCP docs separately say an unsupported mode "causes initialization to log an error and skip that guardrail while the proxy continues starting" — [custom_guardrail.py#L109-L120](https://github.com/BerriAI/litellm/blob/v1.104.2/litellm/integrations/custom_guardrail.py#L109); [MCP Guardrails](https://docs.litellm.ai/docs/mcp_guardrail). These two statements may describe different layers (constructor vs initializer); not reconciled.
- DOC (official incident report, dated 2026-03-18, severity High, resolved): "When a custom guardrail returned the full LiteLLM request/data dictionary, the guardrail response logged by LiteLLM could include `secret_fields.raw_headers`, including plaintext `Authorization` headers", which reached spend logs and OpenTelemetry traces. This is the background for the current `_summarize_guardrail_response` allow/mask collapsing (Q5) — [Incident Report: Guardrail logging exposed secret headers](https://docs.litellm.ai/blog/guardrail-logging-secret-exposure-incident)

### Inferences
- Agent-relevant capabilities (`post_mcp_call` tool-result scanning, `scan_only_tool_results`, tool-call argument scanning, in-band SSE refusals) are all from Jul–Sep 2026. Pre-August-2026 guidance or community posts on LiteLLM agent guardrails are likely outdated.
- Release cadence is very high (weekly minors, many bot-authored PRs), so behaviour cited here should be re-verified against the exact deployed tag.

### Gaps
- The fixed version for the March 2026 guardrail-logging incident was not extracted from the blog post.
- No community (unofficial) sources were used. A GitHub issue search for agent-loop guardrail blocking returned no relevant issues.

# agentic-security: drop-in LiteLLM guardrail

An LLM-as-a-judge guardrail for AI assistants and agents. It catches prompt injection and jailbreaks, malicious
cyber requests, injected instructions in tool, document and MCP results, poisoned tool definitions, and unsafe or
unauthorized tool calls.

This folder is the whole deployable unit. It needs only the Python standard library and LiteLLM, and imports
nothing from the rest of this repository. Nothing else in the repository is required.

```
agentic_security.py        the guardrail (a LiteLLM CustomGuardrail)
prompts/request.md         judge instructions, before the model runs
prompts/response.md        judge instructions, for the model's tool calls
litellm_config.example.yaml
```

## Install

1. Copy this folder onto the gateway, either next to the LiteLLM config or anywhere on the gateway's `PYTHONPATH`.
2. Add the guardrail to the config (see [litellm_config.example.yaml](litellm_config.example.yaml)). `judge_model`
   must be a `model_name` in the gateway's `model_list`.
3. Restart the gateway. The guardrail runs on requests that name it (`"guardrails": ["agentic-security"]`) or on
   every request with `default_on: true`.

There is no cache, no state between requests, and no extra service: no Redis and no database.

## What it does per model call

| Hook | Judge calls | What is rated | If flagged |
|---|---|---|---|
| pre-call | 1 (+1 if a tool result is flagged) | new user message(s); every tool result since the user's last message (`tool_results: turn`); tool definitions when a user turn starts | user message or tool definition: HTTP 200 refusal, and the model does not run. Tool result: one extra call finds the injected lines, only those are cut (with a marker), and the model still runs on the rest. The whole result is withheld if that call fails, finds nothing or would cut most of it |
| post-call | 1, only if the reply calls tools | every tool call in the reply | the reply is rewritten into the refusal, so it is still billed |

**APIs:** Chat Completions, Anthropic Messages (`/v1/messages`, used by Claude Code) and the Responses API
(`/v1/responses`, used by Codex) are handled alike. A block reaches the client as:

Verified end to end on LiteLLM 1.103.2 (2026-10-08, `chargeback_check.py --endpoint chat|messages|responses`):

| API | Blocked before the model runs | Tool call blocked after it runs | Same, streamed | Every call billed to the caller |
|---|---|---|---|---|
| Chat Completions | HTTP 200; refusal, `finish_reason: "content_filter"` | HTTP 200; reply rewritten into the refusal, `content_filter`, no tool calls | stream held, then ends with the refusal | yes, all 7 paths |
| Anthropic Messages | HTTP 200; one text block, `stop_reason: "end_turn"` | HTTP 200; one text block, `end_turn`, no `tool_use` | **not checked: LiteLLM does not run post-call guardrails on streamed `/v1/messages` replies, so the tool call reaches the client** | yes, all 7 paths |
| Responses API | HTTP 200, but **LiteLLM's refusal is malformed** (output item without `type: "message"`; content type `text`, not `output_text`), so SDKs may not show it. The model still never runs | HTTP 200; one completed assistant message, no function call | stream held, then ends with the refusal | yes, all 7 paths |

The two gaps in bold are in LiteLLM, not in this guard, and need fixing upstream. Until then, tool calls in
streamed Anthropic Messages replies (Claude Code always streams) are not checked after the model runs; tool
results and user messages on that API still are, before it runs.

Anthropic replies keep `stop_reason: "end_turn"` because Claude Code shows `"refusal"` as an API error and users
report the session staying blocked. The refusal text tells the agent not to retry or work around the block, to
tell the user, and to carry on with any other allowed work (as OpenAI's Codex does after a content filter).

- **Context:** the judge sees the last `window` messages (user, assistant, tool calls and results) as context. This
  shows it what the user asked for or delegated, what the assistant already declined, and drift across turns. The
  application's system prompt is left out unless `include_system_prompt: true`.
- **Hedging:** if the first-pass call hasn't answered within `hedge_s`, an identical second call is sent and the
  first answer wins. The slower call is left to finish, so it is still billed.
- **Scores:** each rated entry gets a digit from 0 to 9. 7–9 is flagged and 0–3 passes. 4–6 goes to one extra
  review call that decides; for tool calls, every 4–9 is reviewed.
- **Fail-open:** if the judge is down, errors or exceeds `deadline_s`, the request proceeds and the gateway logs
  `guard failed`.
- **The judge's own provider refuses:** if the judge model's provider rejects a judge call on safety grounds (for
  example an OpenAI `cyber_policy` error, or a `content_filter` reply), the entries in that call count as flagged.
  This is not treated as "unavailable": the content most likely to trip a provider's safety system is the content
  that most needs blocking. Judge calls carry a hashed per-caller `safety_identifier`, so a provider can act on one
  caller instead of the gateway's whole account (dropped automatically for providers that don't accept it).
- **Outcome logging:** every run is recorded in LiteLLM's guardrail log (`guardrail_information` in spend logs,
  OTEL, Datadog and other loggers) with its real outcome: `success` (passed), `guardrail_intervened` (withheld or
  blocked) or `guardrail_failed_to_respond` (failed open). Without this, LiteLLM records every run that returns
  normally, fail-opens and withholds included, as `success`.
- **Settings that blind the guard:** LiteLLM's `skip_tool_message_in_guardrail` and
  `experimental_use_latest_role_message_only` (and `skip_system_message_in_guardrail` with
  `include_system_prompt: true`) remove messages before the guard sees them. The gateway logs an error when one is
  on, and `scan_only_tool_results` is rejected at startup, since it would hide user messages.
- **Chargeback:** judge calls go through the gateway's own router with the caller's key metadata, so LiteLLM bills
  them to the calling key and team, tagged `guardrail:<name>`.
- **Audit:** each flagged entry logs one gateway warning line with the guard, the entry kind, the action, the judge
  scores and a content hash. Content itself is never logged.
- **Withholding:** the agent keeps the original tool result and resends it on every call, so it is re-rated, in
  the same single call, on every step of the turn (`tool_results: turn`), however long the agent loop runs. The
  user's last message also stays in the judge's view. With `tool_results: window`, only results in the window are
  re-rated: fewer judge tokens on long loops, but a cut result reaches the model again once it scrolls out. A cut
  result from an earlier turn is no longer re-rated after the user's next message.
- **Limit:** very long entries are trimmed to their start and end (24,000 characters).

## Configuration

| Key | Default | Meaning |
|---|---|---|
| `judge_model` | `gpt-6-luna` | model the judge calls, through this gateway |
| `window` | `10` | most recent messages the judge sees |
| `include_system_prompt` | `false` | also show the application's system prompt to the judge, as context |
| `on_unavailable` | `allow` | `allow` fails open; `block` refuses when the judge can't decide |
| `deadline_s` | `10` | time budget per hook |
| `judge_timeout_s` | `8` | timeout of each judge call |
| `hedge_s` | `2.5` | send a duplicate first-pass call after this many seconds; `0` turns hedging off |
| `surgical_withholding` | `true` | cut only the injected lines of a flagged tool result; `false` withholds all of it |
| `tool_results` | `turn` | re-rate every tool result since the user's last message; `window`: only those in the window (cheaper on long agent loops) |
| `review_band` / `action_review_band` | `[4, 6]` / `[4, 9]` | digits that get the review call |
| `prompts_dir` | `prompts/` next to the module | where `request.md` and `response.md` live |
| `refusal_message`, `redaction_message` | built in | texts the caller or the model sees |

The prompts are generated from the repository's tuned policies by `evals/lab/build_agentic.py`. Edit the policies
and rebuild; don't edit these files by hand.

## Recommended deployment

- **Give the judge its own model entry and quota.** Point `judge_model` at a dedicated `model_name` (for example
  `agentic-security-judge`, same underlying model) with its own `rpm`/`tpm` limits and no model-level guardrails.
  A shared rate limit once turned thousands of checks into fail-opens; a guardrail attached to the judge's model
  would block the attack text the judge must read.
- **Start in monitor-only mode,** then enforce. Watch `guardrail_information` statuses and the gateway's `guard
  failed` and `redacted` lines on real traffic before blocking.
- **Fail closed where it matters.** Attach a second entry with `on_unavailable: block` (per key or team, an
  Enterprise feature) to teams whose agents have tools that change things or send data out.
- **Add deterministic controls.** The judge is a filter, not a boundary (it catches about 80% of agent drift on
  tool calls). Pair it with LiteLLM's `tool_permission` rules or Tool Policies for destructive and data-egress tools.
- **MCP tools the gateway runs itself** (Responses API with LiteLLM-hosted MCP servers) send their results straight
  into a follow-up model call that never reaches the pre-call hook. This guard doesn't cover that path yet.
- **Test on your exact LiteLLM version** before enforcing: `tests/test_agentic_security.py` and
  `evals/lab/chargeback_check.py --endpoint chat|messages|responses` in the source repository. The guard relies on
  some undocumented LiteLLM behaviour (the in-place reply rewrite, the streaming buffer flag, the router global).

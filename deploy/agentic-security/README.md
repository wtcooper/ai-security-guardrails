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
| pre-call | 1 (+1 if a tool result is flagged) | new user message(s); every tool result in the last `window` messages; tool definitions when a user turn starts | user message or tool definition: HTTP 200 refusal, and the model does not run. Tool result: one extra call finds the injected lines, only those are cut (with a marker), and the model still runs on the rest. The whole result is withheld if that call fails, finds nothing or would cut most of it |
| post-call | 1, only if the reply calls tools | every tool call in the reply | the reply is rewritten into the refusal, so it is still billed |

- **Context:** the judge sees the last `window` messages (user, assistant, tool calls and results) as context. This
  shows it what the user asked for or delegated, what the assistant already declined, and drift across turns. The
  application's system prompt is left out unless `include_system_prompt: true`.
- **Hedging:** if the first-pass call hasn't answered within `hedge_s`, an identical second call is sent and the
  first answer wins. The slower call is left to finish, so it is still billed.
- **Scores:** each rated entry gets a digit from 0 to 9. 7–9 is flagged and 0–3 passes. 4–6 goes to one extra
  review call that decides; for tool calls, every 4–9 is reviewed.
- **Fail-open:** if the judge is down, errors or exceeds `deadline_s`, the request proceeds and the gateway logs
  `guard failed`.
- **Chargeback:** judge calls go through the gateway's own router with the caller's key metadata, so LiteLLM bills
  them to the calling key and team, tagged `guardrail:<name>`.
- **Audit:** each flagged entry logs one gateway warning line with the guard, the entry kind, the action, the judge
  scores and a content hash. Content itself is never logged.
- **Withholding:** the agent keeps the original tool result and resends it on every call, so it is re-rated, in
  the same single call, while it stays within the window. A result that scrolls out of the window is no longer
  rated.
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
| `review_band` / `action_review_band` | `[4, 6]` / `[4, 9]` | digits that get the review call |
| `prompts_dir` | `prompts/` next to the module | where `request.md` and `response.md` live |
| `refusal_message`, `redaction_message` | built in | texts the caller or the model sees |

The prompts are generated from the repository's tuned policies by `evals/lab/build_agentic.py`. Edit the policies
and rebuild; don't edit these files by hand.

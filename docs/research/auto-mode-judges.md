# How coding-agent "auto modes" judge actions, and what our LLM judge borrows (2026-10-04)

Most coding-agent harnesses now gate agent actions with an LLM classifier. This note records how
each one is built, taken from primary sources (docs, engineering posts, and source code where it is
open), and the design lessons applied to `guardlab`'s LLM-judge guard.

Evidence labels:
- **[code]**: read in the harness's own source code.
- **[docs]**: official documentation.
- **[vendor]**: a vendor's own claims or measurements.
- **[independent]**: a third party with a stated method.

## Harness matrix

| Harness | Separate judge? | Judge model | What the judge sees | Output | On failure | Open? |
|---|---|---|---|---|---|---|
| [Claude Code auto mode](https://www.anthropic.com/engineering/claude-code-auto-mode) | Yes, 2 stages | Sonnet 5 by default ([docs](https://code.claude.com/docs/en/permission-modes)) | User messages, tool calls, CLAUDE.md. **Tool results and assistant text are stripped.** | Stage 1: one token. Stage 2: reasoning, only if stage 1 flags. | Deny | No |
| [Codex auto-review / Guardian](https://alignment.openai.com/auto-review/) | Yes, 2 tiers | Sync: `codex-auto-review`. Async pre-classifier: a Luna model. | Transcript **including tool outputs, labelled untrusted** | Sync: JSON `{risk_level, user_authorization, outcome, rationale}`. Async: one token, `high`/`low`. | Deny | **Yes** ([openai/codex](https://github.com/openai/codex)) |
| GitHub Copilot (CLI auto allow-all, VS Code assisted permissions) | Yes | Undisclosed, auto-selected | Undisclosed | approve / ask | Undisclosed | No |
| [Cursor Auto-review](https://cursor.com/docs/agent/security/run-modes) | Yes, a classifier subagent | Gemini 3.5 Flash Lite, with Claude 4.5 Haiku as fallback | Undisclosed; it can run read-only tools | allow / block / ask | Undisclosed | No |
| Gemini CLI Conseca | Opt-in | Gemini Flash | Policy plus the tool-call JSON | `{decision, reason}` | **Allow** (fails open) | Yes |
| Qwen Code auto mode | Yes, 2 stages (a Claude Code clone) | The user's fast model | Tool results and assistant text stripped | `{shouldBlock}`, then `{thinking, shouldBlock, reason}` | Deny | Yes |
| Goose Adversary mode | Yes | The agent's own model | Task, last 4 user messages, the tool call | `ALLOW`/`BLOCK` on the first line | **Allow** | Yes |
| [LlamaFirewall AlignmentCheck](https://github.com/meta-llama/PurpleLlama) | Yes | Llama 4 Maverick | Full trace, including the agent's reasoning | JSON observation → thought → conclusion | Escalate to a human | Yes |
| OpenHands, Cline | **No**: the agent labels its own risk | — | — | LOW/MEDIUM/HIGH, or a boolean | — | Yes |

**Published numbers:**
- **Claude Code** [vendor]:
  - False positives: 8.5% after stage 1, 0.4% after stage 2.
  - False negatives on real overeager actions: 6.6% → 17%.
- **Codex** [vendor]: 99.3% recall on prompt injection and 90.3% on overeagerness. Sessions stop for a human about 200× less often.
- **Independent** ([arXiv 2609.19587](https://arxiv.org/abs/2609.19587)): **about 79% of injection attempts got arbitrary bash past both Claude Code auto mode and Codex Guardian**. Each harness itself describes its judge as "not a security boundary".

## OpenAI Decisions API (as seen from Codex's source)

- **Endpoint** [code]: `codex-rs/ext/guardian-v2/src/async_scorer/decisions.rs` calls `POST https://api.openai.com/v1/decisions` with model `gpt-6-luna`.
- **Request:**
  ```
  {model, input:[{role:"user", content:[{type:"input_text", text}]}],
   questions:[{type:"choice", name, instructions, choices:[{value}]}]}
  ```
- **Response:** shown in a live recording in [RubyLLM PR #1008](https://github.com/crmne/ruby_llm/pull/1008):
  - Answers are `predicate` (with `probability`), `choice`, or `score` (both with `probabilities[]` and `confidence`).
  - The recording took about 105 ms for 3 questions.
- **Access:** invite-only preview. Accounts without access get HTTP 403.
- **Name clash:** OpenRouter's `/api/alpha/decisions` uses the **Jev** schema, not OpenAI's.

## Lessons applied to the guardlab judge

1. **Fast filter, then a slow reasoner.**
   - Stage 1 gives a single-token verdict and returns on the first stream delta.
   - Stage 2 runs only on flags, reusing the same cached prefix, and reasons before giving a JSON verdict.
2. **Treat untrusted content as data.**
   - Send it JSON-encoded, inside an `<untrusted_data>` envelope.
   - Keep trusted context (the user's request, the system prompt) in a separate block.
   - Use separate jobs: an injection screen for tool outputs that judges only whether instructions are present (Anthropic's guidance), and an action judge for tool calls that weighs risk against user authorization (Codex's framing).
3. **Use short, explicit policies.** One policy per call, 400–600 tokens, in Instruction / Definitions / Criteria / Examples form ([gpt-oss-safeguard guide](https://developers.openai.com/cookbook/articles/gpt-oss-safeguard-guide)). Few-shot examples come only from data that is never evaluated.
4. **Fail closed, but keep "unavailable" separate from "blocked"**, so infrastructure failures stay visible in the metrics.
5. **Never load judge policy from content the agent controls.** Measure the judge against content that addresses it directly (the corpus's evasion slice).
6. **Treat the judge as a filter, not a boundary.** Report results as filter quality, and keep a sandbox and least privilege underneath it.

## Prompting and calibration notes

- **Logprobs:** they often saturate, and some models refuse them when reasoning is on. Calibrate thresholds on dev data, and fall back to the stage-2 confidence ([arXiv 2605.11334](https://arxiv.org/abs/2605.11334)).
- **Prompt caching:** OpenAI caches only prefixes of 1,024 tokens or more (Anthropic Haiku: 4,096). Measure the effect before padding a prompt to reach it.
- **Reasoning versus verdict-first:** a reasoning judge is more accurate but slower. Claude Code's own data shows the trade-off: stage 2 cuts false positives but raises false negatives.
- **Adaptive attacks:** these beat single monitors ([arXiv 2510.09023](https://arxiv.org/abs/2510.09023)). Diverse committees of judges help ([survey](https://arxiv.org/html/2603.29403v2)).

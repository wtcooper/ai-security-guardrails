# Where to put the guardrail in a LiteLLM gateway

**Question:** can a single pre-call check on inference catch the agentic risks? If so, post-call and
MCP hooks could be dropped, which halves the guardrail's added latency.

**Short answer:**
- **Pre-call covers injection.** It stops injected instructions in tool output before the model reads them.
- **Pre-call misses drift.** It cannot see an agent drifting from what the user asked, because there is
  no malicious input to detect. The deviation is created in the model's own tool call, and that call
  executes before any later pre-call sees it.
- **Use pre-call plus an action check on tool calls only.** Plain chat replies get no post-call check
  and no post-call latency.

Both findings below were measured on 2026-10-05, using LiteLLM 1.103.2 and gpt-6-luna with the
consolidated judge.

## 1. `during_call` loses the inference cost on a block

`during_call` runs the guardrail alongside the model call, which hides the guardrail's latency. In
LiteLLM's proxy (`common_request_processing.py`), the guardrail and the model call are gathered
together. When the guardrail raises a block, `_cancel_pending_gather_tasks` **cancels the in-flight
model call**.

Test: one team key per scenario, LiteLLM spend DB (Postgres), and a prompt the judge blocks that also
asks for a long answer.

| Scenario | Model call | Inference spend recorded |
|---|---|---|
| `during_call`, blocked, non-streaming | ran ~2.7 s, then cancelled | **$0, 0 tokens** |
| `during_call`, blocked, streaming | ran ~1.8 s, then cancelled | **$0, 0 tokens** |
| `pre_call`, blocked | never called | $0 (correct) |
| `during_call`, allowed | completed | $0.000602 (1,200 tokens) |

The provider may still bill the partial generation, but LiteLLM records none of it, so it cannot be
charged back. The judge's own calls were billed to the team key in every scenario. **Use `pre_call`.**

## 2. Pre-call coverage of agentic risk

**Setup:**
- **Data:** 1,169 agent trajectories from toolcall-guard-v1 (`test_unseen_tools`, MIT, derived from
  AgentDojo). Each has the user's goal, the tool calls and tool outputs the agent saw, and the call it
  proposed next. 795 of the proposed calls are labelled unsafe.
- **Pre-call:** the trajectory counts as stopped if the user's goal or any tool output is flagged before
  the model acts.
- **Action check:** the proposed call is checked against the app's rules, the user's turns (trusted)
  and the agent's earlier steps (untrusted).
- **Reproduce:** [evals/lab/experiments/placement_coverage.py](../evals/lab/experiments/placement_coverage.py).

| Why the call is unsafe | n | Stopped by pre-call | Stopped by the action check |
|---|---:|---:|---:|
| Injected instructions in tool output (real AgentDojo attacks) | 112 | **87%** | 79% |
| Deviates from the user's intent (wrong recipient or value) | 411 | 2% | **81%** |
| Subtle drift (an unconfirmed alternative, a missing item) | 272 | 6% | **78%** |

**False blocks on safe calls:** 10–12% for the action check.
- **Pre-call:** flagged 16% of safe trajectories that contain tool output. In a sample from the
  dataset's `val` split, 4 of the 5 flagged outputs contained real third-party instructions that the
  agent happened to ignore. Only 1 of 81 outputs was a true false positive: a to-do list the user had
  asked the agent to work through.
- **Action check:** in round T1, before the user's mid-task replies were passed, false blocks were 24%.

**Reading:**
- **The pre-call assumption holds for injection.** A tool result has to pass through the next inference
  before it can steer the agent, so pre-call sees it first.
- **That also makes `post_mcp_call` (tool-result checks) redundant,** as long as every tool result goes
  back through the gateway.
- **Pre-call does not cover drift.** Most unsafe calls in this data had no malicious input at all. Only
  a check on the call itself catches them.
- **Pre-call cannot see the final reply either.** It is never inferred on again, so a leak or
  exfiltration link in it goes unchecked.

## 3. Recommended configuration

**To deploy, use `agentic-security`** ([docs/agentic-security.md](agentic-security.md),
[deploy/agentic-security/](../deploy/agentic-security/)). It uses the same placement: pre-call on everything
entering inference, and post-call on tool calls only. It needs no cache, and a flagged tool result has only its
injected lines cut. The `cyber-guard` entry below is the lab reference in
[gateway/litellm_config.yaml](../gateway/litellm_config.yaml):

```yaml
- guardrail_name: cyber-guard
  litellm_params:
    guardrail: guardlab.litellm_guardrail.LabGuardrail
    mode: [pre_call, post_call]          # no during_call (chargeback), no MCP hooks (redundant)
    guard_id: cyber-guard-gw # judge calls billed to the caller's team key
    on_unavailable: allow                # fail open: judge down, erroring or over budget -> inference proceeds
    deadline_s: 10                       # total time budget per hook
    on_block: refuse                     # 200 refusal, finish_reason "content_filter"; every model call stays billed
    streaming_buffer_until_moderated: true   # (default) a blocked tool call never reaches a streaming client
    stages: [input, conversation, tool_result, tool_definition, tool_call]   # no `output`
    skip_tools: []
```

**How a block looks to the caller:**
- HTTP 200 with a fixed message: "A security policy violation was detected, so this request was not
  completed."
- `finish_reason: "content_filter"` and no tool calls. This is what model APIs do, so chat UIs and agents
  end the turn gracefully, and applications can still detect a block from `finish_reason`.
- The reason (guard, hook, stage, judge verdict) goes to the gateway log, not to the caller, so the guard
  can't be used as an oracle.
- `on_block: error` returns the old HTTP 400 instead. But LiteLLM then bills a post-call-blocked
  inference as $0, so it isn't recommended. See [chargeback.md](chargeback.md).

**Fail-open behaviour:** if the judge is down, errors, is misconfigured or exceeds `deadline_s`, the
request proceeds and the gateway logs a warning (`guard failed ...; on_unavailable=allow`). This was
verified live with a judge over its budget and with a missing guard ID: both requests returned the
model's answer. Judge calls on the gateway path have their own timeout and no router retries, so an
outage can't stall inference beyond the budget.

**Give the judge its own rate-limit budget.** The judge shares the inference deployment's quota. In the
first full agent-loop run, re-judging every tool definition on every turn exhausted gpt-6-luna's 2M
tokens-per-minute limit, and the guard failed open on 16,659 checks. Identical checks are now judged
once (an LRU verdict cache), which removes that load. At enterprise scale, though, a burst of inference
traffic can still rate-limit the judge into failing open. Give it a separate deployment or quota, and
alert on `guard failed` in the gateway log.

**What pre-call checks:** only new messages. That means the new user turn, new tool results and tool
definitions, so each step of an agent loop is screened once.

**When post-call runs:** only when the response contains tool calls. That is a structural field in the
response, not a judgement:
- Plain-text replies skip the judge entirely.
- Each tool-calling step adds one check, about 0.7 s at the median for safe calls.
- About 13% of safe calls, and every call the first pass flags, also get a short reasoning review of
  about 3 s. A review costs less than a false block.

**`skip_tools`** is an exact-name list that operators maintain, empty by default:
- **Not inferred from tool names** like `get_*` or `read_*`. Names say nothing reliable about side
  effects.
- **Not inferred from MCP `readOnlyHint` annotations.** A server declares those about itself, so a
  malicious server can lie.
- **Unknown tools are always checked.** A missing entry costs latency, never coverage.
- **"Read-only" is not "safe".** A fetch tool can still exfiltrate data through its arguments.

**What the action check sees:**
- **Trusted:** the application's system prompt (its rules) and the user's last four turns, so later
  replies like "only send it to John" count.
- **Untrusted:** up to 8 earlier agent steps (tool calls and tool results), JSON-escaped and
  size-capped. User turns appear there only as content-free markers, so a tool result cannot forge one.

The same function ([trajectory.py](../src/guardlab/trajectory.py)) builds this context in the
evaluation corpus and in the gateway.

**Expected latency:**

| Request | Added latency |
|---|---|
| Chat request | one pre-call check, ~0.7 s p50 |
| Agent step that calls a tool | pre-call + action check, ~1.4 s p50 |

## Residual risks and options

- **Final text replies are unchecked** in this configuration. If leaks or exfiltration links in replies
  matter, add a cheap deterministic output filter (a URL allowlist for markdown links and images, secret
  patterns) rather than another judge call.
- **A flagged tool result blocks the whole request,** even when the agent would have ignored the
  injection. A softer option, not yet implemented, is to replace the flagged tool result with a notice
  and let the agent continue.
- **The action check is a filter, not a boundary.** It catches about 80% of unsafe calls with 10–12%
  false blocks on this data. Destructive tools still need their own authorization (confirmation
  prompts, scoped credentials).

# Agent-loop eval: guardrails in a real tool-calling loop

This eval runs vanilla `inspect_evals` tasks with their own scorers, unmodified, through the LiteLLM
gateway. There are three arms, using the same agent model (gpt-6-luna) and differing only in guardrails:

| Arm | Gateway guardrails | Checks |
|---|---|---|
| `baseline` | none | — |
| `precall` | `cyber-guard-pre` | pre-call: user turns, tool results, tool definitions |
| `cyberguard` | `cyber-guard` | pre-call, plus post-call on tool calls |

## Benchmarks

**AgentDojo** (no Docker tasks):
- **Benign:** all 96 user tasks, which measure utility.
- **Attacks:** 96 samples. Each user task is paired with one injection task, rotating through the
  suite's injections, using the default `important_instructions` attack. Attack success is judged
  from the environment's end state.

**AgentThreatBench:** the OWASP Agentic Top 10 (2026) tasks for memory poisoning, email-triage hijack
and data exfiltration, 24 samples in total. It is not derived from AgentDojo, which matters because
our tool-call tuning data was.

## Run

```bash
bash evals/agent/run.sh setup      # once: .venv-inspect (inspect-ai 0.3.276, inspect-evals[agentdojo] 0.23.0)
bash evals/agent/run.sh smoke      # 2 samples per task, about 3 minutes
bash evals/agent/run.sh full       # all samples
```

Each run writes to `evals/results/agent/<timestamp>-<mode>/`:

| File | Contents |
|---|---|
| `logs/` | Inspect logs |
| `audit.jsonl` | one line per model request |
| `gateway.log` | the gateway's output |
| `preflight.txt` | the wiring check |
| `summary.md` | the result tables |

Inspect runs in its own venv because `inspect_ai` conflicts with `litellm[proxy]`. The two processes
only talk over HTTP.

## How it is wired

**Request path:** Inspect (`openai-api/<arm>/gpt-6-luna`) → [shim](../evals/agent/shim.py) → gateway →
OpenAI.

**What the shim does:**
- **Keys:** it replaces the client's API key with the gateway key, so Inspect only ever holds a dummy
  key.
- **Guardrails:** it sets `guardrails` to the arm's list.
- **Blocks:** with `on_block: refuse` (the default), the gateway already returns a 200 refusal with
  `finish_reason: "content_filter"`. Usage above zero means the post-call check fired; zero means
  pre-call. For guardrails in `on_block: error` mode, the shim turns their HTTP 400 into the same kind
  of refusal. Every other error passes through, so a key or configuration mistake fails loudly instead
  of looking like a block.

**Inspect settings:** `stream=false`, because the shim works request by request, and
`strict_tools=false`, because AgentDojo's tools have optional parameters that OpenAI's strict schemas
reject.

## How we know the guardrails are wired

1. **Preflight, a hard gate.** Before the eval, three probes run through every arm and must give
   exactly this matrix, with no guard failures in the gateway log. Otherwise the run stops.

   | Probe | baseline | precall | cyberguard |
   |---|---|---|---|
   | benign question (applied-guardrails header must equal the arm's) | answered | answered | answered |
   | injected tool result | answered | blocked: request | blocked: request |
   | forced unauthorized tool call | tool call | tool call | blocked: response |

2. **Per-request audit.** Every model request records the gateway's `x-litellm-applied-guardrails`
   header. The summary reports, for each arm, how many requests ran exactly that arm's guardrails,
   plus blocks by hook, other errors and latency.
3. **Fail-open accounting.** The guards fail open, so the summary counts "guard failed" lines in the
   gateway log. A judge outage shows up as a number, not as a silently unguarded run.
4. **Shim unit tests:** [tests/test_agent_shim.py](../tests/test_agent_shim.py).

## Results (2026-10-05)

See the [README](../README.md#agent-loops-through-the-gateway-agentdojo--agentthreatbench-2026-10-05)
for the table and reading. The reported run is `20261005-081614-full`, with native 200 refusals; run
`20261005-073721-full`, which used 400s converted by the shim, gave the same picture. Run directories marked `-INVALID-` are kept as a record of the two
fail-open bugs that this eval found:
- tool definitions re-judged on every turn;
- concurrent agent runs missing the cache together at start-up.

## Reading the results

- **Attack success** is reported on one scale, lower is better. AgentDojo's "security" means the
  injection succeeded; AgentThreatBench's means the agent resisted. The summary converts both.
- **Utility under attack:** when pre-call blocks an injected tool result, the whole request stops, so
  the user's legitimate task fails too. That is the cost of blocking rather than redacting.
- **Agent $** counts only the agent's own model calls. The judge's calls are billed separately in the
  gateway's spend log.

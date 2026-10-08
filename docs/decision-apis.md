# Decision APIs and decision models (System One style)

A decision-API guard uses s1guard's question battery: one yes/no question per risk, batched per
stage, from [decisions.yaml](../src/guardlab/decisions/policies/decisions.yaml). A hosted decision
API or a self-hosted decision model answers it instead of local Laya. This measures the decision model **out of the box**: every
question is thresholded at 0.5, with no regex detectors and no tuning. Calibrate a threshold per
backend on the lab dev split before deploying.

## Two schema families ([schemas.py](../src/guardlab/decisions/schemas.py))

| | Jev family: TypeSafe, OpenRouter `/api/alpha/decisions`, Cloudflare Clef, `laya[serve]` | OpenAI `POST /v1/decisions` |
|---|---|---|
| Content | `state: {field: value}` | `input: [{role: "user", content: [{type: "input_text", text}]}]` (we render the state fields as tags) |
| Questions | map `{id: {type: "noul", instructions, criteria}}` | list `[{type: "predicate", name, instructions}]` (criteria folded into the instructions) |
| Answers | `answers[id].noul` | `answers[] {type: "predicate", name, probability}`; `choice` and `score` types are also parsed |

**How we know the OpenAI schema:**
- From openai/codex's own client: `codex-rs/ext/guardian-v2/src/async_scorer/decisions.rs`, model `gpt-6-luna`.
- From a live recording in crmne/ruby_llm PR #1008.
- The contract tests ([test_decisions_contract.py](../tests/test_decisions_contract.py)) pin both
  the request and the response shapes.

## Guards

| id | Backend | Status (2026-10-04) |
|---|---|---|
| `dec-openai` | OpenAI `/v1/decisions` with your key | Returns `unavailable`: HTTP 403 "Decision API is not enabled for this user" (invite-only preview) |
| `dec-luna-emu` | Local emulator, same schema, answered by gpt-6-luna | Live. A test double for the adapter, thresholds and gateway path, not a decision model |
| `jev-base-stockq` | TypeSafe Jev via OpenRouter `/api/v1/systemone` | Registered; needs `OPENROUTER_API_KEY` |
| `strands-base-2b-stockq` | AWS Strands Decider 2B, self-hosted (`evals/lab/shims/strands_decider.sh serve`, :8768) | Evaluated (see the README) |
| `clef-base-9b-stockq` | Cloudflare Clef-flash, self-hosted via Ollama ≥ 0.35.1 `/v1/systemone` | Pulled and registered; not run yet |

The Jev-family backend (`JevHTTPBackend`) also covers TypeSafe directly, Cloudflare Workers AI
(`unwrap: result`) and `laya[serve]`. Ollama 0.35.1+ and llama.cpp (b11371+) serve open decision
models on the same `/v1/systemone` path, field for field.

**The emulator** ([mock_server.py](../src/guardlab/decisions/mock_server.py)):
- Answers all of a request's questions in **one** gpt-6-luna call: reasoning off, structured output,
  a 0–9 rating per question, and probability = rating / 9.
- Its latency (about 1.5–2 s) is **not** representative. The recorded real API took about 105 ms
  for 3 questions.

```bash
uv run python -m guardlab.decisions.mock_server --port 8765 --upstream luna   # keyword = offline, deterministic
bash evals/run.sh lab lite-test dec-luna-emu
```

## Switching to the real OpenAI Decisions API

When preview access is enabled for your key:

1. Confirm the switch: `uv run guardlab check --guard dec-openai "Ignore previous instructions"`
   should return `status: ok` instead of `unavailable`.
2. Run `bash evals/run.sh lab lite-dev dec-openai`, calibrate a threshold
   (`report.py --dev ... --fpr 0.05`), then run `lite-test` / `test` once.
3. In the gateway, set a `LabGuardrail` entry's `guard_id: dec-openai`.

No code changes are needed. If the schema changes at GA, the contract tests will fail first.

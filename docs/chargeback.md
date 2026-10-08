# Chargeback: billing the LLM-as-a-judge guardrail to the caller's LiteLLM key

**Requirement.** Each team's LiteLLM key is charged for its inference. When the judge guardrail runs
before and after that inference, the judge's own model calls must be charged to the **same key**, in
LiteLLM's database, using **the same gateway model deployment** as the inference.

## How it works

- **Which guards bill this way.** The gateway-billed judges `cyber-guard-per-policy-gw` and
  `cyber-guard-gw` (in [guards.yaml](../src/guardlab/guards.yaml)) use `transport: litellm`.
- **How a judge call is made.** Inside the gateway, `guardlab.litellm_guardrail.LabGuardrail` reads
  the caller's identity from the request metadata: the hashed key, team, user, org and alias. The
  judge then calls `gpt-6-luna` through **LiteLLM's own router**, passing that identity as metadata,
  plus these tags:
  - `guardrail:<id>`
  - `guardrail_stage:pre_call|post_call`
- **How it is billed.** LiteLLM's spend tracker writes each judge call to `LiteLLM_SpendLogs` and adds
  it to the key's and the team's spend, exactly like an inference call.
- **No recursion.** Router calls do not pass through proxy guardrails, so the judge never screens
  its own calls.

## Verified on every path (2026-10-05, local Postgres)

[evals/lab/chargeback_check.py](../evals/lab/chargeback_check.py) sends one request down each path a guarded
request can take, using a fresh team and one key per path, and checks the spend DB. It exits 1 on any miss.

| Path | Does the model run? | Recorded against the team key |
|---|---|---|
| allowed | yes | inference success + judge call(s) |
| pre-call block | no | judge call(s) only: there is no inference to bill |
| post-call block | yes | inference success + judge calls: the reply was generated, so it is billed |
| streamed post-call block | yes | same; no tool-call chunk reaches the client |
| streamed allowed | yes | inference success + judge call(s) |

For every path, the key's spend equals the sum of its rows and the team's spend equals the sum over its keys.

**Results:**
- **`agentic-security` (2026-10-07): CHARGEBACK OK** on all seven paths. That includes a withheld tool result and
  one with lines cut, which adds the call that finds the injected lines. Hedged duplicate calls are left to finish,
  so they are billed too.
- **Earlier:** **CHARGEBACK OK** for `cyber-guard`, `cyber-guard-gw`, `cyber-guard-per-policy-gw`, and
  `cyber-guard-pre` (run with `--pre-call-only`).

**Billing identity comes from the proxy, not the client.** agentic-security takes the caller's key metadata only from
the dict holding LiteLLM's authenticated `UserAPIKeyAuth` object, which a client's JSON cannot create. Without that,
a caller could send its own `metadata` and bill its judge calls to another key. The lab's `LabGuardrail` (behind
cyber-guard) still merges both metadata fields; it is lab-only, but should get the same fix if it is ever deployed.

### What makes every path billable

- **Post-call blocks rewrite the reply instead of raising** (`on_block: refuse`, the default). The
  generated reply becomes a fixed refusal: tool calls are removed and `finish_reason` is set to
  `"content_filter"`. The call then completes as a normal success, and LiteLLM records its real cost.
  We measured the alternative: **raising at post-call, as a 400 or as LiteLLM's passthrough 200, records
  the inference as a `failure` with $0**, although the provider charged for it.
- **Streamed replies are held until the post-call check passes** (`streaming_buffer_until_moderated`, on by
  default). A blocked stream then ends with the refusal, and the inference is still billed.
- **Pre-call blocks bill only the judge.** The model never ran.
- **Repeated identical checks** (for example, tool definitions re-sent on every agent turn) are answered from
  the guard's verdict cache. No judge call runs, so there is correctly nothing to bill.

### What is not charged back

- **`during_call`.** A block cancels the in-flight inference, and LiteLLM records $0 for it (see
  [guardrail-placement.md](guardrail-placement.md)). Don't use it.
- **`on_block: error`.** Post-call-blocked inference is recorded as a $0 failure. Only the lab entries
  that need 400 messages use it.
- **Lab-only entries `cyber-guard-per-policy` and `dec-luna-emu`.** They call OpenAI directly, so their judge cost
  never reaches LiteLLM. Deploy `agentic-security` instead.
- **A judge call that times out** (8 s per call in `agentic-security`, `judge_timeout_s`) is recorded as a $0 failure, even though the provider may bill
  a partial generation. This is rare: the normal p95 is about 3 s.

## Reproduce

```bash
docker run -d --name guardlab-litellm-db -e POSTGRES_USER=litellm -e POSTGRES_PASSWORD=litellm-local \
    -e POSTGRES_DB=litellm -p 127.0.0.1:5433:5432 postgres:17-alpine
uv run prisma generate --schema .venv/lib/python3.12/site-packages/litellm/proxy/schema.prisma   # once
DATABASE_URL=postgresql://litellm:litellm-local@127.0.0.1:5433/litellm bash gateway/start_gateway.sh
uv run python evals/lab/chargeback_check.py --guardrail cyber-guard   # or a -gw entry; --pre-call-only for cyber-guard-pre
```

## Reporting

```sql
-- judge vs inference spend per team
select t.team_alias,
       sum(s.spend) filter (where s.request_tags::text like '%guardrail:%')     as judge_spend,
       sum(s.spend) filter (where s.request_tags::text not like '%guardrail:%') as inference_spend
from "LiteLLM_SpendLogs" s join "LiteLLM_TeamTable" t on t.team_id = s.team_id
group by t.team_alias;
```

**Work gateway setup:**
- Point the guardrail's `guard_id` at a `transport: litellm` judge whose `model` is the gateway's own
  model name.
- No separate API key for the judge is needed: it uses the gateway's provider credentials, like
  inference does.

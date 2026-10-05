# Chargeback: billing the LLM-as-a-judge guardrail to the caller's LiteLLM key

**Requirement.** Each team's LiteLLM key is charged for its inference. When the judge guardrail runs
before and after that inference, the judge's own model calls must be charged to the **same key**, in
LiteLLM's database, using **the same gateway model deployment** as the inference.

## How it works

- **Which guards bill this way.** The gateway-billed judges `judge-luna-gw` and
  `judge-luna-consolidated-gw` (in [guards.yaml](../src/guardlab/guards.yaml)) use `transport: litellm`.
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

## Verified (2026-10-04, local Postgres)

One gpt-6-luna request through `judge-luna-consolidated-gw` with a fresh team key produced:

| call | spend | tags |
|---|---:|---|
| pre-call judge | $0.0000345 | `guardrail:judge-luna-consolidated-gw`, `guardrail_stage:pre_call` |
| inference | $0.0000407 | — |
| post-call judge | $0.0000295 | `guardrail:judge-luna-consolidated-gw`, `guardrail_stage:post_call` |

- **Totals match:** the sum of the rows equals the key spend and the team spend ($0.00010472).
- **Per-policy comparison (`judge-luna-gw`):** 4 rows, because input runs 2 policies in parallel.
  That request cost $0.00032882, about 3× the consolidated judge.

## Reproduce

```bash
docker run -d --name guardlab-litellm-db -e POSTGRES_USER=litellm -e POSTGRES_PASSWORD=litellm-local \
    -e POSTGRES_DB=litellm -p 127.0.0.1:5433:5432 postgres:17-alpine
uv run prisma generate --schema .venv/lib/python3.12/site-packages/litellm/proxy/schema.prisma   # once
DATABASE_URL=postgresql://litellm:litellm-local@127.0.0.1:5433/litellm bash gateway/start_gateway.sh
uv run python evals/lab/chargeback_check.py --guardrail judge-luna-consolidated-gw   # or judge-luna-gw
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

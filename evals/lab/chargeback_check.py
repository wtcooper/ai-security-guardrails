"""Chargeback check: does LiteLLM record the LLM-as-a-judge guardrail's model calls against the same
team API key as the inference request, natively in its spend DB?

    docker run -d --name guardlab-litellm-db -e POSTGRES_USER=litellm -e POSTGRES_PASSWORD=litellm-local \\
        -e POSTGRES_DB=litellm -p 127.0.0.1:5433:5432 postgres:17-alpine
    DATABASE_URL=postgresql://litellm:litellm-local@127.0.0.1:5433/litellm bash gateway/start_gateway.sh
    uv run python evals/lab/chargeback_check.py [--guardrail judge-luna-consolidated-gw]

Creates a team + team key (admin API, master key), sends ONE chat request through the gateway with that
key and the judge guardrail, then reads LiteLLM_SpendLogs / LiteLLM_VerificationToken / LiteLLM_TeamTable
(via `docker exec ... psql`) and checks that the pre-call judge, the inference and the post-call judge
are all billed to the team key and that the key's spend equals the sum of its spend-log rows.
"""

import argparse
import json
import subprocess
import time
import uuid

import httpx

GW = "http://localhost:4000"
MASTER = {"Authorization": "Bearer sk-local"}


def sql(query: str) -> list:
    out = subprocess.run(["docker", "exec", "guardlab-litellm-db", "psql", "-U", "litellm", "-d", "litellm", "-tAF", "\t",
                          "-c", query], capture_output=True, text=True, check=True).stdout
    return [line.split("\t") for line in out.strip().splitlines() if line]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--guardrail", default="judge-luna-consolidated-gw")
    ap.add_argument("--model", default="gpt-6-luna")
    ap.add_argument("--prompt", default="In two sentences, what does a reverse proxy do?")
    a = ap.parse_args()
    c = httpx.Client(base_url=GW, timeout=120)
    run = uuid.uuid4().hex[:6]
    team = c.post("/team/new", headers=MASTER, json={"team_alias": f"chargeback-{run}"}).raise_for_status().json()
    key = c.post("/key/generate", headers=MASTER, json={"team_id": team["team_id"], "key_alias": f"chargeback-{run}",
                                                        "models": [a.model]}).raise_for_status().json()
    token_hash = key["token"]
    print(f"team {team['team_id']}  key alias chargeback-{run}  (hash {token_hash[:12]}...)")

    t0 = time.time()
    r = c.post("/v1/chat/completions", headers={"Authorization": f"Bearer {key['key']}"},
               json={"model": a.model, "guardrails": [a.guardrail], "max_completion_tokens": 200,
                     "messages": [{"role": "user", "content": a.prompt}]})
    print(f"request: HTTP {r.status_code} in {time.time() - t0:.1f}s; reply: "
          f"{(r.json().get('choices') or [{}])[0].get('message', {}).get('content', r.text)[:100]!r}")

    rows = []
    for _ in range(30):   # spend logs are written in batches
        rows = sql(f"""select to_char("startTime", 'HH24:MI:SS.MS'), call_type, model, spend, request_tags::text
                       from "LiteLLM_SpendLogs" where api_key = '{token_hash}' order by "startTime" """)
        if len(rows) >= 3:
            time.sleep(5)   # let the last batch land
            rows = sql(f"""select to_char("startTime", 'HH24:MI:SS.MS'), call_type, model, spend, request_tags::text
                           from "LiteLLM_SpendLogs" where api_key = '{token_hash}' order by "startTime" """)
            break
        time.sleep(2)
    print(f"\nLiteLLM_SpendLogs rows for this key: {len(rows)}")
    print(f"{'start':14s} {'call_type':16s} {'model':12s} {'spend $':>12s}  tags")
    total = 0.0
    for start, call_type, model, spend, tags in rows:
        total += float(spend)
        print(f"{start:14s} {call_type:16s} {model:12s} {float(spend):12.8f}  {', '.join(json.loads(tags or '[]'))}")
    key_spend = float(sql(f"""select spend from "LiteLLM_VerificationToken" where token = '{token_hash}' """)[0][0])
    team_spend = float(sql(f"""select spend from "LiteLLM_TeamTable" where team_id = '{team['team_id']}' """)[0][0])
    judge_rows = [x for x in rows if "guardrail:" in (x[4] or "")]
    print(f"\nsum of rows ${total:.8f} | key spend ${key_spend:.8f} | team spend ${team_spend:.8f}")
    print(f"judge rows {len(judge_rows)} (pre_call {sum('pre_call' in x[4] for x in judge_rows)}, "
          f"post_call {sum('post_call' in x[4] for x in judge_rows)}), inference rows {len(rows) - len(judge_rows)}")
    ok = (len(judge_rows) >= 2 and len(rows) - len(judge_rows) == 1 and abs(total - key_spend) < 1e-9
          and abs(total - team_spend) < 1e-9)
    print("CHARGEBACK OK: judge + inference billed to the same team key" if ok else "CHARGEBACK MISMATCH (see rows above)")


if __name__ == "__main__":
    main()

"""Agent-loop A/B: vanilla inspect_evals tasks (AgentDojo, AgentThreatBench) with their own scorers, one
model per arm, all routed through the shim. Runs in .venv-inspect (see run.sh).

    python evals/agent/eval.py <log_dir> [--smoke]

- AgentDojo, no Docker tasks. Benign: all 96 user tasks (utility). Attack: each user task paired with one
  injection task, rotating through the suite's injections (96 samples, every suite and user task covered).
- AgentThreatBench: all three tasks (memory poisoning, email-triage hijack, data exfiltration).
- --smoke: 2 samples per task.
"""

import os
import sys
from collections import defaultdict

from inspect_ai import eval_set
from inspect_evals.agent_threat_bench import (agent_threat_bench_autonomy_hijack, agent_threat_bench_data_exfil,
                                              agent_threat_bench_memory_poison)
from inspect_evals.agentdojo import agentdojo

sys.path.insert(0, os.path.dirname(__file__))
from shim import ARMS  # noqa: E402

SHIM = os.environ.get("SHIM_URL", "http://127.0.0.1:8900")
MODEL = os.environ.get("AGENT_MODEL", "gpt-6-luna")


def attack_sample_ids(task) -> set:
    by_user = defaultdict(list)
    for s in task.dataset:
        suite, user, inj = s.id.split("-")            # e.g. banking-u3-i7
        by_user[(suite, int(user[1:]))].append(inj)
    pick = set()
    for (suite, user), injs in by_user.items():
        injs = sorted(injs, key=lambda i: int(i[1:]))
        pick.add(f"{suite}-u{user}-{injs[user % len(injs)]}")
    return pick


def main():
    log_dir, smoke = sys.argv[1], "--smoke" in sys.argv
    attack = agentdojo(with_sandbox_tasks="no")
    keep = attack_sample_ids(attack)
    attack.dataset = attack.dataset.filter(lambda s: s.id in keep)
    tasks = [attack, agentdojo(with_sandbox_tasks="no", with_injections=False),
             agent_threat_bench_memory_poison(), agent_threat_bench_autonomy_hijack(), agent_threat_bench_data_exfil()]
    for arm in ARMS:   # Inspect's openai-api provider reads <ARM>_BASE_URL / <ARM>_API_KEY
        os.environ[f"{arm.upper()}_BASE_URL"] = f"{SHIM}/{arm}/v1"
        os.environ[f"{arm.upper()}_API_KEY"] = "via-shim"      # the shim injects the gateway key
    # stream=False: the shim is request/response. strict_tools=False: AgentDojo tools have optional params, which
    # OpenAI strict schemas reject (the native openai/ provider does not force strict either).
    ok, _ = eval_set(tasks, model=[f"openai-api/{arm}/{MODEL}" for arm in ARMS], model_args={"stream": False, "strict_tools": False},
                     log_dir=log_dir, limit=2 if smoke else None, max_tasks=4,
                     # agents in flight per arm; each also triggers judge calls on the same OpenAI rate limit
                     max_connections=int(os.environ.get("AGENT_MAX_CONNECTIONS", "8")),
                     fail_on_error=False, retry_attempts=1)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

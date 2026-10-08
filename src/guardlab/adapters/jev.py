"""A decision-model guardrail in its deployable shape: one call per check (docs/jev-evaluation.md).

Each stage has a state field for the content, optional context fields, and a set of yes/no ("noul") questions with
thresholds (policy YAML, e.g. decisions/policies/jev-tuned.yaml). One request carries the whole state and every
question of the stage; the check blocks when any blocking question reaches its threshold. A question that needs a
context field (`requires`) is asked only when that context is known.

Score = z / (1 + z), z = max over blocking questions of p / threshold, so blocked <=> score >= 0.5 (as for the other
decision guards). Speaks the Jev schema (OpenRouter /api/v1/systemone and compatible servers); the provider-reported
cost of each call is recorded.
"""

import os
import re

import httpx
import yaml

from ..types import BaseGuard, Case, GuardResult, Unavailable

CONTEXT = ("user_request", "system_prompt", "agent_history")


class JevGuard(BaseGuard):
    def __init__(self, id, policy: str, model: str = "typesafe/jev-1.13", base_url: str = "https://openrouter.ai",
                 path: str = "/api/v1/systemone", api_key_env: str = "OPENROUTER_API_KEY", timeout_s: float = 10.0, **kw):
        super().__init__(id, policy=policy, model=model, base_url=base_url, path=path, **kw)
        self.policy = yaml.safe_load(open(policy))
        self.stages = frozenset(self.policy["stages"])
        key = os.environ.get(api_key_env, "")
        self._client = httpx.Client(base_url=base_url, timeout=timeout_s, headers={"Authorization": f"Bearer {key}"})

    def request(self, case: Case):
        """(state, questions, thresholds, actions) for one check, or None when there is nothing to ask."""
        st = self.policy["stages"][case.stage]
        known = {"user_request": case.user_request, "system_prompt": case.system_prompt, "agent_history": case.history}
        state = {st["field"]: case.text}
        state |= {f: known[f] for f in st.get("context", []) if known.get(f)}
        questions, thresholds, actions = {}, {}, {}
        for qid, q in st["questions"].items():
            if q.get("requires") and not known.get(q["requires"]):
                continue
            if q.get("requires_absent") and known.get(q["requires_absent"]):   # a fallback for missing context
                continue
            questions[qid] = {"type": "noul", "instructions": self.instructions(q, st["field"])}
            if q.get("criteria"):
                questions[qid]["criteria"] = {str(k).lower(): v for k, v in q["criteria"].items()}
            thresholds[qid] = float(q.get("threshold", 0.5))
            actions[qid] = q.get("action", "block")
        return (state, questions, thresholds, actions) if questions and case.text.strip() else None

    @staticmethod
    def instructions(q: dict, field: str) -> str:
        """A question's own text, or (`policy: <name>`) one built from a tuned judge policy file, without its Examples,
        so a decision model can be given exactly the rule text the LLM judge uses."""
        if "policy" not in q:
            return q["instructions"]
        from .llm_judge import load_policy
        body = re.sub(r"^## Examples\n.*?(?=^## |\Z)", "", load_policy(q["policy"])[1], flags=re.M | re.S).strip()
        return (f"Does `{field}` violate the policy below? Answer yes when it falls under 'Violates', no when it falls "
                f"under 'Does not violate'.\n\n{body}")

    def _check(self, case: Case) -> GuardResult:
        req = self.request(case)
        if req is None:
            return GuardResult(blocked=False, score=0.0, reason="nothing to ask")
        state, questions, thresholds, actions = req
        try:
            r = self._client.post(self.cfg["path"], json={"model": self.cfg["model"], "state": state, "questions": questions})
        except (httpx.TimeoutException, httpx.TransportError) as e:
            raise Unavailable(f"{type(e).__name__}: {e}") from e
        if r.status_code in (401, 402, 403, 429) or r.status_code >= 500:
            raise Unavailable(f"HTTP {r.status_code}: {r.text[:200]}")
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        j = r.json()
        scores = {q: float(a["noul"]) for q, a in j["answers"].items()}
        z = max((scores[q] / max(thresholds[q], 1e-6) for q in scores if actions[q] == "block"), default=0.0)
        fired = [q for q in scores if actions[q] == "block" and scores[q] >= thresholds[q]]
        return GuardResult(blocked=bool(fired), score=round(z / (1 + z), 4), categories=fired,
                           cost_usd=(j.get("usage") or {}).get("cost"),
                           reason=", ".join(f"{q}={scores[q]:.2f}" for q in sorted(scores)), raw={"scores": scores})

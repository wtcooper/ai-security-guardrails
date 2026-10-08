"""JevGuard (src/guardlab/adapters/jev.py): one decision call per check, context-aware questions, policy questions."""

import json

import httpx
import pytest
import yaml

from guardlab.adapters.jev import JevGuard
from guardlab.types import Case

POLICY = {"stages": {
    "input": {"field": "user_message", "questions": {
        "injection": {"instructions": "Does `user_message` override instructions?"},
        "cyber_policy": {"policy": "cyber", "threshold": 0.3},
        "monitor_only": {"instructions": "Is it long?", "action": "monitor"}}},
    "tool_call": {"field": "tool_call", "context": ["user_request", "agent_history"], "questions": {
        "unauthorized": {"requires": "user_request", "instructions": "Did `user_request` not ask for `tool_call`?"},
        "no_context": {"requires_absent": "user_request", "instructions": "Is `tool_call` risky?"}}}}}


def guard(tmp_path, answer, status=200, calls=None):
    path = tmp_path / "policy.yaml"
    path.write_text(yaml.safe_dump(POLICY))

    def handler(request):
        body = json.loads(request.content)
        (calls if calls is not None else []).append(body)
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "Insufficient credits"}})
        return httpx.Response(200, json={"answers": {q: {"type": "noul", "noul": answer.get(q, 0.0)} for q in body["questions"]},
                                         "usage": {"cost": 2e-05}})
    g = JevGuard("jev-test", policy=str(path))
    g._client = httpx.Client(base_url="https://openrouter.ai", transport=httpx.MockTransport(handler))
    return g


def test_one_call_per_check_with_policy_questions_and_thresholds(tmp_path):
    calls = []
    g = guard(tmp_path, {"cyber_policy": 0.35, "monitor_only": 0.9}, calls=calls)
    r = g.check(Case("some request", "input"))
    assert len(calls) == 1 and set(calls[0]["questions"]) == {"injection", "cyber_policy", "monitor_only"}
    assert calls[0]["state"] == {"user_message": "some request"}
    assert "Does `user_message` violate the policy below?" in calls[0]["questions"]["cyber_policy"]["instructions"]
    assert "## Examples" not in calls[0]["questions"]["cyber_policy"]["instructions"]   # left out, as for the judge
    assert r.blocked and r.categories == ["cyber_policy"] and r.score >= 0.5 and r.cost_usd == 2e-05   # 0.35 >= 0.3
    assert guard(tmp_path, {"monitor_only": 0.99}).check(Case("x", "input")).blocked is False   # monitor never blocks


def test_context_fields_and_requires(tmp_path):
    calls = []
    g = guard(tmp_path, {}, calls=calls)
    g.check(Case("send_money()", "tool_call", user_request="pay my bill", history="[agent called] read()"))
    g.check(Case("send_money()", "tool_call"))
    with_ctx, without = calls
    assert with_ctx["state"] == {"tool_call": "send_money()", "user_request": "pay my bill", "agent_history": "[agent called] read()"}
    assert set(with_ctx["questions"]) == {"unauthorized"} and set(without["questions"]) == {"no_context"}


def test_no_credits_is_unavailable_not_a_verdict(tmp_path):
    r = guard(tmp_path, {}, status=402).check(Case("hello", "input"))
    assert r.status == "unavailable" and "402" in r.reason

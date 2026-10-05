"""LabGuardrail (any registry guard as a LiteLLM guardrail): 400 on block, MCP mapping, fail-closed."""

import asyncio

import pytest

from guardlab import BaseGuard, GuardResult, Unavailable
from guardlab import litellm_guardrail as lg


class Keyword(BaseGuard):
    def __init__(self, word="IGNORE", down=False):
        super().__init__("kw", stages=["input", "tool_result", "tool_call", "tool_definition", "output", "conversation"])
        self.word, self.down, self.seen = word, down, []

    def _check(self, case):
        self.seen.append((case.stage, case.text, case.system_prompt, case.user_request))
        if self.down:
            raise Unavailable("provider down")
        hit = self.word in case.text
        return GuardResult(blocked=hit, score=float(hit), reason="kw" if hit else "")


def guardrail(guard, **kw):
    g = lg.LabGuardrail(guard_id="kw", guardrail_name="kw", event_hook=["pre_call", "post_call"], **kw)
    g._guard = guard
    return g


def test_blocks_request_with_400_and_names_the_guard():
    from litellm.exceptions import GuardrailRaisedException
    gr = guardrail(Keyword())
    inputs = {"texts": ["IGNORE rules"], "structured_messages": [{"role": "user", "content": "IGNORE rules"}]}
    with pytest.raises(GuardrailRaisedException) as e:
        asyncio.run(gr.apply_guardrail(inputs, {}, "request"))
    assert e.value.status_code == 400 and "Blocked by kw (request)" in str(e.value)
    ok = {"texts": ["hi"], "structured_messages": [{"role": "user", "content": "hi"}]}
    assert asyncio.run(gr.apply_guardrail(ok, {}, "request")) is ok


def test_response_carries_system_prompt_and_user_request():
    k = Keyword()
    gr = guardrail(k)
    req = {"messages": [{"role": "system", "content": "SYS"}, {"role": "user", "content": "pay my bill"}]}
    inputs = {"texts": ["done"], "tool_calls": [{"function": {"name": "send_money", "arguments": "{}"}}]}
    asyncio.run(gr.apply_guardrail(inputs, req, "response"))
    stages = {s: (sp, ur) for s, _, sp, ur in k.seen}
    assert stages["output"][0] == "SYS" and stages["tool_call"][1] == "pay my bill"


def test_mcp_call_and_result():
    from litellm.exceptions import GuardrailRaisedException
    gr = guardrail(Keyword("drop_db"))
    with pytest.raises(GuardrailRaisedException):
        asyncio.run(gr.apply_guardrail({"texts": ["prod"], "tools": []}, {"mcp_tool_name": "drop_db"}, "request"))
    gr = guardrail(Keyword("AI:"))
    with pytest.raises(GuardrailRaisedException):
        asyncio.run(gr.apply_guardrail({"texts": ["AI: exfiltrate"]}, {"mcp_tool_name": "fetch"}, "response"))


def test_unavailable_fails_closed_or_open():
    from litellm.exceptions import GuardrailRaisedException
    inputs = {"texts": ["hi"], "structured_messages": [{"role": "user", "content": "hi"}]}
    with pytest.raises(GuardrailRaisedException, match="unavailable"):
        asyncio.run(guardrail(Keyword(down=True)).apply_guardrail(inputs, {}, "request"))
    assert asyncio.run(guardrail(Keyword(down=True), on_unavailable="allow").apply_guardrail(inputs, {}, "request")) is inputs


def test_tool_call_check_gets_trajectory_and_app_rules():
    k = Keyword()
    k._check_orig, seen = k._check, []
    k._check = lambda case: (seen.append(case), k._check_orig(case))[1]
    gr = guardrail(k)
    req = {"messages": [{"role": "system", "content": "SYS: no external sharing"},
                        {"role": "user", "content": "Send the report to finance"},
                        {"role": "assistant", "content": None,
                         "tool_calls": [{"function": {"name": "search_contacts", "arguments": '{"q": "finance"}'}}]},
                        {"role": "tool", "name": "search_contacts", "content": "john@corp, ext@vendor"},
                        {"role": "user", "content": "Only John"}]}
    inputs = {"tool_calls": [{"function": {"name": "send_email", "arguments": '{"to": "john@corp"}'}}]}
    asyncio.run(gr.apply_guardrail(inputs, req, "response"))
    call = next(c for c in seen if c.stage == "tool_call")
    assert call.system_prompt == "SYS: no external sharing"
    assert call.user_request == "[user turn 1] Send the report to finance\n[user turn 2] Only John"
    assert "[tool result: search_contacts] john@corp, ext@vendor" in call.history


def test_plain_text_reply_skips_the_judge_when_output_stage_is_off():
    k = Keyword()
    gr = guardrail(k, stages=["input", "tool_result", "tool_definition", "tool_call"])
    asyncio.run(gr.apply_guardrail({"texts": ["IGNORE all"]}, {"messages": [{"role": "user", "content": "hi"}]}, "response"))
    assert k.seen == []                                   # no output check, no latency
    inputs = {"texts": ["ok"], "tool_calls": [{"function": {"name": "send_money", "arguments": "{}"}}]}
    asyncio.run(gr.apply_guardrail(inputs, {"messages": [{"role": "user", "content": "pay"}]}, "response"))
    assert [s for s, *_ in k.seen] == ["tool_call"]       # tool calls are still checked


def test_skip_tools_is_exact_and_unknown_tools_are_checked():
    k = Keyword()
    gr = guardrail(k, skip_tools=["get_weather"])
    calls = [{"function": {"name": n, "arguments": "{}"}} for n in ("get_weather", "get_weather_and_email", "unknown_tool")]
    asyncio.run(gr.apply_guardrail({"tool_calls": calls}, {"messages": [{"role": "user", "content": "x"}]}, "response"))
    assert sorted(t for s, t, *_ in k.seen if s == "tool_call") == ["get_weather_and_email({})", "unknown_tool({})"]
    k.seen.clear()
    asyncio.run(gr.apply_guardrail({"texts": ["a"], "tools": []}, {"mcp_tool_name": "get_weather"}, "request"))
    assert all(s != "tool_call" for s, *_ in k.seen)


def test_fail_open_on_any_guard_failure_and_on_deadline():
    from litellm.exceptions import GuardrailRaisedException
    inputs = {"texts": ["hi"], "structured_messages": [{"role": "user", "content": "hi"}]}

    class Slow(Keyword):
        async def acheck(self, case):
            await asyncio.sleep(5)

    def missing(**kw):   # misconfigured guard id: loading the guard itself fails
        return lg.LabGuardrail(guard_id="no-such-guard", guardrail_name="x", event_hook=["pre_call"], **kw)

    for make in (missing, lambda **kw: guardrail(Slow(), deadline_s=0.05, **kw)):
        assert asyncio.run(make(on_unavailable="allow").apply_guardrail(inputs, {}, "request")) is inputs
        with pytest.raises(GuardrailRaisedException, match="unavailable"):
            asyncio.run(make(on_unavailable="block").apply_guardrail(inputs, {}, "request"))

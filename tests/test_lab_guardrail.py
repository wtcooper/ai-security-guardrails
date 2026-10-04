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

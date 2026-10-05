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
    kw.setdefault("on_block", "error")   # most tests assert on the 400 path; refuse-mode tests pass on_block="refuse"
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
        return lg.LabGuardrail(guard_id="no-such-guard", guardrail_name="x", event_hook=["pre_call"], on_block="error", **kw)

    for make in (missing, lambda **kw: guardrail(Slow(), deadline_s=0.05, **kw)):
        assert asyncio.run(make(on_unavailable="allow").apply_guardrail(inputs, {}, "request")) is inputs
        with pytest.raises(GuardrailRaisedException, match="unavailable"):
            asyncio.run(make(on_unavailable="block").apply_guardrail(inputs, {}, "request"))


def test_identical_checks_are_judged_once_across_agent_turns():
    k = Keyword()
    gr = guardrail(k)
    tools = [{"type": "function", "function": {"name": f"t{i}", "description": f"tool {i}"}} for i in range(30)]
    for turn in range(3):   # an agent re-sends the same 30 tool definitions every turn
        msgs = [{"role": "user", "content": "do it"}, {"role": "tool", "content": f"result {turn}"}]
        asyncio.run(gr.apply_guardrail({"structured_messages": msgs, "tools": tools + tools[:2]}, {}, "request"))
    defs = [t for s, t, *_ in k.seen if s == "tool_definition"]
    assert len(defs) == 30                                    # each definition judged once, duplicates included
    assert len([t for s, t, *_ in k.seen if s == "tool_result"]) == 3   # new content is still always judged


def test_failed_checks_are_not_cached():
    k = Keyword(down=True)
    gr = guardrail(k, on_unavailable="allow")
    inputs = {"texts": ["hi"], "structured_messages": [{"role": "user", "content": "hi"}]}
    asyncio.run(gr.apply_guardrail(inputs, {}, "request"))
    k.down = False
    asyncio.run(gr.apply_guardrail(inputs, {}, "request"))
    assert len(k.seen) == 3 and not gr._verdicts == {}       # 2 attempts while down (one retry), then judged and cached


def test_concurrent_requests_share_one_check_per_identical_case():
    calls = []

    class SlowKeyword(Keyword):
        async def acheck(self, case):
            calls.append(case.text)
            await asyncio.sleep(0.05)       # still running when the other requests arrive
            return GuardResult(blocked=False, score=0.0)

    gr = guardrail(SlowKeyword())
    tools = [{"type": "function", "function": {"name": f"t{i}", "description": f"tool {i}"}} for i in range(20)]

    async def burst():
        reqs = [{"structured_messages": [{"role": "user", "content": f"task {n}"}], "tools": tools} for n in range(10)]
        await asyncio.gather(*(gr.apply_guardrail(r, {}, "request") for r in reqs))

    asyncio.run(burst())
    assert len(calls) == 20 + 10          # 20 tool definitions judged once in total, plus each distinct user turn


def test_refuse_mode_raises_litellms_200_passthrough_with_a_fixed_message():
    from litellm.exceptions import ModifyResponseException
    gr = guardrail(Keyword(), on_block="refuse")
    inputs = {"texts": ["IGNORE rules"], "structured_messages": [{"role": "user", "content": "IGNORE rules"}]}
    with pytest.raises(ModifyResponseException) as e:
        asyncio.run(gr.apply_guardrail(inputs, {"model": "m"}, "request"))
    assert e.value.message == lg.REFUSAL_MESSAGE and "IGNORE" not in e.value.message   # no reason leaked to the caller
    assert e.value.detection_info["hook"] == "request" and "kw" in e.value.detection_info["reason"]
    with pytest.raises(ValueError):
        guardrail(Keyword(), on_block="maybe")


def test_post_call_refusal_rewrites_the_reply_so_the_paid_inference_completes():
    from types import SimpleNamespace as NS
    reply = NS(choices=[NS(finish_reason="tool_calls", message=NS(content="sure", function_call=None,
                                                                    tool_calls=[{"function": {"name": "send_money"}}]))])
    gr = guardrail(Keyword("send_money"), on_block="refuse")
    inputs = {"texts": ["sure"], "tool_calls": [{"function": {"name": "send_money", "arguments": "{}"}}]}
    out = asyncio.run(gr.apply_guardrail(inputs, {"response": reply, "messages": [{"role": "user", "content": "hi"}]},
                                         "response"))    # no exception: the call completes and is billed
    ch = reply.choices[0]
    assert (ch.message.content, ch.message.tool_calls, ch.finish_reason) == (lg.REFUSAL_MESSAGE, None, "content_filter")
    assert out["texts"] == [lg.REFUSAL_MESSAGE]


def test_streamed_post_call_refusal_ends_the_stream_instead_of_rewriting():
    from types import SimpleNamespace as NS

    from litellm.exceptions import ModifyResponseException
    reply = NS(choices=[NS(finish_reason="tool_calls", message=NS(content=None, function_call=None, tool_calls=[{}]))])
    gr = guardrail(Keyword("send_money"), on_block="refuse")
    inputs = {"texts": [], "tool_calls": [{"function": {"name": "send_money", "arguments": "{}"}}]}
    with pytest.raises(ModifyResponseException):   # LiteLLM terminates the stream with content_filter
        asyncio.run(gr.apply_guardrail(inputs, {"response": reply, "stream": True, "model": "m",
                                                "messages": [{"role": "user", "content": "hi"}]}, "response"))


def test_streams_are_held_until_the_post_call_check_passes_by_default():
    assert guardrail(Keyword()).streaming_buffer_until_moderated is True
    assert guardrail(Keyword(), streaming_buffer_until_moderated=False).streaming_buffer_until_moderated is False


def test_refuse_is_the_default_so_new_entries_keep_billing_intact():
    assert lg.LabGuardrail(guard_id="kw", guardrail_name="kw", event_hook=["pre_call"]).on_block == "refuse"

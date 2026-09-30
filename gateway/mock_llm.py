"""`mock-echo`: a deterministic model for guardrail-isolation evals (no Ollama needed).

It replies with whatever the SYSTEM message dictates, so the post_call guardrail can be
tested on a chosen output or tool call while the user turn stays benign:

    system: "MOCK_OUTPUT: <assistant text>"
    system: 'MOCK_TOOL_CALL: {"name": "run_shell", "arguments": {...}}'
    (no directive) -> "OK."
"""

import json

import litellm
from litellm import CustomLLM


def _directive(messages: list) -> tuple[str, str]:
    for m in messages:
        c = m.get("content") if m.get("role") == "system" else None
        if isinstance(c, str):
            for key in ("MOCK_OUTPUT:", "MOCK_TOOL_CALL:"):
                if c.startswith(key):
                    return key, c[len(key):].strip()
    return "MOCK_OUTPUT:", "OK."


class MockEcho(CustomLLM):
    async def acompletion(self, *args, **kwargs):
        kind, value = _directive(kwargs.get("messages") or [])
        if kind == "MOCK_TOOL_CALL:":
            call = json.loads(value)
            return await litellm.acompletion(
                model="openai/mock-echo", messages=kwargs["messages"], mock_response="",
                mock_tool_calls=[{"id": "call_1", "type": "function",
                                  "function": {"name": call["name"], "arguments": json.dumps(call["arguments"])}}])
        return await litellm.acompletion(model="openai/mock-echo", messages=kwargs["messages"], mock_response=value)


mock_echo = MockEcho()

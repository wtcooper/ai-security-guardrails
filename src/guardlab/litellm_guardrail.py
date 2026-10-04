"""LiteLLM custom guardrail that serves ANY guardlab registry guard (judge, decision API, OSS classifier,
s1guard), so the guard you evaluate is the guard you deploy:

    guardrails:
      - guardrail_name: judge-luna
        litellm_params:
          guardrail: guardlab.litellm_guardrail.LabGuardrail
          mode: [pre_call, post_call, pre_mcp_call, post_mcp_call]
          guard_id: judge-luna          # registry id (src/guardlab/guards.yaml)
          on_unavailable: block         # or allow (fail open)

Same traffic mapping as s1guard's guardrail: request -> new user turns (input), recent user turns
(conversation), new tool results, tool definitions; response -> reply (output, with the system prompt)
and tool calls (tool_call, with the user's request); MCP -> call + tool descriptions, then results.
A block raises GuardrailRaisedException -> HTTP 400 "Blocked by <guard id> (<request|response>): <reason>".
The guard's own model calls go directly to its provider, never back through this gateway.
"""

import asyncio
import json
from typing import Literal, Optional

from litellm._logging import verbose_proxy_logger
from litellm.exceptions import GuardrailRaisedException
from litellm.integrations.custom_guardrail import CustomGuardrail
from litellm.types.utils import GenericGuardrailAPIInputs

from s1guard.guard import (CONVERSATION_TURNS, _new_messages, last_user_message, message_text, system_prompt_of,
                           tool_call_text, tool_definition_text)

from .registry import load_guard
from .types import Case


def cases_from_inputs(inputs: dict, request_data: dict, input_type: str) -> list:
    texts = [t for t in inputs.get("texts") or [] if t and t.strip()]
    mcp_tool = request_data.get("mcp_tool_name")
    if mcp_tool:
        if input_type == "response":
            return [Case(t, "tool_result") for t in texts]
        args = json.dumps(request_data.get("mcp_arguments") or request_data.get("arguments") or {})
        return [Case(f"{mcp_tool}({args})", "tool_call")] + [
            Case(tool_definition_text(t), "tool_definition") for t in inputs.get("tools") or []
            if t.get("function", {}).get("description")]
    all_messages = request_data.get("messages") or inputs.get("structured_messages") or []
    system = system_prompt_of(all_messages)
    if input_type == "response":
        user_request = last_user_message(request_data.get("messages") or [])
        out = [Case("\n".join(texts), "output", system_prompt=system)] if texts else []
        return out + [Case(tool_call_text(tc), "tool_call", user_request=user_request) for tc in inputs.get("tool_calls") or []]
    messages = list(inputs.get("structured_messages") or [{"role": "user", "content": t} for t in texts])
    cases = []
    for m in _new_messages(messages):
        text = message_text(m)
        if not text.strip():
            continue
        if m.get("role") == "user":
            cases.append(Case(text, "input", system_prompt=system))
        elif m.get("role") in ("tool", "function"):
            cases.append(Case(text, "tool_result"))
    user_turns = [message_text(m) for m in messages if m.get("role") == "user"]
    if len(user_turns) > 1:
        cases.append(Case("\n".join(user_turns[-CONVERSATION_TURNS:]), "conversation"))
    return cases + [Case(tool_definition_text(t), "tool_definition") for t in inputs.get("tools") or []]


class LabGuardrail(CustomGuardrail):
    def __init__(self, guard_id: str = "", on_unavailable: str = "block", **kwargs):
        super().__init__(**kwargs)
        self.guard_id = guard_id or self.guardrail_name
        self.on_unavailable = on_unavailable
        self._guard = None

    @property
    def guard(self):
        if self._guard is None:   # lazy: the gateway does not load every local model at startup
            self._guard = load_guard(self.guard_id)
        return self._guard

    async def apply_guardrail(self, inputs: GenericGuardrailAPIInputs, request_data: dict,
                              input_type: Literal["request", "response"],
                              logging_obj: Optional[object] = None) -> GenericGuardrailAPIInputs:
        guard = self.guard
        cases = [c for c in cases_from_inputs(dict(inputs), request_data, input_type) if c.stage in guard.stages]
        results = await asyncio.gather(*(guard.acheck(c) for c in cases))
        blocks = [(c, r) for c, r in zip(cases, results) if r.status == "ok" and r.blocked]
        down = [(c, r) for c, r in zip(cases, results) if r.status in ("unavailable", "error")]
        if down and self.on_unavailable == "block":
            blocks += down
        for c, r in blocks + down:
            verbose_proxy_logger.warning("%s %s %s %s: %s", self.guard_id, input_type, c.stage, r.status, r.reason)
        if blocks:
            reason = "; ".join(f"{c.stage}: {r.reason if r.status == 'ok' else 'unavailable (' + r.reason[:80] + ')'}"
                               for c, r in blocks)
            raise GuardrailRaisedException(guardrail_name=self.guardrail_name,
                                           message=f"Blocked by {self.guard_id} ({input_type}): {reason}",
                                           should_wrap_with_default_message=False, blocked_content=True)
        return inputs

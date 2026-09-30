"""LiteLLM custom guardrail backed by s1guard.

Implements LiteLLM's unified `apply_guardrail` interface, so one class covers chat
completions, Responses/Anthropic-style endpoints and MCP tool calls:

    guardrails:
      - guardrail_name: s1guard
        litellm_params:
          guardrail: s1guard.litellm_guardrail.S1Guardrail
          mode: [pre_call, post_call, pre_mcp_call, post_mcp_call]

Request  -> newest user turn(s), multi-turn escalation, new tool results, tool definitions
Response -> assistant text, tool calls the model wants to make
MCP      -> call name + arguments and tool description (pre), tool result (post)

A block raises GuardrailRaisedException -> HTTP 400 "... Blocked by s1guard: <risk ids + framework ids>".
Backend/policy come from env (S1GUARD_BACKEND, S1GUARD_POLICY; see s1guard.backends).
"""

import asyncio
import json
from typing import Literal, Optional

from litellm._logging import verbose_proxy_logger
from litellm.exceptions import GuardrailRaisedException
from litellm.integrations.custom_guardrail import CustomGuardrail
from litellm.types.utils import GenericGuardrailAPIInputs

from .guard import Guard, Verdict, tool_definition_text


class S1Guardrail(CustomGuardrail):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.guard = Guard()  # loads the model once, at proxy start

    async def apply_guardrail(
        self,
        inputs: GenericGuardrailAPIInputs,
        request_data: dict,
        input_type: Literal["request", "response"],
        logging_obj: Optional[object] = None,
    ) -> GenericGuardrailAPIInputs:
        verdict = await asyncio.to_thread(self._classify, inputs, request_data, input_type)
        if verdict.findings:
            verbose_proxy_logger.warning("s1guard %s %s: %s", input_type, verdict.action, verdict.reason())
        if verdict.blocked:
            raise GuardrailRaisedException(
                guardrail_name=self.guardrail_name,
                message=f"Blocked by s1guard ({input_type}): {verdict.reason()}",
                should_wrap_with_default_message=False,
                blocked_content=True,
            )
        return inputs

    def _classify(self, inputs: GenericGuardrailAPIInputs, request_data: dict, input_type: str) -> Verdict:
        texts = [t for t in inputs.get("texts") or [] if t and t.strip()]
        mcp_tool = request_data.get("mcp_tool_name")
        if mcp_tool:
            if input_type == "response":
                return Verdict.merge(self.guard.check(t, "tool_result") for t in texts)
            args = json.dumps(request_data.get("mcp_arguments") or request_data.get("arguments") or {})
            verdicts = [self.guard.check(f"{mcp_tool}({args})", "tool_call")]
            verdicts += [self.guard.check(tool_definition_text(t), "tool_definition")
                         for t in inputs.get("tools") or [] if t.get("function", {}).get("description")]
            return Verdict.merge(verdicts)
        if input_type == "request":
            messages = inputs.get("structured_messages") or [{"role": "user", "content": t} for t in texts]
            return self.guard.check_request(list(messages), inputs.get("tools"))
        return self.guard.check_response("\n".join(texts), inputs.get("tool_calls"))

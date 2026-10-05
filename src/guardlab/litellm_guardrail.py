"""LiteLLM custom guardrail that serves ANY guardlab registry guard (judge, decision API, OSS classifier,
s1guard), so the guard you evaluate is the guard you deploy:

    guardrails:
      - guardrail_name: judge-luna
        litellm_params:
          guardrail: guardlab.litellm_guardrail.LabGuardrail
          mode: [pre_call, post_call, pre_mcp_call, post_mcp_call]
          guard_id: judge-luna          # registry id (src/guardlab/guards.yaml)
          on_unavailable: block         # or allow (fail open): judge down, erroring, or over deadline_s
          deadline_s: 10                # optional: total time budget per hook; over budget = unavailable
          stages: [input, conversation, tool_result, tool_definition, tool_call]   # optional: omit `output` to
                                        # skip the judge on plain-text replies (post-call runs only on tool calls)
          skip_tools: []                # optional: exact names of vetted tools the action check skips;
                                        # unknown tools are always checked

Same traffic mapping as s1guard's guardrail: request -> new user turns (input), recent user turns
(conversation), new tool results, tool definitions; response -> reply (output, with the system prompt)
and tool calls (tool_call, with the system prompt, the user's recent turns as trusted context and the
agent's earlier steps as untrusted history); MCP -> call + tool descriptions, then results.
A block raises GuardrailRaisedException -> HTTP 400 "Blocked by <guard id> (<request|response>): <reason>".
Judges with `transport: litellm` call their model through this gateway's router, billed to the caller's
key (chargeback; router calls skip guardrails, so no recursion); other guards call their provider directly.
"""

import asyncio
import json
from collections import OrderedDict
from typing import Literal, Optional

from litellm._logging import verbose_proxy_logger
from litellm.exceptions import GuardrailRaisedException
from litellm.integrations.custom_guardrail import CustomGuardrail
from litellm.types.utils import GenericGuardrailAPIInputs

from s1guard.guard import (CONVERSATION_TURNS, _new_messages, last_user_message, message_text, system_prompt_of,
                           tool_call_text, tool_definition_text)

from .registry import load_guard
from .trajectory import task_context
from .types import CALLER, Case

VERDICT_CACHE_SIZE = 4096   # identical checks (e.g. the same tool definitions sent on every agent turn) are judged once


def _tool_name(tc) -> str:
    fn = tc.get("function", tc) if isinstance(tc, dict) else {}
    return str(fn.get("name", "")) if isinstance(fn, dict) else ""


def cases_from_inputs(inputs: dict, request_data: dict, input_type: str, skip_tools=frozenset()) -> list:
    texts = [t for t in inputs.get("texts") or [] if t and t.strip()]
    mcp_tool = request_data.get("mcp_tool_name")
    if mcp_tool:
        if input_type == "response":
            return [Case(t, "tool_result") for t in texts]
        args = json.dumps(request_data.get("mcp_arguments") or request_data.get("arguments") or {})
        call = [] if mcp_tool in skip_tools else [Case(f"{mcp_tool}({args})", "tool_call")]
        return call + [
            Case(tool_definition_text(t), "tool_definition") for t in inputs.get("tools") or []
            if t.get("function", {}).get("description")]
    all_messages = request_data.get("messages") or inputs.get("structured_messages") or []
    system = system_prompt_of(all_messages)
    if input_type == "response":
        request, history = task_context(request_data.get("messages") or [])
        request = request or last_user_message(request_data.get("messages") or [])
        out = [Case("\n".join(texts), "output", system_prompt=system)] if texts else []
        return out + [Case(tool_call_text(tc), "tool_call", system_prompt=system, user_request=request, history=history)
                      for tc in inputs.get("tool_calls") or [] if _tool_name(tc) not in skip_tools]
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
    def __init__(self, guard_id: str = "", on_unavailable: str = "block", stages=None, skip_tools=None,
                 deadline_s: Optional[float] = None, **kwargs):
        super().__init__(**kwargs)
        self.guard_id = guard_id or self.guardrail_name
        self.on_unavailable = on_unavailable
        self.deadline_s = float(deadline_s) if deadline_s else None
        self.stages = frozenset(stages) if stages else None          # None: every stage the guard supports
        self.skip_tools = frozenset(skip_tools or ())                # exact names only; never inferred
        self._guard = None
        self._verdicts: OrderedDict = OrderedDict()                   # case key -> ok verdict (LRU)
        self._inflight: dict = {}                                     # case key -> running check (single-flight)

    @property
    def guard(self):
        if self._guard is None:   # lazy: the gateway does not load every local model at startup
            self._guard = load_guard(self.guard_id)
        return self._guard

    async def apply_guardrail(self, inputs: GenericGuardrailAPIInputs, request_data: dict,
                              input_type: Literal["request", "response"],
                              logging_obj: Optional[object] = None) -> GenericGuardrailAPIInputs:
        try:
            cases, results = await asyncio.wait_for(self._run(inputs, request_data, input_type), self.deadline_s)
        except Exception as e:   # anything else failing (load, mapping, deadline) = the guard could not decide
            verbose_proxy_logger.warning("%s %s: guard failed (%s: %s); on_unavailable=%s", self.guard_id, input_type,
                                         type(e).__name__, str(e)[:200], self.on_unavailable)
            if self.on_unavailable != "block":
                return inputs
            raise GuardrailRaisedException(guardrail_name=self.guardrail_name,
                                           message=f"Blocked by {self.guard_id} ({input_type}): unavailable ({type(e).__name__})",
                                           should_wrap_with_default_message=False, blocked_content=True)
        blocks = [(c, r) for c, r in zip(cases, results) if r.status == "ok" and r.blocked]
        down = [(c, r) for c, r in zip(cases, results) if r.status in ("unavailable", "error")]
        if down and self.on_unavailable == "block":
            blocks += down
        for c, r in down:   # one marker for every fail-open/fail-closed path, so audits can count them
            verbose_proxy_logger.warning("%s %s: guard failed on %s (%s; on_unavailable=%s): %s", self.guard_id,
                                         input_type, c.stage, r.status, self.on_unavailable, r.reason[:200])
        for c, r in blocks:
            if r.status == "ok":
                verbose_proxy_logger.warning("%s %s %s blocked: %s", self.guard_id, input_type, c.stage, r.reason)
        if blocks:
            reason = "; ".join(f"{c.stage}: {r.reason if r.status == 'ok' else 'unavailable (' + r.reason[:80] + ')'}"
                               for c, r in blocks)
            raise GuardrailRaisedException(guardrail_name=self.guardrail_name,
                                           message=f"Blocked by {self.guard_id} ({input_type}): {reason}",
                                           should_wrap_with_default_message=False, blocked_content=True)
        return inputs

    async def _run(self, inputs, request_data: dict, input_type: str) -> tuple:
        guard = self.guard
        cases = [c for c in cases_from_inputs(dict(inputs), request_data, input_type, self.skip_tools)
                 if c.stage in guard.stages and (self.stages is None or c.stage in self.stages)]
        meta = {**(request_data.get("litellm_metadata") or {}), **(request_data.get("metadata") or {})}
        caller = {k: v for k, v in meta.items() if k.startswith("user_api_key") and isinstance(v, (str, int, float))}
        caller["tags"] = [f"guardrail_stage:{'pre_call' if input_type == 'request' else 'post_call'}"]
        token = CALLER.set(caller)   # read by guards that bill their model calls to the caller's key
        try:
            return cases, await asyncio.gather(*(self._verdict(guard, c) for c in cases))
        finally:
            CALLER.reset(token)

    async def _verdict(self, guard, case):
        """Cached verdict, or the result of the one check already running for an identical case (so concurrent
        agent turns sending the same tool definitions trigger one judge call, not one each)."""
        k = case.key()
        if k in self._verdicts:
            self._verdicts.move_to_end(k)
            return self._verdicts[k]
        task = self._inflight.get(k)
        if task is None:
            task = self._inflight[k] = asyncio.ensure_future(guard.acheck(case))
            task.add_done_callback(lambda t, k=k: self._settle(k, t))
        return await asyncio.shield(task)   # one request's deadline must not cancel the shared check

    def _settle(self, k, task) -> None:
        self._inflight.pop(k, None)
        if not task.cancelled() and task.exception() is None and task.result().status == "ok":
            self._verdicts[k] = task.result()
            if len(self._verdicts) > VERDICT_CACHE_SIZE:
                self._verdicts.popitem(last=False)

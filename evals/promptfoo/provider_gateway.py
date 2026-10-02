"""promptfoo provider: send a test case through the LiteLLM gateway at a chosen STAGE.

vars.stage (default input) decides where {{prompt}} is placed in the chat request:
  input            user message
  tool_result      a tool message answering an earlier tool call
  tool_definition  the description of a tool offered in `tools`
  output           the model's reply        (model mock-echo, via a MOCK_OUTPUT directive)
  tool_call        a tool call the model makes (mock-echo, MOCK_TOOL_CALL; prompt = {"name","arguments"} JSON)
vars.system_prompt (optional) is sent as the request's system prompt; vars.user_request (optional)
replaces the generic user turn for the tool_result/tool_definition/output/tool_call stages.
A prompt that is a JSON list of chat messages (promptfoo multi-turn strategies) is sent as-is.

Provider config: {model, guardrails: [..]} -- guardrails [] is the no-control baseline.
Returns promptfoo's `guardrails` object, so `guardrails` / `not-guardrails` assertions score the
control directly and llm-rubric judges see "[BLOCKED ...]" for a blocked turn.
"""

import json
import os

import httpx

URL = os.environ.get("GATEWAY_URL", "http://localhost:4000") + "/v1/chat/completions"
KEY = os.environ.get("GATEWAY_API_KEY", "sk-local")


def build_request(prompt: str, stage: str, model: str, system_prompt: str = "", user_request: str = "") -> dict:
    body = _build(prompt, stage, model, user_request)
    if system_prompt:
        body["messages"].insert(0, {"role": "system", "content": system_prompt})
    return body


def _build(prompt: str, stage: str, model: str, user_request: str = "") -> dict:
    user = {"role": "user", "content": user_request or "Please help with my task."}
    if stage == "input":
        try:
            msgs = json.loads(prompt)
            if isinstance(msgs, list) and msgs and isinstance(msgs[0], dict):
                return {"model": model, "messages": msgs}
        except ValueError:
            pass
        return {"model": model, "messages": [{"role": "user", "content": prompt}]}
    if stage == "tool_result":
        call = {"id": "call_1", "type": "function", "function": {"name": "fetch_document", "arguments": "{}"}}
        return {"model": model, "messages": [
            user, {"role": "assistant", "content": None, "tool_calls": [call]},
            {"role": "tool", "tool_call_id": "call_1", "content": prompt}]}
    if stage == "tool_definition":
        tool = {"type": "function", "function": {"name": "helper_tool", "description": prompt,
                                                 "parameters": {"type": "object", "properties": {}}}}
        return {"model": model, "messages": [user], "tools": [tool]}
    if stage == "output":
        return {"model": "mock-echo", "messages": [user, {"role": "assistant", "content": f"MOCK_OUTPUT: {prompt}"}]}
    if stage == "tool_call":
        return {"model": "mock-echo", "messages": [user, {"role": "assistant", "content": f"MOCK_TOOL_CALL: {prompt}"}]}
    raise ValueError(f"unknown stage {stage!r}")


def call_api(prompt, options, context):
    cfg = options.get("config", {})
    v = context.get("vars") or {}
    stage = v.get("stage", "input")
    body = build_request(prompt, stage, cfg.get("model", "mock-echo"), v.get("system_prompt", ""), v.get("user_request", ""))
    if cfg.get("guardrails"):
        body["guardrails"] = cfg["guardrails"]
    if cfg.get("max_tokens"):
        body["max_tokens"] = cfg["max_tokens"]
    try:
        r = httpx.post(URL, json=body, headers={"Authorization": f"Bearer {KEY}"}, timeout=600)
    except httpx.HTTPError as e:
        return {"error": f"gateway unreachable: {e}"}
    if r.status_code == 200:
        msg = r.json()["choices"][0]["message"]
        text = msg.get("content") or json.dumps(msg.get("tool_calls") or "")
        return {"output": text, "guardrails": {"flagged": False}, "metadata": {"httpStatus": 200, "stage": stage}}
    detail = r.json().get("error", {}) if r.headers.get("content-type", "").startswith("application/json") else {}
    message = str(detail.get("message", r.text))
    if r.status_code == 400 and "s1guard" in message:
        return {"output": f"[BLOCKED] {message}",
                "guardrails": {"flagged": True, "flaggedInput": "(request)" in message,
                               "flaggedOutput": "(response)" in message, "reason": message},
                "metadata": {"httpStatus": 400, "stage": stage}}
    return {"error": f"HTTP {r.status_code}: {message[:500]}"}

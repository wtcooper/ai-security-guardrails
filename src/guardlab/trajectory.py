"""Render an agent's recent steps (tool calls and tool results) as compact text for the action check.

Used identically by the corpus builder (toolcall-guard-v1 `history`) and the LiteLLM guardrail (the
request's `messages`), so the judge sees the same shape in evaluation and in production. The history is
untrusted data: it is where injected instructions and planted details come from.

Robust to unknown shapes: OpenAI chat messages (`tool_calls[].function.{name,arguments}` with JSON-string
arguments), flat `{name, arguments}` calls with dict arguments, and string or content-part tool results.
Anything unrecognised is skipped, never raised."""

import json

MAX_STEPS = 8          # most recent steps kept
MAX_STEP_CHARS = 1500  # per step: head + tail
MAX_TOTAL_CHARS = 8000
MAX_USER_TURNS = 4     # the user's recent turns form the trusted task context (request + mid-task replies)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit // 2] + " [...] " + text[-limit // 2:]


def _content(m: dict) -> str:
    c = m.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(str(p.get("text", "")) for p in c if isinstance(p, dict))
    return "" if c is None else str(c)


def _call(tc) -> str:
    if not isinstance(tc, dict):
        return ""
    fn = tc.get("function") if isinstance(tc.get("function"), dict) else tc
    args = fn.get("arguments", "")
    if not isinstance(args, str):
        args = json.dumps(args, ensure_ascii=False, default=str)
    return f"{fn.get('name', '?')}({args})"


def task_context(messages, max_user_turns: int = MAX_USER_TURNS) -> tuple:
    """(trusted user request, untrusted history) for checking the agent's next action.

    The trusted part is the user's last few turns (the request plus any replies mid-task, such as
    "yes, send it to John"); the untrusted part is every agent and tool step since the earliest of them.
    User turns appear in the history only as content-free markers, so text inside a tool result that
    imitates a marker gains nothing."""
    msgs = [m for m in messages or [] if isinstance(m, dict)]
    users = [i for i, m in enumerate(msgs) if m.get("role") == "user" and _content(m).strip()][-max_user_turns:]
    if not users:
        return None, render_history(msgs) or None
    turns = [_clip(_content(msgs[i]).strip(), MAX_STEP_CHARS) for i in users]
    request = turns[0] if len(turns) == 1 else "\n".join(f"[user turn {n}] {t}" for n, t in enumerate(turns, 1))
    return request, render_history(msgs[users[0] + 1:]) or None


def render_history(messages) -> str:
    steps = []
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role == "assistant":
            steps += [f"[agent called] {_clip(c, MAX_STEP_CHARS)}" for c in map(_call, m.get("tool_calls") or []) if c]
            text = _content(m).strip()
            if text:
                steps.append(f"[agent said] {_clip(text, MAX_STEP_CHARS)}")
        elif role == "user":
            steps.append("[user replied: see trusted context]")
        elif role in ("tool", "function"):
            text = _content(m).strip()
            if text:
                steps.append(f"[tool result: {m.get('name') or 'tool'}] {_clip(text, MAX_STEP_CHARS)}")
    out = "\n".join(steps[-MAX_STEPS:])
    return out if len(out) <= MAX_TOTAL_CHARS else "[earlier steps truncated] " + out[-MAX_TOTAL_CHARS:]

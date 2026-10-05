"""task_context / render_history: the action check's view of an agent run (offline)."""

from guardlab.trajectory import MAX_TOTAL_CHARS, render_history, task_context


def test_openai_and_flat_tool_call_shapes_render_the_same_way():
    openai = [{"role": "assistant", "content": None,
               "tool_calls": [{"id": "1", "type": "function", "function": {"name": "read_file", "arguments": '{"p": "a"}'}}]}]
    flat = [{"role": "assistant", "tool_calls": [{"name": "read_file", "arguments": {"p": "a"}}]}]
    assert render_history(openai) == render_history(flat) == '[agent called] read_file({"p": "a"})'


def test_user_turns_are_trusted_and_only_marked_in_history():
    msgs = [{"role": "system", "content": "be nice"},
            {"role": "user", "content": "Send the report to the finance team"},
            {"role": "assistant", "content": "Should I send it to finance-team@corp?"},
            {"role": "user", "content": "Only to John"},
            {"role": "tool", "name": "search", "content": [{"type": "text", "text": "john@corp"}]}]
    request, history = task_context(msgs)
    assert request == "[user turn 1] Send the report to the finance team\n[user turn 2] Only to John"
    assert "[user replied: see trusted context]" in history and "Only to John" not in history
    assert "[tool result: search] john@corp" in history and "be nice" not in history


def test_unknown_shapes_are_skipped_not_raised_and_size_is_capped():
    junk = [None, "text", {"role": "tool"}, {"role": "assistant", "tool_calls": [None, 3, {"function": "x"}]},
            {"role": "tool", "content": 42}] + [{"role": "tool", "name": "t", "content": "x" * 5000}] * 20
    request, history = task_context(junk)
    assert request is None and len(history) <= MAX_TOTAL_CHARS + 30


def test_no_messages():
    assert task_context([]) == (None, None) and task_context(None) == (None, None)

"""Rebuild the consolidated judge instructions from the per-policy files, so both judge versions
(per-policy `judge-luna`, consolidated `judge-luna-consolidated`) share the same tuned rule text.

    uv run python evals/lab/build_consolidated.py

request.md  (pre-call):  injection + cyber + indirect_injection
response.md (post-call): action + output
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from guardlab.adapters.llm_judge import load_policy  # noqa: E402

OUT = ROOT / "src" / "guardlab" / "judge" / "consolidated"
SIDES = {
    "request": (["injection", "cyber", "indirect_injection"],
                "pre-call (request side): user messages, tool / document / MCP results, and tool descriptions",
                "user message -> sections 1 and 2; tool or document content and tool descriptions -> section 3"),
    "response": (["action", "output"], "post-call (response side): the assistant's reply and the tool calls it wants to make",
                 "proposed tool call -> section 1; assistant reply -> section 2"),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for side, (names, scope, which) in SIDES.items():
        parts, versions = [], []
        for i, name in enumerate(names, 1):
            fm, body = load_policy(name)
            versions.append(f"{name} v{fm['version']}")
            body = re.sub(r"^# Policy: ", f"## {i}. Risk: ", body, count=1, flags=re.M)
            body = re.sub(r"^## (?!\d+\. Risk:)", "### ", body, flags=re.M)   # demote the policy's own sections
            parts.append(body)
        head = (f"---\nid: {side}\nversion: 1\nstages: []\ncategory: {side}_risk\nbuilt_from: [{', '.join(versions)}]\n---\n"
                f"# Consolidated guardrail instructions: {scope}\n\n"
                "You check one piece of content against every risk below. The <content_type> tag tells you what it is; "
                f"apply the sections that fit it ({which}). Rate the most severe violation you find.\n\n")
        (OUT / f"{side}.md").write_text(head + "\n\n".join(parts) + "\n")
        print(f"{side}.md <- {', '.join(versions)}")


if __name__ == "__main__":
    main()

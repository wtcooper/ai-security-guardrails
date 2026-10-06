"""Rebuild the consolidated judge instructions from the per-policy files, so both judge versions
(per-policy `cyber-guard-per-policy`, consolidated `cyber-guard`) share the same tuned rule text.

    uv run python evals/lab/build_consolidated.py

request.md  (pre-call):  injection + cyber + indirect_injection
response.md (post-call): action + output

The shipped instructions leave out each policy's Examples section: measured on three dev slices it is worth
nothing (docs/judge.md, round S1), and dropping it removes ~19% of the prompt. The examples stay in the policy
files, where they document the intent for whoever tunes them. --keep-examples ships them anyway.

With --ablations it also writes consolidated/ablations/<variant>-<side>.md, each differing from the shipped
prompt in exactly one way, so a comparison against the shipped prompt measures that one thing:
  withexamples          the shipped prompt plus every policy's Examples
  nodefs                every policy's Definitions removed
  nodefs-<policy>       only that policy's Definitions removed (e.g. nodefs-cyber: is a rewrite's new
                        Definitions section earning its place?)
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


def drop_section(text: str, heading: str | None) -> str:
    """Remove every '### <heading>' block (up to the next ## or ### heading, or the end); None keeps everything."""
    if heading is None:
        return text
    return re.sub(rf"^### {heading}\n.*?(?=^#{{2,3}} |\Z)", "", text, flags=re.M | re.S)


def main():
    ablate = "--ablations" in sys.argv
    keep_examples = "--keep-examples" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ablations").mkdir(exist_ok=True)
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
        assemble = lambda ps: head + "\n\n".join(ps) + "\n"
        ship = lambda text: text if keep_examples else drop_section(text, "Examples")
        full = assemble(parts)
        shipped = ship(full)
        if ablate:   # every variant differs from `shipped` in exactly one way
            variants = {"withexamples": full, "nodefs": drop_section(shipped, "Definitions")}
            for i, name in enumerate(names):
                one = parts[:i] + [drop_section(parts[i], "Definitions")] + parts[i + 1:]
                variants[f"nodefs-{name}"] = ship(assemble(one))
            for old in (OUT / "ablations").glob(f"*-{side}.md"):
                old.unlink()
            for variant, text in variants.items():
                (OUT / "ablations" / f"{variant}-{side}.md").write_text(text)
                print(f"  ablations/{variant}-{side}.md  ({len(text.split())} words)")
        (OUT / f"{side}.md").write_text(shipped)
        print(f"{side}.md <- {', '.join(versions)}  ({len(shipped.split())} words)")


if __name__ == "__main__":
    main()

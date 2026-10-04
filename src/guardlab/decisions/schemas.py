"""Serializers for the two decision-API schema families.

Jev family (TypeSafe Jev, OpenRouter /api/alpha/decisions, Cloudflare Clef, laya[serve]):
    {"model", "state": {field: value}, "questions": {id: {"type": "noul", "instructions", "criteria"}}}
    -> {"answers": {id: {"noul": p}}}
s1guard already speaks this (s1guard.backends.SystemOneHTTPBackend).

OpenAI Decisions API (invite-only preview; shape from openai/codex guardian-v2 decisions.rs and a
recorded live response in crmne/ruby_llm PR #1008):
    {"model", "input": [{"role": "user", "content": [{"type": "input_text", "text"}]}],
     "questions": [{"type": "predicate", "name", "instructions"} | {"type": "choice", "name",
                   "instructions", "choices": [{"value", "description"?}]}]}
    -> {"answers": [{"type": "predicate", "name", "probability"} |
                    {"type": "choice", "name", "choice", "probabilities": [{"value", "probability"}],
                     "confidence"}], "usage": {...}}
"""

import json


def render_state(state: dict) -> str:
    """Jev-style named fields as tagged text, so questions that cite `field_name` still resolve."""
    return "\n".join(f"<{k}>\n{v if isinstance(v, str) else json.dumps(v)}\n</{k}>" for k, v in state.items())


def predicate_instructions(q: dict) -> str:
    """A Jev noul question + criteria as one predicate instruction."""
    text = q.get("instructions") or q.get("question", "")
    c = q.get("criteria") or {}
    if c:
        text += f" Answer yes when: {c.get('true', '')}. Answer no when: {c.get('false', '')}."
    return text


def to_openai(model: str, state: dict, questions: dict) -> dict:
    return {"model": model,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": render_state(state)}]}],
            "questions": [{"type": "predicate", "name": qid, "instructions": predicate_instructions(q)}
                          for qid, q in questions.items()]}


def from_openai(resp: dict, benign_values=("no", "benign", "safe", "low", "none")) -> dict:
    """{name: P(risk)}. Predicate -> probability; choice -> 1 - P(benign value); score -> expected level."""
    out = {}
    for a in resp["answers"]:
        if a["type"] == "predicate":
            out[a["name"]] = float(a["probability"])
        elif a["type"] == "choice":
            probs = {p["value"]: float(p["probability"]) for p in a.get("probabilities", [])}
            out[a["name"]] = 1.0 - sum(p for v, p in probs.items() if v.lower() in benign_values)
        elif a["type"] == "score":
            ps = a.get("probabilities", [])
            n = max(1, len(ps) - 1)
            out[a["name"]] = sum(i * float(p["probability"]) for i, p in enumerate(ps)) / n
    return out


def from_jev(resp: dict, unwrap: str = "") -> dict:
    body = resp.get(unwrap, resp) if unwrap else resp
    return {qid: float(a["noul"]) for qid, a in body["answers"].items()}

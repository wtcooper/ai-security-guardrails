"""s1guard core: ask each stage's System One question battery, apply policy thresholds,
return a Verdict mapped to OWASP LLM / MCP / Agentic Top 10 and MITRE ATLAS IDs."""

import os
import time
from dataclasses import asdict, dataclass, field
from importlib import resources
from typing import Any, Dict, Iterable, List, Optional

import yaml

from .backends import Backend, backend_from_env
from .detectors import DETECTORS

STAGE_FIELDS = {
    "input": "user_message",
    "conversation": "conversation",
    "tool_result": "tool_output",
    "tool_definition": "tool_description",
    "tool_call": "tool_call",
    "output": "assistant_reply",
}
CONVERSATION_TURNS = 6          # user turns fed to the multi-turn escalation question
_ACTION_RANK = {"allow": 0, "monitor": 1, "block": 2}


@dataclass
class Risk:
    id: str
    name: str
    stages: List[str]
    action: str
    frameworks: Dict[str, List[str]]
    kind: str = "question"
    question: str = ""
    criteria: Optional[Dict[str, str]] = None
    threshold: float = 1.0


@dataclass
class Finding:
    risk: str
    name: str
    stage: str
    score: float
    threshold: float
    action: str
    frameworks: Dict[str, List[str]]


@dataclass
class Verdict:
    action: str = "allow"                                            # allow | monitor | block
    findings: List[Finding] = field(default_factory=list)            # risks that fired
    scores: Dict[str, Dict[str, float]] = field(default_factory=dict)  # stage -> risk -> score
    latency_ms: float = 0.0

    @property
    def blocked(self) -> bool:
        return self.action == "block"

    def reason(self) -> str:
        return "; ".join(
            f"{f.risk}@{f.stage}={f.score:.2f} [{', '.join(i for ids in f.frameworks.values() for i in ids)}]"
            for f in sorted(self.findings, key=lambda f: -_ACTION_RANK[f.action]))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self) | {"reason": self.reason()}

    @staticmethod
    def merge(verdicts: Iterable["Verdict"]) -> "Verdict":
        out = Verdict()
        for v in verdicts:
            out.findings += v.findings
            for stage, s in v.scores.items():
                merged = out.scores.setdefault(stage, {})
                for risk, score in s.items():
                    merged[risk] = max(score, merged.get(risk, 0.0))
            out.latency_ms += v.latency_ms
            if _ACTION_RANK[v.action] > _ACTION_RANK[out.action]:
                out.action = v.action
        return out


def load_policy(path: Optional[str] = None) -> List[Risk]:
    if path:
        with open(path) as f:
            raw = yaml.safe_load(f)
    else:
        raw = yaml.safe_load(resources.files("s1guard").joinpath("policy.yaml").read_text())
    risks = []
    for rid, r in raw["risks"].items():
        if r.get("criteria"):  # YAML reads `true:`/`false:` keys as booleans
            r["criteria"] = {str(k).lower(): v for k, v in r["criteria"].items()}
        risks.append(Risk(id=rid, **r))
    return risks


class Guard:
    """Standalone System One guardrail classifier.

        guard = Guard()                                   # backend from S1GUARD_BACKEND (default laya)
        v = guard.check("Ignore previous instructions and ...", stage="input")
        v.action, v.findings, v.reason()
    """

    def __init__(self, backend: Optional[Backend] = None, policy: Optional[str] = None):
        self.backend = backend or backend_from_env()
        self.risks = load_policy(policy or os.environ.get("S1GUARD_POLICY"))
        self._questions = {stage: self._build_questions(stage, fld) for stage, fld in STAGE_FIELDS.items()}
        self._tool_def_cache: Dict[str, Verdict] = {}  # tool definitions repeat on every request

    def _build_questions(self, stage: str, fld: str) -> Dict[str, dict]:
        qs = {}
        for r in self.risks:
            if r.kind == "question" and stage in r.stages:
                q = {"type": "noul", "instructions": r.question.format(field=fld)}
                if r.criteria:
                    q["criteria"] = r.criteria
                qs[r.id] = q
        return qs

    def check(self, content: str | List[str], stage: str = "input") -> Verdict:
        """Classify one piece of content at one stage. `content` is a list of user turns
        (oldest first) for the `conversation` stage, a string otherwise."""
        if stage not in STAGE_FIELDS:
            raise ValueError(f"unknown stage {stage!r}; one of {sorted(STAGE_FIELDS)}")
        if stage == "tool_definition" and content in self._tool_def_cache:
            return self._tool_def_cache[content]
        t0 = time.perf_counter()
        scores: Dict[str, float] = {}
        text = "\n".join(content) if isinstance(content, list) else content
        for r in self.risks:
            if r.kind == "detector" and stage in r.stages:
                scores[r.id] = DETECTORS[r.id](text)
        if self._questions[stage] and text.strip():
            scores |= self.backend.predict({STAGE_FIELDS[stage]: content}, self._questions[stage])
        v = self._decide(stage, scores)
        v.latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        if stage == "tool_definition":
            if len(self._tool_def_cache) > 4096:
                self._tool_def_cache.clear()
            self._tool_def_cache[content] = v
        return v

    def _decide(self, stage: str, scores: Dict[str, float]) -> Verdict:
        v = Verdict(scores={stage: {k: round(s, 4) for k, s in scores.items()}})
        for r in self.risks:
            if r.id not in scores:
                continue
            threshold = 0.5 if r.kind == "detector" else r.threshold
            if scores[r.id] >= threshold:
                v.findings.append(Finding(r.id, r.name, stage, round(scores[r.id], 4), threshold,
                                          r.action, r.frameworks))
                if _ACTION_RANK[r.action] > _ACTION_RANK[v.action]:
                    v.action = r.action
        return v

    # ------------------------------------------------------------ chat-shaped helpers
    def check_request(self, messages: List[dict], tools: Optional[List[dict]] = None) -> Verdict:
        """Screen an OpenAI-style chat request: the newest user turn(s), multi-turn escalation,
        tool results added since the last assistant turn, and tool definitions."""
        verdicts = []
        tail = _new_messages(messages)
        for m in tail:
            text = message_text(m)
            if not text.strip():
                continue
            if m.get("role") == "user":
                verdicts.append(self.check(text, "input"))
            elif m.get("role") in ("tool", "function"):
                verdicts.append(self.check(text, "tool_result"))
        user_turns = [message_text(m) for m in messages if m.get("role") == "user"]
        if len(user_turns) > 1 and any(m.get("role") == "user" for m in tail):
            verdicts.append(self.check(user_turns[-CONVERSATION_TURNS:], "conversation"))
        for t in tools or []:
            verdicts.append(self.check(tool_definition_text(t), "tool_definition"))
        return Verdict.merge(verdicts)

    def check_response(self, text: str = "", tool_calls: Optional[List[dict]] = None) -> Verdict:
        verdicts = [self.check(text, "output")] if text.strip() else []
        for tc in tool_calls or []:
            verdicts.append(self.check(tool_call_text(tc), "tool_call"))
        return Verdict.merge(verdicts)


def _new_messages(messages: List[dict]) -> List[dict]:
    """Messages after the last assistant turn -- earlier ones were screened on a previous request."""
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "assistant":
            return messages[i + 1:]
    return messages


def message_text(m: dict) -> str:
    c = m.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(p.get("text", "") for p in c if isinstance(p, dict))
    return ""


def tool_definition_text(tool: dict) -> str:
    fn = tool.get("function", tool)
    params = fn.get("parameters") or fn.get("input_schema") or {}
    # Parameter descriptions are a common hiding place for poisoned instructions.
    pdesc = [f"{k}: {v.get('description', '')}" for k, v in (params.get("properties") or {}).items()
             if isinstance(v, dict) and v.get("description")]
    return "\n".join([f"name: {fn.get('name', '')}", f"description: {fn.get('description', '')}", *pdesc])


def tool_call_text(tc: dict) -> str:
    fn = tc.get("function", tc)
    return f"{fn.get('name', '')}({fn.get('arguments', '')})"

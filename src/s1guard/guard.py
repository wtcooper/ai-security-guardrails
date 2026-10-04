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
    context_question: str = ""   # asked instead of `question` when its context is known
    context_threshold: Optional[float] = None  # threshold for the context variant (default: threshold)
    context_field: str = "system_prompt"       # which context the context question reads
    model: str = ""      # kind: classifier -- Hugging Face text-classification model id
    label: str = ""      # kind: classifier -- the label whose probability is the risk score
    revision: str = ""   # kind: classifier -- pinned model revision (commit sha)


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
        self._context_questions = {stage: self._build_questions(stage, fld, context=True)
                                   for stage, fld in STAGE_FIELDS.items()}
        self._tool_def_cache: Dict[str, Verdict] = {}  # tool definitions repeat on every request
        self._pipelines: Dict[str, Any] = {}

    def _build_questions(self, stage: str, fld: str, context: bool = False) -> Dict[str, dict]:
        """The stage's question battery; with context=True only the risks that have a
        `context_question`, which also reads its `context_field` from the state. A risk with only
        a context question is asked only when that context is known."""
        qs = {}
        for r in self.risks:
            if r.kind == "question" and stage in r.stages and (r.context_question if context else r.question):
                q = {"type": "noul", "instructions": (r.context_question if context else r.question).format(field=fld)}
                if r.criteria:
                    q["criteria"] = r.criteria
                qs[r.id] = q
        return qs

    def check(self, content: str | List[str], stage: str = "input", system_prompt: Optional[str] = None,
              user_request: Optional[str] = None) -> Verdict:
        """Classify one piece of content at one stage. `content` is a list of user turns
        (oldest first) for the `conversation` stage, a string otherwise. When a risk's context is
        known (`system_prompt`, or the `user_request` behind a tool call), its `context_question`
        is asked against it instead."""
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
            elif r.kind == "classifier" and stage in r.stages and text.strip():
                scores[r.id] = self._classify(r, text)
        fld = STAGE_FIELDS[stage]
        context = {k: v for k, v in (("system_prompt", system_prompt), ("user_request", user_request)) if v}
        field_of = {r.id: r.context_field for r in self.risks}
        ctx = {q: d for q, d in self._context_questions[stage].items() if field_of[q] in context}
        plain = {q: d for q, d in self._questions[stage].items() if q not in ctx}
        if plain and text.strip():
            scores |= self.backend.predict({fld: content}, plain)
        for cf in dict.fromkeys(field_of[q] for q in ctx):  # one call per context: other questions keep
            group = {q: d for q, d in ctx.items() if field_of[q] == cf}   # the state they were calibrated on
            if text.strip():
                scores |= self.backend.predict({cf: context[cf], fld: content}, group)
        v = self._decide(stage, scores, set(ctx) if text.strip() else set())
        v.latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        if stage == "tool_definition":
            if len(self._tool_def_cache) > 4096:
                self._tool_def_cache.clear()
            self._tool_def_cache[content] = v
        return v

    def _classify(self, r: Risk, text: str, window: int = 1500, stride: int = 1000, max_windows: int = 8) -> float:
        """Encoder-classifier risk (e.g. a prompt-injection DeBERTa): P(r.label), max over character
        windows so an injection at the end of a long tool output is not truncated away."""
        from .backends import DEVICE_LOCK

        with DEVICE_LOCK:  # shared with LayaBackend: MPS cannot run two models from two threads at once
            if r.model not in self._pipelines:
                from transformers import pipeline  # optional dependency, only for classifier risks

                from .backends import _default_device
                self._pipelines[r.model] = pipeline("text-classification", model=r.model,
                                                    revision=r.revision or None, device=_default_device(),
                                                    truncation=True, max_length=512, top_k=None)
            pipe = self._pipelines[r.model]
            starts = list(range(0, max(1, len(text) - window + stride), stride))[:max_windows]
            outs = pipe([text[i:i + window] for i in starts])
        return max(next((x["score"] for x in out if x["label"] == r.label), 0.0) for out in outs)

    def _decide(self, stage: str, scores: Dict[str, float], context_ids: frozenset = frozenset()) -> Verdict:
        v = Verdict(scores={stage: {k: round(s, 4) for k, s in scores.items()}})
        for r in self.risks:
            if r.id not in scores:
                continue
            threshold = 0.5 if r.kind == "detector" else r.threshold
            if r.id in context_ids and r.context_threshold is not None:
                threshold = r.context_threshold
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
        system = system_prompt_of(messages)
        tail = _new_messages(messages)
        for m in tail:
            text = message_text(m)
            if not text.strip():
                continue
            if m.get("role") == "user":
                verdicts.append(self.check(text, "input", system))
            elif m.get("role") in ("tool", "function"):
                verdicts.append(self.check(text, "tool_result"))
        user_turns = [message_text(m) for m in messages if m.get("role") == "user"]
        if len(user_turns) > 1 and any(m.get("role") == "user" for m in tail):
            verdicts.append(self.check(user_turns[-CONVERSATION_TURNS:], "conversation"))
        for t in tools or []:
            verdicts.append(self.check(tool_definition_text(t), "tool_definition"))
        return Verdict.merge(verdicts)

    def check_response(self, text: str = "", tool_calls: Optional[List[dict]] = None,
                       system_prompt: Optional[str] = None, user_request: Optional[str] = None) -> Verdict:
        verdicts = [self.check(text, "output", system_prompt)] if text.strip() else []
        for tc in tool_calls or []:
            verdicts.append(self.check(tool_call_text(tc), "tool_call", user_request=user_request))
        return Verdict.merge(verdicts)


def _new_messages(messages: List[dict]) -> List[dict]:
    """Messages after the last assistant turn -- earlier ones were screened on a previous request."""
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "assistant":
            return messages[i + 1:]
    return messages


def last_user_message(messages: List[dict]) -> Optional[str]:
    for m in reversed(messages):
        if m.get("role") == "user" and message_text(m).strip():
            return message_text(m)
    return None


def system_prompt_of(messages: List[dict]) -> Optional[str]:
    text = "\n".join(message_text(m) for m in messages if m.get("role") in ("system", "developer"))
    return text or None


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

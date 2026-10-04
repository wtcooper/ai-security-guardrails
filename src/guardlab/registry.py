"""Guard registry: guards.yaml maps a guard id to an adapter and its config.

    from guardlab import load_guard
    g = load_guard("s1-v4")
    g.check(Case("Ignore previous instructions", stage="input"))

`${VAR}` in values expands from the environment (and `${REPO}` to the repo root). Point
GUARDLAB_REGISTRY at another YAML to use a different registry."""

import importlib
import os
import re
from importlib import resources
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
ADAPTERS = {
    "regex": "guardlab.adapters.regex:RegexGuard",
    "s1guard": "guardlab.adapters.s1guard:S1Guard",
    "hf_classifier": "guardlab.adapters.hf_classifier:HFClassifier",
    "llm_judge": "guardlab.adapters.llm_judge:LLMJudge",
    "decision_api": "guardlab.adapters.decision_api:DecisionAPIGuard",
    "hf_generative": "guardlab.adapters.hf_generative:HFGenerative",
    "ollama_guardian": "guardlab.adapters.ollama_guardian:OllamaGuardian",
    "policy_shim": "guardlab.adapters.policy_shim:PolicyShim",
    "llamaguard_server": "guardlab.adapters.llamaguard_server:LlamaGuardServer",
}
META = ("family", "license", "trained_on", "notes")  # documentation fields, not adapter config


def _expand(v):
    if isinstance(v, str):
        return re.sub(r"\$\{(\w+)\}", lambda m: str(REPO) if m.group(1) == "REPO" else os.environ.get(m.group(1), ""), v)
    if isinstance(v, list):
        return [_expand(x) for x in v]
    if isinstance(v, dict):
        return {k: _expand(x) for k, x in v.items()}
    return v


def registry() -> dict:
    path = os.environ.get("GUARDLAB_REGISTRY")
    text = Path(path).read_text() if path else resources.files("guardlab").joinpath("guards.yaml").read_text()
    return yaml.safe_load(text)["guards"]


def list_guards() -> dict:
    return registry()


def load_guard(gid: str):
    reg = registry()
    if gid not in reg:
        raise KeyError(f"unknown guard {gid!r}; known: {', '.join(reg)}")
    cfg = dict(reg[gid])
    adapter = cfg.pop("adapter")
    meta = {k: cfg.pop(k) for k in META if k in cfg}
    module, cls = ADAPTERS[adapter].split(":")
    return getattr(importlib.import_module(module), cls)(id=gid, meta=meta, **_expand(cfg))

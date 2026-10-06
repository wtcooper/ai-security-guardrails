# Lab and build documentation

Guides for comparing the four guardrail approaches, building custom policies and decision models,
and evaluating their gateway behavior.

| Doc | What it covers |
|---|---|
| [benchmark.md](benchmark.md) | The combined cyber benchmark (OWASP LLM/MCP/Agentic + MITRE coverage map) and the five public benchmarks |
| [lab.md](lab.md) | How the evaluation works: corpus, splits, run modes, scoring, adding a guard, gotchas |
| [agent-eval.md](agent-eval.md) | Agent-loop eval: vanilla Inspect AgentDojo + AgentThreatBench through the gateway, three guardrail arms, wiring checks |
| [guardrail-placement.md](guardrail-placement.md) | Where to put the guardrail in LiteLLM: the during_call chargeback test, pre-call vs action-check coverage of agentic risk, the recommended `cyber-guard` config |
| [chargeback.md](chargeback.md) | Billing the judge guardrail's model calls to the caller's LiteLLM key (verified in the spend DB) |
| [judge.md](judge.md) | LLM-as-a-judge design and tuning history, including selected cyber policy v4 and frozen validation |
| [cyber-tuning-handoff.md](cyber-tuning-handoff.md) | Historical cyber-tuning handoff; the selected v4 outcome is recorded in judge.md, rounds K27–K34 |
| [cyber-policy-plan.md](cyber-policy-plan.md) | Original malicious-cyber-policy specification; v4 implementation and current tradeoffs are recorded in judge.md |
| [decision-apis.md](decision-apis.md) | Decision APIs and self-hosted decision models: schemas, guards, the test double, switching to the OpenAI Decisions API |
| [guardrail-showdown.md](guardrail-showdown.md) | Earlier head-to-head of s1guard against public encoders (rounds 1–2) |
| [s1guard.md](s1guard.md) | System One decision-model implementation and fine-tuned checkpoints; training currently paused |
| [training-methods.md](training-methods.md) | s1guard fine-tuning methods writeup (v1–v4) |
| [research/oss-guardrails.md](research/oss-guardrails.md) | Vetted open-source guardrail classifier shortlist (2026-10) |
| [research/auto-mode-judges.md](research/auto-mode-judges.md) | How coding-agent auto modes judge actions; lessons for our judge |
| [research/system-one-decision-models-landscape.md](research/system-one-decision-models-landscape.md) | Decision-model landscape review (2026-10-03), with notes in [research/notes/](research/notes/) |

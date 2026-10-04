# Benchmarks: the lab's combined cyber benchmark + well-known public benchmarks

The lab reports guards on two kinds of benchmark:
1. **The guardlab cyber benchmark** (`rep`): our combined, curated benchmark, 407 dev + 407 test
   single-turn cases. It is built from recognized public sources and covers the OWASP Top 10 for LLM
   apps (2026), the OWASP MCP Top 10, the OWASP Agentic Top 10, and MITRE ATLAS / ATT&CK, cyber
   security only. Tune on dev; report on test.
2. **Well-known public benchmarks** (`public`): five benchmarks run independently, each reported on
   its own, so results compare directly with vendor tables such as Sentinel v2's. They are never
   used for tuning. Some cases overlap with the combined benchmark, and that is fine.

```bash
bash evals/run.sh lab rep-test '<guards>'      # combined benchmark (held out)
bash evals/run.sh lab public '<guards>'        # the five public benchmarks
uv run python evals/lab/report.py evals/results/lab/public-*.json --by set --cell f1   # per-benchmark F1 table
```

## 1. guardlab cyber benchmark (rep)

Each split has about 230 attacks and about 180 benign cases. Every case is single-turn:
- indirect injection arrives as tool or document content;
- tool calls carry the user's request;
- output checks carry the system prompt.

| Category (attacks per split) | Stage | Risks covered | OWASP LLM 2026 | OWASP MCP | OWASP Agentic | MITRE | Sources |
|---|---|---|---|---|---|---|---|
| prompt_injection (30) | input | Direct injection, goal hijacking, secret and prompt extraction | LLM01, LLM08 | — | ASI01 | AML.T0051.000, T0056 | CyberSecEval prompt injection (Meta), PromptInject |
| evasion (20) | input | Guard manipulation ("approved / authorized test" notes aimed at the classifier) | LLM01 | — | ASI01 | AML.T0054, T0051 | CyberSecEval injections wrapped in classifier-addressed notes |
| indirect_injection (40) | tool_result | Instructions hidden in emails, tables, code, web pages and tool outputs | LLM01 | MCP06, MCP03 | ASI01 | AML.T0051.001, T0110.002 | **BIPIA** (Microsoft), **InjecAgent**, **AgentDojo**, deepset-in-UltraChat, hand-written |
| tool_poisoning (25) | tool_definition | Malicious instructions in tool/MCP descriptions | LLM01 | MCP03 | ASI04 | AML.T0110.000 | InjecAgent tool descriptions + authored poisoning |
| unsafe_tool_call (35) | tool_call | Unrequested, destructive, exfiltrating or privilege-abusing agent actions | LLM03 (Excessive Agency), LLM02 | MCP01, MCP02, MCP10 | ASI02, ASI03 | AML.T0053, T0086, T0101 | **InjecAgent** attacker tool calls, toolcall-guard-v1 (AgentDojo-derived), authored |
| data_leakage (25) | input | Attempts to extract secrets, system prompts and private data | LLM02, LLM08 | MCP10 | — | AML.T0057, T0056 | ai-security-evals M2S leakage variants, CyberSecEval |
| output_leak (20) | output | Replies that leak the system prompt, private data or secrets | LLM08, LLM02 | MCP01 | — | AML.T0056, T0057 | CyberSecEval system prompts + real model replies |
| cyber (30) | input | Requests for offensive cyber capability | — | — | — | ATT&CK tactics, AML.T0102 | **CyberSecEval MITRE + Interpreter**, AdvBench (cyber subset), M2S variants |
| benign (about 180) | all stages | Legitimate security work, trigger-word prompts, clean documents, normal tool calls and replies | — | — | — | — | CyberSecEval false-refusal set, **NotInject**, BIPIA clean contexts, InjecAgent tools, real model replies |

**How it's built.** Stratified quotas per category and per benign stage
([build_corpus.py](../evals/lab/build_corpus.py) `REP_ATTACK` / `REP_BENIGN`), drawn from the
dev/test splits of the full cyber corpus. Every row carries its source and licence, and
[manifest.json](../evals/lab/data/manifest.json) pins the counts and sha256.

**Contamination.**
- s1guard trained on some of these sources, so its rows are flagged and excluded for it.
- The judge's policies were tuned on dev only; few-shot examples are synthetic and leak-checked by a
  test.

**Not covered** (multi-turn or system-level, outside single-turn guards):
- multi-turn crescendo: this repo has a separate promptfoo red-team config;
- supply chain (LLM04, MCP04);
- training-data poisoning (LLM05);
- authentication and authorization gaps (MCP07);
- cascading failures (ASI08).

## 2. Public benchmarks (public)

| Benchmark | What it measures | Cases | Licence | Notes |
|---|---|---:|---|---|
| deepset/prompt-injections (test) | Direct injection, English + German | 116 | Apache-2.0 | Most-cited PI set. s1guard, ProtectAI and Horizon trained on its train split. |
| jackhhao/jailbreak-classification (test) | DAN-style jailbreak prompts vs benign | 262 | Apache-2.0 | 2023. s1guard and ProtectAI trained on its train split. |
| xTRam1/safe-guard-prompt-injection (test) | Synthetic injections vs benign | 400 of 2,060 (stratified) | none declared | GPT-3.5-generated |
| rogue-security/prompt-injections-benchmark | Jailbreak vs benign | 400 of 5,000 (stratified) | CC-BY-NC-4.0, gated | **Sentinel's own vendor benchmark** (home advantage for Sentinel) |
| microsoft/BIPIA (test) | **Indirect** injection in email, table and code content | 400 (200 clean / 200 attacked) | MIT code, CC-BY-SA contexts | The only one of the five covering agentic or indirect risk |

- **Why not WildJailbreak** (one of Sentinel's five)? Its prompts are labelled by harm and carry
  content-safety payloads, including the biological and chemical material this lab must not test.
- **Same benchmarks as Sentinel v2's model card.** Sentinel reports deepset, jackhhao, xTRam1,
  rogue-security and WildJailbreak, so with WildJailbreak dropped four of our five columns line up
  with its published F1 table.
- **The public injection benchmarks are direct and input-only.** That's why the combined benchmark
  carries the agentic coverage.

# ai-security-guardrails: how it was built

Set out to build a fast in-house AI-risk classifier; became a guardrail comparison lab that shipped a drop-in AI-judge gateway guardrail, then found faster decision models that match it.

**2026-09-30 → 2026-10-08** · 19 agent sessions over 7 active days · 19 commits · agents: claude 18, codex 1

## The problem

The user's enterprise serves inference through a LiteLLM gateway and had been evaluating commercial runtime guardrails such as AWS Bedrock Guardrails, Azure Content Safety, Palo Alto Prisma AIRS and Google Model Armor. Newly released System One decision models, Jev and the open-source Laya, suggested a low-latency, low-cost way to classify the top AI risks.

**Intent:** Build a System One-level classifier usable as a runtime protection guard that detects the 2026 OWASP LLM Top 10, the OWASP MCP and Agentic Top 10 lists, and known MITRE-style risks.

**Success looked like:**
- Build it and run a selective smoke test on a small eval set showing the guardrail fires when called; a full corpus sweep was not required.
- Use local models while building and testing, to avoid burning context and cost.

## How it unfolded

### 1. Building an in-house fast risk classifier (2026-09-30 – 2026-10-02)

Work began on s1guard, a guard built on the open-source Laya model, wired into LiteLLM and tested with promptfoo on local models. The user soon redirected effort from latency to detection quality, which led to a detection benchmark and local fine-tuning on the user's Mac, with successive fine-tuned versions improving most risks.

- s1guard: zero-shot classifier guardrail with promptfoo evals — *shipped*
- Quality-first detection: benchmark and local fine-tuning — *shipped*

### 2. Head-to-head testing overturned the in-house model (2026-10-03 – 2026-10-04)

A showdown first favored a hybrid of the fine-tuned model plus a public injection classifier. The user questioned whether the comparison was fair; it was not, because s1guard had been tuned on the same benchmark family. On clean public sets, off-the-shelf classifiers beat the fine-tuned model and ran faster, and fine-tuning was paused.

- Showdown against public guards — *shipped*
- Fairness check and the clean benchmark — *exploration*

### 3. Turning the project into a guardrail comparison lab (2026-10-04 – 2026-10-05)

The repo was rebuilt as guardlab, with adapters for LLM judges, decision APIs and open-source guards, scored on public benchmarks. An OpenAI usage warning narrowed all testing to cyber security. The judge was tuned over many rounds, consolidated into a single pre-call and post-call judge billed to the calling application, and the guards were regrouped by who runs the inference.

- guardlab: restructuring into an evaluation lab — *shipped*
- Tuning the LLM judge, narrowed to cyber security — *shipped*
- Open-source guards and well-known public benchmarks — *shipped*
- Consolidated judge with gateway chargeback — *shipped*
- Regrouping guards by who runs the inference — *shipped*

### 4. Fitting guardrails to enterprise billing and AI agents (2026-10-05 – 2026-10-05)

The enterprise's practice of avoiding during-call guardrails was confirmed: a mid-call block cancels inference and leaves no spend record. Checks stayed before the call, plus after it only for responses with tool calls, and the guard was made to fail open. A new agent-loop eval showed guardrails stopped attacks but ended agent tasks, so blocks became normal refusal replies and every call path was proven billable.

- Guardrail placement, chargeback and fail-open — *shipped*
- Standalone agent-loop eval — *shipped*
- Blocks as refusals, and billing on every path — *shipped*

### 5. Hardening the AI judge against cyber attacks hit a ceiling (2026-10-06 – 2026-10-06)

An ablation trimmed cyber-guard's prompts. Hardening the policy wording was blocked by Claude's safety classifier, so the work moved to a Codex session through a written spec and later a handoff. Neither agent's rewording rounds brought false flags down, and the adopted v4 transferred a few targeted rules onto the original policy. The README swung from leading with cyber-guard back to presenting the repo as a comparison lab.

- Simplifying cyber-guard and leading the README with it — *shipped*
- Hardening the cyber policy across two agents — *shipped*
- Re-centering the README on the comparison lab — *shipped*

### 6. A simpler drop-in guardrail became the one to deploy (2026-10-07 – 2026-10-08)

Questions about tool results and system prompts exposed that cyber-guard fired many parallel judge calls per agent step and depended on a cache. Under a strict no-cache, drop-in constraint, the agent built agentic-security with at most one judge call on each side of the model. It matched cyber-guard on most tests, used fewer judge calls and let more agent tasks finish, so it became the recommended deployment and cyber-guard became a lab reference. A strong agent model mostly resisted the test attacks on its own, but against a weaker agent that fell for them, agentic-security stopped the attacks that succeeded without a guardrail.

- Tool-result redaction inside cyber-guard (parked) — *abandoned*
- agentic-security: a drop-in guardrail with no cache — *shipped*
- Proving agentic-security protects a weaker agent — *shipped*

### 7. Faster decision models caught up with the AI judge (2026-10-08 – 2026-10-08)

The user turned to decision models as faster alternatives to the judge. Jev, a hosted decision API, was tuned overnight and on held-out data matched the judges' quality much faster, so it was positioned as a pre-filter in front of the judge. The user then required every score to come from one held-out set run fresh, which exposed mixed test sets, reused lab results and training overlap in the old fine-tune. On that footing the project returned to training its own decision model, this time on rented GPUs and clean data: a fine-tuned 9B model matched Jev, while the small Laya model stayed well behind. The data's provenance and licenses were documented, but the latest work was not yet committed.

- Jev: a hosted decision API tuned into a fast guardrail — *shipped*
- Self-hosted decision models: size comparison and a 9B fine-tune on rented GPUs — *partial*
- One held-out test set, run fresh, for every guard — *partial*
- Documenting where the training and test data came from — *partial*

## Key pivots

- **2026-09-30 · scope-change:** A low-latency guardrail tuned zero-shot → Detection quality first, with a benchmark and local fine-tuning; latency deferred. The user asked how to get better detection across all risk types and said latency could wait.
- **2026-10-03 · abandoned:** Train our own classifier and recommend a hybrid of fine-tuned v4 plus a public injection classifier → Fine-tuning paused; the repo became a lab comparing guard families, with an LLM judge as the main new build. The showdown benchmark was in-distribution for s1guard. On clean public sets the public classifiers beat v4 on every set and ran much faster.
- **2026-10-04 · re-planned:** Pressing on when blocked by an unfunded API key, with judge tuning in a single pass → Stop and ask when blocked, and tune the judge over multiple rounds. The user saw the agent forging ahead past the credit failure and corrected it.
- **2026-10-04 · scope-change:** A broad corpus covering all AI risks, including content safety → Cyber security only, with the harmful-content judge policy retired. OpenAI flagged the user's traffic for prohibited biological use and the user risked being blocked.
- **2026-10-04 · re-planned:** Llama Guard 4 and Nemotron quietly skipped → Both added to the lab and served locally. The user pointed out both were in the agreed plan and had been dropped without asking.
- **2026-10-05 · re-planned:** Renaming the decision-API category → Categories split by who runs the inference: LLM judge, hosted decision API, self-hosted decision model, self-hosted classifier. The user said the naming conflated someone else's hosted inference with self-hosted models, which can be fine-tuned.
- **2026-10-05 · re-planned:** Blocks returned as HTTP 400 errors, with post-call blocks left to LiteLLM → Blocks returned as 200 refusals, with blocked replies rewritten so every call is billed. The agent-loop eval showed a 400 ends the whole agent task, and post-call blocks were recorded as zero-cost failures.
- **2026-10-06 · re-planned:** Claude writes the hardened cyber policy itself → Claude writes a spec and a Codex session implements and tunes the policy. Claude's replies authoring the policy wording were stopped by its safety classifier.
- **2026-10-06 · thrashed:** Repeated rewordings of cyber policy v3 to cut false flags, first by Claude and then by Codex → v3 restored, then a narrow transfer of v3 rules onto the original v1 adopted as v4. No rewording passed the false-flag gate, and a fresh uncached repeat did not confirm the apparent gains. *(cost: 2 sessions)*
- **2026-10-06 · re-planned:** README leading with cyber-guard as the primary story → README centered on comparing guardrail approaches, with cyber-guard as one customization. The user decided the cyber-guard framing misrepresented the project's purpose as a lab.
- **2026-10-07 · re-planned:** Judge each message and tool piece in separate parallel calls, kept affordable by a verdict cache → At most one judge call before and one after each model call, over a fixed recent window, with no cache. Counting showed many judge calls per agent step without the cache, and the target enterprise gateway allows only a drop-in Python file and config.
- **2026-10-07 · abandoned:** cyber-guard as the guardrail to deploy, with tool-result redaction added → agentic-security deployed; cyber-guard kept as a lab benchmark and its stashed redaction work dropped. cyber-guard needed a cache to be affordable, while agentic-security matched it on most slices with fewer judge calls and more agent tasks completed.
- **2026-10-07 · abandoned:** A wording-only tuning round to lift agentic-security's cyber recall → Shipped prompt kept unchanged; closing the gap left to a change in the cyber policy that cyber-guard shares. Under the user's rule that F1 must improve with no added false positives, the round raised false positives as much as recall on broader checks.
- **2026-10-08 · re-planned:** A task-completion table presented as evidence that agentic-security protects agents → Per-sample attack success for the strong agent and a weaker Gemma 4 agent. The user said the table did not show attack success. The breakdown showed the strong agent resisted attacks on its own, so only the weaker agent revealed what the guardrail stopped.
- **2026-10-08 · scope-change:** Further tuning of agentic-security → Evaluating and tuning Jev, a hosted decision API, as a runtime guardrail. The user wanted to build out the Jev route next and left the agent to tune it overnight.
- **2026-10-08 · scope-change:** Own-model fine-tuning paused after the clean benchmark → A larger 9B decision model fine-tuned, and Laya retrained, on rented GPUs with clean training data. Jev showed a decision model could match the judge, and the user wanted to see what a fine-tuned model of appropriate size could do, on rented GPU time under a budget cap.
- **2026-10-08 · re-planned:** Comparing guards with scores from different test mixes and lab runs that reused saved verdicts → One held-out set scored fresh for every guard, with caching off and overlapping cases excluded. The user required like-for-like numbers never touched by training; the agent found mixed sets, reused results and the old fine-tune's training overlap with the held-out set.

## What shipped

- s1guard: a zero-shot System One classifier with a LiteLLM guardrail and promptfoo evals, later moved to experiments/ (2026-09-30, 1 commits)
- Per-stage detection benchmark, local Laya fine-tuning pipeline, and fine-tuned models with context-aware checks (2026-10-02, 1 commits)
- Showdown harness and hybrid policy comparing s1guard with public guards (2026-10-04, 1 commits)
- guardlab evaluation lab: guard registry, adapters for LLM judges, decision APIs and open-source guards, and public benchmark sets (2026-10-04, 1 commits)
- Consolidated LLM judge whose calls are billed to the caller's gateway key, with Llama Guard 4 served locally (2026-10-05, 1 commits)
- Guard lineup regrouped by inference ownership, with DeBERTa and Strands Decider added and a roadmap (2026-10-05, 1 commits)
- Pre-call placement, a trajectory-aware tool-call check, and a fail-open gateway guard (2026-10-05, 1 commits)
- Standalone agent-loop eval on AgentDojo and AgentThreatBench (2026-10-05, 1 commits)
- Refusal-style blocks and verified chargeback on every request path (2026-10-05, 1 commits)
- Prompt-section ablation, a cyber-only eval slice, and the cyber policy hardening spec (2026-10-06, 2 commits)
- Cyber policy v4, a README centered on the comparison lab, and model-neutral judge names (2026-10-06, 2 commits)
- agentic-security, a drop-in LiteLLM guardrail with surgical withholding, and deployment docs that recommend it (2026-10-07, 2 commits)
- Evidence that agentic-security stops attacks against a weaker agent, a clean four-setup rerun, and the rejected tuning round documented (2026-10-08, 1 commits)
- Jev evaluated and tuned as a hosted decision-API guardrail and pre-filter, with a README that leads with active work and the best-performing options (2026-10-08, 2 commits)

## Intent vs. delivered

- **Set out to:** Train or adapt our own low-latency System One classifier for the top AI risks, plugged into LiteLLM as a custom guardrail and tested with promptfoo on local models.
- **Delivered:** A cyber-security guardrail lab that compares LLM judges, hosted decision APIs, self-hosted decision models and self-hosted classifiers on one held-out test set and public benchmarks, run fresh, plus an agent-loop eval; agentic-security, a drop-in LiteLLM guardrail that makes at most one judge call before and one after each model call, returns blocks as refusals and keeps model calls billable; a tuned Jev configuration that matches the judge's quality much faster and can act as its pre-filter; and, not yet committed, a 9B decision model fine-tuned on rented GPUs that matches Jev. The original fine-tuned classifier work sits in the experiments folder.

## Lessons

- An in-house model that wins on its own test data has not yet won: the fine-tuned classifier led only on a benchmark it had been tuned on, and lost to off-the-shelf classifiers on clean public sets.
- The original idea of a fast in-house decision model was held back by model size: retrained on clean data, the small model still trailed the hosted decision model well behind, while a larger open model fine-tuned on the same data with rented GPUs matched it at low cost.
- Most reversals came from how results were measured, not from the code: benchmark leakage, a shifted baseline, shared API rate limits, reused lab results and scores drawn from different test sets each produced numbers that had to be re-run before a decision could stand. The fix was one held-out set scored fresh for every option.
- Billing rules decide where a guardrail can sit: blocking mid-call cancels inference with no spend record, so checks run before and after the model call and blocks come back as normal refusals that are still billed.
- Guardrails must be tested inside a real agent workflow, not only on single prompts: the agent-loop eval showed that hard error blocks ended whole agent tasks, which led to refusal-style blocks.
- A guardrail's protection only shows against an agent that can be fooled: a strong model resisted the test attacks on its own, so task-completion figures said little, and only a weaker agent's attack-success figures showed what the guardrail stopped.
- State the deployment constraints up front: the no-cache, drop-in-file requirement surfaced only after cyber-guard had been tuned around a cache, and a much simpler design built to that constraint matched it and let more agent tasks finish.
- Security testing runs into AI providers' own safety controls: OpenAI flagged biological-risk test traffic, forcing a cyber-only scope, and Claude's safety classifier stopped it writing hardened cyber policy text, so that wording was delegated to a Codex session through a written spec.
- AI agents need explicit rules for blockers and plan changes: the agent pushed past an unfunded API key and silently dropped planned guards until the user stepped in. Once stated, the stop-when-blocked rule held: the agent halted an unattended overnight run when API credits ran out.
- Automated security reviews of each change found real weaknesses, but the record shows a fix only for the finding raised inside the working session; findings from separate review sessions have no recorded follow-up.

## Open threads

- agentic-security still lets autonomy-hijack attacks through, trails cyber-guard slightly on cyber recall (a wording-only tuning round failed, so the fix needs the shared cyber policy), and raises false alarms on delegated requests such as doing the tasks in a file.
- Surgical cuts are not re-verified before the remaining text reaches the model; an optional verification setting was offered but not built.
- The attack types the user's work evals catch but cyber-guard misses remain unmeasured, since no sanitized cases were available; the roadmap lists generalizing the cyber instructions later.
- The cost of during-call checks and of judge calls that time out is still not billed.
- cyber-guard's lab integration still has the billing-spoof flaw fixed in agentic-security, noted as needing the same fix if it is ever deployed.
- Security review findings with no recorded fix: the forged-assistant-turn bypass in s1guard screening, unescaped trusted_context text in the judge prompt, and injections placed past the encoder's window cap.
- OpenAI's Decisions API is still to be compared with Jev once it is generally available, a decision-model check at the LiteLLM layer like agentic-security is not built, and proposed ideas to cut guarded-request latency were not applied.
- The latest work is uncommitted: the Modal training apps, the single held-out comparison harness, the provenance document, and the plain-language test-set names and README rewrite.
- Base Kev-9B scores are pending, so what fine-tuning added is not yet shown; the model-size write-up and the README's self-hosted row wait on them.
- The old Laya fine-tune's public-benchmark results are not clean because it trained on some public cases, and the held-out set has few tool-definition and tool-result cases, so per-stage scores there are only indicative.

---

*Dates, counts, and commits are computed from agentsview and git. The narrative is model-written; every claim links to its evidence in chronicle.html.*

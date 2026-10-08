# agentic-security: a drop-in guardrail for agents

`agentic-security` is the enterprise-ready sibling of cyber-guard. It uses the same tuned rule text and the same
judge model (gpt-6-luna), but is built for an existing LiteLLM Enterprise deployment that you can't change:

- **Drop-in.** One Python file and two prompt files ([deploy/agentic-security/](../deploy/agentic-security/)), plus
  config. Standard library and LiteLLM only. It imports nothing from this repository's lab code.
- **No cache and no state.** Each request is judged on its own; nothing is shared across requests, pods or restarts.
- **A bounded number of judge calls.** One before the model, and one after it only if the reply calls tools. A
  second call is made only for a borderline score or to cut an injection out of a flagged tool result.
- **Context, not fragments.** The judge sees the last 10 messages (about five agent steps), so it can tell what
  the user asked for or delegated, what the assistant already declined, and drift across turns. The system
  prompt is left out unless configured.
- **The agent keeps working.** A flagged tool result has only its injected lines cut, and the model carries on with
  the rest of the data. cyber-guard instead refuses the turn, which ends the agent's run.

cyber-guard stays unchanged as the lab's per-piece judge. **Summary:** single-message accuracy is on par with
cyber-guard, slightly behind on cyber held-out. It's better at keeping agent tasks alive and uses 11× fewer judge
tokens than cyber-guard without its cache. Details follow.

## Why a second guardrail

cyber-guard splits each request into pieces and judges every piece in its own call: each new user message, the
recent user turns, each tool result, and **each tool definition**.

- **Call count:** in the AgentDojo agent loop, that meant a median of **26 judge calls per agent model call**
  (maximum 46), 20.5 of them re-judging the same tool definitions.
- **The cache it needs:** an in-process verdict cache brings this down to 2–3 calls, but a per-pod cache isn't
  something a large Kubernetes deployment should depend on.
- **No surrounding context:** each piece is judged without the conversation around it. The user-turn check never
  saw the assistant's replies, so it couldn't see "declined, then rephrased".

## How it works

```
agent model call ─▶ PRE-CALL: 1 judge call (hedged)
                     context: last 10 messages (user, assistant, tool calls and results); no system prompt
                     rated:   new user message(s)                → flagged: HTTP 200 refusal, model not run
                              every tool result in the window    → flagged: +1 call finds the injected lines;
                                                                   only those are cut, model runs on the rest
                              tool definitions, on a new user turn → flagged: refusal
                 ─▶ MODEL
                 ─▶ POST-CALL: 1 judge call, only if the reply calls tools
                     rated:   all tool calls in the reply, with the same window as context
                              → flagged: reply rewritten into the refusal (still billed)
```

- **Scores.** The judge returns one digit per rated entry (`1:0 2:8`). 7–9 is flagged and 0–3 passes. 4–6 goes to
  one review call, with brief reasoning and a JSON list of the violating entries. Every flagged tool call is
  reviewed, because that review keeps legitimate actions flowing (below).
- **Surgical withholding.** For a flagged tool result, one more call lists the injected segments: lines, plus
  sentences within long lines. Only those are cut, and each cut is marked. The whole result is withheld instead
  when that call fails, finds nothing, would cut more than 80%, or the result was too long for the judge to read
  in full (over 24,000 characters).
- **No memory needed.** The agent's client keeps the original and resends it every turn, so every tool result
  still in the window is re-rated on each request, inside the same single call. A result that scrolls out of the
  window is no longer rated; that is a known limit.
- **Hedging.** If the first-pass call hasn't answered within 2.5 s, an identical second call goes out and the first
  answer wins. The slower call is left to finish so the gateway still bills it.
- **Tool definitions** are rated when a user turn starts, not on every agent step, since they are static within a
  turn.
- **Unchanged from cyber-guard:** fail-open with a deadline, 200 refusals, buffered streaming, and per-call
  chargeback through the gateway's router (`guardrail:agentic-security` tag), including the hedged and locate calls.

**Lab and deployment run the same code.** The lab adapter
([src/guardlab/adapters/agentic.py](../src/guardlab/adapters/agentic.py)) imports the deployable module and turns
each corpus case into the window the guardrail would build. A tool definition is judged alongside a neutral user
turn, as when deployed. The prompts are built from the shared policies by
[evals/lab/build_agentic.py](../evals/lab/build_agentic.py).

## Results (2026-10-07)

### Single-message accuracy (caught / false flags / F1)

| Slice | cyber-guard | agentic-security |
|---|---|---|
| rep-dev | 89% / 4% / 0.93 | 90% / 4% / 0.93 |
| **rep-test** (held out) | 88% / 4% / 0.92 | **89% / 4% / 0.93** |
| cyber-dev | 92% / 1% / 0.95 | 91% / 3% / 0.94 |
| **cyber-test** (held out) | **94% / 4% / 0.95** | 91% / 6% / 0.93 |
| public benchmarks (never tuned on) | 77% / 2% / 0.86 | **79% / 2% / 0.87** |
| tool calls (tc-dev) | 91% / 7% / 0.93 | 85% / **1%** / 0.92 (with system prompt: 90% / 7% / 0.93) |

- **Scope of the comparison:** agentic-security doesn't screen plain-text replies (45 rep cases); cyber-guard's
  deployed config doesn't either.
- **Noise:** with about 200–400 cases per slice, differences of 2–3 points are borderline.

**Tuning on dev, three versions:**

- **Version 1** lost 12 points of cyber recall. Two causes, both in prompt framing:
  - The delegation rule ("instructions the user delegated are not a violation") wasn't restricted to tool content,
    so the judge applied it to users' own requests.
  - An example answer, "1:0", in the final instruction anchored the judge. Removing it took dev from 14/40 to
    39/40 cyber attacks caught.
- **Version 3** restricts delegation to tool content, drops the example, and gives the review call room to reason.
- **Lab fix:** the lab first judged tool definitions with an empty conversation, which flagged 15 of 25 benign
  definitions; with a user turn alongside, as deployed, it flagged 0 of 25.

### Cyber recall tuning round (2026-10-07): tried, not adopted

**Goal:** close the 3-point cyber recall gap to cyber-guard without adding false positives, so F1 must rise. Only
agentic-security's own framing was varied; the shared policies stay untouched
([experiment](../evals/lab/experiments/agentic_tune.py)). Tuning used dev and pool A; validation used pool B.

**The variants:**
- **maxsev:** "rate the most severe violation; context can raise a user message's rating but never lower it".
- **typed:** entry labels in the policies' vocabulary.
- **both** combined.

Only maxsev beat the shipped prompt on the tuning slices. Replicated, it gained about 4.5 caught and lost 1.5 false
flags out of 336 attacks and 336 legitimate requests. On pool B, averaged over two runs, it caught 89.6% vs 86.6%
with the same 6.5 false flags, and F1 rose from 0.909 to 0.927.

**The broader checks rejected it:** recall rose 1–2 points on every slice, but false positives rose 1–2 points too,
and F1 stayed flat.

| Slice | Shipped (caught / flagged / F1) | maxsev |
|---|---|---|
| rep-dev | 90% / 4% / 0.93 | 92% / 6% / 0.93 |
| rep-test | 89% / 4% / 0.93 | 90% / 5% / 0.93 |
| cyber-test | 91% / 6% / 0.93 | 92% / 8% / 0.93 |
| public | 79% / 2% / 0.87 | 81% / 4% / 0.87 |

**Conclusion:** framing changes sit at the judge's run-to-run noise (about ±2 points; identical runs of the shipped
prompt moved by 4 attacks and 3 false flags on pool A). They trade false positives for recall instead of improving
accuracy. Most remaining misses are confident 0s on reconnaissance-style requests ("discovery", "collection"). Closing
the gap needs content changes to the shared cyber policy, which would also change cyber-guard.

### System prompt: does a safety-heavy one cause over-flagging?

On 324 dev user messages (187 attacks, 137 legitimate look-alikes), with no system prompt, a plain one and a
safety-heavy one ([experiment](../evals/lab/experiments/system_prompt.py)):

- **No over-flagging:** the safety prompt added at most one false flag for either judge.
- **No benefit on user messages either:** recall and F1 moved within noise.
- **It does matter for tool calls:** with it, unsafe calls caught went from 85% to 90%, and legitimate calls blocked
  from 1% to 7%.
- **Recommendation:** leave it off by default; `agentic-security-sys` is the measured alternative.

### Latency: classifier time only, no inference

The test replayed 180 real AgentDojo requests (60 short, 60 medium and 60 long histories) through each guardrail's
own hooks, with gpt-6-luna called directly ([harness](../evals/lab/experiments/latency.py)). All times are seconds.

| | Pre-call p50 / p95 | Post-call p50 / p95 | Pre + post per step p50 / p95 / p99 | Judge calls per pre-call | Prompt tokens per pre-call |
|---|---|---|---|---:|---:|
| **agentic-security** | 1.18 / 3.52 | 1.04 / 5.87 | **2.0 / 7.7 / 14.3** | 1.0 | **4.4k** |
| with hedging (now default) | 1.35 / 2.60 | 1.06 / 5.54 | 2.2 / 6.0 / 8.3 | 1.0 | 4.4k |
| cyber-guard, no cache | 2.72 / 5.42 | 1.13 / 4.21 | 3.5 / 7.6 / 21.0 | 20 (up to 36) | 50k |
| cyber-guard, warm cache | 0.95 / 2.46 | 1.08 / 3.98 | 1.7 / 4.5 / 7.2 | 1.7 | 4.5k |

- **History length barely matters.** agentic-security's pre-call cost is 4.0–5.1k tokens from short to long histories.
- **Hedging removes the provider's slow tail on pre-call** (worst case 17 s down to 3.2 s) for about 6% more calls.
- **The rest of the tail is the tool-call review,** which takes a median of about 5 s when it runs.
- **Median differences of about 0.2 s between runs are OpenAI variation.**

**Should the tool-call review be faster?** Tool-call dev slice, 154 unsafe and 86 legitimate calls
([experiment](../evals/lab/experiments/review_band.py)):

| Tool-call review | Caught | Legit calls blocked | F1 | p50 / p95 |
|---|---:|---:|---:|---:|
| **4–9, low effort (kept)** | 86% | **1.2%** | 0.920 | 3.2 / 5.7 s |
| 4–9, no reasoning | 88% | 4.7% | 0.925 | 2.5 / 4.1 s |
| 4–8 | 87% | 4.7% | 0.918 | 1.0 / 5.0 s |
| 4–6 only | 88% | 7.0% | 0.915 | 1.1 / 3.2 s |

F1 is a wash, but only the current review keeps legitimate tool calls flowing, and blocked calls end agent tasks.
Its latency only lands on suspicious calls: about 10% in real traffic, since benign calls score 0–3.

### Surgical withholding

On the 116 dev tool-result attacks ([experiment](../evals/lab/experiments/surgical.py)):

- **Flagged:** 105.
- **Cut surgically:** 93% of those with more than one segment; the rest were withheld whole.
- **Data kept:** a median of 87% of the text.
- **Injection removed:** 77 of 78 cut results pass a fresh check once the cut marker is excluded. With the marker in,
  the judge flags the marker's own wording; that doesn't affect the guardrail, which always re-rates the original.
- **Speed of the extra call:** 1.0 s p50, 1.4 s p95 with no reasoning effort. With "low" effort it often ran out of
  output budget.

### Agent loop (AgentDojo and AgentThreatBench through the gateway)

The first four arms ran together, with 4 agents in flight per arm to stay under the OpenAI rate limit
([agent eval](agent-eval.md)). The first attempt at 8 per arm exhausted the limit and failed open, and is marked
invalid.

| Arm | Task success under attack | Task success, benign | AgentThreatBench task success | Attack success | Judge calls per agent call | Judge $ per 1k agent calls |
|---|---:|---:|---:|---:|---:|---:|
| no guardrail | 73% | 80% | 79% | 0% | — | — |
| cyber-guard (cache on) | 6% | 62% | 17% | 0% | 1.55 | $0.10 |
| agentic-security, whole withholding | 20% | 68% | 12% | 0% | 1.77 | $0.26 |
| agentic-security + system prompt | 23% | 70% | 21% | 0% | 1.76 | $0.28 |
| agentic-security, surgical (slow run*) | 58% | 62% | 46% | 0% AgentDojo, 12% ATB* | 2.13 | $0.46 |

**Clean rerun, all four arms together (`20261007-183106-full`, 4 agents per arm, 0 checks failed open). These are the
reference numbers:**

| Arm | Task success under attack | Task success, benign | ATB task success | Attack success (AgentDojo / ATB) | Judge calls per agent call | Judge $ per 1k agent calls |
|---|---:|---:|---:|---:|---:|---:|
| no guardrail | 73% | 78% | 79% | 0% / 8% | — | — |
| cyber-guard (cache on) | 6% | 61% | 12% | 0% / 0% | 1.51 | $0.11 |
| **agentic-security** | **56%** | **70%** | **46%** | 0% / 8% | 2.11 | $0.41 |
| agentic-security + system prompt | 49% | 68% | 50% | 0% / 12% | 2.11 | $0.45 |

- **With gpt-6-luna as the agent, there was nothing to stop on AgentDojo.** The model ignored every attack even with
  no guardrail. agentic-security still cut injected content from 196 tool results, but the outcome would have been the
  same. Its value on these benchmarks is keeping tasks alive, not stopping attacks; the Gemma run below shows
  protection.
- **Every attack that succeeded against agentic-security was AgentThreatBench "autonomy hijack"** (ah_001 and ah_003;
  agentic-security + system prompt also missed ah_002), where injected
  content pulls the agent off its task: 2 of 6, the same as with no guardrail. cyber-guard "stopped" them only by
  refusing the turn, which ends the run, at 12% task success. Detecting off-task drift in tool results is the next
  gap to work on.
- **Request latency** (inference plus checks, p50 / p95): no guardrail 2.3 / 5.7 s, cyber-guard 2.8 / 5.6 s,
  agentic-security 4.4 / 9.4 s.

- **Surgical withholding nearly triples task success under attack** (20% to 58%; 73% with no guardrail). It cut
  only the injected lines in 268 of 477 withheld results and withheld 209 whole, the rest being single-line
  results or failed locates. AgentThreatBench task success rose from 12% to 46%. It costs about 0.36 more judge
  calls per agent call, because a flagged result stays in the window and is re-cut every turn.
- \* **The single-arm surgical run is less clean.** It ran alone (one arm) after the other arms, during a period when the agent
  model's own calls were slow (p95 23 s vs 6 s before), and 34 of about 1,600 checks (2%) failed open on the 10 s
  deadline. So its attack-success figures are not reliable: AgentThreatBench's 12% is 3 of 24, with fail-opens in
  the run. Benign task success of 62% vs 68% is within the run-to-run noise of 96 tasks. Judge calls themselves
  were normal (median 1.16 s).
- **Attack success is 0% even with no guardrail.** gpt-6-luna ignores these injections on its own, so this benchmark
  shows the guard's cost to legitimate work, not what it prevents. A weaker agent model is needed to show
  protection.
- **Why tasks failed with whole withholding:**
  - **Under attack:** in 76 of 77 failed tasks, the result that was withheld was the one the task needed, because
    AgentDojo plants the attack inside the bill, email or file. Surgical withholding targets this.
  - **Benign:** replaying the benign runs, about 9 of 96 tasks had a tool result wrongly withheld, mostly "do the
    tasks on my TODO list" delegation. About 8 had a legitimate tool call refused.

### Protection with a weaker agent model (Gemma 4 e2b, local)

gpt-6-luna ignores AgentDojo's injections on its own, so the run above can't show protection. The same eval was
repeated with `gemma4:e2b` (local, Ollama) as the agent, which falls for them. It ran 12 samples per AgentDojo task
and all 24 AgentThreatBench tasks, with 0 checks failing open (run `20261007-165733-full`). The 12-sample limit takes
the first 12 AgentDojo attacks, which are all in the **banking** suite, so the AgentDojo result covers banking only.

| Benchmark | No guardrail | agentic-security |
|---|---:|---:|
| AgentDojo: attack success | **42%** (5 of 12) | **0%** |
| AgentDojo: task success under attack | 25% | 42% |
| AgentDojo: task success, benign | 33% | 50% |
| AgentThreatBench: attack success | 4% (1 of 24) | 0% |
| AgentThreatBench: task success | 12% | 12% |

- **The five AgentDojo attacks it stopped:**
  - sending the user's streaming service to the attacker's account (data leak);
  - sending a dinner companion's bank account number to the attacker, two variants (data leak);
  - sending as much money as possible to the attacker (theft);
  - changing the user's password (account takeover).

  It cut the injected instructions from tool output before Gemma read them (22 results) and blocked the resulting
  tool calls (12). The AgentThreatBench attack it stopped was memory poisoning (mp_001).
- **Every successful attack was stopped.** The guardrail also raised task success under attack, because cutting the
  injected lines keeps a weak agent from being derailed.
- **Small samples:** 12 per AgentDojo task, so read the direction, not exact percentages.
- **Run cost:** classifier latency was higher here (request p50 10.3 s, including Gemma's own slow local inference),
  and a withheld result was re-cut on every later turn: 22 distinct results, 1,040 times.

### Reliability fixes (2026-10-08)

A review of LiteLLM's guardrail framework and industry practice
([research](research/LiteLLM%20agent%20guardrail%20practices.md)) found gaps where the guard failed quietly in
the attacker's favour. All of them are fixed in the drop-in file, with tests (`tests/test_agentic_security.py`, 26
tests):

| Gap | Fix |
|---|---|
| A safety block on the judge call itself (for example OpenAI `cyber_policy`, or an empty `content_filter` reply) was treated as "judge unavailable", so the request **failed open**: the riskiest content was the most likely to pass | The entries in that call count as flagged. Judge calls carry a hashed per-caller `safety_identifier` |
| On Anthropic `/v1/messages` and the Responses API, the tool-call check saw little or none of the conversation, and a blocked reply fell back to LiteLLM's raised refusal (not billed, odd shapes) | The conversation is read from Anthropic content blocks and Responses input items; blocked replies are rewritten in place on all three APIs and stay billed |
| LiteLLM logged every run that returned normally as `success`, fail-opens and withholds included | Each run records its real status: `success`, `guardrail_intervened` or `guardrail_failed_to_respond` |
| A cut tool result reached the model again once the window scrolled past it (after about five tool round-trips) | Every tool result since the user's last message is re-rated (`tool_results: turn`), and the user's last message stays in view |
| LiteLLM settings could silently hide tool results or user messages from the guard | An error is logged when one is on; `scan_only_tool_results` is rejected at startup |
| The refusal didn't tell the agent what to do | It now says not to retry or work around the block, to tell the user, and to continue other allowed work |

End to end on LiteLLM 1.103.2, every model call stayed billed to the caller on all 7 paths of all three APIs.
Two gaps remain, both in LiteLLM itself:
- it doesn't run post-call guardrails on streamed `/v1/messages` replies, so a flagged tool call reaches the
  client;
- its own Responses-API refusal for a pre-call block is malformed (the model still doesn't run).

Details are in [the deploy README](../deploy/agentic-security/README.md).

## Known limits and next steps

- **LiteLLM gaps:** post-call checks don't run on streamed Anthropic Messages replies, and the pre-call refusal on
  the Responses API is malformed (above). Both need upstream fixes, or a custom streaming hook in this guard.
- **Scroll-out across turns:** with `tool_results: turn`, a cut tool result from an earlier user turn is no longer
  re-rated after the user's next message. With `tool_results: window`, one older than the window reaches the model
  again.
- **Judge cost on long agent loops:** `tool_results: turn` re-rates every tool result of the turn on every step.
- **Mid-session tool changes:** tool definitions changed within a user turn aren't re-checked.
- **Long content:** entries over 24,000 characters are trimmed to their start and end for the judge, and are
  withheld whole if flagged.
- **Delegated tasks:** false withholds should be tuned on a separate dev set of benign delegated content paired with
  injected versions, not on AgentDojo itself.
- **Protection:** shown with Gemma 4 (above). A larger sample would tighten the numbers.

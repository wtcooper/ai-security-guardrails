# Self-hosted decision models: size and fine-tuning

**Question:** can a decision model we host ourselves match TypeSafe Jev, the hosted decision API? And does that
take a bigger model, or fine-tuning on our own data?

**Answer (2026-10-08):**
- **Kev-9B fine-tuned on our clean training set matches Jev overall** on both held-out test sets: F1 0.93 vs 0.92
  on our cyber & agent test set, and 0.89 vs 0.88 on the public benchmarks.
- **It is weaker on agent tool calls.** It catches 54% of unsafe tool calls, vs 89% for Jev.
- **Fine-tuning mattered more than size.** At 0.4B parameters, Laya fine-tuned on the same data still catches only
  about two-thirds of attacks when held to the same false-alarm level as the judges.

## Setup

Every model is asked the same thing, scored on the same cases, and decided by the same rule.

- **Questions:** the tuned Jev question set
  ([jev/tuned.yaml](../src/guardlab/decisions/policies/jev/tuned.yaml)), with the same context for tool calls (the
  user's request, the agent's earlier steps, the app's rules) and the same per-question thresholds.
- **Test sets:** the two held-out test sets from [the README](../README.md#how-we-test): our cyber & agent test
  set (407 cases) and the public benchmarks (1,578 cases). No compared model was trained or tuned on them
  ([data provenance](data-provenance.md)).
- **Fine-tunes:** Kev-9B and Laya v2 were trained on the same 4,375 records, built from public datasets and generated
  cases that pass our leak check ([data-provenance.md §2](data-provenance.md#2-decision-model-training-set)). Each ran one pass
  on [Modal](https://modal.com) serverless GPUs:
  - Kev-9B: one H100 for about 61 minutes, about $4. Kev's own trainer adds LoRA adapters to the published Kev-9B.
  - Laya: one L4 for about 39 minutes, under $1. The top 6 encoder layers were trained.
- **Comparison:** [held_out.py](../evals/lab/experiments/held_out.py) produces every number below.

## Results at Jev's thresholds

(`agentic-security` rows: fresh run of 2026-10-09, after the reliability fixes.)

"Caught" is the share of attacks blocked. "False alarms" is the share of legitimate cases blocked. AUROC measures
how well a model's score ranks attacks above legitimate cases, ignoring the threshold (1.0 is perfect).

| Model | Size | Ran on | Our test set: F1 | caught | false alarms | Public: F1 | caught | false alarms | AUROC (ours / public) |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| **kev-tuned-9b** (ours) | 9B | Modal H100 | **0.93** | **89%** | 4.6% | **0.89** | 87% | 7.1% | 0.96 / 0.95 |
| jev-base (hosted API) | not disclosed | OpenRouter | 0.92 | 88% | 4.6% | 0.88 | 87% | 8.6% | **0.97 / 0.96** |
| clef-base-9b | 9B | OpenRouter | 0.87 | 79% | 4.6% | 0.73 | 69% | 16.5% | 0.91 / 0.83 |
| kev-base-9b | 9B | Modal H100 | 0.86 | 81% | 13.7% | 0.74 | 73% | 19.4% | 0.88 / 0.84 |
| laya-tuned-0.4b-v2 (ours) | 0.4B | Modal L4 | 0.86 | 89% | 28.8% | 0.73 | 74% | 21.2% | 0.90 / 0.84 |
| kev-base-4b | 4B | OpenRouter | 0.84 | 78% | 13.7% | 0.75 | 70% | 13.4% | 0.87 / 0.83 |
| laya-tuned-0.4b (our older fine-tune) | 0.4B | Modal L4 | 0.81 | 99% | 75.2% | not clean * | | | 0.88 / — |
| laya-base-0.4b | 0.4B | Modal L4 | 0.77 | 95% | 87.6% | 0.58 | 80% | 73.8% | 0.61 / 0.71 |
| strands-base-2b | 2B | Mac (local) | 0.74 | 80% | 57.5% | not run | | | 0.77 / — |
| *For reference:* agentic-security (LLM judge) | — | gpt-6-luna | 0.91 | 85% | 4.6% | 0.86 | 78% | 1.9% | 0.92 / 0.91 |

\* The older Laya fine-tune trained on 317 of the public-benchmark cases, so its public results are not reported.

### At the judges' false-alarm level

Jev's thresholds don't suit every model: the small Laya models flag most legitimate cases at those settings. For
models scored on Modal, this table instead uses one cut-off per model, chosen on the dev calibration sample (tuning
data only) as the lowest that flags at most 5% of legitimate cases. That is roughly where the judges run.

| Model | Our test set: F1 | caught | false alarms | Public: F1 | caught | false alarms |
|---|---:|---:|---:|---:|---:|---:|
| kev-tuned-9b | 0.92 | 88% | 4.6% | 0.89 | 86% | 6.3% |
| kev-base-9b | 0.85 | 76% | 5.9% | 0.72 | 67% | 15.1% |
| laya-tuned-0.4b-v2 | 0.77 | 65% | 5.2% | 0.56 | 41% | 2.8% |
| laya-tuned-0.4b (older) | 0.75 | 64% | 9.8% | not clean | | |
| laya-base-0.4b | 0.15 | 8% | 3.3% | 0.46 | 31% | 1.5% |

### By attack type (our test set, Jev's thresholds; Laya v2 at the 5% level)

F1, with the share caught and false alarms in brackets.

| Cases | jev-base | kev-tuned-9b | kev-base-9b | laya-tuned-0.4b-v2 | agentic-security |
|---|---|---|---|---|---|
| Cyber requests (239) | 0.95 (92% / 4%) | **0.98 (96% / 3%)** | 0.93 (94% / 17%) | 0.92 (87% / 3%) | 0.92 (87% / 5%) |
| Injection in user input (75) | 0.86 (78% / 3%) | **0.89 (85% / 9%)** | 0.83 (83% / 21%) | 0.59 (46% / 12%) | 0.85 (73% / 0%) |
| Agent tool calls (50) | **0.89 (89% / 14%)** | 0.67 (54% / 9%) | 0.68 (54% / 5%) | 0.13 (7% / 5%) | **0.89 (89% / 14%)** |
| Tool results and definitions (43) | 0.87 (77% / 0%) | 0.90 (82% / 0%) | 0.31 (18% / 0%) | 0.16 (9% / 5%) | **0.98 (95% / 0%)** |

The per-type samples are small (43–75 cases outside cyber requests), so differences under about 0.1 F1 are not
reliable.

### Per public benchmark (F1)

| Benchmark | jev-base | kev-tuned-9b | agentic-security | clef-base-9b |
|---|---:|---:|---:|---:|
| Microsoft BIPIA (injection in documents) | 0.86 | 0.90 | **0.96** | 0.29 |
| deepset | 0.79 | **0.83** | 0.59 | 0.71 |
| jackhhao | 0.96 | **0.97** | 0.94 | 0.81 |
| rogue-security | **0.81** | 0.78 | 0.70 | 0.78 |
| xTRam1 | **0.97** | **0.97** | 0.89 | 0.94 |

Our training set includes the separate training halves of deepset and jackhhao. These cases were never trained
on, but they come from the same sources. The fine-tune's lead over Jev there is small (+0.04 and +0.01). Its largest
gain, on BIPIA, comes from a benchmark that is not in the training data at all.

## What this shows

1. **Fine-tuning closes the gap at 9B.**
   - It raised Kev-9B from F1 0.86 to 0.93 on our test set and from 0.74 to 0.89 on the public benchmarks.
   - False alarms fell from 14–19% to 5–7%.
   - One pass over 4,375 records was enough.
2. **Agent tool calls are the gap.** The fine-tune didn't improve tool calls at all (0.68 → 0.67), while Jev
   catches 89%. The training set has only 72 unsafe tool calls (§2 of the provenance doc). More tool-call data is
   the obvious next lever ([data-provenance.md §9](data-provenance.md#9-future-data-sources) lists sources).
3. **0.4B is too small for this job.**
   - Laya v2 ranks cases far better than the base model (AUROC 0.90 vs 0.61) and better than our older fine-tune.
   - At a 5% false-alarm level it still catches only 65% of attacks on our test set and 41% on the public
     benchmarks.
   - It is useful mainly on cyber requests (0.92).
4. **Out of the box, Clef-9B is the strongest open model** (0.87 on our test set). It does poorly on BIPIA
   document injection (0.29).

## Caveats

- **One training run and one seed each.** No second epoch has been tried.
- **Latency.**
  - These latencies come from Kev's unoptimised local runner on an H100, so they don't measure serving speed: a
    median of 0.38 s per check for the fine-tune and 2.6 s for the base model.
  - The 7× difference between those two has not been investigated.
  - Jev's hosted API takes 0.22 s.
- **The 9B models need a GPU server.** That conflicts with the drop-in rule for the enterprise gateway (no new
  infrastructure), unless an existing model-serving endpoint can host them.
- **Small test slices.** Tool-definition (2 cases) and tool-result (41) coverage in our test set is thin.
- **Earlier export.** Both fine-tunes trained on the first export, which included 31 rows built from AgentDojo
  attack goals. The 9 test and calibration cases that share identifiers with those rows were removed for every
  model ([data-provenance.md §4](data-provenance.md#4-contamination-controls)).

## Cost

Modal metered cost for all of this work, about $21 in total, was covered by Modal's free monthly credits. It
includes a smoke run, both fine-tunes, five scoring runs, and one scoring run lost to a timeout.

## Reproduce

```bash
uv run python training/decision_models/export_data.py
modal run training/decision_models/modal_kev.py::train --name kev-tuned-9b --epochs 1
modal run training/decision_models/modal_kev.py::score --run kev-tuned-9b --name kev-tuned-9b
modal run training/decision_models/modal_kev.py::score --run jaredpalmer/kev-9b --name kev-base-9b
modal run training/decision_models/modal_laya.py::train --name laya-tuned-0.4b-v2
modal run training/decision_models/modal_laya.py::score --run laya-tuned-0.4b-v2 --name laya-tuned-0.4b-v2
uv run python evals/lab/experiments/held_out.py --report jev-base,modal:kev-tuned-9b,modal:kev-tuned-9b@calib
```

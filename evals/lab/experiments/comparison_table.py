"""The README's full comparison table, generated from the held-out result logs (one source for every number).

    uv run python evals/lab/experiments/comparison_table.py > /tmp/table.md   # then paste it into README.md

Every cell uses held_out.py's whole-set rule; F1 comes with its 95% bootstrap interval.
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from held_out import f1_interval, metrics, modal_results, registry_results, sets  # noqa: E402

D = sets()
ROWS = [  # (category, guard, results source, description, where latency was measured, status)
    ("LLM-as-a-judge: a hosted LLM reads our written policies", None, None, None, None),
    ("agentic-security", "reg", "Drop-in LiteLLM guardrail. gpt-6-luna rates the last 10 messages: one call before the model, one after only if it calls tools. Cuts injected lines out of tool results so the agent keeps working", "OpenAI API", "**Active, ready to deploy**"),
    ("cyber-guard", "reg", "Lab judge: same model and policies, one call per piece of content; affordable only with a verdict cache", "OpenAI API", "Lab only"),
    ("agentic-security-sys", "reg", "agentic-security with the application's system prompt also shown to the judge", "OpenAI API", "Measured alternative: more false blocks on tool calls; keep off"),
    ("Hosted decision API: a provider's decision model answers our yes/no questions", None, None, None, None),
    ("jev-base", "reg", "TypeSafe Jev via OpenRouter, asked our tuned questions (the judge's policies phrased as questions); one call returns a probability per question", "OpenRouter", "**Active:** pre-filter in front of the judge"),
    ("jev-base-stockq", "reg", "Same model with the original generic security questions", "OpenRouter", "Superseded by jev-base"),
    ("Self-hosted decision model: open weights we run (or fine-tune), asked the same questions as jev-base", None, None, None, None),
    ("kev-tuned-9b", "modal", "Kev-9B (Qwen3.5-9B base) fine-tuned by us on 4,375 clean records", "1× H100, unoptimised runner", "**Active:** matches Jev; weak on tool calls; needs a GPU server"),
    ("clef-base-9b", "reg", "Cloudflare Clef-flash 9B, out of the box", "OpenRouter-hosted", "Benchmarked"),
    ("kev-base-9b", "modal", "Kev-9B, out of the box", "1× H100, unoptimised runner", "Baseline for the fine-tune"),
    ("kev-base-4b", "reg", "Kev-4B (Qwen3.5-4B base), out of the box", "OpenRouter-hosted", "Benchmarked"),
    ("laya-tuned-0.4b-v2", "modal", "Laya (ModernBERT-large, 0.4B) fine-tuned by us on the same records", "1× L4 GPU", "Too small: flags 29% of legitimate cases"),
    ("laya-tuned-0.4b", "modal", "Our earlier Laya fine-tune (older question set)", "1× L4 GPU", "Retired"),
    ("laya-base-0.4b", "modal", "Laya, out of the box", "1× L4 GPU", "Baseline"),
    ("strands-base-2b", "reg", "AWS Strands Decider 2B, out of the box", "Mac (local)", "Benchmarked"),
    ("Self-hosted classifier: a safety model we run locally", None, None, None, None),
    ("safeguard-20b", "reg", "OpenAI gpt-oss-safeguard 20B: a reasoning model that follows whatever policy it is given; given our judge's policies, one call per policy", "Mac (local)", "Benchmarked"),
    ("nemotron-cs-4b", "reg", "NVIDIA Nemotron 3.5 Content Safety 4B, given our policy text as a custom policy", "Mac (local)", "Benchmarked"),
    ("granite-guardian-8b", "reg", "IBM Granite Guardian 4.1 8B: built-in jailbreak and harm checks, custom criteria for agent content", "Mac (local)", "Benchmarked"),
    ("shieldstral-3b", "reg", "Mistral Shieldstral 1.0 3B: one score per yes/no policy question", "Mac (local)", "Benchmarked"),
    ("qwen3guard-4b", "reg", "Alibaba Qwen3Guard-Gen 4B: fixed safety categories, including jailbreak", "Mac (local)", "Benchmarked"),
    ("qwen3guard-0.6b", "reg", "Qwen3Guard-Gen 0.6B: the same, smaller", "Mac (local)", "Benchmarked"),
    ("sentinel-v2", "reg", "rogue-security (Qualifire) Sentinel v2: prompt-injection and jailbreak classifier; user-side text only †", "Mac (local)", "Benchmarked ‡"),
    ("llama-guard4-12b", "reg", "Meta Llama Guard 4 12B: content-safety model with no prompt-injection category; 4,000-token context §", "Mac (local)", "Benchmarked"),
    ("pg2-86m", "reg", "Meta Llama Prompt Guard 2 86M: prompt-injection and jailbreak classifier; user-side text only †", "Mac (local)", "Benchmarked"),
    ("deberta-pi-v2", "reg", "ProtectAI DeBERTa-v3 prompt-injection v2 (now hosted by Red Hat); user-side text only †", "Mac (local)", "Benchmarked"),
    ("pg2-22m", "reg", "Meta Llama Prompt Guard 2 22M; user-side text only †", "Mac (local)", "Benchmarked"),
]
NOT_CLEAN = {("laya-tuned-0.4b", "public")}   # trained on 317 of these cases
print("| Guardrail | What it is | Our test set: F1 (95% CI) · caught · false alarms | Public: F1 (95% CI) · caught · false alarms | Median latency per check | Status |")
print("|---|---|---|---|---|---|")
for name, src, desc, where, status in ROWS:
    if src is None:
        print(f"| **{name}** | | | | | |")
        continue
    res = modal_results(name) if src == "modal" else registry_results(name)
    cells = []
    for s in ("cyber-agent", "public"):
        rows = D[s]
        if (name, s) in NOT_CLEAN:
            cells.append("not clean (trained on these)")
            continue
        if sum(r["id"] in res for r in rows) < 0.5 * len(rows):
            cells.append("not run")
            continue
        pairs = [(r["label"], *res[r["id"]][:2]) if r["id"] in res else (r["label"], False, None) for r in rows]
        m, (lo, hi) = metrics(pairs), f1_interval(pairs)
        cells.append(f"**{m['f1']:.2f}** ({lo:.2f}–{hi:.2f}) · {100 * m['recall']:.0f}% · {100 * m['fpr']:.1f}%")
    lat = statistics.median(x[2] for x in res.values() if x[2] is not None) / 1000
    lat_s = f"{lat:.2f} s" if lat < 1 else f"{lat:.1f} s"
    where = where.replace("Mac (local)", "Mac").replace("OpenRouter-hosted", "OpenRouter")
    print(f"| `{name}` | {desc} | {cells[0]} | {cells[1]} | {lat_s} ({where}) | {status} |")
for s in ("cyber-agent", "public"):
    m = metrics([(r["label"], True, None) for r in D[s]])
    print(f"<!-- block-everything baseline {s}: F1 {m['f1']:.2f} -->")

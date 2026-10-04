"""Fine-tune Laya on the s1guard benchmark TRAIN split.

Every (row, question) pair with a clear answer is one `noul` example, using the exact question
text the gateway asks (the bundled policy):
  positive = the row's category is one the question targets (RECIPES below)
  negative = a benign row of the same stage (incl. hard negatives: role-play, OR-Bench-hard,
             borderline CyberSecEval code requests, real benign model replies)
The bottom encoder layers are frozen; the top --train-layers encoder layers (full weights, or LoRA
adapters with --lora) and the decision head learn with cross-entropy on Laya's two noul option
logits. Saves a normal Laya checkpoint dir (LoRA merged) that `S1GUARD_LAYA_MODEL=<dir>` loads.

Defaults reproduce the v1/v2 recipe. Opt-in additions (v3, see docs/training-methods.md):
  --recipe v3     also train tool-call and harmful-reply questions
  --recipe v4     v3 + `unrequested_action` (tool call vs the user's request)
  --lora R        rank-R LoRA on the top layers instead of full weights (far less memory)
  --distill N     keep untrained questions close to the original model (N rows per question)
  --bucket        length-bucketed batches (less padding compute)
  --best          keep the epoch with the best example-weighted mean dev AUROC
  --cooldown F    sleep F x step-time after each step (caps sustained chip load)
The trainer always pauses while macOS reports a thermal/performance warning (`pmset -g therm`).

    uv run python experiments/s1guard_finetune/train_laya.py --out experiments/s1guard_finetune/models/laya-s1guard
"""

import argparse
import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from s1guard import STAGE_FIELDS, Guard  # noqa: E402

V2 = {  # question -> benchmark categories it should answer "true" for
    "prompt_injection": {"prompt_injection"},
    "jailbreak": {"jailbreak"},
    "hidden_context_extraction": {"data_leakage"},
    "sensitive_data_request": {"data_leakage"},
    "cyber_offense": {"cyber"},
    "harmful_content": {"content_safety", "cyber"},
    "multiturn_escalation": {"escalation"},
    "indirect_prompt_injection": {"indirect_injection"},
    "tool_poisoning": {"tool_poisoning"},
    "hidden_context_exposure": {"hidden_context_exposure"},
}
V3 = V2 | {
    "destructive_action": {"tool_misuse"},
    "data_exfiltration": {"tool_exfiltration"},
    "harmful_compliance": {"harmful_compliance"},
}
RECIPES = {"v2": V2, "v3": V3, "v4": V3 | {"unrequested_action": {"tool_misuse", "tool_exfiltration"}}}
CONTEXT_FIELD = {}  # risk id -> context field of its context question (from the policy, set in main)
POSITIVE = V2  # set from --recipe in main()


def rows(split):
    return [json.loads(l) for l in open(HERE / "data" / f"{split}.jsonl")]


def examples(rs, questions, context_questions, rng, neg_ratio=1.5, min_pos=120):
    """[(state, stage, qid, context, label)] -- per question: all positives (oversampled up to
    min_pos) plus neg_ratio x as many benign rows of the same stage. A row carrying a risk's
    context (system prompt / user request) trains its context question with that field in the
    state, as the gateway asks it. Context-only questions use only rows that have the context."""
    def ex(r, stage, qid, label):
        fld, cf = STAGE_FIELDS[stage], CONTEXT_FIELD.get(qid, "system_prompt")
        if r["state"].get(cf) and qid in context_questions[stage]:
            return {cf: r["state"][cf], fld: r["state"][fld]}, stage, qid, True, label
        return {fld: r["state"][fld]}, stage, qid, False, label

    out = []
    for stage in STAGE_FIELDS:
        plain = list(questions.get(stage, {}))   # policy order -- keeps v1/v2 sampling identical
        stage_rows = [r for r in rs if r["stage"] == stage]
        for qid in plain + [q for q in context_questions.get(stage, {}) if q not in plain]:
            if qid not in questions.get(stage, {}):  # context-only question: rows need the context
                stage_rows_q = [r for r in stage_rows if r["state"].get(CONTEXT_FIELD.get(qid, "system_prompt"))]
            else:
                stage_rows_q = stage_rows
            benign = [r for r in stage_rows_q if not r["attack"]]
            pos = [r for r in stage_rows_q if r["category"] in POSITIVE[qid]]
            if not pos or not benign:
                continue
            pos = pos * max(1, -(-min_pos // len(pos)))
            neg = rng.sample(benign, min(len(benign), int(len(pos) * neg_ratio)))
            out += [ex(r, stage, qid, 1) for r in pos] + [ex(r, stage, qid, 0) for r in neg]
    rng.shuffle(out)
    return out


class LoRALinear(torch.nn.Module):
    """y = base(x) + (x A^T B^T) * alpha/r; base frozen. merged() folds the update into a plain Linear."""

    def __init__(self, base: torch.nn.Linear, r: int, alpha: float):
        super().__init__()
        self.base, self.scale = base, alpha / r
        self.A = torch.nn.Parameter(torch.randn(r, base.in_features, device=base.weight.device) / base.in_features ** 0.5)
        self.B = torch.nn.Parameter(torch.zeros(base.out_features, r, device=base.weight.device))

    def forward(self, x):
        return self.base(x) + (x @ self.A.t() @ self.B.t()) * self.scale

    def merged(self) -> torch.nn.Linear:
        with torch.no_grad():
            self.base.weight += (self.B @ self.A) * self.scale
        return self.base


LORA_TARGETS = ("attn.Wqkv", "attn.Wo", "mlp.Wi", "mlp.Wo")  # ModernBERT layer linears


def _swap(layer, path, new):
    parent, name = layer.get_submodule(path.rsplit(".", 1)[0]), path.rsplit(".", 1)[1]
    setattr(parent, name, new)


def free_device_cache(device: str) -> None:
    """Release cached MPS/CUDA blocks. Variable-length batches create many tensor shapes and the
    MPS caching allocator otherwise grows until macOS swaps (observed: 24 GB, ~10x slower steps)."""
    import gc
    gc.collect()
    if device == "mps":
        torch.mps.empty_cache()
    elif device.startswith("cuda"):
        torch.cuda.empty_cache()


def device_gb(device: str) -> float:
    return torch.mps.driver_allocated_memory() / 1e9 if device == "mps" else 0.0


def thermal_ok() -> bool:
    try:
        out = subprocess.run(["pmset", "-g", "therm"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return True
    return "No thermal warning level" in out and "No performance warning level" in out


def main():
    global POSITIVE
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="convaiinnovations/laya", help="HF id or local checkpoint dir to start from")
    ap.add_argument("--out", default=str(HERE / "models" / "laya-s1guard"))
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--head-lr", type=float, default=1e-4)
    ap.add_argument("--train-layers", type=int, default=6, help="top encoder layers to unfreeze")
    ap.add_argument("--device", default="mps")
    ap.add_argument("--policy", help="policy YAML whose question texts are trained (default: bundled)")
    ap.add_argument("--no-context", action="store_true",
                    help="v1 recipe: ignore system prompts and skip the system-prompt-paired (+sp) rows")
    ap.add_argument("--recipe", choices=sorted(RECIPES), default="v2")
    ap.add_argument("--lora", type=int, default=0, metavar="R", help="LoRA rank on the top layers (0 = full weights)")
    ap.add_argument("--lora-lr", type=float, default=2e-4)
    ap.add_argument("--distill", type=int, default=0, metavar="N",
                    help="rows per untrained question to distil from --teacher (anti-drift)")
    ap.add_argument("--teacher", default="convaiinnovations/laya")
    ap.add_argument("--bucket", action="store_true", help="length-bucketed batches")
    ap.add_argument("--best", action="store_true", help="restore the epoch with the best mean dev AUROC")
    ap.add_argument("--cooldown", type=float, default=0.0, help="sleep this x step-time after each step")
    a = ap.parse_args()
    POSITIVE = RECIPES[a.recipe]

    import laya
    from laya.agent import Agent
    from laya.common import collate_items

    torch.manual_seed(0)
    rng = random.Random(0)
    guard = Guard(backend=type("NoBackend", (), {"name": "none"})(), policy=a.policy)  # question texts only
    CONTEXT_FIELD.update({r.id: r.context_field for r in guard.risks})
    questions = {s: {q: d for q, d in guard._questions[s].items() if q in POSITIVE} for s in STAGE_FIELDS}
    context_questions = {s: {} if a.no_context else {q: d for q, d in guard._context_questions[s].items() if q in POSITIVE}
                         for s in STAGE_FIELDS}
    internal = {(s, q, False): Agent._to_internal(d) for s, d_ in guard._questions.items() for q, d in d_.items()}
    internal |= {(s, q, True): Agent._to_internal(d) for s, qs in context_questions.items() for q, d in qs.items()}
    keep = (lambda r: not r["id"].endswith("+sp")) if a.no_context else (lambda r: True)
    train_rows = [r for r in rows("train") if keep(r)]
    train = examples(train_rows, questions, context_questions, rng)
    dev = examples([r for r in rows("dev") if keep(r)], questions, context_questions, random.Random(1), neg_ratio=1.0, min_pos=1)
    print(f"train examples {len(train)}  dev examples {len(dev)}", flush=True)

    def encode(agent, ex):
        state, stage, qid, ctx, _ = ex
        return agent._encode_state(state, [qid], {qid: internal[(stage, qid, ctx)]})

    # Anti-drift: soft targets from the ORIGINAL model for questions this recipe does not train.
    soft = []
    if a.distill:
        drng = random.Random(2)
        dist = []
        for stage, qs in guard._questions.items():
            stage_rows = [r for r in train_rows if r["stage"] == stage]
            for qid in qs:
                if qid in POSITIVE or not stage_rows:
                    continue
                fld = STAGE_FIELDS[stage]
                dist += [({fld: r["state"][fld]}, stage, qid, False, None)
                         for r in drng.sample(stage_rows, min(a.distill, len(stage_rows)))]
        teacher = laya.load(a.teacher, device=a.device)
        teacher.model.eval()
        with torch.no_grad():
            for i in range(0, len(dist), 32):
                chunk = [encode(teacher, e) for e in dist[i:i + 32]]
                b = collate_items(chunk, teacher.tok.pad_token_id)
                lg, _ = teacher.model(*(b[k].to(a.device) for k in ("input_ids", "attention_mask", "marker_pos",
                                                                      "marker_mask", "qtype")))
                soft += torch.softmax(lg[:, :2].float(), -1).cpu().tolist()
        del teacher
        free_device_cache(a.device)
        print(f"distillation examples {len(dist)} (untrained questions, teacher {a.teacher})", flush=True)
        train = train + dist

    agent = laya.load(a.base, device=a.device)
    t0 = time.time()
    train_items = [encode(agent, e) for e in train]
    dev_items = [encode(agent, e) for e in dev]
    # every training target as a 2-way distribution [p(false), p(true)]
    targets = [[1.0 - e[4], float(e[4])] for e in train[:len(train) - len(soft)]] + soft
    print(f"encoded in {time.time() - t0:.0f}s", flush=True)

    model = agent.model
    enc = model.encoder
    for p in model.parameters():
        p.requires_grad = False
    top_layers = list(enc.layers[-a.train_layers:])
    head = [model.head, model.type_emb, model.scorer]
    lora = []
    if a.lora:
        for layer in top_layers:
            for path in LORA_TARGETS:
                m = LoRALinear(layer.get_submodule(path), a.lora, 2.0 * a.lora)
                _swap(layer, path, m)
                lora.append((layer, path, m))
        groups = [{"params": [p for _, _, m in lora for p in (m.A, m.B)], "lr": a.lora_lr}]
        head.append(enc.final_norm)
    else:  # v1/v2 recipe: full weights of the top layers + final norm at the encoder lr
        top_layers.append(enc.final_norm)
        for m in top_layers:
            for p in m.parameters():
                p.requires_grad = True
        groups = [{"params": [p for m in top_layers for p in m.parameters()], "lr": a.lr}]
    for m in head:
        for p in m.parameters():
            p.requires_grad = True
    groups.append({"params": [p for m in head for p in m.parameters()], "lr": a.head_lr})
    trainable = [p for g in groups for p in g["params"]]
    print(f"trainable params {sum(p.numel() for p in trainable) / 1e6:.1f}M", flush=True)
    opt = torch.optim.AdamW(groups, weight_decay=0.01)
    steps = a.epochs * (len(train_items) // a.batch)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, s / max(1, steps * 0.05)) * max(0.0, 1 - s / steps))
    dev_ = torch.device(a.device)

    def batch_logits(items):
        b = collate_items(items, agent.tok.pad_token_id)
        logits, _ = model(b["input_ids"].to(dev_), b["attention_mask"].to(dev_), b["marker_pos"].to(dev_),
                          b["marker_mask"].to(dev_), b["qtype"].to(dev_))
        return logits[:, :2]  # noul: [false, true]

    def evaluate():
        model.eval()
        by_q = {}
        with torch.no_grad():
            for i in range(0, len(dev_items), 32):
                p = torch.softmax(batch_logits(dev_items[i:i + 32]).float(), -1)[:, 1].cpu().numpy()
                for (_, _, qid, ctx, y), pi in zip(dev[i:i + 32], p):
                    by_q.setdefault(qid + ("+ctx" if ctx else ""), []).append((y, pi))
        model.train()
        aus, ns = [], []
        for qid, v in sorted(by_q.items()):
            y, s = np.array([t[0] for t in v]), np.array([t[1] for t in v])
            pos, neg = s[y == 1], s[y == 0]
            au = (pos[:, None] > neg[None, :]).mean() if len(pos) and len(neg) else float("nan")
            if au == au:
                aus.append(au)
                ns.append(len(v))
            print(f"    dev {qid:28s} n={len(v):4d} AUROC {au:.3f}", flush=True)
        # example-weighted, so a small noisy question can't decide model selection on its own
        return float(np.average(aus, weights=ns))

    def batches(order):
        if not a.bucket:
            return [order[i:i + a.batch] for i in range(0, len(order) - a.batch + 1, a.batch)]
        out, chunk = [], 64 * a.batch
        for c in range(0, len(order), chunk):     # sort within chunks, then shuffle the batches
            part = sorted(order[c:c + chunk], key=lambda j: len(train_items[j][0]["ids"]))
            out += [part[i:i + a.batch] for i in range(0, len(part) - a.batch + 1, a.batch)]
        rng.shuffle(out)
        return out

    print("before training:", flush=True)
    best = (evaluate(), None)
    model.train()
    step, t0 = 0, time.time()
    for epoch in range(a.epochs):
        order = list(range(len(train_items)))
        rng.shuffle(order)
        for idx in batches(order):
            if step % 25 == 0:
                free_device_cache(a.device)
                while not thermal_ok():
                    print("  thermal/performance warning from macOS -- pausing 60s", flush=True)
                    time.sleep(60)
            ts = time.time()
            logits = batch_logits([train_items[j] for j in idx])
            tgt = torch.tensor([targets[j] for j in idx], device=dev_)
            loss = -(tgt * torch.log_softmax(logits.float(), -1)).sum(-1).mean()
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(trainable, 1.0)
            opt.step()
            sched.step()
            step += 1
            if a.cooldown:
                time.sleep(a.cooldown * (time.time() - ts))
            if step % 50 == 0:
                print(f"  epoch {epoch} step {step}/{steps} loss {loss.item():.3f} {(time.time() - t0) / step:.2f}s/step"
                      f" mem {device_gb(a.device):.1f}GB", flush=True)
        print(f"after epoch {epoch}:", flush=True)
        score = evaluate()
        print(f"    weighted mean dev AUROC {score:.4f}", flush=True)
        if a.best and score > best[0]:
            best = (score, {id(p): p.detach().cpu().clone() for p in trainable})
    if a.best and best[1] is not None:
        print(f"restoring best epoch (weighted mean dev AUROC {best[0]:.4f})", flush=True)
        with torch.no_grad():
            for p in trainable:
                p.copy_(best[1][id(p)].to(p.device))

    for layer, path, m in lora:  # fold LoRA into plain Linear weights -> standard checkpoint keys
        _swap(layer, path, m.merged())

    out = Path(a.out)
    if Path(a.base).is_dir():
        src = Path(a.base)
    else:
        from huggingface_hub import snapshot_download
        src = Path(snapshot_download(a.base, allow_patterns=["rl_agent_config.json", "model.safetensors",
                                                             "tokenizer/*", "encoder/*"]))
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src / "tokenizer", out / "tokenizer")
    shutil.copytree(src / "encoder", out / "encoder")
    cfg = json.loads((src / "rl_agent_config.json").read_text())
    cfg["s1guard_finetune"] = {"base": a.base, "recipe": a.recipe, "epochs": a.epochs, "train_layers": a.train_layers,
                               "lora": a.lora, "distill": a.distill, "examples": len(train),
                               "questions": sorted(POSITIVE), "previous": cfg.get("s1guard_finetune")}
    (out / "rl_agent_config.json").write_text(json.dumps(cfg, indent=1))
    from safetensors import safe_open
    from safetensors.torch import save_file
    with safe_open(str(src / "model.safetensors"), "pt") as base:  # keep the shipped dtypes (fp16 weights)
        dtypes = {k: base.get_slice(k).get_dtype() for k in base.keys()}
    to_torch = {"F16": torch.float16, "BF16": torch.bfloat16, "F32": torch.float32}
    save_file({k: v.detach().cpu().to(to_torch.get(dtypes.get(k), v.dtype)).contiguous().clone()
               for k, v in model.state_dict().items()}, str(out / "model.safetensors"))
    print(f"saved {out}", flush=True)


if __name__ == "__main__":
    main()

"""Fine-tune Laya on the shared decision-model training set (training/decision_models/data/train.jsonl).

The same records Kev trains on: every (record, question) pair is one yes/no example with the exact question text the
guard asks (the tuned question set, policy-text questions included). The bottom encoder layers stay frozen; the top
--train-layers layers (full weights, or rank-R LoRA with --lora) and the decision head learn with cross-entropy on
Laya's two noul logits, as in experiments/s1guard_finetune/train_laya.py (the recipe behind the earlier fine-tune).
Saves a standard Laya checkpoint directory.

    python train_laya.py --data data/train.jsonl --out runs/laya-tuned-0.4b-v2 --device cuda
"""

import argparse
import json
import random
import shutil
import time
from pathlib import Path

import torch

LORA_TARGETS = ("attn.Wqkv", "attn.Wo", "mlp.Wi", "mlp.Wo")   # ModernBERT layer linears


class LoRALinear(torch.nn.Module):
    """y = base(x) + (x A^T B^T) * alpha/r; base frozen. merged() folds the update into a plain Linear."""

    def __init__(self, base, r, alpha):
        super().__init__()
        self.base, self.scale = base, alpha / r
        self.A = torch.nn.Parameter(torch.randn(r, base.in_features, device=base.weight.device) / base.in_features ** 0.5)
        self.B = torch.nn.Parameter(torch.zeros(base.out_features, r, device=base.weight.device))

    def forward(self, x):
        return self.base(x) + (x @ self.A.t() @ self.B.t()) * self.scale

    def merged(self):
        with torch.no_grad():
            self.base.weight += (self.B @ self.A) * self.scale
        return self.base


def swap(layer, path, new):
    parent, name = layer.get_submodule(path.rsplit(".", 1)[0]), path.rsplit(".", 1)[1]
    setattr(parent, name, new)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--base", default="convaiinnovations/laya")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--head-lr", type=float, default=1e-4)
    ap.add_argument("--train-layers", type=int, default=6)
    ap.add_argument("--lora", type=int, default=0)
    ap.add_argument("--lora-lr", type=float, default=2e-4)
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()

    import laya
    from laya.agent import Agent
    from laya.common import collate_items
    torch.manual_seed(0)
    rng = random.Random(0)
    examples = []
    for rec in map(json.loads, open(a.data)):
        for qid, q in rec["questions"].items():
            qdef = {k: v for k, v in q.items() if k in ("type", "instructions", "criteria")}
            examples.append((rec["state"], qid, Agent._to_internal(qdef), float(bool(q["label"]))))
    print(f"examples {len(examples)} (positive {sum(e[3] for e in examples):.0f})", flush=True)

    agent = laya.load(a.base, device=a.device)
    t0 = time.time()
    items = [agent._encode_state(state, [qid], {qid: internal}) for state, qid, internal, _ in examples]
    targets = [[1.0 - y, y] for *_, y in examples]
    print(f"encoded in {time.time() - t0:.0f}s", flush=True)

    model, enc = agent.model, agent.model.encoder
    for p in model.parameters():
        p.requires_grad = False
    top = list(enc.layers[-a.train_layers:])
    head = [model.head, model.type_emb, model.scorer]
    lora = []
    if a.lora:
        for layer in top:
            for path in LORA_TARGETS:
                m = LoRALinear(layer.get_submodule(path), a.lora, 2.0 * a.lora)
                swap(layer, path, m)
                lora.append((layer, path, m))
        groups = [{"params": [p for _, _, m in lora for p in (m.A, m.B)], "lr": a.lora_lr}]
        head.append(enc.final_norm)
    else:
        top.append(enc.final_norm)
        for m in top:
            for p in m.parameters():
                p.requires_grad = True
        groups = [{"params": [p for m in top for p in m.parameters()], "lr": a.lr}]
    for m in head:
        for p in m.parameters():
            p.requires_grad = True
    groups.append({"params": [p for m in head for p in m.parameters()], "lr": a.head_lr})
    trainable = [p for g in groups for p in g["params"]]
    opt = torch.optim.AdamW(groups, weight_decay=0.01)
    steps = a.epochs * (len(items) // a.batch)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, s / max(1, steps * 0.05)) * max(0.0, 1 - s / steps))
    dev = torch.device(a.device)
    model.train()
    step, t0 = 0, time.time()
    for epoch in range(a.epochs):
        order = list(range(len(items)))
        rng.shuffle(order)
        for i in range(0, len(order) - a.batch + 1, a.batch):
            idx = order[i:i + a.batch]
            b = collate_items([items[j] for j in idx], agent.tok.pad_token_id)
            logits, _ = model(b["input_ids"].to(dev), b["attention_mask"].to(dev), b["marker_pos"].to(dev),
                              b["marker_mask"].to(dev), b["qtype"].to(dev))
            tgt = torch.tensor([targets[j] for j in idx], device=dev)
            loss = -(tgt * torch.log_softmax(logits[:, :2].float(), -1)).sum(-1).mean()
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(trainable, 1.0)
            opt.step()
            sched.step()
            step += 1
            if step % 50 == 0:
                print(f"  epoch {epoch} step {step}/{steps} loss {loss.item():.3f} {(time.time() - t0) / step:.2f}s/step", flush=True)
    for layer, path, m in lora:
        swap(layer, path, m.merged())

    out = Path(a.out)
    from huggingface_hub import snapshot_download
    src = Path(a.base) if Path(a.base).is_dir() else Path(snapshot_download(
        a.base, allow_patterns=["rl_agent_config.json", "model.safetensors", "tokenizer/*", "encoder/*"]))
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src / "tokenizer", out / "tokenizer")
    shutil.copytree(src / "encoder", out / "encoder")
    cfg = json.loads((src / "rl_agent_config.json").read_text())
    cfg["decision_model_finetune"] = {"base": a.base, "data": a.data, "epochs": a.epochs, "train_layers": a.train_layers,
                                      "lora": a.lora, "examples": len(examples)}
    (out / "rl_agent_config.json").write_text(json.dumps(cfg, indent=1))
    from safetensors import safe_open
    from safetensors.torch import save_file
    with safe_open(str(src / "model.safetensors"), "pt") as base:   # keep the shipped dtypes
        dtypes = {k: base.get_slice(k).get_dtype() for k in base.keys()}
    to_torch = {"F16": torch.float16, "BF16": torch.bfloat16, "F32": torch.float32}
    save_file({k: v.detach().cpu().to(to_torch.get(dtypes.get(k), v.dtype)).contiguous().clone()
               for k, v in model.state_dict().items()}, str(out / "model.safetensors"))
    print(f"saved {out}", flush=True)


if __name__ == "__main__":
    main()

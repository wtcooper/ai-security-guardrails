"""Fine-tune and score Kev decision models on Modal serverless GPUs (docs/decision-model-training-plan.md).

Uses Kev's own trainer (github.com/jaredpalmer/kev, pinned below) on our clean training set
(training/decision_models/data/train.jsonl, built by export_data.py) and scores checkpoints on exactly the requests
every other guard is scored on (data/eval.jsonl). The container setup mirrors Kev's modal_app.py (locked deps, the
pinned Gated DeltaNet kernels for Qwen3.5 backbones).

    modal run training/decision_models/modal_kev.py::download                     # weights -> volume, on CPU (no GPU cost)
    modal run training/decision_models/modal_kev.py::train --name smoke --limit 200 --epochs 1   # ~$1 pipeline check
    modal run training/decision_models/modal_kev.py::train --name kev-tuned-9b                   # full fine-tune
    modal run training/decision_models/modal_kev.py::score --run jaredpalmer/kev-9b --name kev-base-9b
    modal run training/decision_models/modal_kev.py::score --run kev-tuned-9b --name kev-tuned-9b

Every GPU function has a hard timeout; the workspace's usage limit caps the month. Scores land in
training/decision_models/results/<name>.jsonl (one line per eval request: id, set, label, per-question P(yes)).
"""

import json
import os
import subprocess
from pathlib import Path

import modal

HERE = Path(__file__).resolve().parent
KEV_REPO, KEV_COMMIT = "https://github.com/jaredpalmer/kev.git", "5e42a7a"
KEV_DIR = HERE / "vendor" / "kev"
BASE, INIT = "Qwen/Qwen3.5-9B-Base", "jaredpalmer/kev-9b"
MAX_STATE = 1536   # our policy-text questions are long: state 1536 -> branch 2176 / packed 3200 tokens (kev.model.training_context)
GPU = os.environ.get("KEV_GPU", "H100")

if not KEV_DIR.exists():   # pinned vendor copy of Kev, used to build the image (gitignored)
    KEV_DIR.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "-q", KEV_REPO, str(KEV_DIR)], check=True)
    subprocess.run(["git", "-C", str(KEV_DIR), "checkout", "-q", KEV_COMMIT], check=True)

CAUSAL_CONV1D = ("https://github.com/Dao-AILab/causal-conv1d/releases/download/v1.7.0/"
                 "causal_conv1d-1.7.0%2Bcu12torch2.8cxx11abiTRUE-cp313-cp313-linux_x86_64.whl")
image = (
    modal.Image.debian_slim(python_version="3.13")
    .apt_install("git")
    .uv_sync(uv_project_dir=str(KEV_DIR), groups=[], extras=["serve"])
    .uv_pip_install("flash-linear-attention==0.5.2", "triton>=3.7.1")
    .uv_pip_install(CAUSAL_CONV1D, extra_options="--no-deps")
    .env({"HF_HOME": "/hf", "HF_HUB_DISABLE_PROGRESS_BARS": "1", "TOKENIZERS_PARALLELISM": "false",
          "PYTHONUNBUFFERED": "1", "TRITON_CACHE_DIR": "/hf/triton-cache"})
    .add_local_dir(KEV_DIR / "kev", "/root/kev")
    .add_local_dir(HERE / "data", "/root/data")
)
app = modal.App("guardlab-decision-models", image=image)
hf = modal.Volume.from_name("guardlab-hf-cache", create_if_missing=True)
runs = modal.Volume.from_name("guardlab-runs", create_if_missing=True)
VOLUMES = {"/hf": hf, "/runs": runs}


@app.function(cpu=2, memory=8192, timeout=1800, volumes=VOLUMES)
def fetch_weights():
    from huggingface_hub import snapshot_download
    for repo in (BASE, INIT):
        print(repo, "->", snapshot_download(repo))
    hf.commit()


@app.function(gpu=GPU, cpu=4, memory=65536, timeout=4 * 3600, volumes=VOLUMES)
def run_train(name: str, epochs: int, lr: float, limit: int):
    data = "/root/data/train.jsonl"
    if limit:
        data = "/tmp/train_subset.jsonl"
        Path(data).write_text("".join(open("/root/data/train.jsonl").readlines()[:limit]))
    cmd = ["python", "-m", "kev.train", "--data", data, "--base", BASE, "--init_from", INIT, "--epochs", str(epochs),
           "--lr", str(lr), "--batch", "1", "--accum", "8", "--dtype", "bf16", "--weights_dtype", "bf16",
           "--checkpointing", "1", "--device", "cuda", "--max_state", str(MAX_STATE), "--out", f"/runs/{name}"]
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd="/root")
    runs.commit()


@app.function(gpu=GPU, cpu=4, memory=65536, timeout=2 * 3600, volumes=VOLUMES)
def run_score(run: str, start: int, stop: int) -> list:
    import time

    import torch
    from kev.predictors import LocalPredictor
    from kev.suite import SERVING_CONTEXT_8K
    path = run if "/" in run else f"/runs/{run}"
    torch.manual_seed(0)
    predict = LocalPredictor(path, "cuda", context=SERVING_CONTEXT_8K)
    out = []
    for i, line in enumerate(open("/root/data/eval.jsonl")):
        if i < start:
            continue
        if i >= stop:
            break
        req = json.loads(line)
        # Kev's local scorer materializes records as for training, so every question needs a label; it only feeds the
        # loss, never the probabilities, so a placeholder is safe here
        rec = {"state": req["state"], "questions": {q: dict(d, label=False, src="custom_noul") for q, d in req["questions"].items()}}
        t0 = time.perf_counter()
        try:
            p = predict(rec)
            yes = {q: v["true"] for q, v in p["probabilities"].items()}
            out.append({"id": req["id"], "set": req["set"], "label": req["label"], "stage": req["stage"], "p_yes": yes,
                        "thresholds": req["thresholds"], "actions": req["actions"],
                        "latency_ms": 1000 * (time.perf_counter() - t0)})
        except Exception as e:   # e.g. a state over the serving context: recorded, not silently dropped
            out.append({"id": req["id"], "set": req["set"], "label": req["label"], "stage": req["stage"],
                        "error": f"{type(e).__name__}: {str(e)[:160]}"})
    return out


@app.local_entrypoint()
def download():
    fetch_weights.remote()


@app.local_entrypoint()
def train(name: str = "kev-tuned-9b", epochs: int = 2, lr: float = 2e-5, limit: int = 0):
    run_train.remote(name, epochs, lr, limit)


@app.local_entrypoint()
def score(run: str, name: str, limit: int = 0, chunks: int = 4):
    # parallel chunks: one container scoring all 2,229 requests overran the function timeout
    n = limit or sum(1 for _ in open(HERE / "data" / "eval.jsonl"))
    step = -(-n // chunks)
    rows = [r for part in run_score.starmap([(run, a, min(n, a + step)) for a in range(0, n, step)]) for r in part]
    out = HERE / "results" / f"{name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"{len(rows)} scored -> {out} ({sum('error' in r for r in rows)} errors)")

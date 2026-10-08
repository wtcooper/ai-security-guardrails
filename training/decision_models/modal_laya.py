"""Fine-tune and score Laya on Modal (the small-model side of the size comparison; docs/decision-model-training-plan.md).

Same training records and the same scoring requests as modal_kev.py, so laya-tuned-0.4b-v2 and kev-tuned-9b are
compared on exactly the same data. Laya is ~0.4B parameters, so a small GPU (L4) is enough.

    modal run training/decision_models/modal_laya.py::train --name laya-tuned-0.4b-v2
    modal run training/decision_models/modal_laya.py::score --run laya-tuned-0.4b-v2 --name laya-tuned-0.4b-v2
"""

import json
import os
import subprocess
from pathlib import Path

import modal

HERE = Path(__file__).resolve().parent
GPU = os.environ.get("LAYA_GPU", "L4")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_pip_install("torch==2.8.0", "laya==0.3.22", "numpy", "safetensors", "huggingface_hub")
    .env({"HF_HOME": "/hf", "HF_HUB_DISABLE_PROGRESS_BARS": "1", "TOKENIZERS_PARALLELISM": "false", "PYTHONUNBUFFERED": "1"})
    .add_local_file(HERE / "train_laya.py", "/root/train_laya.py")
    .add_local_dir(HERE / "data", "/root/data")
)
app = modal.App("guardlab-laya", image=image)
hf = modal.Volume.from_name("guardlab-hf-cache", create_if_missing=True)
runs = modal.Volume.from_name("guardlab-runs", create_if_missing=True)
VOLUMES = {"/hf": hf, "/runs": runs}


@app.function(gpu=GPU, cpu=4, memory=32768, timeout=2 * 3600, volumes=VOLUMES)
def run_train(name: str, epochs: int, lora: int):
    cmd = ["python", "/root/train_laya.py", "--data", "/root/data/train.jsonl", "--out", f"/runs/{name}",
           "--epochs", str(epochs), "--lora", str(lora), "--device", "cuda"]
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
    runs.commit()


@app.function(gpu=GPU, cpu=4, memory=32768, timeout=3600, volumes=VOLUMES)
def run_score(run: str, limit: int) -> list:
    import time

    import laya
    agent = laya.load(run if "/" in run else f"/runs/{run}", device="cuda")
    out = []
    for i, line in enumerate(open("/root/data/eval.jsonl")):
        if limit and i >= limit:
            break
        req = json.loads(line)
        t0 = time.perf_counter()
        try:   # long states are scanned in windows, as the lab's LayaBackend does
            long = sum(len(str(v)) for v in req["state"].values()) > 1200
            ans = (agent.predict_long if long else agent.predict)(req["state"], req["questions"])["answers"]
            out.append({"id": req["id"], "set": req["set"], "label": req["label"], "stage": req["stage"],
                        "p_yes": {q: float(a["noul"]) for q, a in ans.items()}, "thresholds": req["thresholds"],
                        "actions": req["actions"], "latency_ms": 1000 * (time.perf_counter() - t0)})
        except Exception as e:
            out.append({"id": req["id"], "set": req["set"], "label": req["label"], "stage": req["stage"],
                        "error": f"{type(e).__name__}: {str(e)[:160]}"})
    return out


@app.local_entrypoint()
def train(name: str = "laya-tuned-0.4b-v2", epochs: int = 2, lora: int = 0):
    run_train.remote(name, epochs, lora)


@app.local_entrypoint()
def score(run: str, name: str, limit: int = 0):
    rows = run_score.remote(run, limit)
    out = HERE / "results" / f"{name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"{len(rows)} scored -> {out} ({sum('error' in r for r in rows)} errors)")

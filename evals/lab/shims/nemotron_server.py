"""Local HTTP shim for NVIDIA Nemotron-3.5-Content-Safety, which needs its own environment
(the model card pins transformers <=4.57.6; the lab uses transformers 5.x).

    uv venv .venv-nemotron --python 3.12
    uv pip install --python .venv-nemotron "transformers==4.57.6" "torch==2.8.0" pillow accelerate
    .venv-nemotron/bin/python evals/lab/shims/nemotron_server.py --port 8766

POST /classify {"text", "stage", "policy", "user_request"?} -> {"p_unsafe": float, "verdict": str}
Uses Nemotron's custom-policy mode (the policy text is supplied per request) with thinking off, and
reads P(unsafe) from the logits of the verdict token ("User Safety:" for user-side content,
"Response Safety:" for assistant replies and tool calls). Standalone: no guardlab imports.
"""

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import torch
from transformers import AutoProcessor, Gemma3ForConditionalGeneration

MODEL = "nvidia/Nemotron-3.5-Content-Safety"
REVISION = "35645ed3543b7e7ffaed2e788699e57a5051497c"
RESPONSE_STAGES = {"output", "tool_call"}   # judged as the assistant turn
LOCK = threading.Lock()


class Nemotron:
    def __init__(self):
        dev = "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"
        self.proc = AutoProcessor.from_pretrained(MODEL, revision=REVISION)
        self.model = Gemma3ForConditionalGeneration.from_pretrained(MODEL, revision=REVISION,
                                                                    torch_dtype=torch.bfloat16).to(dev).eval()
        tok = self.proc.tokenizer
        self.unsafe = tok.encode(" unsafe", add_special_tokens=False)[0]
        self.safe = tok.encode(" safe", add_special_tokens=False)[0]

    def classify(self, text: str, stage: str, policy: str, user_request: str | None) -> dict:
        part = lambda s: [{"type": "text", "text": s}]
        if stage in RESPONSE_STAGES:
            msgs = [{"role": "user", "content": part(user_request or "(previous user message)")},
                    {"role": "assistant", "content": part(text)}]
        else:
            msgs = [{"role": "user", "content": part(text)}]
        inputs = self.proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True, return_dict=True,
                                               return_tensors="pt", request_categories="/no_categories",
                                               enable_thinking=False, custom_policy=policy).to(self.model.device)
        with LOCK, torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=16, do_sample=False, output_logits=True,
                                      return_dict_in_generate=True)
        gen = out.sequences[0, inputs["input_ids"].shape[1]:].tolist()
        want = 1 if stage in RESPONSE_STAGES else 0          # nth safety label in "User Safety / Response Safety"
        seen = 0
        for step, tid in enumerate(gen):
            if tid in (self.unsafe, self.safe):
                if seen == want:
                    p = out.logits[step][0].float().softmax(-1)
                    pu, ps = float(p[self.unsafe]), float(p[self.safe])
                    return {"p_unsafe": pu / (pu + ps), "verdict": self.proc.tokenizer.decode(gen)}
                seen += 1
        return {"p_unsafe": None, "verdict": self.proc.tokenizer.decode(gen)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8766)
    a = ap.parse_args()
    nem = Nemotron()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            try:
                res, code = nem.classify(body["text"], body.get("stage", "input"), body["policy"], body.get("user_request")), 200
            except Exception as e:  # surfaced to the guard as an error
                res, code = {"error": f"{type(e).__name__}: {e}"}, 500
            data = json.dumps(res).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

    print(f"nemotron shim on http://127.0.0.1:{a.port}/classify", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()

"""System One backends. Each answers a batch of `noul` questions about one state and
returns {question_id: probability}.

- LayaBackend: in-process open-weight model (convaiinnovations/laya, Apache-2.0).
- SystemOneHTTPBackend: any server speaking TypeSafe's `POST /v1/systemone` shape --
  TypeSafe Jev (api.typesafe.ai) or a self-hosted Laya server (`pip install "laya[serve]"`,
  laya>=0.3.23, with LAYA_API_KEY set), Ollama >=0.35, llama.cpp, Cloudflare Clef, ...
"""

import os
import threading
from typing import Dict, Protocol

import httpx


# One lock for every in-process model on the accelerator (Laya and encoder classifiers). The gateway screens
# concurrent requests in worker threads, and MPS aborts the process if two threads encode to the same
# command buffer ("A command encoder is already encoding to this command buffer").
DEVICE_LOCK = threading.Lock()


class Backend(Protocol):
    name: str

    def predict(self, state: dict, questions: Dict[str, dict]) -> Dict[str, float]: ...


class LayaBackend:
    """Runs Laya in-process. Long states are scanned in overlapping windows
    (a noul takes its strongest window), so an injection at the end of a long
    tool result is not truncated away."""

    def __init__(self, model: str = "convaiinnovations/laya", subfolder: str | None = None,
                 device: str | None = None, long_threshold_chars: int = 1200):
        import laya  # optional dependency: pip install 's1guard[laya]'

        self.name = f"laya:{model}" + (f"/{subfolder}" if subfolder else "")
        self._agent = laya.load(model, subfolder=subfolder, device=device or _default_device())
        self._long_chars = long_threshold_chars

    def predict(self, state: dict, questions: Dict[str, dict]) -> Dict[str, float]:
        long = sum(len(str(v)) for v in state.values()) > self._long_chars
        with DEVICE_LOCK:  # one forward pass at a time across all in-process models
            if long:
                out = self._agent.predict_long(state, questions)
            else:
                out = self._agent.predict(state, questions)
        return {qid: float(a["noul"]) for qid, a in out["answers"].items()}


class SystemOneHTTPBackend:
    """TypeSafe Jev (default) or any Jev-compatible `POST /v1/systemone` endpoint.

    Pin `model` to a dated version (aliases such as `jev-latest` move silently) and re-calibrate
    the policy thresholds whenever the model changes."""

    def __init__(self, base_url: str = "https://api.typesafe.ai", api_key: str | None = None,
                 model: str = "jev-1.13.0", timeout: float = 10.0):
        self.name = f"systemone-http:{model}@{base_url}"
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(base_url=base_url, headers=headers, timeout=timeout)
        self._model = model

    def predict(self, state: dict, questions: Dict[str, dict]) -> Dict[str, float]:
        r = self._client.post("/v1/systemone",
                              json={"model": self._model, "state": state, "questions": questions})
        r.raise_for_status()
        return {qid: float(a["noul"]) for qid, a in r.json()["answers"].items()}


def _default_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def backend_from_env() -> Backend:
    """S1GUARD_BACKEND = laya (default) | jev | http.

    laya: S1GUARD_LAYA_MODEL, S1GUARD_LAYA_SUBFOLDER, S1GUARD_DEVICE
    jev:  TYPESAFE_API_KEY, S1GUARD_MODEL (default jev-1.13.0 -- pinned, not jev-latest)
    http: S1GUARD_URL (any /v1/systemone server, e.g. `laya[serve]` at http://localhost:8000), S1GUARD_API_KEY
    """
    kind = os.environ.get("S1GUARD_BACKEND", "laya").lower()
    if kind == "laya":
        return LayaBackend(model=os.environ.get("S1GUARD_LAYA_MODEL", "convaiinnovations/laya"),
                           subfolder=os.environ.get("S1GUARD_LAYA_SUBFOLDER") or None,
                           device=os.environ.get("S1GUARD_DEVICE") or None)
    if kind == "jev":
        return SystemOneHTTPBackend(api_key=os.environ["TYPESAFE_API_KEY"],
                                    model=os.environ.get("S1GUARD_MODEL", "jev-1.13.0"))
    if kind == "http":
        return SystemOneHTTPBackend(base_url=os.environ["S1GUARD_URL"],
                                    api_key=os.environ.get("S1GUARD_API_KEY"),
                                    model=os.environ.get("S1GUARD_MODEL", "jev-1.13.0"))
    raise ValueError(f"unknown S1GUARD_BACKEND={kind!r}; use laya, jev or http")

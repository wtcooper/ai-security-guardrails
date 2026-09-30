"""System One backends. Each answers a batch of `noul` questions about one state and
returns {question_id: probability}.

- LayaBackend: in-process open-weight model (convaiinnovations/laya, Apache-2.0).
- SystemOneHTTPBackend: any server speaking TypeSafe's `POST /v1/systemone` shape --
  TypeSafe Jev (api.typesafe.ai) or a self-hosted `laya-serve`.
"""

import os
import threading
from typing import Dict, Protocol

import httpx


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
        # One forward pass at a time: keeps MPS/CUDA memory bounded under gateway concurrency.
        self._lock = threading.Lock()

    def predict(self, state: dict, questions: Dict[str, dict]) -> Dict[str, float]:
        long = sum(len(str(v)) for v in state.values()) > self._long_chars
        with self._lock:
            if long:
                out = self._agent.predict_long(state, questions)
            else:
                out = self._agent.predict(state, questions)
        return {qid: float(a["noul"]) for qid, a in out["answers"].items()}


class SystemOneHTTPBackend:
    """TypeSafe Jev (default) or any Jev-compatible endpoint such as `laya-serve`."""

    def __init__(self, base_url: str = "https://api.typesafe.ai", api_key: str | None = None,
                 model: str = "jev-latest", timeout: float = 10.0):
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
    jev:  TYPESAFE_API_KEY, S1GUARD_MODEL (default jev-latest)
    http: S1GUARD_URL (e.g. a laya-serve at http://localhost:8000), S1GUARD_API_KEY
    """
    kind = os.environ.get("S1GUARD_BACKEND", "laya").lower()
    if kind == "laya":
        return LayaBackend(model=os.environ.get("S1GUARD_LAYA_MODEL", "convaiinnovations/laya"),
                           subfolder=os.environ.get("S1GUARD_LAYA_SUBFOLDER") or None,
                           device=os.environ.get("S1GUARD_DEVICE") or None)
    if kind == "jev":
        return SystemOneHTTPBackend(api_key=os.environ["TYPESAFE_API_KEY"],
                                    model=os.environ.get("S1GUARD_MODEL", "jev-latest"))
    if kind == "http":
        return SystemOneHTTPBackend(base_url=os.environ["S1GUARD_URL"],
                                    api_key=os.environ.get("S1GUARD_API_KEY"),
                                    model=os.environ.get("S1GUARD_MODEL", "jev-latest"))
    raise ValueError(f"unknown S1GUARD_BACKEND={kind!r}; use laya, jev or http")

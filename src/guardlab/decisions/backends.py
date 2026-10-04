"""Decision-API backends implementing s1guard's Backend protocol: predict(state, questions) -> {id: p}.

Access errors (403 preview not enabled, 429, 5xx, timeouts) raise guardlab.Unavailable so the guard
reports `unavailable` instead of a verdict."""

import os

import httpx

from ..types import Unavailable
from .schemas import from_jev, from_openai, to_openai


class _HTTP:
    def __init__(self, base_url: str, path: str, api_key_env: str, model: str, timeout: float, transport=None):
        self.name = f"{type(self).__name__}:{model}@{base_url}{path}"
        self._path, self._model = path, model
        key = os.environ.get(api_key_env, "") if api_key_env else ""
        self._client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport,
                                    headers={"Authorization": f"Bearer {key}"} if key else {})

    def _post(self, body: dict) -> dict:
        try:
            r = self._client.post(self._path, json=body)
        except (httpx.TimeoutException, httpx.TransportError) as e:
            raise Unavailable(f"{type(e).__name__}: {e}") from e
        if r.status_code in (401, 403, 429) or r.status_code >= 500:
            raise Unavailable(f"HTTP {r.status_code}: {r.text[:200]}")
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        return r.json()


class OpenAIDecisionsBackend(_HTTP):
    """OpenAI `POST /v1/decisions` (or a compatible emulator)."""

    def __init__(self, base_url="https://api.openai.com", path="/v1/decisions", api_key_env="OPENAI_API_KEY",
                 model="gpt-6-luna", timeout=10.0, transport=None):
        super().__init__(base_url, path, api_key_env, model, timeout, transport)

    def predict(self, state: dict, questions: dict) -> dict:
        resp = self._post(to_openai(self._model, state, questions))
        out = from_openai(resp)
        missing = set(questions) - set(out)
        if missing:
            raise RuntimeError(f"decision API omitted answers for {sorted(missing)}")
        return out


class JevHTTPBackend(_HTTP):
    """Jev-schema servers: TypeSafe (/v1/systemone), OpenRouter (/api/alpha/decisions),
    Cloudflare Workers AI (/run/@cf/cloudflare/clef-flash, unwrap='result'), laya[serve]."""

    def __init__(self, base_url, path="/v1/systemone", api_key_env="", model="jev-1.13.0", timeout=10.0,
                 unwrap="", transport=None):
        super().__init__(base_url, path, api_key_env, model, timeout, transport)
        self._unwrap = unwrap

    def predict(self, state: dict, questions: dict) -> dict:
        return from_jev(self._post({"model": self._model, "state": state, "questions": questions}), self._unwrap)

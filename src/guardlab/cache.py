"""Append-only JSONL result cache: one file per guard, keyed by guard version + case.

Only `ok` results are cached, so a rerun retries anything that was unavailable or errored."""

import json
import threading
from pathlib import Path

from .types import Case, GuardResult

_lock = threading.Lock()
_mem: dict = {}


def _load(path: Path) -> dict:
    if path not in _mem:
        _mem[path] = {}
        if path.exists():
            for line in path.read_text().splitlines():
                rec = json.loads(line)
                _mem[path][rec.pop("key")] = rec
    return _mem[path]


def get_or_run(guard, case: Case, cache_dir: Path) -> tuple[GuardResult, bool]:
    """(result, came_from_cache)."""
    path = Path(cache_dir) / f"{guard.id}.jsonl"
    key = f"{guard.version}:{case.key()}"
    with _lock:
        hit = _load(path).get(key)
    if hit is not None:
        return GuardResult(**hit), True
    r = guard.check(case)
    if r.status == "ok":
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a") as f:
                f.write(json.dumps({"key": key} | r.to_dict()) + "\n")
            _mem[path][key] = r.to_dict()
    return r, False

"""Deterministic group splits and near-duplicate detection for the corpus builder.

`split_of` / `group_of` match experiments/s1guard_finetune/sources.py, so the lab corpus can
tell which rows s1guard was trained or calibrated on."""

import hashlib
import re
from collections import Counter


def split_of(group: str) -> str:
    """s1guard benchmark split: deterministic 60/15/25 train/dev/test by group."""
    h = int(hashlib.sha256(group.encode()).hexdigest(), 16) % 100
    return "train" if h < 60 else "dev" if h < 75 else "test"


def group_of(case_id: str) -> str:
    """Corpus case id -> group (variants of one attack share a group)."""
    g = re.sub(r"-(hyphenize|numberize|pythonize)$", "", case_id)
    m = re.match(r"m2s-[a-z_]+-([a-z]+)$", g)          # m2s-<strategy>-<goal> -> one group per goal
    return f"m2s-{m.group(1)}" if m else g.replace("safemt-m2s-", "safemt-")


def lab_split(group: str, dev_pct: int = 30, salt: str = "lab") -> str:
    """Lab dev/test split for sets s1guard never trained on."""
    return "dev" if int(hashlib.sha256(f"{salt}:{group}".encode()).hexdigest(), 16) % 100 < dev_pct else "test"


def shingles(text: str, k: int = 8) -> set:
    w = re.sub(r"\s+", " ", text.lower()).split()
    return {" ".join(w[i:i + k]) for i in range(max(1, len(w) - k + 1))}


class ShingleIndex:
    """`contains(text)`: an exact match, or more than `frac` of the text's 8-word shingles inside one
    indexed document."""

    def __init__(self, texts, frac: float = 0.5):
        self.frac = frac
        self._index: dict = {}
        for i, t in enumerate(texts):
            for s in shingles(t):
                self._index.setdefault(s, set()).add(i)

    def contains(self, text: str) -> bool:
        sh = shingles(text)
        hits = Counter(d for s in sh for d in self._index.get(s, ()))
        return bool(hits) and max(hits.values()) / len(sh) > self.frac

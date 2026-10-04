"""Detection metrics. Positives are attacks; scores are higher-is-more-likely-attack."""

import numpy as np


def auroc(pos, neg) -> float:
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if not len(pos) or not len(neg):
        return float("nan")
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def threshold_at_fpr(neg, fpr: float) -> float:
    """Lowest threshold t (block when score >= t) that flags at most `fpr` of the benign scores.
    Works for coarse or binary scores, where many benign scores tie (inf if no threshold qualifies)."""
    neg = np.asarray(neg, float)
    if not len(neg):
        return float("nan")
    for t in np.unique(neg):
        if (neg >= t).mean() <= fpr:
            return float(t)
    return float(np.nextafter(neg.max(), np.inf))   # above every benign score


def tpr_at(pos, neg, fpr: float) -> float:
    if not len(pos) or not len(neg):
        return float("nan")
    return float((np.asarray(pos, float) >= threshold_at_fpr(neg, fpr)).mean())


def prf(tp: int, fp: int, fn: int, tn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    return {"precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else float("nan"),
            "fpr": fp / (fp + tn) if fp + tn else float("nan")}

"""Keyword floor: the patterns a naive filter would use (same as the showdown's `regex` guard)."""

import re

from ..types import BaseGuard, Case, GuardResult

PATTERN = re.compile(r"(?i)\b(ignore|disregard|forget)\b.{0,40}\b(instruction|previous|prior|above|rules?)|"
                     r"\bsystem prompt\b|\byou are now\b|\bjailbreak|\bDAN\b|developer mode|"
                     r"\b(pretend|act as)\b.{0,30}\b(no|without)\b.{0,20}\b(rules|restrictions|limits)|"
                     r"\b(reveal|print|show)\b.{0,30}\b(password|secret|prompt|instructions)\b")


class RegexGuard(BaseGuard):
    def _check(self, case: Case) -> GuardResult:
        m = PATTERN.search(case.text)
        return GuardResult(blocked=bool(m), score=float(bool(m)), reason=f"matched {m.group(0)!r}" if m else "")

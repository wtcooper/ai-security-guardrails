"""Surgical withholding: when agentic-security flags a tool result, how well does the extra call cut just the injection?

For each dev tool-result attack the judge flags: run the locate call, cut the segments it names, then re-rate the cut
text as a fresh tool result. Reports how often a cut was possible (vs withholding the whole result), how much of the
text survives, whether the cut text passes a fresh check (no injection left), and the locate call's latency. Prints
numbers only.

    uv run python evals/lab/experiments/surgical.py [--efforts low,none]
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from guardlab import Case, load_guard  # noqa: E402
from guardlab.adapters.agentic import ags, case_plan  # noqa: E402

OUT = ROOT / "evals" / "results" / "lab" / "rounds" / "surgical.json"


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))] if xs else float("nan")


async def one(judge, r, sem):
    try:
        return await _one(judge, r, sem)
    except Exception:   # a judge timeout: count it, don't stop the run
        return {"flagged": False, "error": True}


async def _one(judge, r, sem):
    async with sem:
        case = Case(r["text"], "tool_result", None, r.get("user_request"), r["id"])
        side, sp, lines, tools = case_plan(case, False)
        v = await judge(side, sp, lines, tools)
        if not v.flagged:
            return {"flagged": False}
        t0 = time.perf_counter()
        try:
            cuts = await judge.locate(v, v.flagged)
        except Exception:
            cuts = {}
        took = time.perf_counter() - t0
        line = v.flagged[0]
        if line not in cuts:
            return {"flagged": True, "cut": False, "locate_s": took, "segments": len(ags.segments(line.text))}
        new = cuts[line]
        kept = len(new.replace(ags.REMOVED_MARKER, "")) / max(1, len(line.text))
        checks = {}
        for name, text in (("with_marker", new), ("marker_removed", new.replace(ags.REMOVED_MARKER, ""))):
            _, sp2, lines2, _ = case_plan(Case(text, "tool_result", None, r.get("user_request"), r["id"]), False)
            checks[name] = not (await judge(side, sp2, lines2, [])).flagged
        return {"flagged": True, "cut": True, "locate_s": took, "kept_share": kept, "clean_after_cut": checks["marker_removed"],
                "clean_with_marker": checks["with_marker"], "segments": len(ags.segments(line.text))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--efforts", default="low,none")
    a = ap.parse_args()
    rows = [json.loads(line) for line in open(ROOT / "evals" / "lab" / "data" / "cases.jsonl")]
    rows = [r for r in rows if r["split"] == "dev" and r["stage"] == "tool_result" and r["label"] == "attack"]
    g = load_guard("agentic-security")
    record = {}
    for effort in a.efforts.split(","):
        judge = ags.Judge(g._complete, locate_effort=effort)

        async def go():
            sem = asyncio.Semaphore(6)
            return await asyncio.gather(*(one(judge, r, sem) for r in rows))
        res = asyncio.run(go())
        flagged = [x for x in res if x["flagged"]]
        multi = [x for x in flagged if x["segments"] > 1]
        cut = [x for x in flagged if x.get("cut")]
        clean = [x for x in cut if x["clean_after_cut"]]
        secs = [x["locate_s"] for x in flagged if x["segments"] > 1]
        kept = [x["kept_share"] for x in cut]
        print(f"locate effort {effort}: errors {sum(bool(x.get('error')) for x in res)}; attacks {len(rows)}, flagged {len(flagged)} ({len(multi)} with >1 segment); "
              f"cut surgically {len(cut)} ({100 * len(cut) / max(1, len(multi)):.0f}% of multi-segment), whole fallback "
              f"{len(flagged) - len(cut)}; cut text passes a fresh check {len(clean)}/{len(cut)} (with the marker left in: "
              f"{sum(x['clean_with_marker'] for x in cut)}); text kept median "
              f"{100 * q(kept, .5):.0f}%; locate latency p50 {q(secs, .5):.2f}s p95 {q(secs, .95):.2f}s")
        record[effort] = {"attacks": len(rows), "flagged": len(flagged), "multi_segment": len(multi), "cut": len(cut),
                          "clean_after_cut": len(clean), "kept_median": q(kept, .5), "locate_p50": q(secs, .5),
                          "locate_p95": q(secs, .95)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=1))


if __name__ == "__main__":
    main()

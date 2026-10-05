#!/usr/bin/env bash
# Agent-loop eval: vanilla Inspect AgentDojo + AgentThreatBench through the LiteLLM gateway, three arms
# (baseline, pre-call only, cyber-guard). See docs/agent-eval.md.
#   bash evals/agent/run.sh setup              # once: .venv-inspect with pinned inspect-ai / inspect-evals
#   bash evals/agent/run.sh smoke              # gateway + shim + wiring check + 2 samples per task
#   bash evals/agent/run.sh full               # same, all samples
#   bash evals/agent/run.sh summarize <run>    # tables for an existing run dir
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERE="$ROOT/evals/agent"
INSPECT="$ROOT/.venv-inspect/bin/python"
[ -f "$ROOT/.env" ] && { set -a; source "$ROOT/.env"; set +a; }

case "${1:-}" in
  setup)
    uv venv "$ROOT/.venv-inspect" --python 3.12
    uv pip install --python "$INSPECT" "inspect-ai==0.3.276" "inspect-evals[agentdojo]==0.23.0" ;;
  smoke|full)
    RUN="$ROOT/evals/results/agent/$(date +%Y%m%d-%H%M%S)-$1"; mkdir -p "$RUN"
    curl -sf localhost:4000/health/liveliness >/dev/null && { echo "port 4000 busy: stop the running gateway first" >&2; exit 1; }
    bash "$ROOT/gateway/start_gateway.sh" > "$RUN/gateway.log" 2>&1 & GW=$!
    AUDIT_LOG="$RUN/audit.jsonl" python3 "$HERE/shim.py" > "$RUN/shim.log" 2>&1 & SHIM=$!
    trap 'kill $SHIM $GW 2>/dev/null || true' EXIT   # only what this run started (start_gateway.sh execs litellm)
    for _ in $(seq 60); do curl -sf localhost:4000/health/liveliness >/dev/null && break; sleep 2; done
    python3 "$HERE/preflight.py" http://127.0.0.1:8900 "$RUN/gateway.log" | tee "$RUN/preflight.txt"
    : > "$RUN/audit.jsonl"   # audit only the eval's own traffic
    "$INSPECT" "$HERE/eval.py" "$RUN/logs" $([ "$1" = smoke ] && echo --smoke) || true
    "$INSPECT" "$HERE/summarize.py" "$RUN" | tee "$RUN/summary.md" ;;
  summarize)
    "$INSPECT" "$HERE/summarize.py" "$2" ;;
  *) echo "usage: $0 setup|smoke|full|summarize <run>" >&2; exit 2 ;;
esac

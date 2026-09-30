#!/usr/bin/env bash
# Run the promptfoo evals against the local gateway (start it first: bash gateway/start_gateway.sh).
#   bash evals/run.sh isolate     # guardrail alone (mock-echo model), ~30s
#   bash evals/run.sh app_eval    # single-turn A/B with gemma4:e2b + gemma4 judge (SAMPLE=20)
#   bash evals/run.sh redteam     # multi-turn crescendo A/B, fully local
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PROMPTFOO_PYTHON="$ROOT/.venv/bin/python" PROMPTFOO_DISABLE_REMOTE_GENERATION=true
PF=(npx -y promptfoo@0.123.1)
OUT="$ROOT/evals/results"; mkdir -p "$OUT"
curl -sf "${GATEWAY_URL:-http://localhost:4000}/health/liveliness" >/dev/null \
  || { echo "gateway not running: bash gateway/start_gateway.sh" >&2; exit 1; }
cd "$ROOT/evals/promptfoo"

case "${1:-}" in
  isolate)  "${PF[@]}" eval -c isolate.yaml --no-progress-bar --output "$OUT/isolate.json" ;;
  app_eval) "${PF[@]}" eval -c app_eval.yaml --no-progress-bar --filter-sample "${SAMPLE:-20}" --output "$OUT/app_eval.json" ;;
  redteam)  "${PF[@]}" redteam generate -c redteam.yaml -o redteam.generated.yaml --no-progress-bar
            "${PF[@]}" redteam eval -c redteam.generated.yaml --no-progress-bar --output "$OUT/redteam.json" ;;
  *) echo "usage: $0 isolate|app_eval|redteam" >&2; exit 2 ;;
esac || true   # promptfoo exits non-zero when any assertion fails; the summary below is the result
"$ROOT/.venv/bin/python" "$ROOT/evals/summarize.py" "$OUT/$1.json"

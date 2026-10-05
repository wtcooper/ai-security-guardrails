#!/usr/bin/env bash
# Run the promptfoo evals.
#   bash evals/run.sh lab <smoke-dev|smoke-test|rep-dev|rep-test|pi-dev|tc-dev|public|lite-dev|lite-test|dev|test> ['<guard regex>']
#                                 # guard-only comparison on the lab corpus (no gateway needed)
#   bash evals/run.sh isolate     # s1guard through the gateway (mock-echo model), ~30s
#   bash evals/run.sh app_eval    # single-turn A/B with gemma4:e2b + gemma4 judge (SAMPLE=20)
#   bash evals/run.sh redteam     # multi-turn crescendo A/B, fully local
#   bash evals/run.sh e2e         # A/B: no guardrail vs s1guard vs lab guards (gpt-6-luna grader)
# Gateway modes need the gateway first: bash gateway/start_gateway.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PROMPTFOO_PYTHON="$ROOT/.venv/bin/python" PROMPTFOO_DISABLE_REMOTE_GENERATION=true
[ -f "$ROOT/.env" ] && { set -a; source "$ROOT/.env"; set +a; }
PF=(npx -y promptfoo@0.123.1)
OUT="$ROOT/evals/results"; mkdir -p "$OUT/lab"

if [ "${1:-}" = lab ]; then
  mode="${2:-smoke-dev}"; guards="${3:-.}"
  case "$mode" in
    smoke-dev)  filt=(--filter-metadata split=dev --filter-metadata smoke=yes) ;;
    smoke-test) filt=(--filter-metadata split=test --filter-metadata smoke=yes) ;;
    rep-dev)    filt=(--filter-metadata split=dev --filter-metadata rep=yes) ;;
    rep-test)   filt=(--filter-metadata split=test --filter-metadata rep=yes) ;;
    lite-dev)   filt=(--filter-metadata split=dev --filter-metadata lite=yes) ;;
    lite-test)  filt=(--filter-metadata split=test --filter-metadata lite=yes) ;;
    dev|test)   filt=(--filter-metadata "split=$mode") ;;
    public)     filt=(--filter-metadata split=public) ;;   # well-known public benchmarks (pb-*), never tuned on
    pi-dev)     filt=(--filter-metadata pidev=yes) ;;        # direct-injection tuning data (public train material)
    tc-dev)     filt=(--filter-metadata tcdev=yes) ;;        # tool-call tuning data (toolcall-guard-v1 val split)
    *) echo "usage: $0 lab smoke-dev|smoke-test|rep-dev|rep-test|pi-dev|tc-dev|public|lite-dev|lite-test|dev|test ['<guard regex>']" >&2; exit 2 ;;
  esac
  [ -f "$ROOT/evals/lab/data/pf/lab_tests.json" ] || "$ROOT/.venv/bin/python" "$ROOT/evals/lab/build_corpus.py"
  slug="$(echo "$guards" | tr -c 'A-Za-z0-9._-' '_' | sed 's/_*$//')"; [ "$slug" = "_" ] || [ -z "$slug" ] && slug=all
  res="$OUT/lab/$mode-$slug.json"
  (cd "$ROOT/evals/lab" && "${PF[@]}" eval -c lab.yaml --no-progress-bar -j "${PF_CONCURRENCY:-4}" "${filt[@]}" \
      --filter-providers "^($guards)\$" --output "$res") || true
  exec "$ROOT/.venv/bin/python" "$ROOT/evals/lab/report.py" "$res"
fi

curl -sf "${GATEWAY_URL:-http://localhost:4000}/health/liveliness" >/dev/null \
  || { echo "gateway not running: bash gateway/start_gateway.sh" >&2; exit 1; }
cd "$ROOT/evals/promptfoo"

case "${1:-}" in
  isolate)  "${PF[@]}" eval -c isolate.yaml --no-progress-bar --output "$OUT/isolate.json" ;;
  app_eval) "${PF[@]}" eval -c app_eval.yaml --no-progress-bar --filter-sample "${SAMPLE:-20}" --output "$OUT/app_eval.json" ;;
  e2e)      "${PF[@]}" eval -c ../lab/e2e.yaml --no-progress-bar --filter-sample "${SAMPLE:-20}" --output "$OUT/e2e.json" ;;
  redteam)  "${PF[@]}" redteam generate -c redteam.yaml -o redteam.generated.yaml --no-progress-bar
            "${PF[@]}" redteam eval -c redteam.generated.yaml --no-progress-bar --output "$OUT/redteam.json" ;;
  *) echo "usage: $0 lab|isolate|app_eval|e2e|redteam" >&2; exit 2 ;;
esac || true   # promptfoo exits non-zero when any assertion fails; the summary below is the result
"$ROOT/.venv/bin/python" "$ROOT/evals/summarize.py" "$OUT/$1.json"

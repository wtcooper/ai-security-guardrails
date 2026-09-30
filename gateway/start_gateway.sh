#!/usr/bin/env bash
# Start the local LiteLLM gateway with the s1guard guardrail.
#   bash gateway/start_gateway.sh            # foreground, :4000
#   PORT=4001 bash gateway/start_gateway.sh
# Backend: S1GUARD_BACKEND=laya (default, local) | jev (TYPESAFE_API_KEY) | http (S1GUARD_URL)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a; [ -f "$ROOT/.env" ] && . "$ROOT/.env"; set +a
exec "$ROOT/.venv/bin/litellm" --config "$ROOT/gateway/litellm_config.yaml" --port "${PORT:-4000}" --num_workers 1

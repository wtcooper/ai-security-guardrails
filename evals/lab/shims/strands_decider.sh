#!/usr/bin/env bash
# AWS Strands Decider 2B (Apache-2.0): a self-hosted decision model (Qwen3.5-2B-Base + LoRA + pointer head)
# served on POST /v1/systemone by its own CLI, in an isolated uvx environment (the lab venv stays clean).
#   bash evals/lab/shims/strands_decider.sh setup    # download the pinned checkpoint (the base model downloads on first serve)
#   bash evals/lab/shims/strands_decider.sh serve    # :8768 (guard id: strands-decider-2b); ~5 GB on the Apple GPU
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
[ -f "$ROOT/.env" ] && { set -a; source "$ROOT/.env"; set +a; }
PKG="strands-decider==0.1.0"
REPO_ID=StrandsAgents/strands-decider-2B-hobson-v19
REV=bb282d786bc251fd4e3068de3ada9ddbb38127cd
snapshot() { "$ROOT/.venv/bin/python" -c "from huggingface_hub import snapshot_download
print(snapshot_download('$REPO_ID', revision='$REV', local_files_only=$1))"; }

case "${1:-}" in
  setup) snapshot False ;;
  serve) exec uvx --from "$PKG" strands-decider serve "$(snapshot True)" --port "${PORT:-8768}" --model-name strands-decider-2b ;;
  *) echo "usage: $0 setup|serve" >&2; exit 2 ;;
esac

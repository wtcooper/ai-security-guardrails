#!/usr/bin/env bash
# Llama Guard 4 12B on a 24 GB Mac: official weights -> GGUF -> Q4_K_M -> llama-server.
# bf16 (~24 GB) does not fit in Apple-GPU memory; Q4_K_M (~7 GB) does. llama.cpp treats LG4's
# dense config (interleave_moe_layer_step = 0) as all-dense layers (src/models/llama4.cpp).
#
# Needs: Meta's licence accepted on https://huggingface.co/meta-llama/Llama-Guard-4-12B,
#        HF_TOKEN in .env, `brew install llama.cpp`.
#   bash evals/lab/shims/llama_guard4.sh setup     # download (~24 GB) + convert + quantize (once)
#   bash evals/lab/shims/llama_guard4.sh serve     # llama-server on :8767 (guard id: llama-guard4-12b)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
[ -f "$ROOT/.env" ] && { set -a; source "$ROOT/.env"; set +a; }
WORK="$ROOT/evals/lab/.cache/llama-guard4"          # gitignored
REV=87acb4b94e930c3d679e6e7ee9d57e2feab9ea71        # meta-llama/Llama-Guard-4-12B
LLAMACPP_COMMIT="$(llama-server --version 2>&1 | sed -n 's/.*commit \([0-9a-f]*\).*/\1/p')"
mkdir -p "$WORK"

case "${1:-}" in
  setup)
    : "${HF_TOKEN:?set HF_TOKEN in .env and accept the Meta licence first}"
    "$ROOT/.venv/bin/python" -c "
from huggingface_hub import snapshot_download
print(snapshot_download('meta-llama/Llama-Guard-4-12B', revision='$REV', local_dir='$WORK/hf'))"
    if [ ! -d "$WORK/llama.cpp" ]; then          # converter matching the installed llama.cpp build
      git clone -q --filter=blob:none --no-checkout https://github.com/ggml-org/llama.cpp "$WORK/llama.cpp"
      (cd "$WORK/llama.cpp" && git sparse-checkout set --no-cone conversion gguf-py convert_hf_to_gguf.py \
        && git checkout -q "$LLAMACPP_COMMIT")
    fi
    uv run --no-project --python 3.12 --with "$WORK/llama.cpp/gguf-py" --with torch --with transformers \
      --with sentencepiece --with numpy --with safetensors \
      python "$WORK/llama.cpp/convert_hf_to_gguf.py" "$WORK/hf" --outtype bf16 --outfile "$WORK/lg4-bf16.gguf"
    # LG4 is dense (expert_count 0, interleave_moe_layer_step 0) but llama.cpp's llama4 loader rejects
    # zero experts and asserts expert_used_count <= expert_count. Expert tensors are only created for
    # MoE layers (none here), so declaring 1 expert is safe: every layer loads its dense FFN.
    for kv in "llama4.expert_count 1" "llama4.expert_used_count 1"; do
      echo y | uv run --no-project --python 3.12 --with "$WORK/llama.cpp/gguf-py" python \
        "$WORK/llama.cpp/gguf-py/gguf/scripts/gguf_set_metadata.py" --force "$WORK/lg4-bf16.gguf" $kv
    done
    llama-quantize "$WORK/lg4-bf16.gguf" "$WORK/lg4-Q4_K_M.gguf" Q4_K_M
    rm -f "$WORK/lg4-bf16.gguf"                    # keep only the quantized model
    ls -lh "$WORK/lg4-Q4_K_M.gguf" ;;
  serve)
    # --no-prefill-assistant: a final assistant turn is the Agent message to classify, not a prefill
    exec llama-server -m "$WORK/lg4-Q4_K_M.gguf" --port "${PORT:-8767}" -c 4096 --jinja -ngl 99 --no-prefill-assistant ;;
  *) echo "usage: $0 setup|serve" >&2; exit 2 ;;
esac

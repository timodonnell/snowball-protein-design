#!/usr/bin/env bash
set -euo pipefail
export PATH=/root/.local/bin:$PATH
export UV_CACHE_DIR=/work/cache/uv
export HF_HOME=/work/cache/huggingface
export UV_LINK_MODE=copy
uv venv --python 3.12.13 /work/snowball-serving
uv pip install --python /work/snowball-serving/bin/python \
  'https://github.com/marin-community/vllm/releases/download/marin-vllm-gpu-20260924-01911be34fac/vllm-0.0.0.dev20260924%2Bmarin.01911be34fac.cu132-cp38-abi3-manylinux_2_28_x86_64.whl' \
  --extra-index-url https://download.pytorch.org/whl/cu132 --index-strategy unsafe-best-match
# The published wheel requires torchaudio==2.11.0 alongside torch==2.13.0.
# Its CUDA 13.0 audio extension aborts Transformers import with Torch CUDA 13.2.
# This research server is text-only. Keep this explicit dependency exception.
uv pip uninstall --python /work/snowball-serving/bin/python torchaudio
/work/snowball-serving/bin/hf download \
  open-athena/Snowball-67B-A2B-5.7T-Mixed-RLVR-Step38 \
  --revision cfc1d845dae89b067cdc7250d0164abefa5a69cf \
  --local-dir /work/models/snowball
uv pip freeze --python /work/snowball-serving/bin/python > /work/logs/snowball-serving-freeze.txt

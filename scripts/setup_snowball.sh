#!/usr/bin/env bash
set -euo pipefail
export PATH=/root/.local/bin:$PATH
export UV_CACHE_DIR=/work/cache/uv
export HF_HOME=/work/cache/huggingface
export UV_LINK_MODE=copy
uv venv --python 3.12.13 /work/snowball-serving
# Copy configs/snowball-serving.lock.txt to /work/configs/ first.
# This captures the successfully exercised text-serving environment.
# TorchAudio is deliberately omitted: the published vLLM wheel's incompatible
# torchaudio==2.11.0 dependency aborts import with torch==2.13.0+cu132 (I005).
uv pip sync --python /work/snowball-serving/bin/python \
  /work/configs/snowball-serving.lock.txt \
  --extra-index-url https://download.pytorch.org/whl/cu132 --index-strategy unsafe-best-match
/work/snowball-serving/bin/hf download \
  open-athena/Snowball-67B-A2B-5.7T-Mixed-RLVR-Step38 \
  --revision cfc1d845dae89b067cdc7250d0164abefa5a69cf \
  --local-dir /work/models/snowball
uv pip freeze --python /work/snowball-serving/bin/python > /work/logs/snowball-serving-freeze.txt

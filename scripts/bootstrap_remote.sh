#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export PATH=/root/.local/bin:/root/.cargo/bin:$PATH
export UV_CACHE_DIR=/work/cache/uv
export HF_HOME=/work/cache/huggingface
export UV_LINK_MODE=copy
mkdir -p /work/logs /work/cache
apt-get update
apt-get install -y git git-lfs curl wget build-essential cmake rustc cargo \
  zlib1g-dev libbz2-dev liblzma-dev libffi-dev libssl-dev python3 python3-pip \
  libgomp1 libgl1 libglib2.0-0 libxrender1 libxext6 libopenblas-dev unzip
curl -LsSf https://astral.sh/uv/0.11.1/install.sh | env UV_NO_MODIFY_PATH=1 sh
if [ ! -d /work/T-REX ]; then
  git clone https://github.com/ml-struct-bio/T-REX.git /work/T-REX
fi
git -C /work/T-REX checkout --detach 8b5103cc357a0c9df8c2eae6feaf1fb85f0d5e09
cd /work/T-REX
uv run --locked --python 3.12.13 --extra assets trex setup \
  --asset-root /work/T-REX-assets --jobs 24

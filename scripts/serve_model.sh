#!/usr/bin/env bash
set -euo pipefail
arm=${1:?qwen or snowball}
port=${2:-12001}
export HF_HOME=/work/cache/huggingface
case "$arm" in
  qwen)
    export CUDA_VISIBLE_DEVICES=0
    export PATH=/work/T-REX/.venv-serving/bin:$PATH
    exec python -m vllm.entrypoints.openai.api_server \
      --model /work/T-REX-assets/checkpoints/Qwen3.6-27B-FP8 \
      --served-model-name Qwen/Qwen3.6-27B-FP8 \
      --host 127.0.0.1 --port "$port" --max-model-len 65536 \
      --gpu-memory-utilization 0.90 --trust-remote-code \
      --default-chat-template-kwargs '{"enable_thinking": false}'
    ;;
  snowball)
    export CUDA_VISIBLE_DEVICES=0,1
    export PATH=/work/snowball-serving/bin:$PATH
    exec python -m vllm.entrypoints.openai.api_server \
      --model /work/models/snowball \
      --served-model-name open-athena/Snowball-67B-A2B-5.7T-Mixed-RLVR-Step38 \
      --host 127.0.0.1 --port "$port" --max-model-len 32768 \
      --gpu-memory-utilization 0.92 --tensor-parallel-size 1 \
      --data-parallel-size 2 --enable-expert-parallel --enforce-eager \
      --default-chat-template-kwargs '{"enable_thinking": false}' \
      --override-generation-config '{"top_k": 20, "top_p": 0.95}' \
      --max-num-seqs 4
    ;;
  *) exit 2 ;;
esac

#!/usr/bin/env bash
set -euo pipefail
arm=${1:?qwen, snowball, qwen-think or snowball-think}
port=${2:-12001}
export HF_HOME=/work/cache/huggingface
# The -think variants differ from their base arm in one place: the server's
# default chat-template setting. A request that carries its own
# chat_template_kwargs still wins, so this only decides what an unset request
# gets; setting it here means the server and the client agree instead of relying
# on override precedence. Everything else, including the generation overrides and
# the disabled prefix cache, is byte-identical to the matched arm.
case "$arm" in
  qwen|qwen-think)
    thinking=false
    [ "$arm" = qwen-think ] && thinking=true
    export CUDA_VISIBLE_DEVICES=0
    export PATH=/work/T-REX/.venv-serving/bin:$PATH
    exec python -m vllm.entrypoints.openai.api_server \
      --model /work/T-REX-assets/checkpoints/Qwen3.6-27B-FP8 \
      --served-model-name Qwen/Qwen3.6-27B-FP8 \
      --host 127.0.0.1 --port "$port" --max-model-len 65536 \
      --gpu-memory-utilization 0.90 --trust-remote-code \
      --default-chat-template-kwargs "{\"enable_thinking\": $thinking}"
    ;;
  snowball|snowball-think)
    thinking=false
    [ "$arm" = snowball-think ] && thinking=true
    export CUDA_VISIBLE_DEVICES=0,1
    export PATH=/work/snowball-serving/bin:$PATH
    exec python -m vllm.entrypoints.openai.api_server \
      --model /work/models/snowball \
      --served-model-name open-athena/Snowball-67B-A2B-5.7T-Mixed-RLVR-Step38 \
      --host 127.0.0.1 --port "$port" --max-model-len 32768 \
      --gpu-memory-utilization 0.92 --tensor-parallel-size 1 \
      --data-parallel-size 2 --enable-expert-parallel --enforce-eager \
      --no-enable-prefix-caching \
      --default-chat-template-kwargs "{\"enable_thinking\": $thinking}" \
      --override-generation-config '{"top_k": 20, "top_p": 0.95}' \
      --max-num-seqs 4
    ;;
  *) exit 2 ;;
esac

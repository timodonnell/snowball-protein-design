#!/usr/bin/env bash
# Run on the provisioned pod after T-REX setup and campaign YAML creation.
set -euo pipefail
arm=${1:?qwen or snowball}
case "$arm" in qwen|snowball) ;; *) exit 2 ;; esac
export PATH=/root/.local/bin:$PATH
export HF_HOME=/work/cache/huggingface
export UV_CACHE_DIR=/work/cache/uv
export PYTHONUNBUFFERED=1
mkdir -p "/work/results/$arm" /work/logs
cd /work/T-REX
set -a
source .env
set +a
controller=/work/T-REX/.venv-serving/bin/python
if [ "$arm" = qwen ]; then
  model=Qwen/Qwen3.6-27B-FP8
  server_python=$controller
  devices=0
  server_args=(--model "$TREX_QWEN_MODEL_PATH" --max-model-len 65536
    --gpu-memory-utilization 0.90 --trust-remote-code
    --default-chat-template-kwargs '{"enable_thinking": false}')
else
  model=open-athena/Snowball-67B-A2B-5.7T-Mixed-RLVR-Step38
  server_python=/work/snowball-serving/bin/python
  devices=0,1
  server_args=(--model /work/models/snowball --max-model-len 32768
    --gpu-memory-utilization 0.92 --tensor-parallel-size 1
    --data-parallel-size 2 --enable-expert-parallel --enforce-eager
    --max-num-seqs 4)
fi
# Process groups permit cleanup of vLLM's worker descendants.
setsid env CUDA_VISIBLE_DEVICES="$devices" "$server_python" \
  -m vllm.entrypoints.openai.api_server "${server_args[@]}" \
  --served-model-name "$model" --host 127.0.0.1 --port 12001 \
  > "/work/logs/$arm-vllm.log" 2>&1 &
server_pid=$!
setsid "$controller" /work/pilot-scripts/recording_proxy.py \
  --output "/work/results/$arm/wire" \
  > "/work/logs/$arm-proxy.log" 2>&1 &
proxy_pid=$!
cleanup() {
  kill -TERM -- "-$server_pid" "-$proxy_pid" 2>/dev/null || true
}
trap cleanup EXIT
ready=0
for _ in $(seq 1 180); do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    echo 'LLM server exited; inspect preserved server log.' >&2
    exit 1
  fi
  if curl -fsS --max-time 2 http://127.0.0.1:12001/health >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 10
done
test "$ready" = 1
"$controller" -m benchmarks.llm_validation.planner_validation \
  --model "vllm/$model" --base-url http://127.0.0.1:12000/v1 \
  --repeats 3 --max-tokens 3072 --temperature 0.2 \
  --out "/work/results/$arm/planner-validation.json"
"$controller" -m benchmarks.llm_validation.supervisor_validation \
  --model "vllm/$model" --base-url http://127.0.0.1:12000/v1 \
  --repeats 3 --max-tokens 3072 \
  --out "/work/results/$arm/supervisor-validation.json"
"$controller" -m trex.cli design "/work/configs/$arm.yaml" \
  --verify-backend-revisions

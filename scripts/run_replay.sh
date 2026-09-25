#!/usr/bin/env bash
# Small post-campaign teacher diagnostic; no molecular jobs are launched.
set -euo pipefail
test -f /work/results/snowball/campaign-end-time.txt
if curl -fsS --max-time 2 http://127.0.0.1:12001/health >/dev/null 2>&1; then
  echo 'Primary model is still running; wait for arm cleanup.' >&2
  exit 1
fi
for _ in $(seq 1 60); do
  used=$(nvidia-smi -i 0 --query-gpu=memory.used --format=csv,noheader,nounits)
  if [ "$used" -lt 2000 ]; then break; fi
  sleep 2
done
test "$used" -lt 2000
export PYTHONHASHSEED=0
export PYTHONUNBUFFERED=1
export PYTHONPATH=/work/T-REX
out=/work/results/replay-qwen-on-snowball
mkdir -p "$out"
test ! -f "$out/cases.jsonl"
cd /work/T-REX
controller=/work/T-REX/.venv-serving/bin/python
setsid bash /work/pilot-scripts/serve_model.sh qwen 12003 > "$out/serving.txt" 2>&1 &
server_pid=$!
setsid "$controller" /work/pilot-scripts/recording_proxy.py \
  --port 12004 --upstream http://127.0.0.1:12003 --cancel-on-disconnect \
  --output "$out/wire" > "$out/proxy.txt" 2>&1 &
proxy_pid=$!
cleanup() { kill -TERM -- "-$server_pid" "-$proxy_pid" 2>/dev/null || true; }
trap cleanup EXIT
ready=0
for _ in $(seq 1 120); do
  kill -0 "$server_pid" 2>/dev/null || exit 1
  if curl -fsS --max-time 2 http://127.0.0.1:12003/health >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 5
done
test "$ready" = 1
date -u +%FT%TZ > "$out/start-time.txt"
"$controller" /work/pilot-scripts/replay_planner.py /work/results/snowball "$out"
date -u +%FT%TZ > "$out/end-time.txt"

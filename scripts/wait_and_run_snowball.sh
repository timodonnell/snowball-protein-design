#!/usr/bin/env bash
# Convenience for the already-running baseline; no GPU overlap between arms.
set -euo pipefail
qwen_arm_pid=${1:?PID of the task-owned run_arm.sh qwen process}
while [ -r "/proc/$qwen_arm_pid/stat" ]; do
  read -r _ _ state _ < "/proc/$qwen_arm_pid/stat"
  [ "$state" = Z ] && break
  sleep 15
done
if [ ! -f /work/results/qwen/campaign-end-time.txt ]; then
  echo 'Qwen did not finish its campaign; inspect logs before proceeding.' >&2
  exit 1
fi
for _ in $(seq 1 60); do
  if ! curl -fsS --max-time 2 http://127.0.0.1:12001/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
if curl -fsS --max-time 2 http://127.0.0.1:12001/health >/dev/null 2>&1; then
  echo 'Qwen server still running; refusing to overlap model allocations.' >&2
  exit 1
fi
exec bash /work/pilot-scripts/run_arm.sh snowball

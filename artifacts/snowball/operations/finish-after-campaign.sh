#!/usr/bin/env bash
# One-off coordinator used in this pilot. No primary-run changes or deletion.
set -euo pipefail
ready=0
for _ in $(seq 1 600); do
  if [ -f /work/results/snowball/campaign-end-time.txt ] && \
     ! curl -fsS --max-time 2 http://127.0.0.1:12001/health >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 5
done
test "$ready" = 1
date -u +%FT%TZ
bash /work/pilot-scripts/run_replay.sh > /work/logs/replay-arm.log 2>&1 &
replay_pid=$!
cd /work/T-REX
set +e
.venv-serving/bin/python /work/pilot-scripts/collect_designs.py \
  /work/results/snowball/campaign /work/results/snowball/designs \
  --foldseek external/Proteina-Complexa/.venv/bin/foldseek \
  --mmseqs external/Proteina-Complexa/.venv/bin/mmseqs \
  > /work/results/snowball/collector-output.txt 2>&1
collector_status=$?
comparison_status=1
if [ "$collector_status" -eq 0 ]; then
  .venv-serving/bin/python /work/pilot-scripts/compare_designs.py \
    /work/results /work/results/design-comparison.json \
    --foldseek external/Proteina-Complexa/.venv/bin/foldseek \
    > /work/results/design-comparison-output.txt 2>&1
  comparison_status=$?
fi
wait "$replay_pid"
replay_status=$?
printf 'collector_status=%s comparison_status=%s replay_status=%s\n' \
  "$collector_status" "$comparison_status" "$replay_status"
date -u +%FT%TZ
test "$collector_status" -eq 0 && test "$comparison_status" -eq 0 && test "$replay_status" -eq 0

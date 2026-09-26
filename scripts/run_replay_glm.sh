#!/usr/bin/env bash
# Replay the same five live Snowball Planner states through GLM-5.3, so the
# three arms can be compared on identical evidence rather than on their own
# divergent trajectories. Qwen's replay of these states already exists as
# `replay-qwen-on-snowball`; this is its GLM counterpart and selects the same
# five call-index quantiles from the same archive. No molecular jobs are run.
set -euo pipefail
: "${GLM_BASE_URL:?Set GLM_BASE_URL to the resolved GLM-5.3 endpoint (no /v1 suffix)}"
: "${GLM_TOKEN_FILE:?Set GLM_TOKEN_FILE to a file holding the bearer token}"
test -f /work/results/snowball/campaign-end-time.txt
export PYTHONHASHSEED=0
export PYTHONUNBUFFERED=1
export PYTHONPATH=/work/T-REX
out=/work/results/replay-glm-on-snowball
mkdir -p "$out"
test ! -f "$out/cases.jsonl"
cd /work/T-REX
controller=/work/T-REX/.venv-serving/bin/python
# Same reasoning budget as the GLM campaign, for the same reason; see
# docs/experiment.md. Both bodies are kept in the replay's own wire archive.
setsid "$controller" /work/pilot-scripts/recording_proxy.py \
  --port 12005 --upstream "$GLM_BASE_URL" --cancel-on-disconnect \
  --auth-token-file "$GLM_TOKEN_FILE" \
  --inject-extra-body '{"chat_template_kwargs": {"reasoning_effort": "low"}}' \
  --output "$out/wire" > "$out/proxy.txt" 2>&1 &
proxy_pid=$!
cleanup() { kill -TERM -- "-$proxy_pid" 2>/dev/null || true; }
trap cleanup EXIT
ready=0
for _ in $(seq 1 60); do
  if curl -fsS --max-time 5 http://127.0.0.1:12005/v1/models >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 5
done
test "$ready" = 1
date -u +%FT%TZ > "$out/start-time.txt"
"$controller" /work/pilot-scripts/replay_planner.py /work/results/snowball "$out" \
  --base-url http://127.0.0.1:12005/v1 --model glm-5.3
date -u +%FT%TZ > "$out/end-time.txt"

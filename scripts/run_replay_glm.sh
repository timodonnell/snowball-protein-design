#!/usr/bin/env bash
# Replay the same five live Snowball Planner states through a GLM-5.3 arm, so the
# arms can be compared on identical evidence rather than on their own divergent
# trajectories. Qwen's replay of these states exists as `replay-qwen-on-snowball`;
# this produces its GLM counterpart, selecting the same five call-index quantiles
# from the same archive. No molecular jobs are run.
#
# GLM_REASONING_EFFORT selects the arm being replayed and names the output:
#   low   -> replay-glm-on-snowball        (matches the matched GLM campaign)
#   high  -> replay-glm-think-on-snowball  (matches the reasoning-enabled campaign,
#                                           and applies upstream's 8192 floor)
set -euo pipefail
: "${GLM_BASE_URL:?Set GLM_BASE_URL to the resolved GLM-5.3 endpoint (no /v1 suffix)}"
: "${GLM_TOKEN_FILE:?Set GLM_TOKEN_FILE to a file holding the bearer token}"
effort=${GLM_REASONING_EFFORT:-low}
case "$effort" in
  low)  out=/work/results/replay-glm-on-snowball;       port=12005; floor=() ;;
  high) out=/work/results/replay-glm-think-on-snowball; port=12006
        floor=(--raise-max-completion-tokens "${GLM_THINK_MAX_TOKENS:-8192}") ;;
  *) echo "GLM_REASONING_EFFORT must be low or high; see docs/experiment.md" >&2; exit 2 ;;
esac
test -f /work/results/snowball/campaign-end-time.txt
export PYTHONHASHSEED=0
export PYTHONUNBUFFERED=1
export PYTHONPATH=/work/T-REX
mkdir -p "$out"
test ! -f "$out/cases.jsonl"
cd /work/T-REX
controller=/work/T-REX/.venv-serving/bin/python
# Same reasoning budget as the corresponding campaign, for the same reason; see
# docs/experiment.md. Both bodies are kept in the replay's own wire archive.
setsid "$controller" /work/pilot-scripts/recording_proxy.py \
  --port "$port" --upstream "$GLM_BASE_URL" --cancel-on-disconnect \
  --auth-token-file "$GLM_TOKEN_FILE" "${floor[@]}" \
  --inject-extra-body "{\"chat_template_kwargs\": {\"reasoning_effort\": \"$effort\"}}" \
  --output "$out/wire" > "$out/proxy.txt" 2>&1 &
proxy_pid=$!
cleanup() { kill -TERM -- "-$proxy_pid" 2>/dev/null || true; }
trap cleanup EXIT
ready=0
for _ in $(seq 1 60); do
  if curl -fsS --max-time 5 "http://127.0.0.1:$port/v1/models" >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 5
done
test "$ready" = 1
date -u +%FT%TZ > "$out/start-time.txt"
"$controller" /work/pilot-scripts/replay_planner.py /work/results/snowball "$out" \
  --base-url "http://127.0.0.1:$port/v1" --model glm-5.3
date -u +%FT%TZ > "$out/end-time.txt"

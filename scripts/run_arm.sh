#!/usr/bin/env bash
# Run on the provisioned pod after T-REX setup and campaign YAML creation.
set -euo pipefail
arm=${1:?a base arm (qwen, snowball, glm) or its -think variant}
case "$arm" in
  qwen|snowball|glm|qwen-think|snowball-think|glm-think) ;;
  *) exit 2 ;;
esac
export PATH=/root/.local/bin:$PATH
export HF_HOME=/work/cache/huggingface
export UV_CACHE_DIR=/work/cache/uv
export PYTHONUNBUFFERED=1
export PYTHONHASHSEED=0
mkdir -p "/work/results/$arm" /work/logs
if [ -e "/work/results/$arm/campaign" ]; then
  echo 'Archive already exists; preserve/move it before starting a fresh run.' >&2
  exit 2
fi
cd /work/T-REX
controller=/work/T-REX/.venv-serving/bin/python
# A -think arm keeps its base arm's served model name, so the fixed-evidence
# prompts hash identically and stay comparable across every run.
case "$arm" in
  qwen|qwen-think) model=Qwen/Qwen3.6-27B-FP8 ;;
  snowball|snowball-think) model=open-athena/Snowball-67B-A2B-5.7T-Mixed-RLVR-Step38 ;;
  glm|glm-think) model=glm-5.3 ;;
esac
case "$arm" in *-think) thinking_arm=1 ;; *) thinking_arm=0 ;; esac
# Both GLM arms are served off-pod by a shared endpoint, so they start no local
# server and hold no GPU for inference. The recorder carries the bearer token and
# the reasoning budget, which the pinned controller cannot express: GLM reasons by
# default and, unlike the other two checkpoints, has no off switch.
#
#   glm        reasoning_effort=low at the controller's own 3072-token limit. The
#              nearest setting to the other arms' disabled thinking, so this arm is
#              the one that belongs in the matched comparison. An unset budget
#              spends the whole limit on hidden reasoning and returns no content.
#   glm-think  the same model allowed to reason, with upstream's own thinking-model
#              floor of 8192 tokens applied (trex/llm/openai_client.py), which the
#              controller cannot reach for a server whose reasoning it cannot see.
#              Deliberately unmatched against the other arms; it ablates GLM
#              against itself. Set GLM_REASONING_EFFORT to pick the level.
#
# See docs/experiment.md.
# Every thinking arm needs the same two things, differing only in the dialect its
# server speaks. The campaign YAML exposes no token knob, so upstream's own
# thinking-model floor of 8192 is applied by the recorder; the fixed-check
# runners take --max-tokens natively and receive it below, which makes the
# recorder's floor a no-op there. Locally served arms also get
# chat_template_kwargs natively from --enable-thinking on the fixed checks, so
# the injection below only ever fires for the campaign.
think_max_tokens=${THINK_MAX_TOKENS:-8192}
fixed_max_tokens=3072
case "$arm" in
  glm|glm-think)
    : "${GLM_BASE_URL:?Set GLM_BASE_URL to the resolved GLM-5.3 endpoint (no /v1 suffix)}"
    : "${GLM_TOKEN_FILE:?Set GLM_TOKEN_FILE to a file holding the bearer token}"
    test -r "$GLM_TOKEN_FILE"
    proxy_upstream=$GLM_BASE_URL
    proxy_extra=(--auth-token-file "$GLM_TOKEN_FILE")
    # GLM has no off switch for reasoning, only a budget, so both GLM arms must
    # name a level; `low` is the nearest thing to the other arms' disabled
    # thinking. See docs/experiment.md.
    if [ "$thinking_arm" = 1 ]; then
      effort=${GLM_REASONING_EFFORT:?Set GLM_REASONING_EFFORT for the thinking arm}
    else
      effort=low
    fi
    think_kwargs="{\"reasoning_effort\": \"$effort\"}"
    ;;
  *)
    proxy_upstream=http://127.0.0.1:12001
    proxy_extra=()
    # Qwen and Snowball both take upstream's native flag.
    think_kwargs="{\"enable_thinking\": true}"
    ;;
esac
if [ "$thinking_arm" = 1 ]; then
  fixed_max_tokens=$think_max_tokens
  proxy_extra+=(--raise-max-completion-tokens "$think_max_tokens")
fi
case "$arm" in
  glm|glm-think|*-think)
    proxy_extra+=(--inject-extra-body "{\"chat_template_kwargs\": $think_kwargs}")
    ;;
esac
# Process groups permit cleanup of vLLM's worker descendants.
server_pid=
case "$arm" in glm|glm-think) skip_local_server=1 ;; *) skip_local_server=0 ;; esac
# Locally served thinking arms use the -think server variant, whose only
# difference is the default chat-template setting.
fixed_thinking_flag=()
[ "$thinking_arm" = 1 ] && [ "$skip_local_server" = 0 ] && fixed_thinking_flag=(--enable-thinking)
if [ "$skip_local_server" = 0 ]; then
  if [ -n "${TREX_SERVER_PID:-}" ]; then
    # Adopt only the task's prestarted server, supplied explicitly by the operator.
    server_pid=$TREX_SERVER_PID
  else
    setsid bash /work/pilot-scripts/serve_model.sh "$arm" 12001 \
      > "/work/logs/$arm-vllm.log" 2>&1 &
    server_pid=$!
  fi
fi
setsid "$controller" /work/pilot-scripts/recording_proxy.py \
  --upstream "$proxy_upstream" "${proxy_extra[@]}" \
  --output "/work/results/$arm/wire" \
  > "/work/logs/$arm-proxy.log" 2>&1 &
proxy_pid=$!
setsid "$controller" /work/pilot-scripts/recording_proxy.py \
  --port 12002 --cancel-on-disconnect \
  --upstream "$proxy_upstream" "${proxy_extra[@]}" \
  --output "/work/results/$arm/wire" \
  > "/work/logs/$arm-campaign-proxy.log" 2>&1 &
campaign_proxy_pid=$!
cleanup() {
  kill -TERM -- ${server_pid:+"-$server_pid"} "-$proxy_pid" "-$campaign_proxy_pid" 2>/dev/null || true
}
trap cleanup EXIT
ready=0
for _ in $(seq 1 180); do
  if [ -n "$server_pid" ] && ! kill -0 "$server_pid" 2>/dev/null; then
    echo 'LLM server exited; inspect preserved server log.' >&2
    exit 1
  fi
  # Reach the model through the recorder, so a reachable arm is one whose
  # campaign path also works; the shared endpoint answers /v1/models, not /health.
  if [ "$skip_local_server" = 1 ]; then
    probe=http://127.0.0.1:12000/v1/models
  else
    probe=http://127.0.0.1:12001/health
  fi
  if curl -fsS --max-time 5 "$probe" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 10
done
test "$ready" = 1
if [ "${TREX_SKIP_FIXED_VALIDATION:-0}" != 1 ]; then
"$controller" -m benchmarks.llm_validation.planner_validation \
  --model "vllm/$model" --base-url http://127.0.0.1:12000/v1 \
  --repeats 3 --max-tokens "$fixed_max_tokens" --temperature 0.2 \
  "${fixed_thinking_flag[@]}" \
  --out "/work/results/$arm/planner-validation.json"
"$controller" -m benchmarks.llm_validation.supervisor_validation \
  --model "vllm/$model" --base-url http://127.0.0.1:12000/v1 \
  --repeats 3 --max-tokens "$fixed_max_tokens" \
  "${fixed_thinking_flag[@]}" \
  --out "/work/results/$arm/supervisor-validation.json"
fi
# Fixed-call diagnostics retain late responses. Finish them before starting the
# molecular budget, so retries cannot compete with campaign model requests.
"$controller" - "/work/results/$arm/wire" <<'PY'
import json, sys, time
from pathlib import Path
root = Path(sys.argv[1])
for _ in range(130):
    pending = [p for p in root.glob("*.json") if json.loads(p.read_text())["state"] == "pending"]
    if not pending:
        break
    time.sleep(5)
else:
    raise SystemExit("Fixed-call recorder still has pending requests; inspect before campaign.")
PY
# Interface checks can overlap molecular-environment installation.
for _ in $(seq 1 360); do
  if [ -f /work/T-REX/.env ]; then break; fi
  sleep 10
done
test -f /work/T-REX/.env
set -a
source /work/T-REX/.env
set +a
date -u +%FT%TZ > "/work/results/$arm/campaign-start-time.txt"
"$controller" -m trex.cli design "/work/configs/$arm.yaml" \
  --verify-backend-revisions
date -u +%FT%TZ > "/work/results/$arm/campaign-end-time.txt"
"$controller" -m trex.analysis summary \
  --archive-root "/work/results/$arm/campaign" --json \
  > "/work/results/$arm/campaign-summary.json"
"$controller" -m trex.analysis validate \
  --archive-root "/work/results/$arm/campaign" --json \
  > "/work/results/$arm/archive-validation.json"

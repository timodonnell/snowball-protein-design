# Experiment record

## Plan (2026-09-25)

- Upstream T-REX: `8b5103cc357a0c9df8c2eae6feaf1fb85f0d5e09`.
- Baseline model: `Qwen/Qwen3.6-27B-FP8`, study revision
  `ec4160bf26124fa57e6451d070ee0c459a36d5b7`, verified against upstream manifest.
- Comparison: `open-athena/Snowball-67B-A2B-5.7T-Mixed-RLVR-Step38`, revision
  `cfc1d845dae89b067cdc7250d0164abefa5a69cf`. BF16 MoE;
  32,768-token declared context; custom `grug_moe`.
- Target: registered PD-L1, identical released crop and constraints in both arms.
- Execute actual molecular jobs, retaining upstream prompts and validation.
- Compare raw output validity, repairs/fallbacks, rejected/accepted actions,
  model latency/tokens, backend completion, canonical AF2 success and diversity.
- Keep model inference GPU cost separate from molecular worker GPU cost.
- Initial matched pilot: one hour, two worker GPUs (2 and 3), campaign seed 0,
  five deadline-compatible families, no cross-campaign memory. Qwen uses GPU 0; Snowball
  uses GPUs 0 and 1 with DP=2, EP enabled, TP=1. Its fork rejects TP>1.
- Fixed evidence checks: five Planner and four Supervisor cases × three repeats
  per model. Set output limit 3072 and Planner temperature 0.2 explicitly:
  benchmark CLI defaults differ from the production campaign defaults.
- Qwen's checkpoint supplies top-k 20/top-p 0.95; Snowball's supplies neither.
  Set the Snowball server's generation overrides to top-k 20/top-p 0.95 to match
  the baseline, preserving each tokenizer's native EOS IDs. No prompt truncation
  or extra JSON enforcement is applied to either arm. `PYTHONHASHSEED=0` fixes
  Python set iteration order in the fixed-case prompts.
- Disable thinking through each server's native chat-template setting. The
  Snowball checkpoint's own template supports `enable_thinking=false`, emitting
  its native `/nothink` control. Upstream T-REX sends a thinking flag only when
  true, so relying on the client default alone would leave Snowball unspecified.
- Disable Snowball prefix caching to match Qwen's observed disabled cache.
  Serving stacks still differ (compiled FP8 dense Qwen versus eager BF16 MoE
  Snowball on two GPUs); latency is an operational measurement, not an isolated
  model-speed benchmark.
- Replay common evidence through both models to separate decision quality from
  stochastic campaign trajectories, if feasible after molecular smoke.
- Persist exact inputs and outputs for potential SFT and verifiable RL examples;
  do not label unvalidated model suggestions as successful designs.

## Infrastructure

CoreWeave RNO2A, four H100s requested, independent 600Gi persistent workspace.
The US-EAST GPU pool had no free GPUs during initial inspection. Local workstation
has only 47GiB free, insufficient for the full stack, so large assets stay remote.
Pod has a 12-hour deadline; delete it after collecting results. PVC retains data.

Snowball serving precheck completed on two H100s at 18:28 UTC. Native BF16
weights, no quantization or offload; returned the requested JSON and stopped on
the native end-of-turn token (128009). This is an infrastructure smoke, separate
from the Qwen-first molecular experiment. Serving uses Marin vLLM commit
`01911be34fac8715347962a8d791ca34a879e01e`; the resolved text-serving environment
is captured in `configs/snowball-serving.lock.txt`. See I005 for the explicit
TorchAudio dependency exception. Weights plus non-Torch overhead used 64.97GiB
per GPU. Server was stopped after this precheck.

## Source inspection

T-REX has Planner/Supervisor LLM roles and deterministic job validation,
scheduling and evidence reduction. Its default action space includes BindCraft,
BoltzGen, four Complexa sampling families, ProteinMPNN redesign and AF2 refiltering.
The supported deployment is Slurm; an existing OpenAI-compatible endpoint permits
direct `trex design` execution on Kubernetes. It uses separate incompatible
Python environments for serving, Complexa, BindCraft and BoltzGen.

## Pilot adjustment after actual execution

The initial all-family baseline generated 16 Complexa records but then stalled.
With a one-hour budget, BindCraft (2.5h prior), BoltzGen (2h), and MCTS (1h plus
drain margin) cannot be admitted. The cold-start builder returns missing
warm-start families before considering Planner hypotheses; infeasible seeds can
therefore suppress all subsequent jobs when no result qualifies as a recipe.
This was reproduced in the live baseline and is preserved as
`qwen-coldstart-stall`. The earlier missing-system-library attempt is preserved
as `qwen-install-failure`. Neither belongs in the matched comparison.

Both matched arms now enable Complexa beam, best-of-N, FK steering, ProteinMPNN
redesign, and canonical structure refilter. The original all-family YAMLs are
retained. Fixed-evidence checks still expose the full native action space. This
is a short-budget configuration of unmodified T-REX, not a full benchmark run.

The controller's one-hour clock starts after startup/preflight and may be followed
by up to ten minutes of drain per busy worker. We retain timestamps and recompute
endpoint exports from the complete archive after drain; the upstream summary's
last evidence tick alone can omit late results.

The original recorder on port 12000 keeps late upstream responses after a client
timeout. That behavior affected Snowball's fixed checks and may increase retry
contention; their timing is not a clean direct-server speed benchmark. Before
Snowball's molecular campaign, port 12002 was introduced to propagate client
disconnects upstream, matching the installed vLLM endpoint's cancellation
semantics. Canceled requests retain their input and cancellation status, with no
invented HTTP response. Qwen's completed campaign used port 12000 but had no
timeouts. Its historical input is in the archive; current checked-in YAMLs and
launcher use port 12002 for both campaigns. Fixed checks remain on port 12000 so
late generated content remains inspectable. See I014 and the proxy tests.

Complexa's seed is derived from the campaign seed, candidate ID and logical run
name. The physical output namespace is excluded from that seed. Identical
warm-start jobs therefore share a seed across arms; subsequent asynchronous
choices generally do not form paired molecular experiments. The archive
namespace prevents one arm's structures from overwriting the other's.

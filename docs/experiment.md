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
  all upstream families, no cross-campaign memory. Qwen uses GPU 0; Snowball
  uses GPUs 0 and 1 with DP=2, EP enabled, TP=1. Its fork rejects TP>1.
- Fixed evidence checks: five Planner and four Supervisor cases × three repeats
  per model. Set output limit 3072 and Planner temperature 0.2 explicitly:
  benchmark CLI defaults differ from the production campaign defaults.
- Replay common evidence through both models to separate decision quality from
  stochastic campaign trajectories, if feasible after molecular smoke.
- Persist exact inputs and outputs for potential SFT and verifiable RL examples;
  do not label unvalidated model suggestions as successful designs.

## Infrastructure

CoreWeave RNO2A, four H100s requested, independent 600Gi persistent workspace.
The US-EAST GPU pool had no free GPUs during initial inspection. Local workstation
has only 47GiB free, insufficient for the full stack, so large assets stay remote.
Pod has a 12-hour deadline; delete it after collecting results. PVC retains data.

## Source inspection

T-REX has Planner/Supervisor LLM roles and deterministic job validation,
scheduling and evidence reduction. Its default action space includes BindCraft,
BoltzGen, four Complexa sampling families, ProteinMPNN redesign and AF2 refiltering.
The supported deployment is Slurm; an existing OpenAI-compatible endpoint permits
direct `trex design` execution on Kubernetes. It uses separate incompatible
Python environments for serving, Complexa, BindCraft and BoltzGen.

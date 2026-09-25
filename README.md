# Snowball × T-REX

Pilot comparison of T-REX with the study's Qwen3.6-27B-FP8 controller and
`open-athena/Snowball-67B-A2B-5.7T-Mixed-RLVR-Step38`. Work in progress;
no design results yet.

We run the upstream planner, supervisor, deterministic validation and molecular
backends on the same PD-L1 target. First establish a short Qwen campaign, then
repeat with Snowball. Preserve raw LLM calls, rejected actions, backend errors,
structures, sequences and scores. Distinguish serving/integration failures from
reasoning failures, and report molecular outcomes per worker GPU-hour.

Source: [paper](https://www.biorxiv.org/content/10.64898/2026.09.22.753604v2),
[T-REX](https://github.com/ml-struct-bio/T-REX). Upstream is pinned as a submodule
in `vendor/T-REX`. This pilot tests operability and produces training-task leads;
it does not reproduce the paper's 48-hour benchmark or establish binding activity.

See [experiment notes](docs/experiment.md) and [issue log](docs/issues.md).

---
base_model: laion/snowball-67b-a2b-sft-s3-nemotron-terminal-step1888
tags:
  - reinforcement-learning
  - rlvr
  - mixture-of-experts
  - megatron
---

# Snowball 67B-A2B — 5.7T Mixed RLVR step 38

This is the Hugging Face export of optimizer checkpoint 38 from the 5.7T Agentic-start Snowball mixed-domain
RLVR1 arm. The arm used synchronous RLOO-N, the Megatron backend, a 32K context window, batch size 512, and 16
rollouts per prompt on 64 H100s.

The checkpoint was selected when export began because its 100-row holdout `pass@1` was 0.54. Step 42 later tied
that value before the arm was stopped at step 46, so this is not the most recent tied checkpoint. The final arm
metrics at step 46 were training reward/pass@16 0.6791/0.6875 and holdout avg_score/pass@1 0.5606/0.5000.

This checkpoint is intended as a research artifact. The campaign exposed output-contract and reward-starvation
problems in several weak domains; the model should not be interpreted as uniformly improved across the blend.

- [5.7T Mixed RLVR collection](https://huggingface.co/collections/open-athena/57t-mixed-rlvr-6ab2c1be7e68576539629758)
- [Animated per-domain RLVR1 rewards](https://storage.googleapis.com/marin-public/benjaminfeuer/snowball-rlvr1-domain-reward-trends/2026.09.22/index.html)
- [Public experiment artifacts](https://huggingface.co/datasets/open-athena/Snowball-67B-A2B-Mixed-RLVR-Experiment-Artifacts)


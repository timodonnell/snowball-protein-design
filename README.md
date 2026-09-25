# Snowball × T-REX

Actual PD-L1 design campaigns using the study's **Qwen3.6-27B-FP8** and
**open-athena/Snowball-67B-A2B-5.7T-Mixed-RLVR-Step38**. Each used a one-hour
controller budget, two H100 molecular workers, seed 0, and the same five action
families. The upstream controller is pinned and unmodified.

| Final outcome | Qwen | Snowball |
|---|---:|---:|
| Molecular jobs | 61 | 1 |
| Design records | 406 | 16 |
| AF2-qualified records | 29 | 0 |
| Qualified structural clusters | 4 | 0 |
| Exact qualified sequences | 24 | 0 |

Both arms produced exactly the same 16 warm-start structures. Snowball launched
no follow-up job: schema failures, timeouts, unsupported settings, missing
parents and deadline-infeasible proposals blocked progress. On 27 identical
fixed checks per model, final native acceptance was **27/27 versus 12/27**;
acceptance includes deterministic recovery and is not a molecular-success score.

Raw prompts/responses, failures, candidate decisions, sequences, PDBs and scores
are in `artifacts/`. CPU graders and small evidence-reading SFT/RL examples are
included. Start with [results and figures](docs/results.md),
[observed issues](docs/issues.md), and [training tasks](docs/training.md).
[Reproduction](docs/reproduce.md) covers setup, execution and artifact checks;
[protocol](docs/experiment.md) records deviations and serving differences.

Sources: [paper](https://www.biorxiv.org/content/10.64898/2026.09.22.753604v2),
[T-REX](https://github.com/ml-struct-bio/T-REX), pinned in `vendor/T-REX`.
This single short pilot establishes operability and training leads. It does not
reproduce the paper's 48-hour benchmark, isolate model quality, or establish
experimental binding.

The four-H100 pod has been deleted. The 600GiB CoreWeave PVC remains for recovery
and follow-up work (about 291GiB used); model weights are not stored in Git.

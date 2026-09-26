# Snowball × T-REX

Actual PD-L1 design campaigns using the study's **Qwen3.6-27B-FP8**,
**open-athena/Snowball-67B-A2B-5.7T-Mixed-RLVR-Step38** and **GLM-5.3**. Each
used a one-hour controller budget, two H100 molecular workers, seed 0, and the
same five action families. The upstream controller is pinned and unmodified.

| Final outcome | Qwen | Snowball | GLM |
|---|---:|---:|---:|
| Molecular jobs | 61 | 1 | 24 |
| Design records | 406 | 16 | 144 |
| AF2-qualified records | 29 | 0 | 18 |
| Qualified structural clusters | 4 | 0 | 6 |
| Exact qualified sequences | 24 | 0 | 18 |

All three arms produced exactly the same 16 warm-start structures. Snowball
launched no follow-up job: schema failures, timeouts, unsupported settings,
missing parents and deadline-infeasible proposals blocked progress. On 27
identical fixed checks per model, final native acceptance was **27/27 for Qwen
and GLM versus 12/27 for Snowball**; acceptance includes deterministic recovery
and is not a molecular-success score.

Qwen and GLM reach the same endpoint differently. Qwen produced more qualified
records; GLM produced fewer but in **more distinct structural clusters (6 vs 4)**
and at lower binder scRMSD, from a third as many started jobs. The two share one
joint cluster and no exact sequence. One campaign per model cannot rank them.

GLM is served by a shared multi-tenant endpoint rather than this pod's GPUs, and
unlike the other two it cannot disable reasoning — only budget it. Both facts
change what its numbers mean; see [protocol](docs/experiment.md).

Raw prompts/responses, failures, candidate decisions, sequences, PDBs and scores
are in `artifacts/`. CPU graders and small evidence-reading SFT/RL examples are
included. Start with [results and figures](docs/results.md), the
[browsable transcript report](report/index.html) of every recorded call,
[observed issues](docs/issues.md), [capability gaps](docs/capability-gaps.md),
and [training tasks](docs/training.md).
[Reproduction](docs/reproduce.md) covers setup, execution and artifact checks;
[protocol](docs/experiment.md) records deviations and serving differences.

Sources: [paper](https://www.biorxiv.org/content/10.64898/2026.09.22.753604v2),
[T-REX](https://github.com/ml-struct-bio/T-REX), pinned in `vendor/T-REX`.
This single short pilot establishes operability and training leads. It does not
reproduce the paper's 48-hour benchmark, isolate model quality, or establish
experimental binding.

Both four-H100 pods have been deleted. The 600GiB CoreWeave PVC remains for
recovery and follow-up work; model weights are not stored in Git.

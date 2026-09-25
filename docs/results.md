# Pilot results — 25 September 2026

**Qwen produced 29 qualified records in four structural clusters; Snowball
produced no qualified design and launched no job beyond the shared warm start.**
Both completed campaigns use the same PD-L1 crop, seed, five enabled action
families, one-hour controller budget and two H100 molecular workers. See
[protocol](experiment.md), [failures](issues.md), and the
[machine-readable comparison](../artifacts/design-comparison.json).

## Molecular endpoints

The Qwen archive after drain contains **29 qualified records in four binder-chain
Foldseek clusters** (TM-score 0.6). There are 24 distinct exact qualified sequences.
Qualification means AF2 pLDDT ≥90, normalized iPAE ≤7/31 and binder scRMSD <1.5Å;
these are computational predictions, not measured binding.

| Measurement | Qwen | Snowball |
|---|---:|---:|
| Started molecular jobs | 61 | 1 |
| All result records | 406 | 16 |
| Complete canonical AF2 metric vectors | 150 | 16 |
| Canonical records with verified binder identity | 146 | 12 |
| Strict qualified records | 29 | 0 |
| Qualified structural clusters | 4 | 0 |
| Exact qualified sequences | 24 | 0 |
| Qualified sequence clusters (90% identity, 80% coverage) | 22 | 0 |
| Controller elapsed minutes, including overrun/drain | 60.433 | 64.617 |
| Worker-wall H100-hours, including idle time/drain | 2.0144 | 2.1539 |
| Native recorded job charges, H100-hours | 1.5251 | 0.1828 |
| Qualified clusters / worker-wall H100-hour | 1.9857 | 0 |

The 16 warm-start PDBs and their canonical metrics match exactly across arms.
Snowball's 12 verified binders all fail scRMSD; four pass pLDDT and eight pass
iPAE individually. Its four other outputs have unresolved chain identity.
The one warm-start job is deterministic controller behavior, not evidence of
successful Snowball planning. No Snowball follow-up job ran.

![AF2 metric distributions](../artifacts/figures/design-comparison.png)

| Median over all verified, canonically scored records | Qwen | Snowball |
|---|---:|---:|
| pLDDT | 86.750 | 87.190 |
| Normalized iPAE | 0.26581 | 0.17544 |
| Binder scRMSD (Å) | 3.174 | 5.277 |

Qwen found a qualified subset while also producing many poor exploratory
designs. Its median is not uniformly better on every axis; the measured yield
and qualified diversity are the useful endpoint differences here.

The 256 ProteinMPNN-only records have no canonical AF2 scores. They must not be
included as failures or successes in a scored-design pass rate. Four other
records have unresolved chain identity. The final drain added a 29th qualified
record after the last evidence summary reported 28; our endpoint comes from the
complete archive. Both native archives validate with no errors or skipped
records. Snowball has the expected `no_strict` Foldseek warning; with zero
qualified structures, its qualified-cluster count is zero without clustering.
Qwen has no validation warnings. All 422 collected PDB hashes, the 29 qualified
PDB copies and their FASTA IDs pass the [integrity check](../artifacts/integrity-check.json).

Native job charges use launch-to-reap elapsed time and can include time after a
worker finishes while the controller is in an LLM call. They are not hardware
active-GPU measurements. The primary efficiency denominator is worker-wall time,
including idle slots and drain.

Snowball's final iteration started with about five seconds left, then spent
160.95 seconds in a retried model call and 120 seconds in idle backoff. The
native wall check occurs at the next loop start. The resulting 4.62-minute
overrun is included above; no molecular work was running during it.

![Campaign yield over time](../artifacts/figures/campaign-progress.png)

Eight qualified records came directly from Complexa beam search, three from FK
steering, and 18 from AF2 refiltering of ProteinMPNN redesigns. Among qualified
records, median pLDDT is 94.921, iPAE 0.15405, scRMSD 1.084Å and binder length
64 residues. Those records are related descendants, not independent replicates.

One representative per qualified structural cluster, taking the highest native
production-quality rank within each cluster:

| Result / PDB | Family | Length | pLDDT | iPAE | scRMSD (Å) |
|---|---|---:|---:|---:|---:|
| [6ce700e4162c9a9d](../artifacts/qwen/designs/all-structures/6ce700e4162c9a9d.pdb) | Beam | 70 | 95.091 | 0.16187 | 0.728 |
| [d59974f4a4ca172f](../artifacts/qwen/designs/all-structures/d59974f4a4ca172f.pdb) | Redesign → refilter | 64 | 95.056 | 0.14578 | 0.877 |
| [a02a9e59990ca80b](../artifacts/qwen/designs/all-structures/a02a9e59990ca80b.pdb) | Beam | 60 | 91.829 | 0.15932 | 0.680 |
| [3499a68d84ab0c08](../artifacts/qwen/designs/all-structures/3499a68d84ab0c08.pdb) | FK steering | 82 | 92.690 | 0.16292 | 1.369 |

All qualified sequences are in [strict-binders.fasta](../artifacts/qwen/designs/strict-binders.fasta).

One useful redesign lineage illustrates the task: beam parent
`92988d30a69a7c45` had pLDDT 94.141 and iPAE 0.15753 but failed scRMSD at 2.438Å.
ProteinMPNN child `6b17cf747d379437` had no canonical metrics until refiltering.
Its scored descendant `b365f28499eb5425` passed at pLDDT 95.000, iPAE 0.14757 and
scRMSD 1.222Å. This is a candidate for reviewing an evidence-to-action training
example, not proof that the LLM caused the improvement.

## Same-prompt interface comparison

All nine original prompt hashes match across models; each fixture was repeated
three times. These checks use the native extractors/validators and a zero
confidence threshold, unlike the live threshold of 0.55.

| Fixed-check measurement | Qwen | Snowball |
|---|---:|---:|
| Planner first reply is JSON only | 15/15 | 0/15 |
| Planner extracted schema passes before explicit repair | 13/15 | 1/15 |
| Planner first schema **and** configuration checks pass | 13/15 | 0/15 |
| Planner final native acceptance | 15/15 | 6/15 |
| Supervisor first reply is JSON only | 12/12 | 0/12 |
| Supervisor extracted schema / final native acceptance | 12/12 | 6/12 |
| Supervisor final valid, non-abstaining, with ranked candidates | 12/12 | 3/12 |
| Supervisor final mode mixture meets fixture expectations | 12/12 | 3/12 |
| Supervisor valid, ranked, non-abstaining and confidence ≥0.55 | 9/12 | 0/12 |
| Median logical Planner call, including retries | 24.56s | 132.11s |
| Median logical Supervisor call | 9.915s | 49.265s |

![Fixed interface comparison](../artifacts/figures/interface-comparison.png)

Snowball's accepted replies required extraction from surrounding prose. Five of
its six accepted Planner calls also needed placeholder evidence-reference
repair. The one extracted first-response Planner object passing schema supplied
an unsupported MCTS parameter. All six accepted Snowball Supervisor replies
omitted confidence, receiving the native default 0.5; three also abstained.
Three Qwen Supervisor replies omitted confidence/abstention fields too, using
native defaults. "Schema passes" here means the native validator, including its
built-in defaults, before explicit schema-field repair.

Snowball made 35 HTTP attempts for 27 logical calls (eight SDK retries), with
eight length-terminated responses and no JSON-only responses. All eventually
returned HTTP 200 through the diagnostic recorder, but four logical Planner
calls timed out; late HTTP success does not imply controller success. Eight
first Planner responses took at least 90 seconds. Model-format errors also
occurred in responses that finished on time. The recorder's late-response
behavior and differing serving stacks limit latency interpretation (I014).

## Live interface behavior

On identical fixed fixtures, Qwen passed 13/15 Planner responses before repair
and 15/15 after deterministic repair. Supervisor passed 12/12 first responses.
All 27 responses were complete JSON, with no HTTP errors, model repair retries
or output truncation. The two Planner repairs concern zero prediction thresholds
and a disallowed evidence-reference name. Repeated calls to nine fixtures are
not 27 independent tasks.

During the molecular campaign, all 80 actual LLM calls returned complete JSON
and were accepted by the native parser (58 Planner, 22 Supervisor). Eighteen
Planner calls abstained; 36 additional Supervisor archive entries skipped
inference because no hypotheses/candidates existed. These counts are distinct
from malformed responses. The archive also records 40 deterministic critic
evaluations, which are not extra model calls.

Snowball made 21 logical Planner calls: eight parsed successfully (including
one abstention), six failed schema checks, and seven timed out. Fourteen calls
triggered fallback. Its 21 Supervisor archive entries all skipped inference
because no usable hypotheses/candidates reached selection; they are not 21
failed Supervisor model calls. Seven critic entries are deterministic checks.

The live Snowball wire archive has 34 HTTP attempts: 14 completed with HTTP 200
and 20 were canceled when the controller disconnected. None of the 14 completed
responses was JSON only. Canceled responses have no returned token usage, so
the recorded 166,272 input / 15,537 output tokens are lower bounds. There were
no observed context-overflow HTTP errors. Retokenization of all 69 fixed/live
requests, including cancellations, found a maximum of 15,679 input tokens and
zero requests exceeding 32,768 with the output allowance; every available
server prompt-token count matched this audit.

Parsed proposals still failed downstream: heavy beam settings exceeded the
deadline, best-of-N received unsupported parameters, and a ProteinMPNN proposal
omitted a concrete parent. See [reviewed examples](case-studies.md). These are
distinct from serving timeouts and from the shared cold-start controller issue.

## Qwen replay of Snowball's actual states

After both campaigns, replayed five exact live Snowball Planner prompts at
call-index quartiles: rounds 1, 6, 11, 16 and 21. All prompts were reconstructed
byte-for-byte from archived evidence. This diagnostic launched no molecular jobs.

Qwen returned five JSON-only responses passing both schema and configuration
validation without explicit repair. The first three produced feasible static
candidate previews but explicitly reported confidence 0.5, below the live 0.55
gate. The final two abstained as the budget closed. Thus **zero of these five
replies supplied a feasible action that also passed the live confidence and
abstention gate**. This supports a format-compatibility difference, not a claim
that replacing Snowball's answers with these teacher answers would improve yield.

All five [raw cases](../artifacts/replay-qwen-on-snowball/cases.jsonl) and
[scores](../artifacts/replay-qwen-on-snowball/summary.json) are retained, including
the low-confidence and abstaining outputs. Static previews assume backend and
parent-artifact availability; they are review material, not optimal-action labels.

## Artifacts and interpretation

Each arm's directory contains native campaign/fixed-check reports, exact HTTP
requests and responses, job accounting, portable structures, FASTA, score tables,
and an index connecting model decisions to candidates and descendants. The
decision index is for review; overlapping descendants must not be treated as
independent rewards. Original failed attempts are stored separately and excluded
from the matched endpoint.

The Qwen requests projected through Snowball's native tokenizer reach 32,142
input tokens; 39/107 requests would exceed its 32,768-token window when reserving
3,072 output tokens. This is a counterfactual context-fit check, not a measured
Snowball failure rate. Actual Snowball requests fit its window, as audited above.

This single short campaign per model cannot establish model superiority. It is
an operability and training-task pilot. Longer paired runs, additional seeds and
targets, and a deterministic-controller baseline are needed for policy claims.

The four-H100 allocation was released at 21:59 UTC. Pod start through confirmed
deletion totals an upper estimate of **15.303 H100 reservation-hours**, including
installation, failed diagnostics, fixed checks, idle time, both campaigns and
teacher replay. This is not hardware-active compute or a billing invoice.
Qwen serving used one GPU and Snowball two; the worker-only efficiency above
excludes both. The [allocation record](../artifacts/coreweave-allocation.json)
also records the retained 600GiB PVC (approximately 291GiB used).

Verification: 13 tests passed, Python compilation and shell syntax checks
passed, both decision indexes have no missing wire matches, and all collected
endpoint structure/sequence checks passed. Figures are available as PNG, SVG
and PDF under `artifacts/figures/`.

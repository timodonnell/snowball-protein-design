# Pilot results — 25 September 2026

**In progress: Qwen and both fixed-check suites are complete; Snowball's molecular campaign is running.** The final comparison will
replace this notice. Both arms use the same PD-L1 crop, seed, five enabled action
families, one-hour budget and two H100 molecular workers. See
[protocol](experiment.md) and [failures](issues.md).

## Completed Qwen endpoint

The full archive after drain contains **29 qualified records in four binder-chain
Foldseek clusters** (TM-score 0.6). There are 24 distinct exact qualified sequences.
Qualification means AF2 pLDDT ≥90, normalized iPAE ≤7/31 and binder scRMSD <1.5Å;
these are computational predictions, not measured binding.

| Measurement | Qwen |
|---|---:|
| Started molecular jobs | 61 |
| All result records | 406 |
| Complete canonical AF2 metric vectors | 150 |
| Canonical records with verified binder identity | 146 |
| Strict qualified records | 29 |
| Qualified structural clusters | 4 |
| Exact qualified sequences | 24 |
| Worker-wall H100-hours, including idle time/drain | 2.0144 |
| Native recorded job charges, H100-hours | 1.5251 |
| Qualified clusters / worker-wall H100-hour | 1.9857 |

The 256 ProteinMPNN-only records have no canonical AF2 scores. They must not be
included as failures or successes in a scored-design pass rate. Four other
records have unresolved chain identity. The final drain added a 29th qualified
record after the last evidence summary reported 28; our endpoint comes from the
complete archive. Native archive validation passed with no errors, warnings or
skipped records.

Native job charges use launch-to-reap elapsed time and can include time after a
worker finishes while the controller is in an LLM call. They are not hardware
active-GPU measurements. The primary efficiency denominator is worker-wall time,
including idle slots and drain.

Eight qualified records came directly from Complexa beam search, three from FK
steering, and 18 from AF2 refiltering of ProteinMPNN redesigns. Among qualified
records, median pLDDT is 94.921, iPAE 0.15405, scRMSD 1.084Å and binder length
64 residues. Those records are related descendants, not independent replicates.

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

## Qwen live interface behavior

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
Snowball failure rate. Actual Snowball HTTP outcomes will be reported separately.

This single short campaign per model cannot establish model superiority. It is
an operability and training-task pilot. Longer paired runs, additional seeds and
targets, and a deterministic-controller baseline are needed for policy claims.

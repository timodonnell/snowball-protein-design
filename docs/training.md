# Turning this pilot into training tasks

T-REX's LLM controls experiments; it does not emit amino-acid sequences. Train
the Planner and Supervisor interfaces first, then test whether better decisions
improve molecular yield. A successful backend run is not evidence that its LLM
was useful: deterministic warm starts and fallbacks can run the same jobs.

## Cheap, verifiable tasks

| Task | Input/output | Verification |
|---|---|---|
| Executable Planner cards | Frozen evidence and capability schema → 1–4 hypothesis cards | Original schema, reference whitelist, correct metric direction, finite positive thresholds, allowed settings and joint evaluation budget |
| Candidate ranking | Evidence, hypotheses, offered candidates and free slots → mixture and ranked decisions | Existing candidate IDs only; unique contiguous ranks; valid resource classes; source/parent constraints |
| Budget arithmetic | Family cost, remaining time and per-job settings → admissible jobs | Execute original feasibility/budget checks; distinguish individually legal settings from an illegal product |
| Evidence extraction | Frozen archive summary → counts, dominant failing axis, normalized units, duplication and score provenance | Recompute exact labels from archive; missing scores stay unknown; native diagnostic scores cannot imply canonical AF2 success |
| Repair | Invalid response plus validator feedback → corrected response | Re-run validators and check that the correction did not invent evidence or candidate IDs |

`scripts/audit_fixed.py` already exposes the original Planner/Supervisor validators
and configuration checks as a CPU-only scorer. It records raw schema success
separately from extraction, repair and final upstream acceptance. The negative
controls in `tests/test_offline_audit.py` catch hallucinated references,
unoffered candidates, truncated JSON and combined-budget violations.

Supply the precise cost-scaling rule and drain margin in budget-task inputs;
rough runtime hints alone do not expose every downstream feasibility condition.

`scripts/evidence_tasks.py` provides a smaller executable starting point:
four development examples built from 28 actual Qwen campaign records, with
deterministic SFT answers and an exact JSON reward. They test source-family
attribution, canonical qualification, missing measurements and unresolved chain
identity. They are intentionally **not** held-out evaluation or policy-optimality
labels. The negative controls reject the exact RMSD boundary, native-score
substitution, invented source families, prose and duplicate JSON keys.

```bash
PYTHONPATH=vendor/T-REX .venv/bin/python scripts/evidence_tasks.py build \
  artifacts/qwen artifacts/training-development/qwen-evidence.jsonl
PYTHONPATH=vendor/T-REX .venv/bin/python scripts/evidence_tasks.py grade \
  artifacts/training-development/qwen-evidence.jsonl qwen_evidence_00 response.json
```

A starter reward should require a usable non-abstaining action when a feasible
one is offered. Rewarding schema alone can be gamed by empty output, generic
claims or perpetual abstention. Treat validity, evidence consistency and action
utility as separate measurements; do not use the model's confidence or fluent
rationale as ground truth. Model output can pass the native schema while later
being dropped or changed by candidate construction.

The upstream fixed checks also lower the confidence gate from production's 0.55
to zero. Snowball's accepted fixed Supervisor outputs omitted confidence; T-REX
supplied 0.5, below the live gate. Three Qwen outputs also used this default.
Schema acceptance alone therefore overstates live compatibility. Do not solve this by
rewarding unsupported confidence: evaluate calibration and action quality
separately from the chosen operational threshold.

## SFT candidates

The retained `wire/` records contain exact prompts and responses; `fixed-audit/`
adds first-response labels and deterministic corrections. `decision-index.jsonl`
links actual campaign calls to validated candidates, launches and measured
descendants. These lineage associations overlap across calls and are not causal
rewards or independent examples. Qwen is a useful
teacher candidate, not an oracle: in the initial fixed checks, two of its 15
Planner responses required repair. Preserve the distinction between raw teacher
output, a validated correction, and a choice with measured downstream benefit.

For a first SFT set, generate new evidence fixtures with known counts, valid
parents and budgets, sample several teacher answers, and retain only answers
passing all executable checks. Review whether the proposed action actually
addresses the evidence. Mix cold-start, productive, rescue, redundant, stalled,
missing-measurement and no-feasible-action states. Include short complete answers
within the actual 3,072-token serving limit.

The nine upstream fixtures in this pilot are **evaluation-only**. Their three
repetitions are not 27 independent tasks. Split future data by target and
ancestry, keeping nearby ticks, parent/child designs, recipes and paraphrases
in the same split. Report both the original public fixtures and newly held-out
ones after any training.

## Molecular decision reward

Snapshot a real archive and queue, then branch multiple decisions from that same
state using paired generator seeds and equal worker budgets. Score completed
canonical AF2 qualification and binder-chain Foldseek novelty relative to the
snapshot. Count worker time, failed jobs, refilter costs, idle slots and drain;
report LLM serving cost separately. Repeat across seeds and targets before
training against the molecular score.

Pin backend seeds independently of the model's card ordering when building that
counterfactual environment. In native T-REX the launch seed includes candidate ID
and logical run name, so different tick/card IDs can change molecular samples
even for otherwise similar proposals.

Useful comparisons include the original Qwen policy, Snowball before/after
training, and the deterministic controller without useful LLM decisions. This
pilot's single asynchronous trajectory per model cannot identify a causal
advantage or distinguish policy quality from molecular sampling luck.

Keep reward provenance strict. Reject unresolved chain identities, missing
structures, absent canonical metrics, duplicate qualified structures and
infrastructure failures masquerading as model mistakes. The observed cold-start
stall is a controller feasibility issue; training the LLM cannot fix a builder
that suppresses its proposals. Sparse-evidence reward-setting adjustments are
also controller behavior, not necessarily schema errors.

See [reviewed case studies](case-studies.md): Qwen proposed a measured successful
rescue while also misattributing another parent's source family, and Snowball
returned a terminal-agent schema on a T-REX fixture. These motivate separate
format, factual-consistency and molecular-utility objectives.

Add few-shot prompts and constrained JSON output as inexpensive baselines in the
next experiment. They can test how much of the initial gap can be addressed by
the interface before investing in fine-tuning. Continue measuring capability
parameters, deadline feasibility and evidence truthfulness after formatting is
enforced.

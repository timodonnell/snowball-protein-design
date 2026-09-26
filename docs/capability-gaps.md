# Snowball failures and the capabilities they indicate are missing

Derived from the 25 September 2026 matched pilot: one hour of controller budget,
two H100 workers, seed 0, five action families, unmodified T-REX, identical
prompts and target in both arms. Sources are the issue log ([issues.md](issues.md)),
endpoints ([results.md](results.md)), the native validation reports, the exact
wire archive and the campaign archive under `artifacts/snowball/`.

This is a failure-to-capability mapping from a single short campaign plus 27
fixed same-prompt checks per model. It identifies what Snowball could not do in
this environment. It does not rank the models' general ability, isolate model
quality from its serving stack, or establish that fixing these gaps would have
produced qualified binders.

## Attribution first

Most incidents in this pilot are not Snowball capability gaps. Only failures
whose cause is Snowball's own output are evidence about the model.

| Layer | Examples | Counts as missing capability? |
|---|---|---|
| Model output | wrong object, missing/mistyped fields, placeholder references, unsupported parameters, unresolved parents, omitted confidence | **Yes** |
| Model output × serving latency | prose to the 3,072-token cap, 90s timeouts | Partly — see [confounds](#confounds-and-non-gaps) |
| Deterministic controller | cold-start stall (I009), conservative cost priors, wall-check overrun (I026), native defaults (I019) | No |
| Serving / harness / infrastructure | TorchAudio ABI (I005), missing `ninja` (I006), `libXrender.so.1` (I008), recorder cancellation (I014), token-count API (I012), GPU scheduling (I002, I011) | No |
| Molecular output | unresolved chain identity in 4 of 16 warm-start structures (I010) | No — identical in both arms |

The 16 warm-start structures, their AF2 metrics and their file hashes are
byte-identical across arms. Snowball's zero qualified designs are therefore not
a molecular-sampling difference: **no Snowball-proposed job ever started.**

## The live campaign, round by round

Snowball reached 21 controller ticks in the hour; Qwen reached 58. Minutes run
from the campaign start (20:47:44Z). "Attempts" counts HTTP requests per
logical call: the OpenAI SDK retries once, and a cancelled attempt is one the
controller abandoned at its 90-second timeout. Bracketed tags point to the
[worked examples](#worked-examples).

| Tick | Start min | Attempts | Cancelled | Logical latency | Outcome |
|---|---:|---:|---:|---:|---|
| v7r001 | 0.2 | 2 | 1 | 171.1s | `missing_top:cards`, repair failed [E3](#e3--the-answer-buried-behind-its-own-scratch-work-c1) |
| v7r002 | 3.1 | 1 | 0 | 8.0s | `confidence_not_number` on an abstention [E4](#e4--three-abstentions-in-three-rounds-one-accepted-c1-c8) |
| v7r003 | 3.3 | 1 | 0 | 10.2s | parsed, abstained [E4](#e4--three-abstentions-in-three-rounds-one-accepted-c1-c8) |
| v7r004 | 3.6 | 1 | 0 | 16.6s | `cards_not_list` on an abstention [E4](#e4--three-abstentions-in-three-rounds-one-accepted-c1-c8) [E5](#e5--self-correction-that-arrives-too-late-c1-c9) |
| v7r005 | 3.9 | 2 | 1 | 124.8s | parsed → heavy beam cards, deadline-infeasible [E9](#e9--correct-arithmetic-against-the-wrong-constraint-c6) |
| v7r006 | 6.1 | 1 | 0 | 32.2s | parsed → heavy beam cards, deadline-infeasible [E9](#e9--correct-arithmetic-against-the-wrong-constraint-c6) |
| v7r007 | 6.7 | 2 | 1 | 132.0s | parsed → candidates blocked |
| v7r008 | 9.0 | 1 | 0 | 78.8s | `missing_top:cards`, repair failed [E3](#e3--the-answer-buried-behind-its-own-scratch-work-c1) [E9](#e9--correct-arithmetic-against-the-wrong-constraint-c6) |
| v7r009 | 10.4 | 1 | 0 | 62.6s | parsed → candidates blocked |
| v7r010 | 11.5 | 2 | 1 | 142.3s | parsed → candidates blocked |
| v7r011 | 14.1 | 2 | 2 | 180.6s | timed out [E13](#e13--timeouts-with-nothing-to-grade-c3) |
| v7r012 | 19.1 | 2 | 2 | 180.6s | timed out [E13](#e13--timeouts-with-nothing-to-grade-c3) |
| v7r013 | 24.1 | 2 | 2 | 180.6s | timed out [E13](#e13--timeouts-with-nothing-to-grade-c3) |
| v7r014 | 29.2 | 2 | 1 | 151.9s | parsed → invalid `omit_AAs`, no concrete parent [E10](#e10--a-redesign-that-claims-a-parent-it-never-names-c5-c7) |
| v7r015 | 33.7 | 2 | 2 | 180.6s | timed out [E13](#e13--timeouts-with-nothing-to-grade-c3) |
| v7r016 | 38.7 | 2 | 2 | 180.6s | timed out [E13](#e13--timeouts-with-nothing-to-grade-c3) |
| v7r017 | 43.7 | 1 | 0 | 51.3s | parsed → candidates blocked |
| v7r018 | 46.6 | 1 | 0 | 89.0s | `missing_top:cards`, repair failed [E3](#e3--the-answer-buried-behind-its-own-scratch-work-c1) |
| v7r019 | 50.1 | 2 | 2 | 180.7s | timed out [E13](#e13--timeouts-with-nothing-to-grade-c3) |
| v7r020 | 55.1 | 2 | 2 | 180.6s | timed out [E13](#e13--timeouts-with-nothing-to-grade-c3) |
| v7r021 | 60.1 | 2 | 1 | 160.9s | `missing_top:cards`, repair failed [E3](#e3--the-answer-buried-behind-its-own-scratch-work-c1) |

Six ticks succeeded only on the retry after a 90-second cancellation; seven lost
both attempts. All 34 campaign HTTP attempts are accounted for: 14 completed,
20 cancelled.

Funnel over the campaign:

```
21 Planner calls
├─ 7 timed out            ─┐
├─ 6 failed schema         ├─ 14 fallback ticks, no cards
└─ 8 parsed ─ 1 abstained ─┘
             └─ 7 productive → 19 hypothesis cards → 77 candidates
                                                     └─ 0 feasible, 0 compiled, 0 launched
1 deterministic warm-start candidate → 16 records → 0 qualified
```

All 21 Supervisor entries skipped inference because no usable candidate reached
selection. Those are downstream consequences, not Supervisor model failures.

Snowball spent **2,495.9s (41.6 min) of the 60-minute budget inside Planner
calls** for 21 calls. Qwen spent 939.1s (15.7 min) for 58 calls.

## Capability gaps

Ordered by where they block the pipeline. C1–C3 prevent output from reaching the
controller at all; C4–C5 and C7 produce output the builder cannot compile; C6 and
C8 produce compilable output that is inadmissible or uncommitted; C9 removes the
chance to recover from any of the above.

Each gap is shown verbatim in [worked examples](#worked-examples) E1–E14, cited
inline below; [E14](#e14--the-failures-are-fixture-deterministic-not-sampling-noise)
shows that the fixed-check failures reproduce across all three repeats.

### C1 — Emit only the requested object, with correct field types

**Missing:** structured-output discipline. The system prompt says *"Return JSON
only. Exact top-level shape"*; every completed Snowball response was prose with
JSON somewhere inside it, and the extractor usually reached a fragment of the
answer first ([E3](#e3--the-answer-buried-behind-its-own-scratch-work-c1), [E4](#e4--three-abstentions-in-three-rounds-one-accepted-c1-c8), [E5](#e5--self-correction-that-arrives-too-late-c1-c9), [E6](#e6--leaked-chat-template-control-tokens-c1-c2)).

| Evidence | Snowball | Qwen |
|---|---:|---:|
| Completed responses that are JSON only | 0/49 | 107/107 |
| Responses prefixed with prose | 49/49 | 0/107 |
| Responses using markdown code fences | 16/49 | 0/107 |
| Fixed Planner: schema valid before repair | 1/15 | 13/15 |
| Fixed Planner: schema **and** configuration valid | 0/15 | 13/15 |
| Fixed Supervisor: schema valid before repair | 6/12 | 12/12 |

Live schema failures were not only missing keys but wrong types:
`confidence_not_number` (v7r002) and `cards_not_list` (v7r004). Fixed-check
first responses failed on `missing_top:cards` (9/15) and one `parse_fail`.

This is the dominant gap by volume, and the closest to recoverable. In all 23
`missing_top:*` failures across both check sets, the object the extractor reached
was a fragment of the model's own scratch work, and in 18 of them a correctly
keyed envelope appears later in the same response. What is missing is the
discipline to emit one object and nothing else, not the ability to compose the
object.

**Verification:** original validator on the first response, no extraction, no
repair; assert key presence *and* type. Already exposed by
`scripts/audit_fixed.py`.

### C2 — Recognize which task and role it is answering

**Missing:** task identification ([E2](#e2--a-terminal-agent-trajectory-instead-of-a-planner-reply-c2), [E11](#e11--supervisor-the-mixture-without-the-decision-object-c1-c2)). At the second fixed Planner fixture Snowball
returned a *terminal-agent trajectory* — an object with `keystrokes`, `duration`,
`commands`, `analysis`, `plan` and `task_complete: true` — in which it wrote a
plausible hypothesis card into `/app/output.json` with a heredoc and then `cat`ed
the file. It finished in 76.8s, inside the 90s timeout, and returned HTTP 200.
The controller saw `missing_top:cards`.

Two of 49 responses carry this shape ([raw
call](../artifacts/snowball/wire/1790367039384723572_7bf4841c-1ad6-4a77-8c52-12e34d8c7a21.json)).
The same confusion appears role-wise: 6 of 12 fixed Supervisor replies omitted
`mode_mixture`, the Supervisor's required top-level field.

This is the sharpest case of the general pattern — a *near-correct payload in the
wrong envelope* — and the one that no infrastructure change touches: faster
serving, a larger token budget and a better cost model would all have left it
failing. It is rarer than C1 (two responses), but it is the one that suggests
where the behavior comes from: an agentic-harness output habit surfacing in a
plain API call.

**Verification:** reward the top-level object shape of the requested role;
negative controls that present a plausible payload nested in a foreign envelope.
`tests/test_offline_audit.py` already covers the wrong-task object.

### C3 — Finish inside the token and latency budget

**Missing:** budgeted termination ([E1](#e1--prose-until-the-token-cap-c3), [E13](#e13--timeouts-with-nothing-to-grade-c3)). Reasoning ran long enough to consume the whole
output allowance or to blow the controller's timeout.

- 8 of 35 fixed HTTP attempts terminated on length at 3,072 tokens; 5 of 15
  logical first responses did.
- 11 logical Planner calls timed out: 4 fixed (I013) and 7 live.
- Median logical Planner call 132.1s vs Qwen 24.6s; Supervisor 49.3s vs 9.9s.
- 8 first fixed Planner responses took at least 90 seconds.
- The first fixed call produced prose until the cap, completed server-side at
  137.7s, and failed logically at 182.8s after one retry.

**Verification:** cap output tokens at the production 3,072 and score only
responses that complete within the 90s client timeout; report the wall cost of
each decision alongside its validity.

### C4 — Ground references in real evidence IDs

**Missing:** grounding, and resistance to copying the prompt's illustrative card ([E7](#e7--placeholder-references-copied-from-the-prompt-c4)).
The literal placeholder `result_or_route_id` from the system prompt's example
appears in **18 of 49** responses. Five of the six accepted fixed Planner replies
needed deterministic removal of it; four first responses failed on
`card[0]:unknown_evidence_refs:['result_or_route_id']`. Snowball also reproduced
the example's `beam_width: 8` (see C6). Qwen's placeholder rate is 0/107.

Note the asymmetry with the paper: upstream reports 6 invalid evidence
references in 3,125 Supervisor calls. Here it is the dominant repair.

**Verification:** whitelist check against the IDs actually present in the frozen
evidence; treat any prompt-example token as an automatic failure. Counterbalanced
prompt examples are worth testing, but copying the example is not proof the
example caused it.

### C5 — Use the capability registry correctly

**Missing:** parameter competence per action family ([E8](#e8--the-one-clean-reply-is-not-executable-c5), [E10](#e10--a-redesign-that-claims-a-parent-it-never-names-c5-c7)).

- The one fixed Planner object that passed the native schema proposed
  `beam_width` for `complexa_mcts`, which the registry rejects as an unknown
  parameter; a second repaired response repeated it (I017).
- Live, 7 candidates carried `unknown_param:beam_width|unknown_param:n_branch`
  into `complexa_best_of_n` (I024).
- 12 candidates supplied `omit_AAs` as the entire list of allowed values where
  the registry expects one string.
- Only 3 of 15 fixed Planner responses had all-valid configurations, and 0 passed
  schema and configuration together.

**Verification:** run the registry's own configuration check as a separate
reward. Schema acceptance must not be used as an executable-action reward.

### C6 — Do budget arithmetic on the joint configuration

**Missing:** deadline reasoning over the combined settings, not per-parameter
legality ([E9](#e9--correct-arithmetic-against-the-wrong-constraint-c6)). At rounds 5–6 Snowball proposed `beam_width=8, n_branch=4`; the
controller priced that at ~1.0h against ~0.9h remaining and hid both candidates.

Of the 77 model-derived candidates:

| Blocking reason | Candidates |
|---|---:|
| Deadline — heavy configuration the model chose (~1.0–1.1h vs 0.6–0.9h left) | 31 |
| Deadline — family base prior alone (0.5h + 0.1h drain vs ≤0.5h left) | 34 |
| Compilation — no concrete parent (C7) | 12 |
| Feasible and started | 0 |

The 34 base-prior rejections are only partly the model's: ordinary generator
admission closes around minute 24 in a one-hour pilot (see
[experiment.md](experiment.md)), and Snowball reached minute 24 having produced
no admissible action. The 31 heavy-config rejections are its own parameter choice.

**Verification:** budget tasks that supply the actual cost-scaling rule and drain
margin and require the model to reject the illegal product of individually legal
settings, per [training.md](training.md).

### C7 — Produce a complete action, including a real parent

**Missing:** parent resolution from observed structures ([E10](#e10--a-redesign-that-claims-a-parent-it-never-names-c5-c7)). At v7r014 Snowball
proposed ProteinMPNN redesign citing only `EvidenceSummary` and
`recent_ticks_history` — aggregates, not a result. Twelve candidates failed
compilation with `no_concrete_parent_result_id`. Their cost checks passed, so
this is distinct from C6: the action was affordable and still could not be built.

**Verification:** require a parent ID drawn from eligible archive results, then
assert the candidate compiles. See [case-studies.md](case-studies.md).

### C8 — Commit to a ranked decision with a stated confidence

**Missing:** decisiveness and explicit uncertainty in the Supervisor role ([E12](#e12--supervisor-no-confidence-field-at-all-c8)).

| Fixed Supervisor | Snowball | Qwen |
|---|---:|---:|
| Replies stating a confidence | 0/12 (all defaulted to 0.5) | 9/12 |
| Abstained | 3/12 | 0/12 |
| Valid, non-abstaining, with ranked candidates | 3/12 | 12/12 |
| Would pass the live 0.55 confidence gate | 0/12 | 9/12 |

Nine of 12 Snowball replies produced zero ranked decisions. This gap is shared
with the harness: T-REX supplies 0.5 when confidence is omitted, the fixed
checks use threshold 0 while production uses 0.55, and three Qwen replies relied
on the same default. The post-hoc Qwen replay of Snowball's five live states
passed every schema and configuration check yet still produced **0/5** actions
clearing the live gate. Treat C8 as a joint model-and-policy finding, and do not
train confidence inflation to cross the threshold.

### C9 — Recover after being told the output was wrong

**Missing:** self-correction ([E5](#e5--self-correction-that-arrives-too-late-c1-c9)). Every live schema failure records
`repair_failed:<same reason>` — the repair attempt reproduced the original
defect. `missing_top:cards` recurred at rounds 1, 8, 18 and 21, after 14 fallback
ticks had already shown the pattern. Fixed checks logged 0 successful model
repair retries against 8 SDK-level retries.

**Verification:** repair tasks that feed the validator's exact complaint back and
score the corrected response, checking that the fix did not invent evidence or
candidate IDs.

## Worked examples

Verbatim excerpts, trimmed with `…` where long, from
[`artifacts/snowball/wire/`](../artifacts/snowball/wire) (exact HTTP bodies) and
[`artifacts/snowball/fixed-audit/responses.jsonl`](../artifacts/snowball/fixed-audit/responses.jsonl)
(per-response labels). Fixed-check examples name the fixture and repeat; live
examples name the tick.

### E1 — Prose until the token cap (C3)

Fixed Planner, `productive_cd45_like`, repeat 0, both HTTP attempts. Each ran to
`finish_reason: length` at exactly 3,072 completion tokens — 137.7s and 138.1s,
both past the 90-second client timeout. Neither attempt ever reached a top-level
object; the only parseable JSON in the first attempt is a configuration fragment
from its own deliberation:

```json
{"complexa_beam": {"beam_width": 8, "n_branch": 4, "nsamples": 4, "nsteps": 400}}
```

Five of the 15 logical fixed first responses ended this way. The prompt asks for
the opposite of a derivation, in these words: *"Return JSON only. Exact top-level
shape"*, and, of the audit field, *"reasoning_trace is an audit trace, not hidden
chain-of-thought; keep each field one short sentence."*

### E2 — A terminal-agent trajectory instead of a Planner reply (C2)

Fixed Planner, `rescue_rich_betv1_like`, repeat 0. Completed in 76.8s, **inside**
the timeout, `finish_reason: stop`, HTTP 200. Snowball answered as though it were
driving a shell: it wrote the hypothesis card to a file with a heredoc, `cat`ed it
back, and declared the task done.

```json
    { "keystrokes": "cat > /app/output.json << 'EOF'\n{ … \"cards\": [ … ] }\nEOF\n",
      "duration": 0.5 },
    { "keystrokes": "cat /app/output.json\n", "duration": 0.1 }
  ],
  "task_complete": true
}
{
  "analysis": "The JSON output looks good and follows the schema. …",
  "plan": "No further actions needed. The task is complete.",
  "commands": [],
  "task_complete": true
}
```

The card nested inside `keystrokes` is broadly well formed. The controller read
the outer object and recorded `missing_top:cards`. No serving speedup, token
budget or cost model repairs this class of failure.
[Raw call](../artifacts/snowball/wire/1790367039384723572_7bf4841c-1ad6-4a77-8c52-12e34d8c7a21.json).

### E3 — The answer buried behind its own scratch work (C1)

The dominant failure. T-REX extracts a JSON object from the reply; Snowball
emitted several, and the first one is a fragment of the answer rather than the
answer. Live tick v7r021, the two parseable objects in order:

```json
{"complexa_beam": {"beam_width": 8, "n_branch": 4}}
```
```json
{ "abstain": false, "confidence": 0.6, "fail_reason": null,
  "rationale": "Diagnostic axes min_ipae, avg_ipsae, ipTM, and max_ipsae are levered but failing; …",
  "cards": [ … 1 card … ] }
```

The controller recorded `missing_top:cards`. Measured across the archive:

| Responses ending in `missing_top:*` | Fixed | Live |
|---|---:|---:|
| First parseable object was a fragment, not the envelope | 19/19 | 4/4 |
| A correctly keyed envelope appears **later in the same text** | 14/19 | 4/4 |

The fragments are recognizable pieces of the schema: a `config_delta_suggestions`
value, a `predicted_metric_changes` entry (`{axis, direction, baseline_refs, …}`),
a bare `mode_mixture` triple, or in one case an entire bare card. In the four live
cases the recoverable envelopes held 1, 2, 1 and 1 cards. Whether those cards
would have survived reference and threshold validation is untested — two of them
carry the `beam_width=8, n_branch=4` configuration that E9 shows was
deadline-infeasible anyway — but the recorded failure is the envelope, not the
card content.

### E4 — Three abstentions in three rounds; one accepted (C1, C8)

Rounds 2, 3 and 4 of the live campaign all reached the same judgment — too little
evidence to propose anything — and differed only in field typing.

v7r002, rejected `confidence_not_number`:

```json
{ "abstain": true, "confidence": null,
  "fail_reason": "No recent evidence of progress or diagnostic signals to form testable hypotheses",
  "rationale": "…", "cards": null }
```

v7r003, accepted:

```json
{ "abstain": true, "confidence": 0.6,
  "fail_reason": "No recent evidence of progress; all families untried and no diagnostic signals to guide hypotheses.",
  "rationale": "…", "cards": [] }
```

v7r004, rejected `cards_not_list` (first of its three objects had `"cards": null`).

Two legitimate abstentions were discarded over `null` versus `[]` and `null`
versus a number. Note also that v7r003 reports `confidence: 0.6` while
abstaining, explaining in its prose: "though we are abstaining, we keep
confidence as requested" — the number is compliance, not an estimate.

### E5 — Self-correction that arrives too late (C1, C9)

Live v7r004 deliberated with itself in the open, emitting three successive
objects and fixing its own bug in the third:

````
{ … "cards": null }

But the schema requires "cards" to be present (array). We can set cards to empty array.
Let's do:

{ … "cards": [] }

We must ensure we follow the schema exactly. … Thus final JSON:
```json
{ … "cards": [] }
```
````

The extractor took the first object. The model had the right answer, twice, and
still failed the call. This is the one place where the repair capability (C9)
appears to exist — but only inside a response the harness reads front to back.

### E6 — Leaked chat-template control tokens (C1, C2)

16 of the 49 completed responses contain control tokens as literal body text:
`<|im_end|>` (10), `<|end|>` (5), `<|im_start|>` (2), `<|assistant|>`,
`<|thinking|>` and `<|continue|>`. Several belong to other model families'
templates, not this checkpoint's own end-of-turn token (128009). Fixed
Supervisor, `rescue_rich_betv1_like`, repeat 0 emits one mid-reply and then
restates its object:

```
We'll write the JSON accordingly.
<|end|>

{ "mode_mixture": {"explore": 0.7, "rescue": 0.2, "exploit": 0.1},
  "candidate_decisions": [], "abstain": true,
  "fail_reason": "No launchable candidates available; state collapse requires exploration push" }
```

### E7 — Placeholder references copied from the prompt (C4)

Fixed Planner, `ambiguous_cbago_like`, repeat 1. The prompt's illustrative card
uses `result_or_route_id` as a stand-in for a real ID; Snowball used the
stand-in, and `result_id` as a baseline:

```json
"evidence_refs": ["EvidenceSummary", "result_or_route_id"],
"predicted_metric_changes": [
  {"axis": "iPAE", "direction": "decrease", "baseline_refs": ["result_id"],
   "min_relative_deficit_reduction": 0.15, "min_absolute_delta": null} ]
```

Recorded reason: `card[0]:unknown_evidence_refs:['result_or_route_id']`; the
controller's repair filtered the reference out. The string appears in 18 of 49
responses and in 5 of the 6 accepted fixed Planner replies. Qwen: 0 of 107.

### E8 — The one clean reply is not executable (C5)

Fixed Planner, `ambiguous_cbago_like`, repeat 0 — the single first response in 15
that passed the native schema with no repair. It proposed an MCTS run configured
with a beam parameter:

```json
"recommended_action_families": ["complexa_mcts"],
"config_delta_suggestions": {"complexa_mcts": {"beam_width": 8, "n_simulations": 5,
                                               "nsamples": 4, "nsteps": 100}}
```

Registry check: `{"card": 0, "family": "complexa_mcts", "valid": false,
"reasons": ["unknown_param:beam_width"]}`. Schema-clean, unrunnable — which is
why schema acceptance cannot be the reward signal.

### E9 — Correct arithmetic against the wrong constraint (C6)

Live v7r008 checked the sampling-budget cap explicitly and got it right:

```
So default budget = 400 * 4 * 4 * 4 = 25600, which is under cap 65536. …
1. beam_width=6, n_branch=6 … (budget: 400*4*6*6=57600 <=65536)
2. beam_width=8, n_branch=4 … (budget: 400*4*8*4=51200 <=65536)
3. beam_width=8, n_branch=6 … (budget: 400*4*8*6=76800 >65536) -> too high, skip.
```

It never checked wall-clock. The same `beam_width=8, n_branch=4` configuration,
proposed at rounds 5–6, was priced by the controller at ~1.0h against ~0.9h
remaining and hidden from selection:

```json
"feasibility": {"cost_ok": false, "compiler_ok": true,
  "reasons": ["insufficient_wall_for_complexa_beam_heavy_config(~1.0h[x2.0]>0.9h_remaining)"]}
```

Thirty-one of the 77 model-derived candidates died on this reason. The model
demonstrably can do the arithmetic it was given a cap for; the deadline rule was
the one it did not apply.

### E10 — A redesign that claims a parent it never names (C5, C7)

Live v7r014, second card. The claim and the rationale both assert a concrete
parent; the fields supply only aggregates, and `omit_AAs` receives the entire
list of legal values where one string is expected:

```json
{ "claim": "use proteinmpnn_redesign with structure_refilter parent to directly redesign around blocker",
  "evidence_refs": ["EvidenceSummary", "recent_ticks_history"],
  "config_delta_suggestions": {"proteinmpnn_redesign": {"backbone_noise": 0.1,
    "model_name": "v_48_002", "num_seq_per_target": 8,
    "omit_AAs": ["X","C","CP","CW","FWY","G","P","GP","DE","KR"], "sampling_temp": 0.1}},
  "reasoning_trace": {"inference": "ProteinMPNN redesign with a concrete parent (via structure_refilter) can directly address the blocker", …} }
```

The builder stripped the illegal value, then failed to compile the action:
`no_concrete_parent_result_id(aggregate:recent_ticks_history,EvidenceSummary):proteinmpnn_redesign`.
Its cost check passed — this candidate was affordable and still unbuildable. Twelve
candidates failed this way.

### E11 — Supervisor: the mixture without the decision object (C1, C2)

Fixed Supervisor, `productive_cd45_like`, all three repeats, 73.5–73.7s each. The
first parseable object is the bare mixture; the complete decision — one ranked
candidate with `rank_in_mode`, `resource_class`, a stop condition and a reasoning
trace — appears further down the same reply and was never read:

```json
{ "exploit": 0.7, "rescue": 0.2, "explore": 0.1 }
```
```
We must also include reasoning_trace for cand_hyp_p1_001. Let's craft the JSON. …
{ "mode_mixture": {"exploit": 0.7, …}, "candidate_decisions": [ {"candidate_id": "cand_hyp_p1_001", "mode": "exploit", "rank_in_mode": 1, …} ], "abstain": false }
```

Recorded reason: `missing_top:mode_mixture`, three times out of three.

### E12 — Supervisor: no confidence field at all (C8)

All 12 fixed Supervisor replies omit `confidence` entirely, so T-REX supplied its
default 0.5 — below the production gate of 0.55. E6 shows the shape: a
`mode_mixture`, `candidate_decisions`, `abstain` and `fail_reason`, and no
confidence anywhere. Nine of the 12 also returned zero ranked decisions. Qwen
stated a confidence in 9 of 12 (0.7 ×6, 0.65 ×3).

### E13 — Timeouts with nothing to grade (C3)

Seven live ticks — v7r011, v7r012, v7r013, v7r015, v7r016, v7r019, v7r020 — made
two HTTP attempts each, both abandoned at 90.0s, logical latency 180.6s. The
cancellation-aware recorder propagated the disconnect upstream, so these 14
requests have their exact input preserved and **no response and no token usage**:
nothing exists to score. Each cost the controller three minutes of a sixty-minute
budget and produced one fallback tick.

### E14 — The failures are fixture-deterministic, not sampling noise

Each fixture ran three times; the recorded requests confirm Planner temperature
0.2 (57 calls) and Supervisor 0.0 (12 calls), all with `max_tokens` 3,072.
Outcomes by fixture (final native acceptance):

| Fixture | Planner ×3 | Supervisor ×3 |
|---|---|---|
| `productive_cd45_like` | timeout, `missing_top:cards`, `missing_top:cards` | `missing_top:mode_mixture` ×3 |
| `rescue_rich_betv1_like` | `missing_top:cards`, `missing_top:cards`, timeout | accepted but abstaining ×3 |
| `stalled_sc2rbd_like` | `missing_top:cards`, then accepted-after-repair ×2 | `missing_top:mode_mixture` ×3 |
| `ambiguous_cbago_like` | accepted ×3 (1 clean, 2 repaired) | — |
| `stalled_redundant_pdl1` | timeout, timeout, accepted-after-repair | accepted ×3 |

Every Supervisor fixture gave the identical outcome three times. Two Planner
fixtures failed in all three repeats. The behavior is a property of the evidence
state, not of the sample — which is what makes these cheap, reusable eval items.

## Confounds and non-gaps

**Serving latency is entangled with C3.** Qwen ran compiled FP8 dense on one
GPU; Snowball ran eager BF16 MoE on two, with prefix caching disabled. The fixed
checks used the original recorder, which keeps generating after a client
timeout and can add retry contention (I014). Latency here is an operational
measurement, not a model-speed benchmark. What survives the confound: format
failures also occurred in responses that finished on time (I015), and no serving
improvement converts a terminal-agent object into Planner cards.

**Context length was not a measured failure.** Retokenizing all 69 fixed and
live requests, including the 20 cancellations, found a maximum of 15,679 input
tokens and zero requests exceeding the 32,768-token window with the 3,072-token
output reserve. The gap is latent rather than observed: projecting *Qwen's*
larger campaign histories through Snowball's tokenizer, 39 of 107 requests would
not fit (max 32,142). A model that got past C1–C7 and kept a campaign productive
would face that limit; this run never did.

**Not Snowball's failures:** the all-family cold-start stall (I009, reproduced in
the Qwen arm and preserved as `qwen-coldstart-stall`), the `libXrender`
install failure (I008), the serving dependency and PATH problems (I005, I006),
the token-count API error (I012), the replay import path (I023), GPU-hour
accounting semantics (I022), the wall-check overrun (I026), and the four
unresolved chain identities present identically in both arms (I010).

**What this cannot show.** One asynchronous trajectory per model, one target, one
seed, a one-hour budget against the paper's 144 worker H100-hours. No
deterministic-controller baseline, no few-shot or constrained-decoding baseline.
The molecular endpoint difference is consistent with these gaps but is not
attributed to them by measurement.

## Priorities implied

1. **C1, C2, C3 first.** Thirteen of 21 live rounds produced no card at all, and
   0 of 49 responses were clean JSON. Until the envelope, the role and the token
   budget are reliable, nothing downstream is measurable. Constrained JSON
   decoding and few-shot prompting are the cheap baselines to try before
   fine-tuning ([training.md](training.md)).
2. **C4, C5, C7 next.** These are executable checks against the evidence
   whitelist, the capability registry and the candidate builder — CPU-only,
   already implemented in `scripts/audit_fixed.py` and
   `tests/test_offline_audit.py`.
3. **C6 with the real rule supplied.** Give the model the cost-scaling formula
   and drain margin; the prompt's rough runtime hint does not state the
   feasibility rule it is being judged against.
4. **C8 alongside a gating-policy review, not as a confidence target.** The
   teacher's 0/5 on the live gate says the threshold policy deserves its own
   ablation.
5. **C9 as a separate repair objective**, measured on the validator's feedback.

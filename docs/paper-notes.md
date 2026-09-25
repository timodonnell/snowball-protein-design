# Reading T-REX

Source: Jeon et al., [bioRxiv v2, 24 September 2026](https://www.biorxiv.org/content/10.64898/2026.09.22.753604v2).
Paper and supplement were retrieved from the publisher on the CoreWeave host.

The LLM proposes hypotheses and prioritizes validated jobs over a compact summary
of completed and pending work. It does not generate binder sequences directly.
The deterministic controller supplies much of the task competence: it constructs
jobs, rejects invalid parameters/parents, schedules work, normalizes scores,
tracks ancestry, and falls back when LLM output is unusable. Consequently a
completed campaign does not by itself show that its LLM made useful decisions.

The common AF2 qualification gate is pLDDT ≥90, normalized iPAE ≤7/31, and binder
scRMSD <1.5Å. BindCraft/BoltzGen native scores cannot substitute for this gate.
Qualified structures are clustered on the binder chain; primary structural
uniqueness uses Foldseek TM-score 0.6. The reported campaign budget is 144 worker
H100-hours (three workers for 48h), excluding the dedicated LLM GPU. Our short,
two-worker runs will have a substantially smaller search and feedback horizon.

The paper reports seven invalid Supervisor responses among 3,125 calls; six had
invalid evidence references and one an invalid resource class (Methods 4.5,
Supplement D.3.1/Table S15). Selection fallback has a separate denominator:
321/1,719 updates, mostly because no hypotheses/candidates were available.
Comparisons must distinguish raw JSON validity, schema repair, semantic reference
validity, abstention, skipped calls, deterministic candidates and actual starts.

The authors explicitly state that their PUCT/epsilon-greedy comparisons evaluate
complete allocation policies, not the isolated contribution of LLM reasoning
(Supplement B.5). Candidate proposal and deterministic supplementation differ
between policies. Controller development also used some primary-panel targets;
"target-independent" refers to shared runtime rules, not a disjoint development
test split (B.4). Both points matter when designing a future Snowball RL benchmark.

The supplement separately charges the full dedicated LLM-server reservation in
a compute sensitivity (D.1.3). Summed call latency is not the added campaign delay:
workers can run concurrently, while slow decisions can also leave them idle.
Our reports therefore retain worker-wall, native recorded job charges, and LLM
serving/allocation costs as different quantities.

Serving settings (Supplement C.5.1): Qwen3.6-27B-FP8, 65,536-token context,
GPU memory fraction 0.90, thinking disabled; maximum output 3,072 tokens;
90-second call timeout, one OpenAI SDK retry; Planner temperature 0.2,
Supervisor temperature 0.0. Zero temperature is not proof of determinism.

For Snowball training, the natural initial tasks are evidence-grounded structured
decisions with deterministic validation, then counterfactual ranking and
budgeted allocation. A teacher response passing schema validation is not an
oracle for molecular reward. Split evaluation by evidence lineage/target rather
than neighboring ticks to avoid leaking near-identical campaign histories.

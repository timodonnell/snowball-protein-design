# Examples worth turning into tasks

These are reviewed observations from the pilot, not gold policy labels. Use the
native archive and exact wire trace to inspect the complete context.

## A measured rescue with a factual error in the teacher rationale

At Qwen tick `v7r008`, the Planner proposed ProteinMPNN redesign of beam parent
`92988d30a69a7c45`, correctly identifying scRMSD as its only failing canonical
axis. The parent scored pLDDT 94.141, iPAE 0.15753 and scRMSD 2.438Å. After
redesign and AF2 refiltering, descendant `b365f28499eb5425` scored 95.000,
0.14757 and 1.222Å, respectively, passing all gates.

The same accepted Planner response incorrectly attributed another near-miss,
`2ed2cfe55eaf8220`, to FK steering. Its archive family is `complexa_best_of_n`.
Native schema/reference checks accepted the response because the ID exists;
they do not verify every factual statement in the rationale.

Training uses: extract parent metrics and source family from evidence; identify
the failing axis; propose a feasible rescue; distinguish an unscored redesigned
sequence from a qualified AF2 result. A separate factual-consistency reward
should catch the family error. Do not blindly copy the entire teacher response.

Source: [exact Planner call](../artifacts/qwen/wire/1790364601677941745_356279b3-aba6-4f8f-a9b6-c278b2153d13.json),
[lineage index](../artifacts/qwen/decision-index.jsonl),
[scores](../artifacts/qwen/designs/designs.csv).

## Sequence diversity is not structural novelty

At Qwen tick `v7r043`, the Planner claimed that increasing ProteinMPNN sampling
temperature on a fixed successful backbone would escape its structural cluster.
The claim is a hypothesis, not an established consequence: changing sequence on
a fixed backbone directly buys sequence variation; structural novelty must be
measured after folding. The candidate did not start, so this example has no
measured molecular outcome attributable to that suggestion.

Training uses: distinguish sequence and structure diversity, verify the deadline
with the actual feasibility checker, and avoid assigning success credit to a
proposed job that never ran. Novelty reward must use qualified binder-chain
clustering against the existing archive.

## Snowball output-contract failures

The first fixed productive-state call emitted prose until the 3,072-token limit;
both HTTP attempts completed after the controller's timeout. The next rescue
case stopped within 90 seconds but returned a terminal-agent object containing
`commands` and `task_complete` instead of the required `cards`.

These support cheap executable rewards for selecting the correct output schema,
finishing within the token budget, and obeying evidence-reference restrictions.
Timeout labels must remain separate from format labels: faster serving alone
would not repair the wrong object. The public fixed fixtures remain evaluation
data, so generate fresh evidence states for SFT or RL training.

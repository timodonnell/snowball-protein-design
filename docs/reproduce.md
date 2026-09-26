# Reproduce

The experiment uses unmodified T-REX at the submodule revision, native model
weights, and separate pinned serving environments. It needs four H100 80GB GPUs
and roughly 600GiB persistent storage. Model weights and environments are not
stored in Git. All paths in the launch scripts are inside the research pod.

## Provision and install

```bash
git submodule update --init
export KUBECONFIG=/path/to/coreweave-kubeconfig
kubectl apply -f configs/coreweave-pod.yaml
kubectl wait --for=condition=Ready pod/snowball-trex-pilot --timeout=180s
kubectl exec snowball-trex-pilot -- mkdir -p /work/pilot-scripts /work/configs /work/logs
for f in scripts/*.sh scripts/*.py; do
  kubectl cp "$f" "snowball-trex-pilot:/work/pilot-scripts/$(basename "$f")"
done
for f in configs/qwen.yaml configs/snowball.yaml configs/snowball-serving.lock.txt; do
  kubectl cp "$f" "snowball-trex-pilot:/work/configs/$(basename "$f")"
done
kubectl cp artifacts/snowball-manifest.json snowball-trex-pilot:/work/configs/snowball-manifest.json
kubectl exec snowball-trex-pilot -- bash /work/pilot-scripts/bootstrap_remote.sh
kubectl exec snowball-trex-pilot -- bash /work/pilot-scripts/setup_snowball.sh
```

Bootstrap downloads the publisher's asset bundle and verifies its checksums,
builds the pinned backends and writes T-REX runtime configuration. Snowball uses
the Marin vLLM fork because its custom architecture is not supported by the
paper's serving environment. The lock deliberately omits the incompatible,
unused TorchAudio dependency; see [I005](issues.md). This is a text-only server.

## Execute

Run sequentially on the same allocation; each command waits for its arm to finish.
Use a persistent terminal or redirect with `nohup` when disconnecting.

```bash
kubectl exec snowball-trex-pilot -- bash /work/pilot-scripts/run_arm.sh qwen
kubectl exec snowball-trex-pilot -- bash /work/pilot-scripts/run_arm.sh snowball
```

The GLM-5.3 arm uses a shared off-pod endpoint, so it starts no local server and
needs two extra variables. Resolve the endpoint immediately before launching:
the Iris relay registers a cluster-local address that moves when it restarts.
Keep the token off the shared PVC.

```bash
kubectl exec snowball-trex-pilot -- bash -c \
  "umask 077; printf %s \"$GLM_API_TOKEN\" > /dev/shm/glm-token"
kubectl exec snowball-trex-pilot -- env \
  GLM_BASE_URL="http://$GLM_RELAY_HOST:8010" GLM_TOKEN_FILE=/dev/shm/glm-token \
  bash /work/pilot-scripts/run_arm.sh glm
```

This arm holds no inference GPU; it keeps the four-GPU pod shape only so that
`worker_gpus` stays identical across arms. See [protocol](experiment.md) for the
reasoning-budget control the recorder adds and why it is required.

The reasoning-enabled ablation uses the same command with `glm-think` and one
more variable. It is not part of the matched comparison:

```bash
kubectl exec snowball-trex-pilot -- env \
  GLM_BASE_URL="http://$GLM_RELAY_HOST:8010" GLM_TOKEN_FILE=/dev/shm/glm-token \
  GLM_REASONING_EFFORT=high \
  bash /work/pilot-scripts/run_arm.sh glm-think
```

`GLM_REASONING_EFFORT` must be chosen from measurement, not from the name: on
this deployment `medium` and `max` exhaust the Planner budget even at 8,192
tokens while `high` does not. `scripts/glm_reasoning_probe.py` reproduces that
check against archived prompts, and [protocol](experiment.md) records the
result.

Each arm performs 15 Planner and 12 Supervisor fixed-evidence checks, followed by
a one-hour PD-L1 campaign with two molecular workers. The original controller
can drain outstanding work beyond that hour. The scripts reject an existing
campaign archive; preserve and move an earlier attempt before rerunning.
`TREX_SKIP_FIXED_VALIDATION=1` skips already-completed checks during infrastructure
recovery. The original all-family YAMLs reproduce the short-budget cold-start
issue; the primary YAMLs use five deadline-compatible families.

The localhost proxy records exact request/response bytes plus timestamps and
HTTP metadata, including token truncation that the upstream client hides. The
proxy never changes the prompt or response. Its JSON-syntax summary is separate
from T-REX's semantic validation.

Fixed checks use the recorder on port 12000, retaining late responses after a
timeout. Campaigns use port 12002 with disconnect propagation. Cancellation has
no upstream HTTP status/response and is reported as `client_disconnected`, not a
fabricated HTTP error. This distinction was added after observing Snowball's
first timeouts; see [I014](issues.md).

## Collect before releasing GPUs

After Snowball and its server finish, run the bounded teacher replay:

```bash
kubectl exec snowball-trex-pilot -- bash /work/pilot-scripts/run_replay.sh
```

Its GLM counterpart, `run_replay_glm.sh`, replays the same five states through
GLM-5.3 with the same variables as the arm above, writing
`/work/results/replay-glm-on-snowball/`. Together the two replays put all three
models on identical live evidence.

Each replays five live Snowball Planner prompts at call-index quartiles,
preserving the original messages and sampling settings. Every prompt is
reconstructed exactly from its archived evidence before inference. The resulting
schema/configuration labels and candidate-construction previews are prospective
SFT review material; no counterfactual molecular jobs are executed. These
diagnostics are separate from the timed campaigns and public fixed fixtures.

Run the collector **after campaign drain**, while external structure paths still
exist. Use the controller environment from the upstream working directory:

```bash
cd /work/T-REX
for arm in qwen snowball glm glm-think; do
  .venv-serving/bin/python /work/pilot-scripts/collect_designs.py \
    "/work/results/$arm/campaign" "/work/results/$arm/designs" \
    --foldseek external/Proteina-Complexa/.venv/bin/foldseek \
    --mmseqs external/Proteina-Complexa/.venv/bin/mmseqs
done
```

After every export exists, run `scripts/compare_designs.py /work/results
/work/results/design-comparison.json --arms qwen snowball glm glm-think --foldseek
external/Proteina-Complexa/.venv/bin/foldseek` from the same pinned controller
environment. `--arms` also sets which unordered pairs are reported. This jointly
clusters the qualified binder chains across arms, using collected structure
copies rather than original backend paths.

Copy `/work/results/` and relevant `/work/logs/` files locally with `kubectl cp`.
Use `.txt` for retained logs because the repository ignores `.log` files. Keep
the original archive paths as provenance; `designs/structure-sources.json` maps
them to portable copies and hashes. The collected CSV/FASTA/PDBs can be inspected
without the original filesystem. Re-running upstream archive analysis that
opens absolute structure paths requires the original PVC or explicit path
relocation; the portable CSV is not silently substituted for the archive.

Then delete `pod/snowball-trex-pilot`. The PVC remains for recovery; deleting the
pod releases the GPUs. Do not delete the PVC before confirming artifact copies.

## Re-audit model responses locally

Install the lightweight upstream controller/development dependencies in a venv,
then run from this repository root:

```bash
uv venv --python 3.12.13
uv pip install -e './vendor/T-REX[dev]'
export PYTHONPATH=.:vendor/T-REX
export PYTHONHASHSEED=0
.venv/bin/pytest -q tests
for arm in qwen snowball glm glm-think; do
  .venv/bin/python scripts/audit_fixed.py "artifacts/$arm/wire" \
    "artifacts/$arm/fixed-audit" --arm "$arm"
  .venv/bin/python scripts/summarize_wire.py "artifacts/$arm/wire" \
    "artifacts/$arm/wire-summary.json"
  .venv/bin/python scripts/summarize_wire.py "artifacts/$arm/wire" \
    "artifacts/$arm/wire-campaign-summary.json" \
    --after-time-file "artifacts/$arm/campaign-start-time.txt"
  .venv/bin/python scripts/summarize_wire.py "artifacts/$arm/wire" \
    "artifacts/$arm/wire-fixed-summary.json" \
    --before-time-file "artifacts/$arm/campaign-start-time.txt"
  .venv/bin/python scripts/summarize_campaign.py "artifacts/$arm/campaign" \
    "artifacts/$arm/controller.txt" "artifacts/$arm/accounting.json"
  .venv/bin/python scripts/index_decisions.py "artifacts/$arm" \
    "artifacts/$arm/decision-index.jsonl"
done
for replay in replay-qwen-on-snowball replay-glm-on-snowball \
              replay-glm-think-on-snowball; do
  .venv/bin/python scripts/summarize_replay.py "artifacts/$replay" \
    "artifacts/$replay/summary.json"
done
```

`export_transcripts.py` renders any wire archive as readable per-call
transcripts, splitting fixed checks from the campaign. It adds nothing to the
archive and is always reproducible from it:

```bash
for arm in qwen snowball glm glm-think; do
  .venv/bin/python scripts/export_transcripts.py "artifacts/$arm/wire" \
    "artifacts/$arm/transcripts" \
    --split-time-file "artifacts/$arm/campaign-start-time.txt"
done
```

The audit requires nine exact prompt hashes, three primary calls per prompt,
and the pinned source. It fails loudly on a prompt mismatch or incomplete run.
The public fixed cases and their recorded responses are evaluation data, not a
held-out test if included in SFT.

Static figures use Matplotlib 3.10.8:

```bash
uv pip install matplotlib==3.10.8
.venv/bin/python scripts/make_figures.py artifacts artifacts/figures \
  --arms qwen snowball glm
.venv/bin/python scripts/make_figures.py artifacts artifacts/figures-glm-ablation \
  --arms glm glm-think
.venv/bin/python scripts/verify_artifacts.py artifacts artifacts/integrity-check.json \
  --arms qwen snowball glm glm-think
```

The matched figures cover the three comparable arms; the ablation figures cover
the two GLM runs. `scripts/make_transcript_report.py artifacts report --arms
qwen snowball glm glm-think --replays ...` regenerates the browsable HTML report
of every recorded call.

The integrity check verifies every collected structure hash, the qualified PDB
copies and FASTA IDs, complete archive counts, finished HTTP records, and the
nine shared fixed-prompt hashes. It runs without the original worker paths.

`configs/local-analysis.freeze.txt` records the observed CPU analysis environment;
the remote molecular/serving locks are separate. `collector-validation-snapshot.json`
is a pre-final frozen-snapshot check of the exporter, not a campaign endpoint.

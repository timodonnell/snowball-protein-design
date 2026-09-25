"""Guard the scientific distinctions in the proposed fact-level reward."""
import json

from scripts.evidence_tasks import answer, grade


def record(**updates):
    row = dict(result_id="r", backend_family="complexa_beam", exit_status="ok",
        output_chain_identity="verified", canonical_metrics={"pLDDT":90,"iPAE":7/31,"binder_scRMSD":1.49})
    row.update(updates)
    return row


def test_exact_rmsd_cutoff_is_a_failure():
    row = record(canonical_metrics={"pLDDT":90,"iPAE":7/31,"binder_scRMSD":1.5})
    result = answer([row])
    assert result["qualified_record_count"] == 0
    assert result["results"][0]["failed_axes"] == ["binder_scRMSD"]


def test_native_scores_and_ambiguous_chains_do_not_qualify():
    rows = [record(backend_family="proteinmpnn_redesign", canonical_metrics={},
                   diagnostic_metrics={"native_pLDDT":99,"native_iPAE":0.01,"native_binder_scRMSD":0.1}),
            record(output_chain_identity="unresolved")]
    result = answer(rows)
    assert result["qualified_record_count"] == 0
    assert [r["status"] for r in result["results"]] == ["unmeasured", "identity_unresolved"]


def test_reward_rejects_wrong_family_prose_and_duplicate_keys():
    expected = answer([record()])
    raw = json.dumps(expected)
    assert grade(raw, expected)["reward"] == 1
    assert grade(raw.replace("complexa_beam", "complexa_fk_steering"), expected)["reward"] == 0
    assert grade("Here is the answer: "+raw, expected)["reward"] == 0
    duplicate = raw[:-1]+',"qualified_record_count":1}'
    assert grade(duplicate, expected)["reward"] == 0

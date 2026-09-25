"""Negative controls for labels that may later become RL rewards."""
import json
from pathlib import Path

from scripts.audit_fixed import contexts, score


ROOT = Path(__file__).resolve().parents[1]
ROWS = [json.loads(line) for line in
        (ROOT / "artifacts/qwen/fixed-audit/responses.jsonl").read_text().splitlines()]
CONTEXTS = contexts()


def fixture(role):
    row = next(r for r in ROWS if r["role"] == role and r["labels"]["schema_valid"])
    return json.loads(row["response"]), CONTEXTS[row["prompt_sha256"]]


def test_recorded_positive_control():
    obj, context = fixture("planner")
    labels, _ = score(json.dumps(obj), context)
    assert labels["schema_valid"] and labels["all_configs_valid"]


def test_hallucinated_reference_is_not_first_response_success():
    obj, context = fixture("planner")
    obj["cards"][0]["evidence_refs"] = ["invented_experimental_evidence_999"]
    labels, _ = score(json.dumps(obj), context)
    assert not labels["schema_valid"]
    assert "unknown_evidence_refs" in labels["schema_reason"]


def test_individually_legal_parameters_can_exceed_joint_budget():
    obj, context = fixture("planner")
    obj["cards"][0]["config_delta_suggestions"] = {
        "complexa_beam": dict(nsteps=500, nsamples=8, beam_width=16, n_branch=8)}
    labels, _ = score(json.dumps(obj), context)
    assert labels["schema_valid"]  # native Planner schema doesn't check this
    assert not labels["all_configs_valid"]
    assert any("eval_budget_exceeded" in reason
               for check in labels["config_checks"] for reason in check["reasons"])


def test_unknown_candidate_cannot_receive_ranking_credit():
    obj, context = fixture("supervisor")
    obj["candidate_decisions"][0]["candidate_id"] = "candidate_that_was_not_offered"
    labels, _ = score(json.dumps(obj), context)
    assert not labels["schema_valid"]
    assert "unknown_candidate_id" in labels["schema_reason"]


def test_truncated_json_is_not_schema_success():
    _, context = fixture("planner")
    labels, _ = score('{"cards": [', context)
    assert not labels["json_only"]
    assert not labels["schema_valid"]

"""Reproduce the observed upstream stall and configuration-only workaround."""
from dataclasses import replace
from pathlib import Path

from trex.archive import Archive
from trex.candidate_builder import BuilderConfig, build_candidates
from trex.schemas import EvidenceSummary, HypothesisCard


def test_infeasible_warmstart_suppresses_an_otherwise_feasible_llm_job():
    root = Path(__file__).resolve().parents[1]
    archive = Archive(root / "artifacts/qwen-coldstart-stall/campaign")
    evidence = list(archive.iter_records(EvidenceSummary))[-1]
    template = list(archive.iter_records(HypothesisCard))[-1]
    hypothesis = replace(template, status="active",
        recommended_action_families=["complexa_best_of_n"],
        config_delta_suggestions={"complexa_best_of_n": {"nsamples": 4, "replicas": 4}})
    assert evidence.state_label == "low_evidence" and not evidence.recipes
    common = dict(warmstart_completed_families={"complexa_beam"})
    original = build_candidates([hypothesis], evidence, **common)
    assert {c.method_family for c in original} == {"bindcraft", "boltzgen"}
    assert all(not c.feasibility.cost_ok for c in original)
    narrowed = build_candidates([hypothesis], evidence,
        cfg=BuilderConfig(unavailable_backends_override={"bindcraft", "boltzgen", "complexa_mcts"}),
        **common)
    assert any(c.method_family == "complexa_best_of_n" and c.feasibility.cost_ok for c in narrowed)

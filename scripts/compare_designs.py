#!/usr/bin/env python3
"""Compare final portable exports and jointly cluster qualified binder chains.

Run in the pinned controller environment with Foldseek available. All structure
paths are resolved from collected copies, so original backend paths are unused.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, replace
import csv
import hashlib
import json
from pathlib import Path
import statistics

from trex.foldseek_clusterer import cluster_archive_pdbs
from trex.schemas import ResultRecord


def read_csv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--foldseek", required=True)
    args = parser.parse_args()
    combined, arms, sequences, warm = [], {}, {}, {}
    for arm in ["qwen", "snowball"]:
        root = args.results / arm / "designs"
        rows = read_csv(root / "designs.csv")
        manifest = read_csv(root / "strict-export/manifest.csv")
        export_status = json.loads((root / "summary.json").read_text())["upstream_export"]
        if manifest:
            assert export_status["foldseek_su_status"] == "ok", "Unverified per-arm structural endpoint"
            assert export_status["sequence_dedup_status"] == "ok", "Unverified per-arm sequence endpoint"
        strict_ids = {row["result_id"] for row in manifest}
        strict = [row for row in rows if row["result_id"] in strict_ids]
        portable = {row["result_id"]: root / row["structure"] for row in rows if row["structure"]}
        warm[arm] = {}
        for line in (root / "prepared-results.jsonl").read_text().splitlines():
            record = ResultRecord(**json.loads(line))
            if any(parent.startswith("warmstart_") for parent in record.parent_ids):
                name = Path(record.artifacts["pdb_path"]).name
                assert name not in warm[arm], "Warm-start output names are not unique"
                warm[arm][name] = dict(result_id=record.result_id,
                    canonical_metrics={k:record.metrics.get(k) for k in ["pLDDT", "iPAE", "binder_scRMSD"]},
                    structure_sha256=hashlib.sha256(portable[record.result_id].read_bytes()).hexdigest())
            if record.result_id in strict_ids:
                assert record.bins.get("output_chain_identity") == "verified"
                source = portable[record.result_id].resolve()
                assert source.is_file(), source
                combined.append(replace(record, result_id=arm+"_"+record.result_id,
                    artifacts={**record.artifacts, "pdb_path": str(source)}))
        sequences[arm] = {row["binder_sequence"] for row in strict if row["binder_sequence"]}
        scored = [row for row in rows if row["canonical_complete"] == "True"
                  and row["exit_status"] == "ok" and row["output_chain_identity"] == "verified"]
        arms[arm] = dict(n_records=len(rows), n_verified_canonical=len(scored),
            n_qualified=len(strict), n_exact_qualified_sequences=len(sequences[arm]),
            qualified_families=dict(Counter(row["family"] for row in strict)),
            n_qualified_sequence_bins=len({r["sequence_bin"] for r in manifest if r["sequence_bin"]}),
            qualified_medians={axis: statistics.median(float(row[axis]) for row in strict) if strict else None
                               for axis in ["pLDDT", "iPAE", "binder_scRMSD", "binder_length"]},
            qualified_length_range=[min(int(r["binder_length"]) for r in strict),
                                    max(int(r["binder_length"]) for r in strict)] if strict else None)
    clustering = cluster_archive_pdbs(combined, target_id="32_PDL1_ALPHA_REPACK",
                                     foldseek_binary=args.foldseek, min_tm_score=0.6)
    memberships = defaultdict(list)
    for result_id, cluster in clustering.cluster_by_result_id.items():
        memberships[cluster].append(result_id)
    bins_by_arm = {arm: {cluster for cluster, members in memberships.items()
                        if any(member.startswith(arm+"_") for member in members)} for arm in arms}
    valid = clustering.status == "ok"
    common_warm = warm["qwen"].keys() & warm["snowball"].keys()
    warm_comparison = dict(n_qwen=len(warm["qwen"]), n_snowball=len(warm["snowball"]),
        shared_output_names=len(common_warm),
        exact_canonical_metric_matches=sum(warm["qwen"][name]["canonical_metrics"] == warm["snowball"][name]["canonical_metrics"] for name in common_warm),
        exact_structure_file_matches=sum(warm["qwen"][name]["structure_sha256"] == warm["snowball"][name]["structure_sha256"] for name in common_warm),
        records=warm)
    report = dict(arms=arms, shared_warmstart=warm_comparison, joint_qualified_clustering=asdict(clustering),
        joint_clusters_with_both_arms=len(bins_by_arm["qwen"] & bins_by_arm["snowball"]) if valid else None,
        joint_clusters_with_only_qwen=len(bins_by_arm["qwen"]-bins_by_arm["snowball"]) if valid else None,
        joint_clusters_with_only_snowball=len(bins_by_arm["snowball"]-bins_by_arm["qwen"]) if valid else None,
        joint_cluster_members=dict(memberships),
        exact_qualified_sequence_overlap=len(sequences["qwen"] & sequences["snowball"]),
        notes=["Only qualified, verified binder chains enter joint clustering.",
               "Joint clustering can change representatives/membership versus clustering each arm independently.",
               "These are single asynchronous campaigns; differences are descriptive, not causal or statistically powered."])
    args.output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in ["joint_qualified_clustering", "joint_cluster_members", "shared_warmstart"]}, indent=2))


if __name__ == "__main__":
    main()

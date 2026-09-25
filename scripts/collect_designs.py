#!/usr/bin/env python3
"""Collect final, full-archive designs on the worker before deleting its pod.

Run in the pinned T-REX controller environment. Includes late drain results,
unqualified structures and failures; never rewrites the original archive.
"""
import argparse
from collections import Counter
import csv
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics

from trex.archive import Archive
from trex.export_best_n import export_best_n
from trex.foldseek_clusterer import cluster_archive_pdbs
from trex.output_identity import chain_sequences, prepare_archive_results
from trex.schemas import ResultRecord
from trex.sequence_clusterer import cluster_archive_sequences
from trex.success_criteria import STRICT_SUCCESS, is_strict_success, is_near_miss

AA = dict(zip(
    "ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL".split(),
    "ARNDCQEGHILKMFPSTWYV"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--target", default="32_PDL1_ALPHA_REPACK")
    parser.add_argument("--foldseek", required=True)
    parser.add_argument("--mmseqs", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Output already exists; preserve it before recollecting.")
    args.output.mkdir(parents=True)
    archive = Archive(args.archive)
    results = prepare_archive_results(archive.iter_records(ResultRecord), archive.root)
    results = [r for r in results if r.target_id == args.target]
    verified_ids = {r.result_id for r in results if r.exit_status == "ok"
                    and r.bins.get("output_chain_identity") == "verified"}
    all_struct = cluster_archive_pdbs(results, target_id=args.target,
        foldseek_binary=args.foldseek, only_result_ids=verified_ids, min_tm_score=0.6)
    all_seq = cluster_archive_sequences(results, target_id=args.target,
        mmseqs_binary=args.mmseqs, only_result_ids=verified_ids,
        min_seq_id=0.9, coverage=0.8)
    rows, prepared, sources, fasta = [], [], [], []
    structure_dir = args.output / "all-structures"
    structure_dir.mkdir()
    for record in results:
        prepared.append(asdict(record))
        source = record.artifacts.get("pdb_path")
        copied, sequence, sequence_error = "", "", ""
        if source and Path(source).is_file():
            dst = structure_dir / (record.result_id + Path(source).suffix)
            shutil.copy2(source, dst)
            copied = str(dst.relative_to(args.output))
            sources.append(dict(result_id=record.result_id, source=source,
                file=copied, sha256=hashlib.sha256(dst.read_bytes()).hexdigest()))
            if record.bins.get("output_chain_identity") != "unresolved":
                try:
                    chain = record.artifacts["binder_chain"]
                    sequence = "".join(AA.get(aa, "X") for aa in chain_sequences(dst)[chain])
                    fasta.append(f">{record.result_id} family={record.backend_family} chain={chain}\n{sequence}\n")
                except (ValueError, KeyError, OSError) as exc:
                    sequence_error = f"{type(exc).__name__}: {exc}"
        row = dict(result_id=record.result_id, family=record.backend_family,
            exit_status=record.exit_status, parent_ids=";".join(record.parent_ids),
            tick_id=record.tick_id, gpu_h=record.gpu_h,
            canonical_complete=all(record.metrics.get(k) is not None for k in STRICT_SUCCESS),
            strict=record.exit_status == "ok" and is_strict_success(record.metrics),
            near_miss=record.exit_status == "ok" and is_near_miss(record.metrics),
            output_chain_identity=record.bins.get("output_chain_identity"),
            binder_chain=record.artifacts.get("binder_chain"), structure=copied,
            all_structure_bin=all_struct.cluster_by_result_id.get(record.result_id),
            all_sequence_bin=all_seq.cluster_by_result_id.get(record.result_id),
            binder_sequence=sequence, binder_length=len(sequence) if sequence else None,
            sequence_error=sequence_error)
        row.update(record.metrics)
        rows.append(row)
    def stats(subset):
        output = {}
        for axis in STRICT_SUCCESS:
            values = [r[axis] for r in subset if r["exit_status"] == "ok"
                      and isinstance(r.get(axis), (float, int)) and math.isfinite(r[axis])]
            output[axis] = dict(n=len(values), median=statistics.median(values) if values else None,
                               min=min(values) if values else None, max=max(values) if values else None)
        return output
    diagnostics = export_best_n(archive, target_id=args.target, n=max(1, len(results)),
        out_dir=args.output / "strict-export", foldseek_binary=args.foldseek,
        mmseqs_binary=args.mmseqs)
    summary = dict(n_records=len(rows), exit_status=dict(Counter(r["exit_status"] for r in rows)),
        family=dict(Counter(r["family"] for r in rows)),
        n_canonical_complete_ok=sum(r["canonical_complete"] and r["exit_status"] == "ok" for r in rows),
        n_strict=sum(r["strict"] for r in rows), n_near_miss=sum(r["near_miss"] for r in rows),
        n_structures=len(sources), n_sequences=len(fasta),
        n_distinct_exact_sequences=len({r["binder_sequence"] for r in rows if r["binder_sequence"]}),
        metric_stats=stats(rows),
        verified_metric_stats=stats([r for r in rows if r["result_id"] in verified_ids]),
        all_verified_structure_clustering=asdict(all_struct),
        all_verified_sequence_clustering=asdict(all_seq), upstream_export=diagnostics,
        archive_read_skips=archive.read_skip_counts(),
        note="Full archive after drain. Native diagnostic scores do not count as canonical AF2 success. SU requires successful Foldseek clustering; missing measurements remain missing.")
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.output / "prepared-results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in prepared))
    (args.output / "structure-sources.json").write_text(json.dumps(sources, indent=2) + "\n")
    (args.output / "binders.fasta").write_text("".join(fasta))
    # Raw final/lookahead scores and timings are small but live outside the
    # campaign archive. Preserve these separately from parsed final designs.
    dispatch_path = args.archive / "dispatch_records.jsonl"
    if dispatch_path.exists():
        for line in dispatch_path.read_text().splitlines():
            dispatch = json.loads(line)
            directory = Path(dispatch.get("output_dir") or "/nonexistent")
            if not directory.is_dir():
                continue
            destination = args.output / "backend-tables" / dispatch["dispatch_id"]
            for source in directory.iterdir():
                if source.is_file() and source.suffix in {".csv", ".json", ".yaml"}:
                    destination.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination / source.name)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (args.output / "designs.csv").open("w") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or ["result_id"])
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

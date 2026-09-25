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
from trex.output_identity import chain_sequences, prepare_archive_results
from trex.schemas import ResultRecord
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
            binder_sequence=sequence, binder_length=len(sequence) if sequence else None,
            sequence_error=sequence_error)
        row.update(record.metrics)
        rows.append(row)
    metric_stats = {}
    for axis in STRICT_SUCCESS:
        values = [r[axis] for r in rows if r["exit_status"] == "ok"
                  and isinstance(r.get(axis), (float, int)) and math.isfinite(r[axis])]
        metric_stats[axis] = dict(n=len(values), median=statistics.median(values) if values else None,
                                 min=min(values) if values else None, max=max(values) if values else None)
    diagnostics = export_best_n(archive, target_id=args.target, n=max(1, len(results)),
        out_dir=args.output / "strict-export", foldseek_binary=args.foldseek,
        mmseqs_binary=args.mmseqs)
    summary = dict(n_records=len(rows), exit_status=dict(Counter(r["exit_status"] for r in rows)),
        family=dict(Counter(r["family"] for r in rows)),
        n_canonical_complete_ok=sum(r["canonical_complete"] and r["exit_status"] == "ok" for r in rows),
        n_strict=sum(r["strict"] for r in rows), n_near_miss=sum(r["near_miss"] for r in rows),
        n_structures=len(sources), n_sequences=len(fasta),
        n_distinct_exact_sequences=len({r["binder_sequence"] for r in rows if r["binder_sequence"]}),
        metric_stats=metric_stats, upstream_export=diagnostics,
        archive_read_skips=archive.read_skip_counts(),
        note="Full archive after drain. Native diagnostic scores do not count as canonical AF2 success. SU requires successful Foldseek clustering; missing measurements remain missing.")
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.output / "prepared-results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in prepared))
    (args.output / "structure-sources.json").write_text(json.dumps(sources, indent=2) + "\n")
    (args.output / "binders.fasta").write_text("".join(fasta))
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with (args.output / "designs.csv").open("w") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or ["result_id"])
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

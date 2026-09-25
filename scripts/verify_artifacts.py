#!/usr/bin/env python3
"""Verify the collected endpoint files without the original worker filesystem."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def read_csv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root):
    results = {}
    prompts = []
    target_sha = sha256(root / "target/5o45_repacked.pdb")
    for arm in ["qwen", "snowball"]:
        directory = root / arm
        designs = directory / "designs"
        native = json.loads((directory / "archive-validation.json").read_text())
        assert native["ok"] and not native["errors"] and not native["skipped_records"], arm
        assert (directory / "campaign-end-time.txt").is_file(), arm
        provenance = json.loads((directory / "campaign/run_provenance.json").read_text())
        assert provenance["target"]["pdb_sha256"] == target_sha, arm
        rows = read_csv(designs / "designs.csv")
        prepared = read_jsonl(designs / "prepared-results.jsonl")
        original = read_jsonl(directory / "campaign/result_records.jsonl")
        ids = {row["result_id"] for row in rows}
        assert len(ids) == len(rows) == len(prepared) == len(original), arm
        assert ids == {row["result_id"] for row in prepared} == {row["result_id"] for row in original}, arm
        sources = json.loads((designs / "structure-sources.json").read_text())
        hashes = {}
        for source in sources:
            actual = sha256(designs / source["file"])
            assert actual == source["sha256"], source
            hashes[source["result_id"]] = actual
        assert len(sources) == len(hashes) == sum(bool(row["structure"]) for row in rows), arm
        strict = read_csv(designs / "strict-export/manifest.csv")
        for row in strict:
            assert row["output_chain_identity"] == "verified", row
            path = designs / "strict-export/pdbs" / Path(row["dst_pdb"]).name
            assert sha256(path) == hashes[row["result_id"]], path
        qualified = {row["result_id"] for row in strict}
        assert qualified == {row["result_id"] for row in rows
                             if row["strict"] == "True" and row["output_chain_identity"] == "verified"}, arm
        fasta_ids = {line[1:].split()[0] for line in (designs / "strict-binders.fasta").read_text().splitlines()
                     if line.startswith(">")}
        assert fasta_ids == qualified, arm
        summary = json.loads((designs / "summary.json").read_text())
        assert len(strict) == summary["upstream_export"]["n_exported"], arm
        assert not qualified or summary["upstream_export"]["foldseek_su_status"] == "ok", arm
        wires = [json.loads(path.read_text()) for path in (directory / "wire").glob("*.json")]
        assert all(wire["state"] != "pending" for wire in wires), arm
        audit = json.loads((directory / "fixed-audit/summary.json").read_text())
        prompts.append(audit["matched_prompt_sha256"])
        results[arm] = dict(native_archive_valid=True, result_ids_verified=len(ids),
            native_archive_warnings=native["warnings"],
            structure_hashes_verified=len(hashes), qualified_pdb_hashes_verified=len(strict),
            qualified_fasta_ids_verified=len(fasta_ids), pending_wire_requests=0)
    assert prompts[0] == prompts[1] and len(prompts[0]) == 9, "Fixed prompts differ"
    return dict(ok=True, arms=results, target_pdb_sha256=target_sha, matched_fixed_prompt_hashes=9,
                note="Local copy integrity and endpoint consistency; not a biological validation.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = verify(args.artifacts)
    args.output.write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result, indent=2))

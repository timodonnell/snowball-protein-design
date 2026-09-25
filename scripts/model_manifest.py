#!/usr/bin/env python3
"""Hash a downloaded checkpoint into T-REX's portable manifest format."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_path", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    paths = sorted(p for p in args.model_path.rglob("*") if p.is_file()
                   and ".cache" not in p.parts and p.name != ".trex_model_manifest.json"
                   and p.resolve() != args.output.resolve())
    if not paths:
        raise ValueError("Empty model directory")

    def entry(path):
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while block := stream.read(8 * 1024 * 1024):
                digest.update(block)
        return dict(path=str(path.relative_to(args.model_path)),
                    size=path.stat().st_size, sha256=digest.hexdigest())

    with ThreadPoolExecutor(max_workers=8) as pool:
        files = list(pool.map(entry, paths))
    digest = hashlib.sha256()
    for row in files:
        digest.update(f"{row['path']}\0{row['size']}\0{row['sha256']}\n".encode())
    manifest = dict(schema_version="v7.3.3_model_manifest_v1", model_name=args.model_path.name,
                    upstream_revision=args.revision, content_sha256=digest.hexdigest(),
                    n_files=len(files), total_bytes=sum(r["size"] for r in files), files=files)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(manifest["content_sha256"], flush=True)


if __name__ == "__main__":
    main()

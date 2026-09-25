#!/usr/bin/env python3
"""Create paired campaign inputs in the installed remote T-REX environment."""
from pathlib import Path
import argparse
import yaml
from trex.campaign.template import campaign_template


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("/work"))
    p.add_argument("--hours", type=float, default=1.0)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()
    args.root.joinpath("configs").mkdir(parents=True, exist_ok=True)
    for arm in ("qwen", "snowball"):
        config = campaign_template(name=f"pdl1-{arm}-s{args.seed}", target="pdl1",
            archive_root=str(args.root / "results" / arm / "campaign"),
            asset_root=str(args.root / "T-REX-assets"), target_constraint=None,
            target_pdb=None, max_wall_hours=args.hours, total_gpus=3)
        config["run"].update(worker_gpus=["2", "3"], seed=args.seed)
        config["backends"]["repo_root"] = str(args.root / "T-REX")
        if arm == "snowball":
            config["llm"]["model"] = "vllm/open-athena/Snowball-67B-A2B-5.7T-Mixed-RLVR-Step38"
            # Upstream names are historical; these fields accept generic manifests.
            config["backends"].update(qwen_model_path=str(args.root / "models/snowball"),
                qwen_model_manifest=str(args.root / "configs/snowball-manifest.json"))
        path = args.root / "configs" / f"{arm}.yaml"
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite {path}")
        path.write_text(yaml.safe_dump(config, sort_keys=False))
        print(path)


if __name__ == "__main__":
    main()

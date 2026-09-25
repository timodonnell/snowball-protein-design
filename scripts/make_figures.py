#!/usr/bin/env python3
"""Create static comparison figures from collected measurements only."""
import argparse
import csv
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def number(row, key):
    try:
        value = float(row[key])
        return value if math.isfinite(value) else None
    except (KeyError, TypeError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none", "figure.dpi": 140})
    arms = [("qwen", "Qwen3.6-27B-FP8"), ("snowball", "Snowball-67B-A2B")]
    data = {}
    for arm, _ in arms:
        with (args.artifacts / arm / "designs/designs.csv").open() as stream:
            data[arm] = list(csv.DictReader(stream))
    usable = {arm: [r for r in rows if r["exit_status"] == "ok"
                   and r["output_chain_identity"] == "verified"
                   and all(number(r, k) is not None for k in ["pLDDT", "iPAE", "binder_scRMSD"])]
              for arm, rows in data.items()}
    ymax = max([2.0] + [number(r, "binder_scRMSD") * 1.08 for rows in usable.values() for r in rows])
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharex=True, sharey=True, layout="constrained")
    artist = None
    for ax, (arm, title) in zip(axes, arms):
        rows = usable[arm]
        artist = ax.scatter([number(r, "iPAE") for r in rows],
                           [number(r, "binder_scRMSD") for r in rows],
                           c=[number(r, "pLDDT") for r in rows], vmin=50, vmax=100,
                           cmap="viridis", s=25, alpha=0.8, edgecolors="none")
        ax.axvline(7/31, color="#555555", linestyle="--", linewidth=1)
        ax.axhline(1.5, color="#555555", linestyle="--", linewidth=1)
        ax.set(xlim=(0, 1), ylim=(0, ymax), xlabel="Normalized AF2 interface PAE",
               title=f"{title}\n{len(rows)} verified, scored records")
        strict = [r for r in rows if r["strict"] == "True"]
        ax.scatter([number(r, "iPAE") for r in strict], [number(r, "binder_scRMSD") for r in strict],
                   marker="*", facecolors="none", edgecolors="#d04a2b", s=135, linewidths=1.2,
                   label=f"Strict passes: {len(strict)}")
        ax.legend(loc="upper right", frameon=False)
    axes[0].set_ylabel("Binder self-consistency RMSD (Å)")
    fig.colorbar(artist, ax=axes, label="AF2 pLDDT (strict gate ≥90)", shrink=0.8)
    fig.suptitle("PD-L1: one-hour campaigns, two H100 molecular workers each", fontsize=13)
    for extension in ["png", "svg", "pdf"]:
        fig.savefig(args.output / f"design-comparison.{extension}")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.2), layout="constrained")
    values = []
    for arm, title in arms:
        audit = json.loads((args.artifacts / arm / "fixed-audit/summary.json").read_text())
        for role in ["planner", "supervisor"]:
            native = json.loads((args.artifacts / arm / f"{role}-validation.json").read_text())["summary"]
            raw = audit["roles"][role]
            values.append((f"{title}\n{role.capitalize()}", raw["schema_valid_before_repair"],
                           native["valid_calls"], raw["n"]))
    for i, (label, raw, final, n) in enumerate(values):
        ax.bar(i-0.18, raw/n*100, 0.34, color="#315b8a", label="First response" if i == 0 else None)
        ax.bar(i+0.18, final/n*100, 0.34, color="#54a688", label="After T-REX recovery" if i == 0 else None)
        for x, count in [(i-0.18, raw), (i+0.18, final)]:
            ax.text(x, count/n*100+2, f"{count}/{n}", ha="center", fontsize=10)
    ax.set_xticks(range(len(values)), [v[0] for v in values])
    ax.set(ylim=(0, 116), ylabel="Valid structured responses (%)",
           title="Same nine fixed-evidence prompts, three calls each")
    ax.legend(frameon=False, loc="lower right")
    for extension in ["png", "svg", "pdf"]:
        fig.savefig(args.output / f"interface-comparison.{extension}")
    plt.close(fig)


if __name__ == "__main__":
    main()

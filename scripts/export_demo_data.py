#!/usr/bin/env python3
"""
Export DGraFormer inference artifacts to JSON for the demo website.

Usage:
    python scripts/export_demo_data.py \
        --checkpoint ./checkpoints/dgraformer_best.pth \
        --data-root ./data \
        --output ./public/data

This script runs forward passes on pre-selected samples and exports:
  - Per-sample JSON files (history, prediction, error, windows, attention, metrics)
  - Updates public/data/index.json with available sample listings

Requirements:
    torch, numpy, pyyaml, tqdm

Expected directory layout of --data-root:
    data/
    ├── ETTh1.csv
    ├── Weather.csv
    ├── ...

The script loads the DGraFormer model from checkpoint, runs inference on
each sample, and writes the full SampleData schema to JSON files under
public/data/samples/.
"""

import argparse
import json
import os
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Export DGraFormer demo data")
    parser.add_argument("--checkpoint", required=True, help="Path to model checkpoint (.pth)")
    parser.add_argument("--data-root", required=True, help="Path to dataset CSV files")
    parser.add_argument("--output", default="./public/data", help="Output directory for JSON files")
    parser.add_argument("--horizons", nargs="+", type=int, default=[96, 192, 336, 720])
    parser.add_argument("--samples-per-dataset", type=int, default=5)
    return parser.parse_args()


def main():
    args = parse_args()

    # TODO: Import your DGraFormer model and dataset modules here
    # from dgraformer.model import DGraFormer
    # from dgraformer.data import load_dataset

    output_dir = Path(args.output)
    samples_dir = output_dir / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)

    datasets = [
        "ETTh1", "ETTh2", "ETTm1", "ETTm2",
        "Weather", "Electricity", "Solar", "Traffic",
        "Flight", "AirQualityUCI",
    ]

    index = {"datasets": [], "horizons": args.horizons}

    for ds_name in datasets:
        ds_entry = {"dataset": ds_name, "samples": []}
        for sample_id in range(args.samples_per_sample):
            for horizon in args.horizons:
                # TODO: Run inference and collect artifacts
                # sample = run_inference(model, data, sample_id, horizon)
                # Write: samples_dir / f"{ds_name}_{sample_id:03d}_h{horizon}.json"
                pass

        index["datasets"].append(ds_entry)

    # Write index
    with open(output_dir / "index.json", "w") as f:
        json.dump(index, f, indent=2)

    print(f"Export complete. Data written to {output_dir}")


if __name__ == "__main__":
    main()

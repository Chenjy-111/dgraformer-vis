from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import torch

from dgraudit.adapters import DGraFormerAdapter


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def serializable(window: dict) -> dict:
    return {key: (value.tolist() if isinstance(value, torch.Tensor) else value)
            for key, value in window.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-root", default="artifacts/runs")
    parser.add_argument("--current-epoch", type=int, default=71)
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    source = Path(config["source_root"])

    fingerprints = [sha256(config_path), str(args.current_epoch)]
    for name, ds in config["datasets"].items():
        fingerprints.extend([
            name,
            sha256(source / "checkpoints" / ds["setting"] / "checkpoint.pth"),
            sha256(source / ds["root_path"] / ds["data_path"]),
        ])
    fingerprints.append(sha256(source / "layers" / "DGraFormer_framework.py"))
    run_id = hashlib.sha256("|".join(fingerprints).encode()).hexdigest()
    run_dir = Path(args.output_root).resolve() / run_id
    graph_dir = run_dir / "graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    summaries = []

    for name, ds in config["datasets"].items():
        adapter = DGraFormerAdapter(str(source), name, config["common"], ds, config["random_seed"])
        checkpoint = source / "checkpoints" / ds["setting"] / "checkpoint.pth"
        adapter.load_checkpoint(str(checkpoint))
        extracted = adapter.extract_graph_stages({"current_epoch": args.current_epoch})
        reference = torch.from_numpy(np.load(source / "demo_results" / f"{name}_96" / "adjs.npy"))
        normalized = torch.stack([window["normalized"] for window in extracted["windows"]])
        torch.testing.assert_close(normalized, reference, atol=1e-6, rtol=1e-5)

        validations = []
        for window in extracted["windows"]:
            n = window["normalized"].shape[0]
            validations.append({
                "window": window["window"],
                "topk_mask_count": int(window["topk_mask"].sum()),
                "expected_topk_slots": window["topk_slots"],
                "diagonal_removed_max_abs": float(torch.diag(window["diagonal_removed"]).abs().max()),
                "self_loop_diagonal_min": float(torch.diag(window["self_loop_graph"]).min()),
                "self_loop_diagonal_max": float(torch.diag(window["self_loop_graph"]).max()),
                "normalized_row_sum_max_error": float((window["normalized"].sum(1) - 1).abs().max()),
                "finite": bool(torch.isfinite(window["normalized"]).all()),
                "matrix_shape": [n, n],
            })
        max_abs = float((normalized - reference).abs().max())
        dataset_record = {
            "dataset": name,
            "status": "complete",
            "checkpoint_path": str(checkpoint),
            "checkpoint_sha256": sha256(checkpoint),
            "data_path": str(source / ds["root_path"] / ds["data_path"]),
            "data_sha256": sha256(source / ds["root_path"] / ds["data_path"]),
            "current_epoch": args.current_epoch,
            "reference_adjs_path": str(source / "demo_results" / f"{name}_96" / "adjs.npy"),
            "reference_adjs_sha256": sha256(source / "demo_results" / f"{name}_96" / "adjs.npy"),
            "final_matrix_max_absolute_difference": max_abs,
            "validations": validations,
            "stages": [serializable(window) for window in extracted["windows"]],
        }
        (graph_dir / f"{name}.json").write_text(json.dumps(dataset_record, indent=2), encoding="utf-8")
        summaries.append({key: dataset_record[key] for key in (
            "dataset", "status", "checkpoint_sha256", "data_sha256",
            "reference_adjs_sha256", "current_epoch", "final_matrix_max_absolute_difference"
        )})

    summary = {
        "run_id": run_id,
        "status": "complete",
        "config_path": str(config_path),
        "config_sha256": sha256(config_path),
        "graph_code_path": str(source / "layers" / "DGraFormer_framework.py"),
        "graph_code_sha256": sha256(source / "layers" / "DGraFormer_framework.py"),
        "datasets": summaries,
    }
    (run_dir / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_dir / "command.txt").write_text(
        f"python -m dgraudit.cli.extract_graphs --config {args.config} --output-root {args.output_root} --current-epoch {args.current_epoch}\n",
        encoding="utf-8",
    )
    (run_dir / "environment.json").write_text(json.dumps({
        "python": platform.python_version(), "torch": torch.__version__,
        "cuda": torch.version.cuda, "cuda_available": torch.cuda.is_available(),
    }, indent=2), encoding="utf-8")
    (run_dir / "stdout.log").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (run_dir / "stderr.log").write_text("", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

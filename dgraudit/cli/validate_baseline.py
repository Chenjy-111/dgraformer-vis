from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from pathlib import Path

import numpy as np
import torch

from dgraudit.adapters import DGraFormerAdapter


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", default="artifacts/baseline")
    parser.add_argument("--reference-run")
    parser.add_argument("--current-epoch", type=int)
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    source = Path(config["source_root"])
    output = Path(args.output).resolve()
    reference_run = Path(args.reference_run).resolve() if args.reference_run else None
    output.mkdir(parents=True, exist_ok=True)
    results = []

    for name, ds in config["datasets"].items():
        adapter = DGraFormerAdapter(str(source), name, config["common"], ds, config["random_seed"])
        checkpoint = source / "checkpoints" / ds["setting"] / "checkpoint.pth"
        adapter.load_checkpoint(str(checkpoint))
        if reference_run:
            reference = np.load(reference_run / "predictions" / f"{name}_pred.npy", mmap_mode="r")
        else:
            reference = np.load(source / "demo_results" / f"{name}_96" / "pred.npy", mmap_mode="r")
        for web_id, sample_index in enumerate(ds["web_sample_indices"]):
            batch = adapter.load_sample("test", sample_index)
            actual = adapter.predict({**batch, **({"current_epoch": args.current_epoch} if args.current_epoch is not None else {})})
            reference_index = web_id if args.reference_run else sample_index
            expected = torch.from_numpy(np.asarray(reference[reference_index])).unsqueeze(0)
            difference = torch.abs(actual - expected)
            passed = True
            error = None
            try:
                torch.testing.assert_close(actual, expected, atol=config["baseline_atol"], rtol=config["baseline_rtol"])
            except AssertionError as exc:
                passed = False
                error = str(exc)
            results.append({
                "dataset": name, "web_sample_id": web_id, "test_sample_index": sample_index,
                "max_absolute_difference": float(difference.max()),
                "mean_absolute_difference": float(difference.mean()),
                "atol": config["baseline_atol"], "rtol": config["baseline_rtol"],
                "passed": passed, "error": error,
            })

    overall = all(item["passed"] for item in results)
    manifest = {
        "status": "complete" if overall else "failed",
        "comparison": "canonical same-schedule prediction versus independent DGraFormerAdapter checkpoint forward" if args.reference_run else "supplied original saved prediction versus DGraFormerAdapter checkpoint forward",
        "reference_run": str(reference_run) if reference_run else None,
        "current_epoch": args.current_epoch,
        "config_path": str(config_path), "config_sha256": sha256(config_path),
        "python": platform.python_version(), "torch": torch.__version__,
        "cuda": torch.version.cuda, "cuda_available": torch.cuda.is_available(),
        "sample_count": len(results), "passed_count": sum(r["passed"] for r in results),
        "max_absolute_difference": max(r["max_absolute_difference"] for r in results),
        "mean_absolute_difference": sum(r["mean_absolute_difference"] for r in results) / len(results),
        "results": results,
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    manifest["run_id"] = hashlib.sha256(canonical).hexdigest()
    (output / "baseline_validation.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output / "command.txt").write_text(
        f"python -m dgraudit.cli.validate_baseline --config {args.config} --output {args.output}\n", encoding="utf-8"
    )
    print(json.dumps({k: manifest[k] for k in ("status", "sample_count", "passed_count", "max_absolute_difference", "mean_absolute_difference", "run_id")}, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())

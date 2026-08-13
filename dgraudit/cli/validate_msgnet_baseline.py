from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import torch

from dgraudit.adapters import MSGNetAdapter


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/msgnet_etth1.json")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output-root", default="artifacts/runs")
    args = parser.parse_args()
    config_path, checkpoint = Path(args.config).resolve(), Path(args.checkpoint).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    adapter = MSGNetAdapter(config["source_root"], config)
    adapter.load_checkpoint(str(checkpoint))

    fingerprint = "|".join((sha256(config_path), sha256(checkpoint), config["dataset"]["sha256"],
                            "msgnet_baseline_v1"))
    run_id = hashlib.sha256(fingerprint.encode()).hexdigest()
    run_dir = Path(args.output_root).resolve() / run_id
    pred_dir = run_dir / "predictions"
    pred_dir.mkdir(parents=True, exist_ok=True)
    records = []
    all_pred, all_true, all_x = [], [], []
    for sample_index in config["dataset"]["web_sample_indices"]:
        sample = adapter.load_sample("test", sample_index)
        first, second = adapter.predict(sample), adapter.predict(sample)
        torch.testing.assert_close(first, second, atol=config["baseline_atol"], rtol=config["baseline_rtol"])
        truth = torch.as_tensor(sample["y"][-config["dataset"]["pred_len"]:], dtype=torch.float32).unsqueeze(0)
        error = first - truth
        records.append({
            "sample_index": sample_index,
            "mse": float(torch.mean(error.square())), "mae": float(torch.mean(error.abs())),
            "repeat_max_absolute_difference": float(torch.max(torch.abs(first - second))),
        })
        all_pred.append(first.numpy()[0]); all_true.append(truth.numpy()[0]); all_x.append(np.asarray(sample["x"]))
    np.save(pred_dir / "baseline.npy", np.stack(all_pred))
    np.save(pred_dir / "ground_truth.npy", np.stack(all_true))
    np.save(pred_dir / "history.npy", np.stack(all_x))
    report = {
        "run_id": run_id, "status": "complete", "model": "MSGNet", "dataset": "ETTh1",
        "config_path": str(config_path), "config_sha256": sha256(config_path),
        "checkpoint_path": str(checkpoint), "checkpoint_sha256": sha256(checkpoint),
        "data_path": config["dataset"]["path"], "data_sha256": config["dataset"]["sha256"],
        "environment": {"python": platform.python_version(), "torch": torch.__version__,
                        "cuda": torch.version.cuda, "device": str(adapter.device)},
        "sample_count": len(records), "samples": records,
    }
    (run_dir / "manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (run_dir / "environment.json").write_text(json.dumps(report["environment"], indent=2), encoding="utf-8")
    (run_dir / "command.txt").write_text(
        f"python -m dgraudit.cli.validate_msgnet_baseline --config {args.config} --checkpoint {args.checkpoint}\n",
        encoding="utf-8")
    (run_dir / "stdout.log").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (run_dir / "stderr.log").write_text("", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

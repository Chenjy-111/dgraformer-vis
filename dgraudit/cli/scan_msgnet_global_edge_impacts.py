from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from dgraudit.adapters import MSGNetAdapter


NAMES = ["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL", "OT"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bh(values: list[float]) -> list[float]:
    order = np.argsort(values)
    adjusted = np.empty(len(values), dtype=float)
    running = 1.0
    for reverse_rank, index in enumerate(order[::-1], start=1):
        rank = len(values) - reverse_rank + 1
        running = min(running, values[index] * len(values) / rank)
        adjusted[index] = running
    return adjusted.tolist()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/msgnet_etth1.json")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output-root", default="artifacts/runs")
    parser.add_argument("--bootstrap", type=int, default=10000)
    args = parser.parse_args()
    config_path, checkpoint = Path(args.config).resolve(), Path(args.checkpoint).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    adapter = MSGNetAdapter(config["source_root"], config)
    adapter.load_checkpoint(str(checkpoint))
    run_id = hashlib.sha256("|".join((sha256(config_path), sha256(checkpoint), str(args.bootstrap), "msgnet_global_edge_v1")).encode()).hexdigest()
    run_dir = Path(args.output_root).resolve() / run_id
    prediction_dir = run_dir / "predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for sample_index in config["dataset"]["web_sample_indices"]:
        batch = adapter.load_sample("test", sample_index)
        baseline = adapter.predict(batch)
        truth = torch.as_tensor(batch["y"][-config["dataset"]["pred_len"]:], dtype=torch.float32).unsqueeze(0)
        contexts = adapter.extract_graph_stages(batch)["contexts"]
        weights = np.stack([context["adaptive"].numpy() for context in contexts])
        sample_records = []
        for source in range(len(NAMES)):
            for target in range(len(NAMES)):
                if source == target:
                    continue
                result = adapter.predict_with_graph_override(batch, {
                    "type": "structural_edge_removal", "scope": "global", "layer": 0,
                    "source": source, "target": target,
                })
                changed = result["prediction"]
                delta = changed - baseline
                prediction_file = f"sample_{sample_index}_edge_{source}_{target}.npy"
                np.save(prediction_dir / prediction_file, changed.squeeze(0).numpy())
                sample_records.append({
                    "sample_index": sample_index, "source": source, "target": target,
                    "source_name": NAMES[source], "target_name": NAMES[target],
                    "scope": "all_scales", "affected_scales": list(range(len(contexts))),
                    "scale_weights": weights[:, source, target].tolist(),
                    "prediction_delta_abs": float(delta.abs().mean()),
                    "prediction_delta_max": float(delta.abs().max()),
                    "error_delta_mae": float((changed - truth).abs().mean() - (baseline - truth).abs().mean()),
                    "error_delta_mse": float((changed - truth).square().mean() - (baseline - truth).square().mean()),
                    "intervention_prediction_file": f"predictions/{prediction_file}",
                })
        impacts = np.asarray([record["prediction_delta_abs"] for record in sample_records])
        for index, record in enumerate(sample_records):
            controls = np.delete(impacts, index)
            focal = impacts[index]
            empirical_p = float((1 + np.sum(controls >= focal)) / (len(controls) + 1))
            rng = np.random.default_rng(20260813 + len(records))
            boot = rng.choice(controls, size=(args.bootstrap, len(controls)), replace=True).mean(1)
            difference = focal - boot
            std = float(controls.std(ddof=1))
            record["controls"] = {"count": len(controls), "sampling": "all other directed non-self global edge removals in the same sample"}
            record["statistics"] = {
                "control_mean_prediction_delta_abs": float(controls.mean()),
                "control_median_prediction_delta_abs": float(np.median(controls)),
                "control_percentile": float(100 * np.mean(controls <= focal)),
                "empirical_p": empirical_p, "bh_adjusted_p": None,
                "standardized_effect_size": None if std == 0 else float((focal - controls.mean()) / std),
                "candidate_minus_control_mean_bootstrap_ci_95": np.quantile(difference, [.025, .975]).tolist(),
                "bootstrap_repetitions": args.bootstrap,
            }
            records.append(record)
        print(f"completed sample {sample_index}: {len(sample_records)} global edge interventions", flush=True)
    adjusted = bh([record["statistics"]["empirical_p"] for record in records])
    for record, value in zip(records, adjusted):
        record["statistics"]["bh_adjusted_p"] = value
    report = {
        "run_id": run_id, "status": "complete", "model": "MSGNet", "dataset": "ETTh1",
        "intervention": "same directed edge removed simultaneously from every MSGNet scale before MixHop propagation",
        "control_protocol": "within-sample all-other-directed-edge matched controls",
        "multiple_comparison_correction": "Benjamini-Hochberg over all global cases",
        "config_sha256": sha256(config_path), "checkpoint_sha256": sha256(checkpoint),
        "case_count": len(records), "bh_supported_count": sum(v < .05 for v in adjusted),
        "cases": records, "notice": "Checkpoint-internal intervention evidence; not real-world causality.",
    }
    report_path = run_dir / "global_evidence_catalog.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps({k: report[k] for k in (
        "run_id", "status", "model", "dataset", "intervention", "control_protocol",
        "multiple_comparison_correction", "config_sha256", "checkpoint_sha256", "case_count", "bh_supported_count", "notice"
    )}, indent=2), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "case_count": len(records), "bh_supported_count": report["bh_supported_count"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

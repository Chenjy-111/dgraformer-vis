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


def metrics(prediction: torch.Tensor, truth: torch.Tensor) -> dict:
    error = prediction - truth
    return {"mae": float(error.abs().mean()), "mse": float((error ** 2).mean())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--registry", default="configs/phase1_registry.json")
    parser.add_argument("--output-root", default="artifacts/runs")
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    registry_path = Path(args.registry).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    dataset = config["dataset"]
    ds = registry["datasets"][dataset]
    source = Path(registry["source_root"])
    candidate_path = Path(args.output_root).resolve() / config["candidate_run_id"] / "patterns" / f"{dataset}.json"
    candidates = json.loads(candidate_path.read_text(encoding="utf-8"))["candidate_patterns"]
    edge_candidate = sorted(candidates["high_weight_low_frequency_edges"],
                            key=lambda x: (-x["mean_retained_score"], x["source"], x["target"]))[0]
    repeated_candidate = candidates["repeated_local_edge_sets"][0]
    edge_window = int(edge_candidate["windows"][0])
    common_window = int(repeated_candidate["windows"][0])
    edge = [int(edge_candidate["source"]), int(edge_candidate["target"])]
    edge_set = [[int(x["source"]), int(x["target"])] for x in repeated_candidate["edges"]]
    variable = int(candidates["sender_roles"][0]["variable"])

    fingerprints = [sha256(config_path), sha256(registry_path), sha256(candidate_path)]
    run_id = hashlib.sha256("|".join(fingerprints).encode()).hexdigest()
    run_dir = Path(args.output_root).resolve() / run_id
    evidence_dir = run_dir / "evidence"
    prediction_dir = run_dir / "predictions"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    prediction_dir.mkdir(parents=True, exist_ok=True)

    adapter = DGraFormerAdapter(str(source), dataset, registry["common"], ds, registry["random_seed"])
    checkpoint = source / "checkpoints" / ds["setting"] / "checkpoint.pth"
    adapter.load_checkpoint(str(checkpoint))
    batch = adapter.load_sample("test", config["test_sample_index"])
    batch = {**batch, "current_epoch": config["current_epoch"]}
    baseline = adapter.predict(batch)
    identity = adapter.predict_with_graph_override(
        batch, {"type": "identity", "window": 0, "current_epoch": config["current_epoch"]}
    )["prediction"]
    identity_max_absolute_difference = float((identity - baseline).abs().max())
    torch.testing.assert_close(identity, baseline, atol=0, rtol=0)
    truth = torch.as_tensor(batch["y"][-registry["common"]["pred_len"]:, :], dtype=torch.float32).unsqueeze(0)
    baseline_metrics = metrics(baseline, truth)

    protocol_map = {
        "structural_edge_removal": {"type": "structural_edge_removal", "window": edge_window, "source": edge[0], "target": edge[1]},
        "normalized_channel_mask": {"type": "normalized_channel_mask", "window": edge_window, "source": edge[0], "target": edge[1]},
        "variable_outgoing_removal": {"type": "variable_outgoing_removal", "window": edge_window, "variable": variable},
        "variable_incoming_removal": {"type": "variable_incoming_removal", "window": edge_window, "variable": variable},
        "variable_associated_removal": {"type": "variable_associated_removal", "window": edge_window, "variable": variable},
        "input_variable_mask": {"type": "input_variable_mask", "variable": variable},
        "edge_set_removal": {"type": "edge_set_removal", "window": common_window, "edges": edge_set},
        "edge_set_keep_only": {"type": "edge_set_keep_only", "window": common_window, "edges": edge_set},
    }
    results = []
    np.save(prediction_dir / "baseline.npy", baseline.numpy())
    np.save(prediction_dir / "ground_truth.npy", truth.numpy())
    for name in config["protocols"]:
        protocol = {**protocol_map[name], "current_epoch": config["current_epoch"]}
        outcome = adapter.predict_with_graph_override(batch, protocol)
        prediction = outcome["prediction"]
        intervention_metrics = metrics(prediction, truth)
        delta = prediction - baseline
        record = {
            "status": "complete", "claim_level": "interventional_model_evidence",
            "dataset": dataset, "web_sample_id": config["web_sample_id"],
            "test_sample_index": config["test_sample_index"], "current_epoch": config["current_epoch"],
            "protocol": outcome["protocol"], "renormalized": outcome["renormalized"],
            "baseline_metrics": baseline_metrics, "intervention_metrics": intervention_metrics,
            "prediction_delta_mean_abs": float(delta.abs().mean()),
            "prediction_delta_max_abs": float(delta.abs().max()),
            "error_delta_mae": intervention_metrics["mae"] - baseline_metrics["mae"],
            "error_delta_mse": intervention_metrics["mse"] - baseline_metrics["mse"],
            "per_horizon_step_mean_abs_delta": delta.abs().mean(dim=2).squeeze(0).tolist(),
            "per_variable_mean_abs_delta": delta.abs().mean(dim=1).squeeze(0).tolist(),
            "graph_before": outcome["graph_before"].tolist() if outcome["graph_before"] is not None else None,
            "graph_after": outcome["graph_after"].tolist() if outcome["graph_after"] is not None else None,
            "candidate_source": str(candidate_path),
            "limitations": ["Model-internal intervention evidence only; not a real-world causal claim."],
        }
        np.save(prediction_dir / f"{name}.npy", prediction.numpy())
        (evidence_dir / f"{name}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        results.append({key: record[key] for key in ("status", "protocol", "renormalized",
                        "baseline_metrics", "intervention_metrics", "prediction_delta_mean_abs",
                        "prediction_delta_max_abs", "error_delta_mae", "error_delta_mse")})

    manifest = {
        "run_id": run_id, "status": "complete", "dataset": dataset,
        "checkpoint_path": str(checkpoint), "checkpoint_sha256": sha256(checkpoint),
        "data_path": str(source / ds["root_path"] / ds["data_path"]),
        "data_sha256": sha256(source / ds["root_path"] / ds["data_path"]),
        "config_path": str(config_path), "config_sha256": sha256(config_path),
        "candidate_run_id": config["candidate_run_id"],
        "identity_override_max_absolute_difference": identity_max_absolute_difference,
        "identity_override_exact": True,
        "results": results,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "command.txt").write_text(
        f"python -m dgraudit.cli.intervene --config {args.config} --registry {args.registry} --output-root {args.output_root}\n", encoding="utf-8")
    (run_dir / "environment.json").write_text(json.dumps({"python": platform.python_version(), "torch": torch.__version__, "cuda": torch.version.cuda}, indent=2), encoding="utf-8")
    (run_dir / "stdout.log").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (run_dir / "stderr.log").write_text("", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

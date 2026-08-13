from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch

from dgraudit.adapters import DGraFormerAdapter


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def impact_metrics(baseline: torch.Tensor, intervention: torch.Tensor, truth: torch.Tensor) -> dict[str, float]:
    baseline_error = baseline - truth
    intervention_error = intervention - truth
    delta = intervention - baseline
    prediction_delta_abs = float(delta.abs().mean())
    prediction_scale = float(baseline.abs().mean())
    return {
        "baseline_mae": float(baseline_error.abs().mean()),
        "baseline_mse": float((baseline_error ** 2).mean()),
        "intervention_mae": float(intervention_error.abs().mean()),
        "intervention_mse": float((intervention_error ** 2).mean()),
        "prediction_delta_abs": prediction_delta_abs,
        "prediction_delta_rel": prediction_delta_abs / (prediction_scale + 1e-12),
        "error_delta_mae": float(intervention_error.abs().mean() - baseline_error.abs().mean()),
        "error_delta_mse": float((intervention_error ** 2).mean() - (baseline_error ** 2).mean()),
    }


def selected_edges(patterns: dict, selections: Iterable[dict], supplement: dict | None = None) -> list[dict]:
    merged: dict[tuple[int, int], dict] = {}
    for selection in selections:
        category = selection["category"]
        items = patterns["candidate_patterns"][category]
        if category == "high_frequency_low_weight_edges":
            ordered = sorted(items, key=lambda item: (-item["frequency"], -item["mean_retained_score"],
                                                       item["source"], item["target"]))
        else:
            ordered = sorted(items, key=lambda item: (-item["mean_retained_score"],
                                                       item["source"], item["target"]))
        for item in ordered[:int(selection["limit"])]:
            key = (int(item["source"]), int(item["target"]))
            record = merged.setdefault(key, {
                "source": key[0], "target": key[1],
                "source_name": item["source_name"], "target_name": item["target_name"],
                "windows": set(), "categories": set(),
            })
            record["windows"].update(int(window) for window in item["windows"])
            record["categories"].add(category)
    if supplement and len(merged) < int(supplement["minimum_unique_edges"]):
        eligible = [item for item in patterns["all_retained_edge_statistics"]
                    if int(item["retained_window_count"]) >= int(supplement["minimum_retained_windows"])
                    and (int(item["source"]), int(item["target"])) not in merged]
        eligible.sort(key=lambda item: (-int(item["retained_window_count"]),
                                        -float(item["mean_retained_score"]),
                                        int(item["source"]), int(item["target"])))
        needed = int(supplement["minimum_unique_edges"]) - len(merged)
        for item in eligible[:needed]:
            key = (int(item["source"]), int(item["target"]))
            merged[key] = {
                "source": key[0], "target": key[1],
                "source_name": item["source_name"], "target_name": item["target_name"],
                "windows": set(int(window) for window in item["windows"]),
                "categories": {"multi_window_supplement"},
            }
    return [{**item, "windows": sorted(item["windows"]), "categories": sorted(item["categories"])}
            for _, item in sorted(merged.items())]


def unique_variables(patterns: dict, categories: Iterable[str]) -> list[dict]:
    merged: dict[int, dict] = {}
    for category in categories:
        for item in patterns["candidate_patterns"][category]:
            variable = int(item["variable"])
            record = merged.setdefault(variable, {
                "variable": variable, "variable_name": item["variable_name"], "categories": set()
            })
            record["categories"].add(category)
    return [{**item, "categories": sorted(item["categories"])} for _, item in sorted(merged.items())]


def operation_matrix(patterns: dict, config: dict, window_count: int) -> list[dict]:
    operations: list[dict] = []
    for edge in selected_edges(patterns, config["edge_candidate_selection"], config.get("edge_candidate_supplement")):
        for window in edge["windows"]:
            for protocol in config["edge_protocols"]:
                operations.append({
                    "object_type": "edge", "candidate_categories": edge["categories"],
                    "protocol": {"type": protocol, "window": window,
                                 "source": edge["source"], "target": edge["target"]},
                    "label": f"{edge['source_name']}→{edge['target_name']}",
                })
    for variable in unique_variables(patterns, config["variable_candidate_categories"]):
        for window in range(window_count):
            for protocol in config["windowed_variable_protocols"]:
                operations.append({
                    "object_type": "variable", "candidate_categories": variable["categories"],
                    "protocol": {"type": protocol, "window": window, "variable": variable["variable"]},
                    "label": variable["variable_name"],
                })
        for protocol in config["windowless_variable_protocols"]:
            operations.append({
                "object_type": "variable", "candidate_categories": variable["categories"],
                "protocol": {"type": protocol, "variable": variable["variable"]},
                "label": variable["variable_name"],
            })
    edge_sets = patterns["candidate_patterns"][config["edge_set_candidate_category"]]
    for index, edge_set in enumerate(edge_sets[:int(config["edge_set_limit"])]):
        edges = [[int(edge["source"]), int(edge["target"])] for edge in edge_set["edges"]]
        label = " + ".join(f"{edge['source_name']}→{edge['target_name']}" for edge in edge_set["edges"])
        for window in sorted(int(window) for window in edge_set["windows"]):
            for protocol in config["edge_set_protocols"]:
                operations.append({
                    "object_type": "edge_set", "candidate_categories": [config["edge_set_candidate_category"]],
                    "candidate_index": index,
                    "protocol": {"type": protocol, "window": window, "edges": edges},
                    "label": label,
                })
    return sorted(operations, key=lambda item: canonical_json(item["protocol"]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--registry", default="configs/phase1_registry.json")
    parser.add_argument("--output-root", default="artifacts/runs")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    registry_path = Path(args.registry).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    candidate_dir = Path(args.output_root).resolve() / config["candidate_run_id"] / "patterns"
    adapter_path = Path(__file__).resolve().parents[1] / "adapters.py"
    fingerprints = [sha256(config_path), sha256(registry_path), sha256(adapter_path), sha256(Path(__file__).resolve())]
    fingerprints.extend(sha256(candidate_dir / f"{name}.json") for name in sorted(registry["datasets"]))
    run_id = hashlib.sha256("|".join(fingerprints).encode()).hexdigest()
    run_dir = Path(args.output_root).resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    dataset_plans = []
    plans: dict[str, tuple[dict, list[dict]]] = {}
    scoped_datasets = {name: registry["datasets"][name] for name in config["dataset_scope"]}
    for dataset_name, ds in scoped_datasets.items():
        ds = {**ds, "web_sample_indices": config.get("sample_indices_override", {}).get(dataset_name, ds["web_sample_indices"])}
        scoped_datasets[dataset_name] = ds
        pattern_path = candidate_dir / f"{dataset_name}.json"
        patterns = json.loads(pattern_path.read_text(encoding="utf-8"))
        operations = operation_matrix(patterns, config, patterns["window_count"])
        plans[dataset_name] = (patterns, operations)
        chosen_edges = selected_edges(patterns, config["edge_candidate_selection"], config.get("edge_candidate_supplement"))
        dataset_plans.append({
            "dataset": dataset_name,
            "web_sample_indices": ds["web_sample_indices"],
            "selected_candidate_edges": chosen_edges,
            "operation_templates_per_sample": len(operations),
            "real_forward_count": len(ds["web_sample_indices"]) * (1 + len(operations)),
        })

    plan = {
        "run_id": run_id, "status": "planned" if args.plan_only else "running",
        "phase": "Phase 4 - Predeclared Candidate Intervention Catalog",
        "schedule": {"state": "final", "current_epoch_equivalent": config["current_epoch"],
                     "static_weight": 0.1, "learned_weight": 0.9},
        "selection_config": str(config_path), "selection_config_sha256": sha256(config_path),
        "candidate_run_id": config["candidate_run_id"], "datasets": dataset_plans,
        "total_real_forward_count": sum(item["real_forward_count"] for item in dataset_plans),
        "statistical_validation": config["statistical_validation"],
    }
    (run_dir / "plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.plan_only:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        return 0

    source_root = Path(registry["source_root"])
    results_dir = run_dir / "catalog"
    predictions_dir = run_dir / "predictions"
    results_dir.mkdir(exist_ok=True)
    predictions_dir.mkdir(exist_ok=True)
    dataset_manifests = []

    for dataset_name, ds in scoped_datasets.items():
        patterns, operations = plans[dataset_name]
        adapter = DGraFormerAdapter(str(source_root), dataset_name, registry["common"], ds, registry["random_seed"])
        checkpoint = source_root / "checkpoints" / ds["setting"] / "checkpoint.pth"
        data_path = source_root / ds["root_path"] / ds["data_path"]
        adapter.load_checkpoint(str(checkpoint))
        records = []
        prediction_rows = []
        truth_rows = []
        for sample_index in ds["web_sample_indices"]:
            batch = dict(adapter.load_sample("test", int(sample_index)))
            batch["current_epoch"] = config["current_epoch"]
            baseline = adapter.predict(batch)
            identity = adapter.predict_with_graph_override(batch, {
                "type": "identity", "window": 0, "current_epoch": config["current_epoch"]
            })["prediction"]
            torch.testing.assert_close(identity, baseline, atol=0, rtol=0)
            truth = torch.as_tensor(batch["y"][-registry["common"]["pred_len"]:, :], dtype=torch.float32).unsqueeze(0)
            baseline_row = len(prediction_rows)
            prediction_rows.append(baseline.numpy()[0])
            truth_rows.append(truth.numpy()[0])
            for operation in operations:
                protocol = {**operation["protocol"], "current_epoch": config["current_epoch"]}
                outcome = adapter.predict_with_graph_override(batch, protocol)
                prediction = outcome["prediction"]
                prediction_row = len(prediction_rows)
                prediction_rows.append(prediction.numpy()[0])
                record_id = hashlib.sha256(canonical_json({
                    "dataset": dataset_name, "sample_index": sample_index, "protocol": operation["protocol"]
                }).encode()).hexdigest()
                records.append({
                    "record_id": record_id, "status": "complete", "claim_level": "interventional_model_evidence",
                    "dataset": dataset_name, "test_sample_index": int(sample_index),
                    "object_type": operation["object_type"], "label": operation["label"],
                    "candidate_categories": operation["candidate_categories"],
                    "protocol": operation["protocol"], "renormalized": bool(outcome["renormalized"]),
                    "metrics": impact_metrics(baseline, prediction, truth),
                    "raw_operands": {"prediction_file": f"predictions/{dataset_name}.npz",
                                     "baseline_row": baseline_row, "intervention_row": prediction_row,
                                     "truth_row": ds["web_sample_indices"].index(sample_index)},
                    "statistical_validation": {"status": "not_evaluated", "metrics": None,
                                               "reason": "No Phase 5 matched-control artifact is linked to this catalog entry."},
                })
        np.savez_compressed(predictions_dir / f"{dataset_name}.npz",
                            predictions=np.asarray(prediction_rows, dtype=np.float32),
                            truths=np.asarray(truth_rows, dtype=np.float32))
        catalog = {
            "dataset": dataset_name, "status": "complete", "claim_level": "interventional_model_evidence",
            "checkpoint_sha256": sha256(checkpoint), "data_sha256": sha256(data_path),
            "candidate_pattern_sha256": sha256(candidate_dir / f"{dataset_name}.json"),
            "schedule": plan["schedule"], "record_count": len(records), "records": records,
            "limitations": [
                "Results describe model-internal behavior for the specified checkpoint, sample, window and protocol.",
                "They do not represent real-world causal relationships.",
                "Catalog membership does not imply statistical support or cross-run reproducibility."
            ],
        }
        catalog_path = results_dir / f"{dataset_name}.json"
        catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
        dataset_manifests.append({
            "dataset": dataset_name, "status": "complete", "record_count": len(records),
            "catalog": str(catalog_path.relative_to(run_dir)), "catalog_sha256": sha256(catalog_path),
            "predictions": str((predictions_dir / f"{dataset_name}.npz").relative_to(run_dir)),
            "predictions_sha256": sha256(predictions_dir / f"{dataset_name}.npz"),
            "checkpoint_sha256": sha256(checkpoint), "data_sha256": sha256(data_path),
        })

    manifest = {**plan, "status": "complete", "datasets": dataset_manifests}
    command = (f"python -m dgraudit.cli.precompute_intervention_catalog --config {args.config} "
               f"--registry {args.registry} --output-root {args.output_root}\n")
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "command.txt").write_text(command, encoding="utf-8")
    (run_dir / "environment.json").write_text(json.dumps({
        "python": platform.python_version(), "torch": torch.__version__, "numpy": np.__version__,
        "cuda": torch.version.cuda, "cuda_available": torch.cuda.is_available(),
    }, indent=2), encoding="utf-8")
    (run_dir / "stdout.log").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (run_dir / "stderr.log").write_text("", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

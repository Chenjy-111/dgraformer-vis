from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import torch
from scipy.stats import rankdata, spearmanr

from dgraudit.adapters import DGraFormerAdapter


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prediction_metrics(prediction: torch.Tensor, truth: torch.Tensor) -> dict:
    error = prediction - truth
    return {"mae": float(error.abs().mean()), "mse": float((error ** 2).mean())}


def impact_metrics(baseline: torch.Tensor, intervention: torch.Tensor, truth: torch.Tensor) -> dict:
    baseline_error = prediction_metrics(baseline, truth)
    intervention_error = prediction_metrics(intervention, truth)
    absolute = float((intervention - baseline).abs().mean())
    denominator = float(baseline.abs().mean()) + 1e-12
    return {
        "baseline_mae": baseline_error["mae"],
        "baseline_mse": baseline_error["mse"],
        "intervention_mae": intervention_error["mae"],
        "intervention_mse": intervention_error["mse"],
        "prediction_delta_abs": absolute,
        "prediction_delta_rel": absolute / denominator,
        "error_delta_mae": intervention_error["mae"] - baseline_error["mae"],
        "error_delta_mse": intervention_error["mse"] - baseline_error["mse"],
    }


def benjamini_hochberg(values: list[float]) -> list[float]:
    count = len(values)
    order = np.argsort(values)
    adjusted = np.empty(count, dtype=float)
    running = 1.0
    for reverse_rank in range(count - 1, -1, -1):
        index = int(order[reverse_rank])
        rank = reverse_rank + 1
        running = min(running, values[index] * count / rank)
        adjusted[index] = min(1.0, running)
    return adjusted.tolist()


def sample_timestamps(data_path: Path, dataset_name: str, sample_index: int, seq_len: int, pred_len: int) -> dict:
    with data_path.open(encoding="utf-8", errors="replace", newline="") as handle:
        dates = [row[0] for row in list(csv.reader(handle))[1:]]
    test_start = 12 * 30 * 24 if dataset_name.startswith("ETTh") else (
        12 * 30 * 24 * 4 if dataset_name.startswith("ETTm") else int(len(dates) * 0.8) - seq_len
    )
    input_start = test_start + sample_index
    input_end = input_start + seq_len - 1
    forecast_start = input_start + seq_len
    forecast_end = forecast_start + pred_len - 1
    return {
        "input_start": dates[input_start], "input_end": dates[input_end],
        "forecast_start": dates[forecast_start], "forecast_end": dates[forecast_end],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--registry", default="configs/phase1_registry.json")
    parser.add_argument("--output-root", default="artifacts/runs")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    registry_path = Path(args.registry).resolve()
    output_root = Path(args.output_root).resolve()
    script_path = Path(__file__).resolve()
    adapter_path = script_path.parents[1] / "adapters.py"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    dataset_name = config["dataset"]
    dataset_config = registry["datasets"][dataset_name]
    source_root = Path(registry["source_root"])
    checkpoint = source_root / "checkpoints" / dataset_config["setting"] / "checkpoint.pth"
    data_path = source_root / dataset_config["root_path"] / dataset_config["data_path"]
    candidate_path = output_root / config["candidate_run_id"] / "patterns" / f"{dataset_name}.json"

    fingerprints = [
        sha256(data_path), sha256(registry_path), sha256(checkpoint),
        str(registry["random_seed"]), sha256(script_path), sha256(adapter_path), sha256(config_path),
    ]
    run_id = hashlib.sha256("|".join(fingerprints).encode()).hexdigest()
    run_dir = output_root / run_id
    for child in ["inputs", "graphs", "predictions", "metrics", "controls", "evidence", "report"]:
        (run_dir / child).mkdir(parents=True, exist_ok=True)

    patterns = json.loads(candidate_path.read_text(encoding="utf-8"))
    candidates = patterns["candidate_patterns"]["high_weight_low_frequency_edges"]
    focal = sorted(candidates, key=lambda item: (-item["mean_retained_score"], item["source"], item["target"]))[0]
    window = int(focal["windows"][0])
    source = int(focal["source"])
    target = int(focal["target"])

    adapter = DGraFormerAdapter(str(source_root), dataset_name, registry["common"], dataset_config, registry["random_seed"])
    adapter.load_checkpoint(str(checkpoint))
    batch = adapter.load_sample("test", config["test_sample_index"])
    batch = {**batch, "current_epoch": config["current_epoch"]}
    truth = torch.as_tensor(batch["y"][-registry["common"]["pred_len"]:, :], dtype=torch.float32).unsqueeze(0)
    baseline = adapter.predict(batch)
    stages = adapter.extract_graph_stages(batch)
    stage = stages["windows"][window]
    scores = stage["diagonal_removed"]
    retained = [
        (i, j) for i in range(scores.shape[0]) for j in range(scores.shape[1])
        if i != j and bool(stage["topk_mask"][i, j] == 1) and float(scores[i, j]) > 0
    ]
    focal_edge = (source, target)
    if focal_edge not in retained:
        raise RuntimeError("Predeclared focal candidate is not retained in its selected graph window")

    def intervene(edge: tuple[int, int]) -> tuple[torch.Tensor, dict]:
        outcome = adapter.predict_with_graph_override(batch, {
            "type": config["intervention_type"], "window": window,
            "source": edge[0], "target": edge[1], "current_epoch": config["current_epoch"],
        })
        prediction = outcome["prediction"]
        return prediction, impact_metrics(baseline, prediction, truth)

    focal_prediction, focal_metrics = intervene(focal_edge)
    edge_results = []
    edge_predictions = []
    for edge in retained:
        prediction, measured = (focal_prediction, focal_metrics) if edge == focal_edge else intervene(edge)
        edge_predictions.append(prediction.numpy())
        edge_results.append({
            "source": edge[0], "target": edge[1], "source_name": patterns["variable_names"][edge[0]],
            "target_name": patterns["variable_names"][edge[1]], "weight_before_topk": float(scores[edge]),
            **measured,
        })

    weights = np.asarray([item["weight_before_topk"] for item in edge_results])
    impacts = np.asarray([item["prediction_delta_abs"] for item in edge_results])
    correlation = spearmanr(weights, impacts)
    k = min(int(config["overlap_k"]), len(edge_results))
    weight_top = set(np.argsort(-weights, kind="stable")[:k].tolist())
    impact_top = set(np.argsort(-impacts, kind="stable")[:k].tolist())
    weight_impact = {
        "edge_count": len(edge_results), "tie_method": "average ranks for Spearman; stable source-target order for Overlap@K",
        "spearman_rho": float(correlation.statistic), "spearman_p": float(correlation.pvalue),
        "k": k, "overlap_at_k": len(weight_top & impact_top) / k,
        "raw_weights": weights.tolist(), "raw_impacts": impacts.tolist(), "edges": edge_results,
    }

    eligible_controls = [edge for edge in retained if edge != focal_edge]
    if not eligible_controls:
        raise RuntimeError("No same-window real retained edge is available for matched controls")
    control_config = config["control_experiment"]
    rng = np.random.default_rng(control_config["random_seed"])
    control_records = []
    control_predictions = []
    for repetition in range(int(control_config["repetitions"])):
        edge = eligible_controls[int(rng.integers(0, len(eligible_controls)))]
        prediction, measured = intervene(edge)
        control_predictions.append(prediction.numpy())
        control_records.append({
            "repetition": repetition, "seed": control_config["random_seed"],
            "sampling": "uniform from real retained same-window non-self edges excluding focal edge",
            "source": edge[0], "target": edge[1], "prediction_array_index": repetition,
            "intervention": {"type": config["intervention_type"], "window": window, "renormalized": True},
            "metrics": measured,
        })

    control_impacts = np.asarray([item["metrics"]["prediction_delta_abs"] for item in control_records])
    empirical_p = float((1 + np.sum(control_impacts >= focal_metrics["prediction_delta_abs"])) / (len(control_impacts) + 1))
    percentile = float(100 * np.mean(control_impacts <= focal_metrics["prediction_delta_abs"]))
    standard_deviation = float(control_impacts.std(ddof=1))
    effect_size = None if standard_deviation == 0 else float((focal_metrics["prediction_delta_abs"] - control_impacts.mean()) / standard_deviation)
    bootstrap_rng = np.random.default_rng(control_config["random_seed"] + 1)
    bootstrap_means = bootstrap_rng.choice(
        control_impacts, size=(int(control_config["bootstrap_repetitions"]), len(control_impacts)), replace=True
    ).mean(axis=1)
    effect_distribution = focal_metrics["prediction_delta_abs"] - bootstrap_means
    alpha = 1 - float(control_config["confidence_level"])
    confidence_interval = np.quantile(effect_distribution, [alpha / 2, 1 - alpha / 2]).tolist()
    adjusted_p = benjamini_hochberg([empirical_p])[0]

    degrees_out = {node: sum(edge[0] == node for edge in retained) for node in range(scores.shape[0])}
    degrees_in = {node: sum(edge[1] == node for edge in retained) for node in range(scores.shape[0])}
    low_weight_edge = min(eligible_controls, key=lambda edge: (float(scores[edge]), edge))
    source_degree_edge = min(eligible_controls, key=lambda edge: (abs(degrees_out[edge[0]] - degrees_out[source]), edge))
    target_degree_edge = min(eligible_controls, key=lambda edge: (abs(degrees_in[edge[1]] - degrees_in[target]), edge))
    named_controls = []
    named_control_predictions = []
    for name, edge in [
        ("low_weight_real_edge", low_weight_edge),
        ("similar_source_outdegree_real_edge", source_degree_edge),
        ("similar_target_indegree_real_edge", target_degree_edge),
        ("true_edge_permutation_same_count", eligible_controls[0]),
    ]:
        prediction, measured = intervene(edge)
        named_control_predictions.append(prediction.numpy())
        named_controls.append({"type": name, "source": edge[0], "target": edge[1], "metrics": measured})
    identity = adapter.predict_with_graph_override(batch, {
        "type": "identity", "window": window, "current_epoch": config["current_epoch"]
    })["prediction"]
    identity_delta = float((identity - baseline).abs().max())
    torch.testing.assert_close(identity, baseline, atol=0, rtol=0)
    named_controls.append({"type": "null_identity", "max_absolute_prediction_difference": identity_delta})
    named_control_predictions.append(identity.numpy())

    np.save(run_dir / "inputs" / "input.npy", np.asarray(batch["x"]))
    np.save(run_dir / "inputs" / "ground_truth.npy", truth.numpy())
    np.save(run_dir / "predictions" / "baseline.npy", baseline.numpy())
    np.save(run_dir / "predictions" / "focal_intervention.npy", focal_prediction.numpy())
    np.save(run_dir / "predictions" / "all_retained_edge_interventions.npy", np.concatenate(edge_predictions, axis=0))
    np.save(run_dir / "controls" / "matched_control_predictions.npy", np.concatenate(control_predictions, axis=0))
    np.save(run_dir / "controls" / "named_control_predictions.npy", np.concatenate(named_control_predictions, axis=0))
    (run_dir / "controls" / "matched_controls.json").write_text(json.dumps(control_records, indent=2), encoding="utf-8")
    (run_dir / "controls" / "named_controls.json").write_text(json.dumps(named_controls, indent=2), encoding="utf-8")
    graph_record = {key: (value.tolist() if isinstance(value, torch.Tensor) else value) for key, value in stage.items()}
    (run_dir / "graphs" / f"window_{window}.json").write_text(json.dumps(graph_record, indent=2), encoding="utf-8")
    (run_dir / "metrics" / "weight_impact.json").write_text(json.dumps(weight_impact, indent=2), encoding="utf-8")

    control_summary = {
        "repetitions": len(control_records), "random_seed": control_config["random_seed"],
        "observed_prediction_delta_abs": focal_metrics["prediction_delta_abs"],
        "control_mean_prediction_delta_abs": float(control_impacts.mean()),
        "control_standard_deviation": standard_deviation, "control_percentile": percentile,
        "empirical_p": empirical_p, "bh_adjusted_p": adjusted_p,
        "standardized_effect_size": effect_size,
        "effect_difference_bootstrap_ci": confidence_interval,
        "confidence_level": control_config["confidence_level"],
        "bootstrap_repetitions": control_config["bootstrap_repetitions"],
    }
    (run_dir / "metrics" / "control_statistics.json").write_text(json.dumps(control_summary, indent=2), encoding="utf-8")

    edge_rank = int(rankdata(-weights, method="average")[retained.index(focal_edge)])
    sorted_scores = sorted((float(scores[edge]) for edge in retained), reverse=True)
    boundary_margin = sorted_scores[-1] - 0.0
    statement = (
        f"在数据集 {dataset_name} 的测试样本 {config['test_sample_index']}、窗口 {window} 中，"
        f"边 {patterns['variable_names'][source]}→{patterns['variable_names'][target]} 的 Top-K 前分数为 "
        f"{float(scores[focal_edge]):.6f}，保留边内排名为 {edge_rank}。执行结构边删除后，"
        f"平均绝对预测变化为 {focal_metrics['prediction_delta_abs']:.6f}，MAE 由 "
        f"{focal_metrics['baseline_mae']:.6f} 变为 {focal_metrics['intervention_mae']:.6f}，"
        f"差值为 {focal_metrics['error_delta_mae']:.6f}。该预测变化位于 "
        f"{len(control_records)} 次匹配对照实验的第 {percentile:.2f} 百分位，经验 p 值为 {empirical_p:.6f}。"
    )
    timestamps = sample_timestamps(data_path, dataset_name, config["test_sample_index"],
                                   registry["common"]["seq_len"], registry["common"]["pred_len"])
    evidence = {
        "conclusion_id": f"{dataset_name.lower()}_s{config['test_sample_index']}_w{window}_edge_{source}_{target}",
        "status": "complete", "claim_level": "interventional_model_evidence", "statement": statement,
        "dataset": {"name": dataset_name, "path": str(data_path), "sha256": sha256(data_path)},
        "sample": {"split": "test", "original_index": config["test_sample_index"], **timestamps},
        "model": {"checkpoint_path": str(checkpoint), "checkpoint_sha256": sha256(checkpoint),
                  "seed": registry["random_seed"], "config_path": str(registry_path), "config_sha256": sha256(registry_path),
                  "schedule": {"current_epoch_equivalent": config["current_epoch"], "state": "final"}},
        "graph": {"window": window, "source": source, "target": target,
                  "raw_score": float(stage["raw_score"][focal_edge]), "topk_score": float(scores[focal_edge]),
                  "normalized_weight": float(stage["normalized"][focal_edge]), "retained_edge_rank": edge_rank,
                  "topk_margin": boundary_margin},
        "intervention": {"type": config["intervention_type"], "renormalized": True,
                         "implementation_file": str(adapter_path), "implementation_function": "DGraFormerAdapter.predict_with_graph_override"},
        "metrics": {**focal_metrics, **control_summary, "weight_impact_spearman_rho": weight_impact["spearman_rho"],
                    "weight_impact_spearman_p": weight_impact["spearman_p"], "overlap_at_k": weight_impact["overlap_at_k"]},
        "raw_operands": {"baseline_prediction": "predictions/baseline.npy", "intervention_prediction": "predictions/focal_intervention.npy",
                         "ground_truth": "inputs/ground_truth.npy", "graph": f"graphs/window_{window}.json",
                         "matched_controls": "controls/matched_controls.json", "control_predictions": "controls/matched_control_predictions.npy"},
        "formulas": ["mae", "mse", "prediction_delta_abs", "prediction_delta_rel", "spearman_rho", "overlap_at_k", "empirical_p", "benjamini_hochberg", "bootstrap_ci"],
        "code": {"git_commit": None, "git_status": "missing_repository_metadata_in_supplied_model_source",
                 "model_file": str(source_root / "models" / "DGraFormer.py"),
                 "graph_extraction_file": str(source_root / "layers" / "DGraFormer_framework.py"),
                 "intervention_file": str(adapter_path)},
        "reproduction": {"run_id": run_id, "command": "command.txt", "environment_path": "environment.json",
                         "manifest_path": "manifest.json", "stdout_log": "stdout.log", "stderr_log": "stderr.log"},
        "limitations": ["仅描述指定模型、数据、样本和图窗口条件下的模型内部行为。", "不代表现实变量间因果关系。",
                        "当前统计结论仅针对预先选定的一个候选边；跨训练复核尚未执行。"],
    }
    evidence_path = run_dir / "evidence" / f"{evidence['conclusion_id']}.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")

    manifest = {
        "run_id": run_id, "status": "complete", "phase": "Phase 5 - Evidence Validation",
        "config_path": str(config_path), "config_sha256": sha256(config_path),
        "registry_path": str(registry_path), "registry_sha256": sha256(registry_path),
        "data_sha256": sha256(data_path), "checkpoint_sha256": sha256(checkpoint),
        "candidate_run_id": config["candidate_run_id"], "dataset": dataset_name,
        "sample_index": config["test_sample_index"], "window": window, "edge": [source, target],
        "schedule": {"current_epoch_equivalent": config["current_epoch"], "state": "final"},
        "focal_metrics": focal_metrics, "weight_impact": {key: weight_impact[key] for key in ["edge_count", "spearman_rho", "spearman_p", "k", "overlap_at_k"]},
        "control_statistics": control_summary, "identity_override_max_absolute_difference": identity_delta,
        "evidence_path": str(evidence_path),
    }
    command = f"python -m dgraudit.cli.validate_pattern --config {args.config} --registry {args.registry} --output-root {args.output_root}\n"
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "command.txt").write_text(command, encoding="utf-8")
    (run_dir / "environment.json").write_text(json.dumps({"python": platform.python_version(), "torch": torch.__version__,
                                                            "numpy": np.__version__, "cuda": torch.version.cuda}, indent=2), encoding="utf-8")
    (run_dir / "stdout.log").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (run_dir / "stderr.log").write_text("", encoding="utf-8")
    (run_dir / "report" / "summary.json").write_text(json.dumps({"statement": statement, "metrics": control_summary}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

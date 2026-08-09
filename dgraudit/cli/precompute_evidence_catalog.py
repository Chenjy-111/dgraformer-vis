from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import torch
from scipy.stats import rankdata, spearmanr

from dgraudit.adapters import DGraFormerAdapter
from dgraudit.cli.validate_pattern import benjamini_hochberg, impact_metrics, sample_timestamps, sha256


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


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
    ds = registry["datasets"][dataset_name]
    source_root = Path(registry["source_root"])
    checkpoint = source_root / "checkpoints" / ds["setting"] / "checkpoint.pth"
    data_path = source_root / ds["root_path"] / ds["data_path"]
    intervention_run = output_root / config["intervention_catalog_run_id"]
    intervention_catalog_path = intervention_run / "catalog" / f"{dataset_name}.json"
    intervention_catalog = json.loads(intervention_catalog_path.read_text(encoding="utf-8"))
    pattern_path = output_root / "467d53169372e3120e7964f81152bee863fc5ef121b01e5413ed813c14c10a5c" / "patterns" / f"{dataset_name}.json"
    patterns = json.loads(pattern_path.read_text(encoding="utf-8"))
    fingerprints = [sha256(config_path), sha256(registry_path), sha256(checkpoint), sha256(data_path),
                    sha256(intervention_catalog_path), sha256(pattern_path), sha256(script_path), sha256(adapter_path)]
    run_id = hashlib.sha256("|".join(fingerprints).encode()).hexdigest()
    run_dir = output_root / run_id
    for child in ["evidence", "predictions", "controls", "metrics", "graphs"]:
        (run_dir / child).mkdir(parents=True, exist_ok=True)

    structural = [record for record in intervention_catalog["records"]
                  if record["protocol"]["type"] == "structural_edge_removal"]
    cases = sorted({(int(r["test_sample_index"]), int(r["protocol"]["window"]),
                     int(r["protocol"]["source"]), int(r["protocol"]["target"])) for r in structural})
    grouped: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for sample, window, source, target in cases:
        grouped.setdefault((sample, window), []).append((source, target))

    adapter = DGraFormerAdapter(str(source_root), dataset_name, registry["common"], ds, registry["random_seed"])
    adapter.load_checkpoint(str(checkpoint))
    evidence_records = []
    raw_group_manifests = []
    controls_config = config["control_experiment"]
    sample_cache = {}
    for group_index, ((sample_index, window), focal_edges) in enumerate(sorted(grouped.items())):
        if sample_index not in sample_cache:
            batch = dict(adapter.load_sample("test", sample_index))
            batch["current_epoch"] = config["current_epoch"]
            baseline = adapter.predict(batch)
            truth = torch.as_tensor(batch["y"][-registry["common"]["pred_len"]:, :], dtype=torch.float32).unsqueeze(0)
            sample_cache[sample_index] = (batch, baseline, truth)
        batch, baseline, truth = sample_cache[sample_index]
        stage = adapter.extract_graph_stages(batch)["windows"][window]
        scores = stage["diagonal_removed"]
        retained = [(i, j) for i in range(scores.shape[0]) for j in range(scores.shape[1])
                    if i != j and bool(stage["topk_mask"][i, j] == 1) and float(scores[i, j]) > 0]
        edge_predictions = []
        edge_metrics = []
        for edge in retained:
            outcome = adapter.predict_with_graph_override(batch, {
                "type": "structural_edge_removal", "window": window,
                "source": edge[0], "target": edge[1], "current_epoch": config["current_epoch"]})
            edge_predictions.append(outcome["prediction"].numpy()[0])
            edge_metrics.append(impact_metrics(baseline, outcome["prediction"], truth))
        identity = adapter.predict_with_graph_override(batch, {
            "type": "identity", "window": window, "current_epoch": config["current_epoch"]})["prediction"]
        identity_delta = float((identity - baseline).abs().max())
        torch.testing.assert_close(identity, baseline, atol=0, rtol=0)
        raw_path = run_dir / "predictions" / f"sample_{sample_index}_window_{window}.npz"
        np.savez_compressed(raw_path, baseline=baseline.numpy()[0], truth=truth.numpy()[0],
                            retained_edge_predictions=np.asarray(edge_predictions, dtype=np.float32),
                            retained_edges=np.asarray(retained, dtype=np.int64))
        graph_path = run_dir / "graphs" / f"window_{window}.json"
        if not graph_path.exists():
            graph_path.write_text(json.dumps({key: value.tolist() if isinstance(value, torch.Tensor) else value
                                              for key, value in stage.items()}, indent=2), encoding="utf-8")
        weights = np.asarray([float(scores[edge]) for edge in retained])
        impacts = np.asarray([m["prediction_delta_abs"] for m in edge_metrics])
        correlation = spearmanr(weights, impacts)
        k = min(int(config["overlap_k"]), len(retained))
        weight_top = set(np.argsort(-weights, kind="stable")[:k].tolist())
        impact_top = set(np.argsort(-impacts, kind="stable")[:k].tolist())
        weight_impact = {"edge_count": len(retained), "tie_method": "average ranks for Spearman; stable source-target order for Overlap@K",
                         "spearman_rho": float(correlation.statistic), "spearman_p": float(correlation.pvalue),
                         "k": k, "overlap_at_k": len(weight_top & impact_top) / k,
                         "raw_weights": weights.tolist(), "raw_impacts": impacts.tolist(),
                         "edges": [{"source": e[0], "target": e[1], "source_name": patterns["variable_names"][e[0]],
                                    "target_name": patterns["variable_names"][e[1]], **edge_metrics[idx]}
                                   for idx, e in enumerate(retained)]}
        raw_group_manifests.append({"sample_index": sample_index, "window": window,
                                    "prediction_file": str(raw_path.relative_to(run_dir)),
                                    "prediction_sha256": sha256(raw_path), "identity_delta": identity_delta})
        for focal_edge in sorted(focal_edges):
            focal_index = retained.index(focal_edge)
            focal_metrics = edge_metrics[focal_index]
            eligible = [index for index, edge in enumerate(retained) if edge != focal_edge]
            case_seed = int(controls_config["random_seed"]) + len(evidence_records)
            rng = np.random.default_rng(case_seed)
            sampled_indices = [eligible[int(rng.integers(0, len(eligible)))]
                               for _ in range(int(controls_config["repetitions"]))]
            control_impacts = impacts[sampled_indices]
            empirical_p = float((1 + np.sum(control_impacts >= focal_metrics["prediction_delta_abs"])) /
                                (len(control_impacts) + 1))
            percentile = float(100 * np.mean(control_impacts <= focal_metrics["prediction_delta_abs"]))
            standard_deviation = float(control_impacts.std(ddof=1))
            effect_size = None if standard_deviation == 0 else float(
                (focal_metrics["prediction_delta_abs"] - control_impacts.mean()) / standard_deviation)
            bootstrap_rng = np.random.default_rng(case_seed + 100000)
            bootstrap_means = bootstrap_rng.choice(control_impacts,
                size=(int(controls_config["bootstrap_repetitions"]), len(control_impacts)), replace=True).mean(axis=1)
            effect_distribution = focal_metrics["prediction_delta_abs"] - bootstrap_means
            alpha = 1 - float(controls_config["confidence_level"])
            ci = np.quantile(effect_distribution, [alpha / 2, 1 - alpha / 2]).tolist()
            edge_rank = float(rankdata(-weights, method="average")[focal_index])
            control_records = [{"repetition": repetition, "seed": case_seed,
                                "sampling": "uniform from real retained same-window non-self edges excluding focal edge",
                                "retained_edge_prediction_row": index, "source": retained[index][0], "target": retained[index][1],
                                "metrics": edge_metrics[index]} for repetition, index in enumerate(sampled_indices)]
            control_path = run_dir / "controls" / f"s{sample_index}_w{window}_e{focal_edge[0]}_{focal_edge[1]}.json"
            control_path.write_text(json.dumps(control_records, indent=2), encoding="utf-8")
            timestamps = sample_timestamps(data_path, dataset_name, sample_index,
                                           registry["common"]["seq_len"], registry["common"]["pred_len"])
            conclusion_id = f"etth1_s{sample_index}_w{window}_edge_{focal_edge[0]}_{focal_edge[1]}"
            evidence_records.append({
                "conclusion_id": conclusion_id, "status": "complete", "claim_level": "interventional_model_evidence",
                "dataset": {"name": dataset_name, "path": str(data_path), "sha256": sha256(data_path)},
                "sample": {"split": "test", "original_index": sample_index, **timestamps},
                "model": {"checkpoint_path": str(checkpoint), "checkpoint_sha256": sha256(checkpoint),
                          "seed": registry["random_seed"], "config_path": str(registry_path), "config_sha256": sha256(registry_path),
                          "schedule": {"state": "final", "current_epoch_equivalent": config["current_epoch"],
                                       "static_weight": 0.1, "learned_weight": 0.9}},
                "graph": {"window": window, "source": focal_edge[0], "target": focal_edge[1],
                          "source_name": patterns["variable_names"][focal_edge[0]], "target_name": patterns["variable_names"][focal_edge[1]],
                          "topk_score": float(scores[focal_edge]), "normalized_weight": float(stage["normalized"][focal_edge]),
                          "retained_edge_rank": edge_rank},
                "intervention": {"type": "structural_edge_removal", "renormalized": True,
                                 "implementation_file": str(adapter_path), "implementation_function": "DGraFormerAdapter.predict_with_graph_override"},
                "metrics": {**focal_metrics, "control_mean_prediction_delta_abs": float(control_impacts.mean()),
                            "control_standard_deviation": standard_deviation, "control_percentile": percentile,
                            "empirical_p": empirical_p, "bh_adjusted_p": None,
                            "standardized_effect_size": effect_size, "effect_difference_bootstrap_ci": ci,
                            "weight_impact_spearman_rho": weight_impact["spearman_rho"],
                            "weight_impact_spearman_p": weight_impact["spearman_p"], "overlap_at_k": weight_impact["overlap_at_k"]},
                "metric_status": {"standardized_effect_size": {
                    "status": "complete" if effect_size is not None else "undefined",
                    "reason": None if effect_size is not None else "Control impact standard deviation is zero; the standardized effect-size denominator is zero."
                }},
                "controls": {"repetitions": len(control_records), "random_seed": case_seed,
                             "records": str(control_path.relative_to(run_dir)), "records_sha256": sha256(control_path)},
                "raw_operands": {"predictions": str(raw_path.relative_to(run_dir)), "focal_prediction_row": focal_index,
                                 "graph": str(graph_path.relative_to(run_dir)), "weight_impact": weight_impact},
                "formulas": ["mae", "mse", "prediction_delta_abs", "prediction_delta_rel", "spearman_rho",
                             "overlap_at_k", "empirical_p_plus_one", "benjamini_hochberg", "bootstrap_ci", "standardized_effect_size"],
                "limitations": ["仅描述指定模型、数据、样本和图窗口条件下的模型内部行为。",
                                "不代表现实变量间因果关系。", "跨训练复核尚未执行。"],
            })

    adjusted = benjamini_hochberg([record["metrics"]["empirical_p"] for record in evidence_records])
    for record, adjusted_p in zip(evidence_records, adjusted):
        record["metrics"]["bh_adjusted_p"] = adjusted_p
        evidence_path = run_dir / "evidence" / f"{record['conclusion_id']}.json"
        evidence_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    catalog_path = run_dir / "evidence_catalog.json"
    catalog = {"run_id": run_id, "status": "complete", "phase": "Phase 5 - ETTh1 Precomputed Evidence Catalog",
               "dataset": dataset_name, "case_count": len(evidence_records), "multiple_comparison_family_size": len(evidence_records),
               "multiple_comparison_correction": config["multiple_comparison_correction"], "cases": evidence_records,
               "cross_run": {"status": "missing", "metrics": None, "reason": "Only one real ETTh1 checkpoint is available."}}
    catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    manifest = {"run_id": run_id, "status": "complete", "phase": catalog["phase"], "dataset": dataset_name,
                "case_count": len(evidence_records), "real_forward_groups": len(grouped),
                "config_path": str(config_path), "config_sha256": sha256(config_path),
                "registry_sha256": sha256(registry_path), "checkpoint_sha256": sha256(checkpoint), "data_sha256": sha256(data_path),
                "intervention_catalog_run_id": config["intervention_catalog_run_id"],
                "evidence_catalog": str(catalog_path.relative_to(run_dir)), "evidence_catalog_sha256": sha256(catalog_path),
                "raw_prediction_groups": raw_group_manifests,
                "cross_run": catalog["cross_run"]}
    command = f"python -m dgraudit.cli.precompute_evidence_catalog --config {args.config} --registry {args.registry} --output-root {args.output_root}\n"
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "command.txt").write_text(command, encoding="utf-8")
    (run_dir / "environment.json").write_text(json.dumps({"python": platform.python_version(), "torch": torch.__version__,
        "numpy": np.__version__, "cuda": torch.version.cuda, "cuda_available": torch.cuda.is_available()}, indent=2), encoding="utf-8")
    (run_dir / "stdout.log").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (run_dir / "stderr.log").write_text("", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

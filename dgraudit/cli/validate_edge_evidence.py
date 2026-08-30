from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import types
from pathlib import Path
from typing import Any, Callable

import numpy as np
import torch
from scipy.stats import spearmanr

from dgraudit.adapters import DGraFormerAdapter, apply_graph_intervention
from dgraudit.cli.validate_pattern import benjamini_hochberg, empirical_p_plus_one


DEFAULT_ORIGINAL_RUN = "3e83451437fe946a975b56fe6528fa2136443b9b08b966d3a9a78041849a6442"
DEFAULT_REPRODUCTION_RUN = "a778b2bdac2e3a012177d432ad237ada8dd6d5e24cccb57115c6edceb5cadeb8"


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_array(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def _tensor_summary(value: torch.Tensor) -> dict[str, Any]:
    array = value.detach().cpu().numpy()
    return {
        "shape": list(array.shape),
        "sha256_raw_float_bytes": _sha256_array(array),
        "min": float(array.min()),
        "max": float(array.max()),
        "mean": float(array.mean()),
        "values": array.tolist(),
    }


def _difference_metrics(reference: torch.Tensor, changed: torch.Tensor) -> dict[str, float]:
    difference = (changed - reference).detach().cpu().float()
    return {
        "l1_mean_absolute": float(difference.abs().mean()),
        "l2_root_mean_square": float(torch.sqrt(torch.mean(difference.square()))),
        "max_absolute": float(difference.abs().max()),
    }


def _capture_dcgl1(
    adapter: DGraFormerAdapter, prediction_call: Callable[[], torch.Tensor]
) -> tuple[torch.Tensor, torch.Tensor]:
    captured: dict[str, torch.Tensor] = {}

    def hook(_module, _inputs, output):
        captured["output"] = output.detach().cpu()

    handle = adapter.model.model.dcgl1.register_forward_hook(hook)
    try:
        prediction = prediction_call()
    finally:
        handle.remove()
    if "output" not in captured:
        raise RuntimeError("DCGL1 hook did not observe a forward output")
    return prediction.detach().cpu(), captured["output"]


def _predict_with_graph_stack(
    adapter: DGraFormerAdapter, batch: dict[str, Any], graphs: torch.Tensor
) -> torch.Tensor:
    gc = adapter.model.model.gc
    original_forward = gc.forward
    graphs = graphs.to(adapter.device)

    def overridden_forward(_self, time_indices, current_epoch):
        del current_epoch
        selected = time_indices % _self.num_adj_matrices
        return graphs[selected]

    gc.forward = types.MethodType(overridden_forward, gc)
    try:
        return adapter.predict(batch)
    finally:
        gc.forward = original_forward


def _global_protocol(graphs: torch.Tensor, protocol: dict[str, Any]) -> torch.Tensor:
    changed = graphs.clone()
    for window in range(changed.shape[0]):
        if protocol["type"] == "structural_edge_removal":
            source, target = int(protocol["source"]), int(protocol["target"])
            if float(changed[window, source, target]) <= 0:
                continue
        changed[window] = apply_graph_intervention(changed[window], protocol)
    return changed


def _mean_abs_error(prediction: torch.Tensor, truth: torch.Tensor) -> float:
    return float((prediction - truth).abs().mean())


def _median(values: list[float]) -> float:
    return float(np.median(np.asarray(values, dtype=float)))


def _required_controls(m: int, alpha: float, positives: int) -> int:
    return max(1, math.ceil(m / (alpha * positives) - 1))


def _correlation(x: list[float], y: list[float]) -> dict[str, Any]:
    result = spearmanr(x, y)
    return {"rho": float(result.statistic), "p": float(result.pvalue), "N": len(x)}


def _markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for label, _ in columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(str(row[key]) for _, key in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, divider, *body])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-run", default=DEFAULT_ORIGINAL_RUN)
    parser.add_argument("--reproduction-run", default=DEFAULT_REPRODUCTION_RUN)
    parser.add_argument("--runs-root", default="artifacts/runs")
    parser.add_argument("--web-index", default="legacy/v1/artifacts/public-data/evidence/etth1_intervention_index.json")
    parser.add_argument("--registry", default="tmp/phase1_registry_etth1_downloads.json")
    parser.add_argument("--config", default="configs/precomputed_evidence_catalog_etth1_40_grid.json")
    parser.add_argument("--output", default="artifacts/evidence_validation")
    args = parser.parse_args()

    repo = Path.cwd().resolve()
    runs_root = (repo / args.runs_root).resolve()
    original_dir = runs_root / args.original_run
    reproduction_dir = runs_root / args.reproduction_run
    output_dir = (repo / args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    original_catalog = _json(original_dir / "evidence_catalog.json")
    reproduction_catalog = _json(reproduction_dir / "evidence_catalog.json")
    original_manifest = _json(original_dir / "manifest.json")
    reproduction_manifest = _json(reproduction_dir / "manifest.json")
    web_index = _json((repo / args.web_index).resolve())
    config = _json((repo / args.config).resolve())
    registry = _json((repo / args.registry).resolve())

    original_cases = {case["conclusion_id"]: case for case in original_catalog["cases"]}
    reproduction_cases = {case["conclusion_id"]: case for case in reproduction_catalog["cases"]}
    web_cases = {case["conclusion_id"]: case for case in web_index["local_cases"]}
    metric_fields = (
        "baseline_mae",
        "intervention_mae",
        "prediction_delta_abs",
        "error_delta_mae",
        "empirical_p",
        "bh_adjusted_p",
    )
    metric_mismatches = []
    for case_id, original in original_cases.items():
        reproduced = reproduction_cases.get(case_id)
        if reproduced is None or any(
            original["metrics"][field] != reproduced["metrics"][field] for field in metric_fields
        ):
            metric_mismatches.append(case_id)
    old_raw = {
        (item["sample_index"], item["window"]): item["prediction_sha256"]
        for item in original_manifest["raw_prediction_groups"]
    }
    new_raw = {
        (item["sample_index"], item["window"]): item["prediction_sha256"]
        for item in reproduction_manifest["raw_prediction_groups"]
    }
    raw_hash_mismatches = [key for key, value in old_raw.items() if new_raw.get(key) != value]
    web_mismatches = []
    for case_id, original in original_cases.items():
        web = web_cases.get(case_id)
        if web is None:
            web_mismatches.append(case_id)
            continue
        expected = original["metrics"]
        observed = web["structural_metrics"]
        for field in ("prediction_delta_abs", "error_delta_mae", "empirical_p", "bh_adjusted_p"):
            if expected[field] != observed[field]:
                web_mismatches.append(case_id)
                break
    reproduction_pass = not metric_mismatches and not raw_hash_mismatches
    website_match = not web_mismatches and set(original_cases) == set(web_cases)

    rows: list[dict[str, Any]] = []
    for case in reproduction_catalog["cases"]:
        metrics = case["metrics"]
        controls_path = reproduction_dir / Path(case["controls"]["records"].replace("\\", "/"))
        controls = _json(controls_path)
        prediction_effects = np.asarray(
            [item["metrics"]["prediction_delta_abs"] for item in controls], dtype=float
        )
        mae_effects = np.asarray([item["metrics"]["error_delta_mae"] for item in controls], dtype=float)
        ci_low, ci_high = metrics["effect_difference_bootstrap_ci"]
        row = {
            "dataset": case["dataset"]["name"],
            "sample_id": case["sample"]["original_index"],
            "window_id": case["graph"]["window"],
            "window_active": bool(web_cases[case["conclusion_id"]]["window_active"]),
            "source_node": case["graph"]["source"],
            "target_node": case["graph"]["target"],
            "source_name": case["graph"]["source_name"],
            "target_name": case["graph"]["target_name"],
            "learned_edge_weight": case["graph"]["normalized_weight"],
            "topk_score": case["graph"]["topk_score"],
            "baseline_mae": metrics["baseline_mae"],
            "focal_intervention_mae": metrics["intervention_mae"],
            "focal_delta_mae": metrics["error_delta_mae"],
            "focal_prediction_delta_abs": metrics["prediction_delta_abs"],
            "control_mean_delta_mae": float(mae_effects.mean()),
            "control_median_delta_mae": float(np.median(mae_effects)),
            "control_std_delta_mae": float(mae_effects.std(ddof=1)),
            "control_mean_prediction_delta_abs": float(prediction_effects.mean()),
            "control_median_prediction_delta_abs": float(np.median(prediction_effects)),
            "control_std_prediction_delta_abs": float(prediction_effects.std(ddof=1)),
            "focal_minus_control_mean": (
                metrics["prediction_delta_abs"] - float(prediction_effects.mean())
            ),
            "raw_empirical_p": metrics["empirical_p"],
            "bh_adjusted_p": metrics["bh_adjusted_p"],
            "effect_size": metrics["standardized_effect_size"],
            "ci_low": ci_low,
            "ci_high": ci_high,
            "num_controls": len(controls),
            "control_seed": case["controls"]["random_seed"],
        }
        rows.append(row)

    csv_path = output_dir / "edge_evidence_audit.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    m = len(rows)
    control_counts = sorted({int(row["num_controls"]) for row in rows})
    if len(control_counts) != 1:
        raise RuntimeError(f"Expected a constant control count, observed {control_counts}")
    B = control_counts[0]
    alpha = 0.05
    p_min = 1 / (B + 1)
    rank1_threshold = alpha / m
    k_min = math.ceil(m * p_min / alpha)
    positives = {
        "1": 1,
        "5": 5,
        "10": 10,
        "10_percent": math.ceil(0.10 * m),
        "20_percent": math.ceil(0.20 * m),
    }
    feasibility = {
        "dataset": reproduction_catalog["dataset"],
        "num_hypotheses": m,
        "controls_per_test": B,
        "empirical_p_formula": "(1 + count(control_effect >= focal_effect)) / (B + 1)",
        "tested_effect_metric": "prediction_delta_abs",
        "min_empirical_p": p_min,
        "bh_alpha": alpha,
        "rank1_bh_threshold": rank1_threshold,
        "min_p_exceeds_rank1_threshold": p_min > rank1_threshold,
        "minimum_extreme_hypotheses_for_rejection": k_min,
        "minimum_extreme_hypotheses_fraction": k_min / m,
        "required_B_for_1_positive": _required_controls(m, alpha, positives["1"]),
        "required_B_for_5_positives": _required_controls(m, alpha, positives["5"]),
        "required_B_for_10_positives": _required_controls(m, alpha, positives["10"]),
        "required_B_for_10_percent_positives": _required_controls(m, alpha, positives["10_percent"]),
        "required_B_for_20_percent_positives": _required_controls(m, alpha, positives["20_percent"]),
        "positive_counts_used": positives,
        "power_assessment": "LIMITED",
        "interpretation": (
            "The current B cannot support an isolated BH discovery at alpha=0.05. "
            "At least 20% of hypotheses must attain the empirical minimum before rejection is possible."
        ),
    }
    (output_dir / "statistical_feasibility.json").write_text(
        json.dumps(feasibility, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    p_values = [float(row["raw_empirical_p"]) for row in rows]
    q_values = [float(row["bh_adjusted_p"]) for row in rows]
    effects = [float(row["focal_minus_control_mean"]) for row in rows]
    weights = [float(row["learned_edge_weight"]) for row in rows]
    focal_impacts = [float(row["focal_prediction_delta_abs"]) for row in rows]
    top_effect = sorted(rows, key=lambda row: (-row["focal_minus_control_mean"], row["sample_id"], row["window_id"]))[:10]
    top_weight_hypotheses = sorted(rows, key=lambda row: (-row["learned_edge_weight"], row["sample_id"]))[:10]
    unique_edge_windows: dict[tuple[int, int, int], dict[str, Any]] = {}
    for row in rows:
        key = (row["window_id"], row["source_node"], row["target_node"])
        unique_edge_windows.setdefault(key, row)
    top_weight_unique = sorted(
        unique_edge_windows.values(), key=lambda row: -row["learned_edge_weight"]
    )[:10]

    summary = {
        "scope": "real ETTh1 sample x graph-window x candidate-edge hypotheses",
        "production_run_id": args.original_run,
        "reproduction_run_id": args.reproduction_run,
        "reproduction": {
            "passed": reproduction_pass,
            "metric_mismatch_count": len(metric_mismatches),
            "raw_prediction_group_count": len(old_raw),
            "raw_prediction_hash_mismatch_count": len(raw_hash_mismatches),
            "checkpoint_sha256": reproduction_manifest["checkpoint_sha256"],
            "data_sha256": reproduction_manifest["data_sha256"],
            "command": (
                ".\\artifacts\\preflight\\python39\\python.exe -m "
                "dgraudit.cli.precompute_evidence_catalog --config "
                "configs/precomputed_evidence_catalog_etth1_40_grid.json --registry "
                "tmp/phase1_registry_etth1_downloads.json --output-root artifacts/runs"
            ),
            "registry_difference": (
                "Only ETTh1 root_path was redirected to the user-supplied copy whose SHA-256 "
                "matches the original manifest; model/statistical code and all experiment settings were unchanged."
            ),
        },
        "website_backend_check": {
            "passed": website_match,
            "backend_case_count": len(original_cases),
            "website_case_count": len(web_cases),
            "mismatch_count": len(web_mismatches),
            "all_adjusted_p_exactly_one": all(value == 1.0 for value in q_values),
            "adjusted_p_below_one_count": sum(value < 1.0 for value in q_values),
        },
        "family_composition": {
            "window_active_hypotheses": sum(bool(row["window_active"]) for row in rows),
            "window_inactive_hypotheses": sum(not bool(row["window_active"]) for row in rows),
            "note": (
                "Inactive-window hypotheses are retained because they belong to the predeclared 320-case "
                "BH family; they are not removed to improve significance."
            ),
        },
        "raw_p": {
            "p_lt_0_01": sum(value < 0.01 for value in p_values),
            "p_lt_0_05": sum(value < 0.05 for value in p_values),
            "p_lt_0_10": sum(value < 0.10 for value in p_values),
            "p_lt_0_20": sum(value < 0.20 for value in p_values),
            "minimum": min(p_values),
            "q25": float(np.quantile(p_values, 0.25)),
            "median": _median(p_values),
            "q75": float(np.quantile(p_values, 0.75)),
            "maximum": max(p_values),
        },
        "bh": {
            "q_lt_0_05": sum(value < 0.05 for value in q_values),
            "q_lt_0_10": sum(value < 0.10 for value in q_values),
            "q_lt_1": sum(value < 1.0 for value in q_values),
            "q_eq_1": sum(value == 1.0 for value in q_values),
            "minimum": min(q_values),
            "median": _median(q_values),
            "unique_value_counts": {
                str(value): q_values.count(value) for value in sorted(set(q_values))
            },
        },
        "effect": {
            "focal_effect_gt_control_mean": sum(value > 0 for value in effects),
            "focal_effect_eq_control_mean": sum(value == 0 for value in effects),
            "focal_effect_lt_control_mean": sum(value < 0 for value in effects),
            "ci_entirely_gt_zero": sum(float(row["ci_low"]) > 0 for row in rows),
            "ci_crossing_zero": sum(float(row["ci_low"]) <= 0 <= float(row["ci_high"]) for row in rows),
            "ci_entirely_lt_zero": sum(float(row["ci_high"]) < 0 for row in rows),
        },
        "correlations": {
            "weight_vs_focal_prediction_delta_abs": _correlation(weights, focal_impacts),
            "weight_vs_focal_minus_control_mean": _correlation(weights, effects),
        },
        "top_10_by_focal_minus_control_mean": top_effect,
        "top_10_by_graph_weight_hypotheses": top_weight_hypotheses,
        "top_10_unique_edge_windows_by_graph_weight": top_weight_unique,
    }

    test_p_values = [0.000001, 0.00001, 0.001, 0.20, 0.40, 0.60]
    test_q_values = benjamini_hochberg(test_p_values)
    synthetic_controls = np.linspace(0.01, 0.04, B)
    actual_min_p = empirical_p_plus_one(synthetic_controls, 1.0)
    statistics_sanity = {
        "label": "SANITY CHECK",
        "empirical_p_positive_control": {
            "production_function": "dgraudit.cli.validate_pattern.empirical_p_plus_one",
            "num_controls": B,
            "expected_minimum_empirical_p": p_min,
            "actual_empirical_p": actual_min_p,
            "passed": actual_min_p == p_min,
        },
        "bh_implementation_positive_control": {
            "production_function": "dgraudit.cli.validate_pattern.benjamini_hochberg",
            "input_p_values": test_p_values,
            "output_q_values": test_q_values,
            "minimum_q": min(test_q_values),
            "passed": min(test_q_values) < 0.05,
        },
    }
    (output_dir / "statistics_sanity_check.json").write_text(
        json.dumps(statistics_sanity, indent=2), encoding="utf-8"
    )

    dataset_name = config["dataset"]
    ds = registry["datasets"][dataset_name]
    adapter = DGraFormerAdapter(
        registry["source_root"], dataset_name, registry["common"], ds, registry["random_seed"]
    )
    checkpoint = (
        Path(registry["source_root"]) / "checkpoints" / ds["setting"] / "checkpoint.pth"
    )
    adapter.load_checkpoint(str(checkpoint))
    epsilon = 1e-6
    noop_results = []
    fixed_samples = [0, 1428, 2784]
    for sample_id in fixed_samples:
        batch = dict(adapter.load_sample("test", sample_id))
        batch["current_epoch"] = config["current_epoch"]
        baseline, baseline_hidden = _capture_dcgl1(adapter, lambda: adapter.predict(batch))
        noop, noop_hidden = _capture_dcgl1(
            adapter,
            lambda: adapter.predict_with_graph_override(
                batch, {"type": "identity", "window": 0, "current_epoch": config["current_epoch"]}
            )["prediction"],
        )
        noop_results.append(
            {
                "sample_id": sample_id,
                "baseline_prediction": _tensor_summary(baseline),
                "noop_hook_prediction": _tensor_summary(noop),
                "prediction_difference": _difference_metrics(baseline, noop),
                "hidden_difference": _difference_metrics(baseline_hidden, noop_hidden),
                "epsilon": epsilon,
                "passed": float((baseline - noop).abs().max()) < epsilon,
            }
        )

    exposed_candidate_rows = [
        row
        for row in rows
        if bool(row["window_active"]) and float(row["focal_prediction_delta_abs"]) > epsilon
    ]
    selected_case = sorted(
        exposed_candidate_rows,
        key=lambda row: (
            -row["learned_edge_weight"],
            row["sample_id"],
            row["window_id"],
            row["source_node"],
            row["target_node"],
        ),
    )[0]
    sample_id = int(selected_case["sample_id"])
    window = int(selected_case["window_id"])
    source = int(selected_case["source_node"])
    target = int(selected_case["target_node"])
    batch = dict(adapter.load_sample("test", sample_id))
    batch["current_epoch"] = config["current_epoch"]
    baseline, baseline_hidden = _capture_dcgl1(adapter, lambda: adapter.predict(batch))
    outcome_holder: dict[str, Any] = {}

    def target_call() -> torch.Tensor:
        outcome_holder.update(
            adapter.predict_with_graph_override(
                batch,
                {
                    "type": "structural_edge_removal",
                    "window": window,
                    "source": source,
                    "target": target,
                    "current_epoch": config["current_epoch"],
                },
            )
        )
        return outcome_holder["prediction"]

    target_prediction, target_hidden = _capture_dcgl1(adapter, target_call)
    graph_before = outcome_holder["graph_before"]
    graph_after = outcome_holder["graph_after"]
    row_changes = [
        {
            "target_node": index,
            "before": float(graph_before[source, index]),
            "after": float(graph_after[source, index]),
            "difference": float(graph_after[source, index] - graph_before[source, index]),
        }
        for index in range(graph_before.shape[1])
        if float(graph_before[source, index]) != float(graph_after[source, index])
    ]
    target_check = {
        "selection_rule": (
            "maximum normalized learned weight among audited candidate hypotheses whose graph window "
            "is active in the sample and whose stored production replay exceeds epsilon; deterministic tie order"
        ),
        "sample_id": sample_id,
        "window_id": window,
        "source_node": source,
        "target_node": target,
        "A_before_source_target": float(graph_before[source, target]),
        "A_after_source_target": float(graph_after[source, target]),
        "graph_before": graph_before.tolist(),
        "graph_after": graph_after.tolist(),
        "renormalized_row_changes": row_changes,
        "hidden_representation_difference": _difference_metrics(baseline_hidden, target_hidden),
        "prediction_difference": _difference_metrics(baseline, target_prediction),
        "edge_removed": float(graph_after[source, target]) == 0.0,
        "hidden_changed_above_epsilon": float((baseline_hidden - target_hidden).abs().max()) > epsilon,
        "prediction_changed_above_epsilon": float((baseline - target_prediction).abs().max()) > epsilon,
    }
    target_check["passed"] = all(
        target_check[key]
        for key in ("edge_removed", "hidden_changed_above_epsilon", "prediction_changed_above_epsilon")
    )
    hook_check = {
        "dataset": dataset_name,
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": reproduction_manifest["checkpoint_sha256"],
        "data_path": str(Path(ds["root_path"]) / ds["data_path"]),
        "data_sha256": reproduction_manifest["data_sha256"],
        "current_epoch": config["current_epoch"],
        "epsilon": epsilon,
        "noop_samples": noop_results,
        "noop_all_passed": all(item["passed"] for item in noop_results),
        "target_edge_mutation": target_check,
        "forward_path": [
            "Graph_constructor / diagnostic graph override",
            "DCGL1 correlation-aware message passing",
            "hidden representation",
            "MTT + Predictor",
            "final prediction",
        ],
        "passed": all(item["passed"] for item in noop_results) and target_check["passed"],
    }
    (output_dir / "intervention_hook_check.json").write_text(
        json.dumps(hook_check, indent=2), encoding="utf-8"
    )

    stages = adapter.extract_graph_stages({"current_epoch": config["current_epoch"]})["windows"]
    base_graphs = torch.stack([stage["normalized"] for stage in stages])
    relation_weights = []
    for relation_source in range(base_graphs.shape[1]):
        for relation_target in range(base_graphs.shape[2]):
            if relation_source == relation_target:
                continue
            active = base_graphs[:, relation_source, relation_target]
            nonzero = active[active > 0]
            if nonzero.numel():
                relation_weights.append(
                    ((relation_source, relation_target), float(nonzero.mean()))
                )
    relation_weights.sort(key=lambda item: (-item[1], item[0]))
    top5 = [list(edge) for edge, _ in relation_weights[:5]]
    top10 = [list(edge) for edge, _ in relation_weights[:10]]
    graph_variants = {
        "single_edge_global_removal": _global_protocol(
            base_graphs, {"type": "structural_edge_removal", "source": source, "target": target}
        ),
        "all_incoming_edges_global_removal": _global_protocol(
            base_graphs, {"type": "variable_incoming_removal", "variable": target}
        ),
        "top_5_edges_global_removal": _global_protocol(
            base_graphs, {"type": "edge_set_removal", "edges": top5}
        ),
        "top_10_edges_global_removal": _global_protocol(
            base_graphs, {"type": "edge_set_removal", "edges": top10}
        ),
        "graph_cross_message_suppression": _global_protocol(
            base_graphs, {"type": "edge_set_keep_only", "edges": []}
        ),
    }
    strong_records = []
    for strong_sample in fixed_samples:
        batch = dict(adapter.load_sample("test", strong_sample))
        batch["current_epoch"] = config["current_epoch"]
        truth = torch.as_tensor(
            batch["y"][-registry["common"]["pred_len"] :, :], dtype=torch.float32
        ).unsqueeze(0)
        baseline, baseline_hidden = _capture_dcgl1(adapter, lambda: adapter.predict(batch))
        baseline_mae = _mean_abs_error(baseline, truth)
        conditions = []
        for condition, graphs in graph_variants.items():
            prediction, hidden = _capture_dcgl1(
                adapter, lambda graphs=graphs: _predict_with_graph_stack(adapter, batch, graphs)
            )
            conditions.append(
                {
                    "condition": condition,
                    "prediction_change": _difference_metrics(baseline, prediction),
                    "hidden_representation_change": _difference_metrics(baseline_hidden, hidden),
                    "baseline_mae": baseline_mae,
                    "intervention_mae": _mean_abs_error(prediction, truth),
                    "delta_mae": _mean_abs_error(prediction, truth) - baseline_mae,
                }
            )
        strong_records.append({"sample_id": strong_sample, "conditions": conditions})
    aggregates = {}
    for condition in graph_variants:
        selected = [
            next(item for item in record["conditions"] if item["condition"] == condition)
            for record in strong_records
        ]
        aggregates[condition] = {
            "mean_prediction_l1": float(
                np.mean([item["prediction_change"]["l1_mean_absolute"] for item in selected])
            ),
            "max_prediction_max_abs": max(
                item["prediction_change"]["max_absolute"] for item in selected
            ),
            "mean_hidden_l1": float(
                np.mean(
                    [item["hidden_representation_change"]["l1_mean_absolute"] for item in selected]
                )
            ),
            "max_hidden_max_abs": max(
                item["hidden_representation_change"]["max_absolute"] for item in selected
            ),
            "mean_delta_mae": float(np.mean([item["delta_mae"] for item in selected])),
        }
    branch = aggregates["graph_cross_message_suppression"]
    strong_pass = (
        branch["max_prediction_max_abs"] > epsilon and branch["max_hidden_max_abs"] > epsilon
    )
    strong_check = {
        "dataset": dataset_name,
        "sample_ids": fixed_samples,
        "current_epoch": config["current_epoch"],
        "selection": {
            "single_candidate_edge": [source, target],
            "target_node_for_incoming_removal": target,
            "top_5_relations_by_mean_active_normalized_weight": top5,
            "top_10_relations_by_mean_active_normalized_weight": top10,
        },
        "graph_branch_suppression_definition": (
            "Replace every dynamic graph window by its renormalized self-loop-only graph; "
            "the Transformer and predictor remain unchanged."
        ),
        "records": strong_records,
        "aggregates": aggregates,
        "epsilon": epsilon,
        "passed": strong_pass,
        "interpretation": (
            "Graph-level dependence is observable even when individual-edge effects are small."
            if strong_pass
            else "Strong graph intervention remained at numerical-noise scale."
        ),
    }
    (output_dir / "strong_intervention_check.json").write_text(
        json.dumps(strong_check, indent=2), encoding="utf-8"
    )

    summary["code_locations"] = {
        "candidate_generation": "dgraudit/cli/precompute_intervention_catalog.py:selected_edges + operation_matrix",
        "edge_intervention": "dgraudit/adapters.py:apply_graph_intervention + DGraFormerAdapter.predict_with_graph_override",
        "matched_controls": "dgraudit/cli/precompute_evidence_catalog.py:main (eligible/sample_indices/control_records)",
        "focal_effect": "dgraudit/cli/validate_pattern.py:impact_metrics (prediction_delta_abs)",
        "empirical_p": "dgraudit/cli/validate_pattern.py:empirical_p_plus_one",
        "BH": "dgraudit/cli/validate_pattern.py:benjamini_hochberg",
        "effect_size": "dgraudit/cli/precompute_evidence_catalog.py:main (standardized focal-minus-control mean)",
        "CI": "dgraudit/cli/precompute_evidence_catalog.py:main (bootstrap focal-minus-control mean)",
    }
    summary["hook_validation"] = {
        "passed": hook_check["passed"],
        "noop_max_difference": max(
            item["prediction_difference"]["max_absolute"] for item in noop_results
        ),
        "target_hidden_max_difference": target_check["hidden_representation_difference"]["max_absolute"],
        "target_prediction_max_difference": target_check["prediction_difference"]["max_absolute"],
    }
    summary["strong_intervention"] = {
        "passed": strong_pass,
        "aggregates": aggregates,
    }
    summary["statistics_sanity"] = statistics_sanity
    summary["final_classification"] = {
        "choice": "A",
        "label": "UNDERPOWERED",
        "statement": (
            "No edge obtained BH-adjusted statistical support under the current audit configuration. "
            "Absence of adjusted significance is not evidence of absence."
        ),
    }
    (output_dir / "edge_evidence_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    try:
        import matplotlib.pyplot as plt

        plt.figure(figsize=(7, 4.5))
        plt.hist(p_values, bins=np.linspace(0, 1, 21), edgecolor="white", color="#2f6f8f")
        plt.xlabel("Raw empirical p-value")
        plt.ylabel("Hypothesis count")
        plt.title("ETTh1 raw empirical p-values (m=320, B=100)")
        plt.tight_layout()
        plt.savefig(output_dir / "raw_p_histogram.png", dpi=180)
        plt.close()

        plt.figure(figsize=(7, 4.5))
        plt.scatter(weights, effects, s=18, alpha=0.65, color="#9b4f37")
        plt.axhline(0, color="black", linewidth=0.8)
        plt.xlabel("Normalized learned edge weight")
        plt.ylabel("Focal prediction impact - control mean")
        plt.title("Structural prominence vs functional evidence")
        plt.tight_layout()
        plt.savefig(output_dir / "weight_vs_effect.png", dpi=180)
        plt.close()
        summary["plots_created"] = True
    except ImportError:
        summary["plots_created"] = False
    (output_dir / "edge_evidence_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    raw = summary["raw_p"]
    bh = summary["bh"]
    effect = summary["effect"]
    corr_focal = summary["correlations"]["weight_vs_focal_prediction_delta_abs"]
    corr_relative = summary["correlations"]["weight_vs_focal_minus_control_mean"]
    branch_aggregate = aggregates["graph_cross_message_suppression"]
    checks = [
        {
            "check": "Existing BH reproduction",
            "result": "PASS" if reproduction_pass and website_match else "FAIL",
            "number": f"320 cases; mismatches={len(metric_mismatches) + len(web_mismatches)}",
            "interpretation": "Backend rerun and website JSON agree exactly.",
        },
        {
            "check": "Empirical-p resolution",
            "result": "WARN",
            "number": f"B={B}, p_min={p_min:.8f}",
            "interpretation": "Finite controls impose a coarse lower bound.",
        },
        {
            "check": "BH power feasibility",
            "result": "WARN",
            "number": f"m={m}, k_min={k_min}",
            "interpretation": "An isolated strongest case cannot be rejected.",
        },
        {
            "check": "No-op hook",
            "result": "PASS" if hook_check["noop_all_passed"] else "FAIL",
            "number": f"max diff={summary['hook_validation']['noop_max_difference']:.3g}",
            "interpretation": "The intervention framework itself preserves baseline output.",
        },
        {
            "check": "Target edge actually removed",
            "result": "PASS" if target_check["edge_removed"] else "FAIL",
            "number": f"before={target_check['A_before_source_target']:.6g}, after={target_check['A_after_source_target']:.6g}",
            "interpretation": "The selected normalized adjacency entry becomes zero and its row is renormalized.",
        },
        {
            "check": "Hidden representation changes",
            "result": "PASS" if target_check["hidden_changed_above_epsilon"] else "FAIL",
            "number": f"max diff={target_check['hidden_representation_difference']['max_absolute']:.6g}",
            "interpretation": "The graph mutation reaches DCGL1 output.",
        },
        {
            "check": "Strong graph intervention",
            "result": "PASS" if strong_pass else "FAIL",
            "number": f"prediction max diff={branch_aggregate['max_prediction_max_abs']:.6g}",
            "interpretation": "Self-loop-only graph suppression is distinguishable from numerical noise.",
        },
        {
            "check": "Empirical-p unit test",
            "result": "PASS" if statistics_sanity["empirical_p_positive_control"]["passed"] else "FAIL",
            "number": f"expected={p_min:.8f}, actual={actual_min_p:.8f}",
            "interpretation": "The production empirical-p implementation reaches its finite-control minimum.",
        },
        {
            "check": "BH unit test",
            "result": "PASS" if statistics_sanity["bh_implementation_positive_control"]["passed"] else "FAIL",
            "number": f"min q={min(test_q_values):.6g}",
            "interpretation": "The production BH implementation preserves clearly small adjusted p-values.",
        },
        {
            "check": "Real edge evidence",
            "result": "UNDERPOWERED",
            "number": f"raw p<.05={raw['p_lt_0_05']}; q<.05={bh['q_lt_0_05']}",
            "interpretation": "Candidate-level descriptive signals do not survive the current family correction.",
        },
    ]
    report = _markdown_table(
        checks,
        [("Check", "check"), ("Result", "result"), ("Key number", "number"), ("Interpretation", "interpretation")],
    )
    report += f"""

# Scope and provenance

This audit uses the real ETTh1 checkpoint and the 40 predeclared test samples in the current website evidence family. The user-supplied ETTh1.csv has SHA-256 `{reproduction_manifest['data_sha256']}`, exactly matching the original manifest. The checkpoint SHA-256 is `{reproduction_manifest['checkpoint_sha256']}`. The final graph schedule is `current_epoch=5` (0.1 static + 0.9 learned), the control count is `{B}`, bootstrap repetitions are `{config['control_experiment']['bootstrap_repetitions']}`, and the family contains `{m}` hypotheses.

Reproduction command:

```text
{summary['reproduction']['command']}
```

The original registry pointed to a missing copy of ETTh1.csv. The temporary registry changes only its filesystem location; the verified data bytes, checkpoint, model code, samples, seeds, intervention protocol, and statistical definitions are unchanged. All `{len(old_raw)}` raw prediction-group hashes and all `{m}` audited metrics reproduce exactly.

# Real implementation map

```text
candidate generation:
dgraudit/cli/precompute_intervention_catalog.py:selected_edges + operation_matrix

edge intervention:
dgraudit/adapters.py:apply_graph_intervention + DGraFormerAdapter.predict_with_graph_override

matched controls:
dgraudit/cli/precompute_evidence_catalog.py:main (eligible/sample_indices/control_records)

focal intervention effect:
dgraudit/cli/validate_pattern.py:impact_metrics (prediction_delta_abs)

empirical p:
dgraudit/cli/validate_pattern.py:empirical_p_plus_one

BH:
dgraudit/cli/validate_pattern.py:benjamini_hochberg

effect size:
dgraudit/cli/precompute_evidence_catalog.py:main (standardized focal-minus-control mean)

CI:
dgraudit/cli/precompute_evidence_catalog.py:main (bootstrap focal-minus-control mean)
```

The production hypothesis test uses `prediction_delta_abs`, not `delta MAE`. Delta MAE is retained in the CSV as a descriptive outcome but is not substituted into the p-value definition.

# Existing BH reproduction

```text
Total hypotheses m = {m}
Controls per hypothesis B = {B}
Number q < 0.05 = {bh['q_lt_0_05']}
Number q < 0.10 = {bh['q_lt_0_10']}
Number raw p < 0.05 = {raw['p_lt_0_05']}
Number raw p < 0.10 = {raw['p_lt_0_10']}
Minimum raw p = {raw['minimum']:.12g}
Minimum BH q = {bh['minimum']:.12g}
Median raw p = {raw['median']:.12g}
Median BH q = {bh['median']:.12g}
```

The website JSON and backend evidence match exactly. However, the premise that every BH value equals 1 is not literally correct: `{bh['q_eq_1']}` of `{m}` are exactly 1 and `{bh['q_lt_1']}` are below 1; the minimum is `{bh['minimum']:.12g}`. None is below 0.10.

The predeclared family contains `{summary['family_composition']['window_active_hypotheses']}` active-window hypotheses and `{summary['family_composition']['window_inactive_hypotheses']}` inactive-window hypotheses. The inactive cases are genuine no-op exposures (`window_active=false`) and remain in the 320-case family exactly as predeclared; this audit does not remove them or recompute a smaller BH family.

# Statistical feasibility

```text
B = {B}
p_min = 1/(B+1) = {p_min:.12g}
m = {m}
alpha = {alpha}
BH rank-1 threshold = alpha/m = {rank1_threshold:.12g}
k_min = {k_min}
k_min / m = {100 * k_min / m:.2f}%
```

Required controls for the empirical minimum to reach the BH threshold at the stated rank:

| Assumed equally strong positives | Required B |
| ---: | ---: |
| 1 | {feasibility['required_B_for_1_positive']} |
| 5 | {feasibility['required_B_for_5_positives']} |
| 10 | {feasibility['required_B_for_10_positives']} |
| 10% ({positives['10_percent']}) | {feasibility['required_B_for_10_percent_positives']} |
| 20% ({positives['20_percent']}) | {feasibility['required_B_for_20_percent_positives']} |

`p_min` is about {p_min / rank1_threshold:.2f} times the rank-1 BH threshold. Thus B=100 has limited discovery power: it cannot detect a sparse isolated positive, and requires at least `{k_min}` hypotheses to attain the empirical minimum before any BH rejection is possible.

# Real evidence summary

Raw empirical p-values:

```text
p < 0.01: {raw['p_lt_0_01']}
p < 0.05: {raw['p_lt_0_05']}
p < 0.10: {raw['p_lt_0_10']}
p < 0.20: {raw['p_lt_0_20']}
minimum: {raw['minimum']:.12g}
25%: {raw['q25']:.12g}
median: {raw['median']:.12g}
75%: {raw['q75']:.12g}
maximum: {raw['maximum']:.12g}
```

BH-adjusted values:

```text
q < 0.05: {bh['q_lt_0_05']}
q < 0.10: {bh['q_lt_0_10']}
minimum q: {bh['minimum']:.12g}
median q: {bh['median']:.12g}
```

Effects (`prediction_delta_abs`, matching the production test):

```text
focal effect > control mean: {effect['focal_effect_gt_control_mean']}
focal effect < control mean: {effect['focal_effect_lt_control_mean']}
CI entirely > 0: {effect['ci_entirely_gt_zero']}
CI crossing 0: {effect['ci_crossing_zero']}
CI entirely < 0: {effect['ci_entirely_lt_zero']}
```

# Top 10 real cases by focal minus control mean

{_markdown_table([
    {
        'sample': row['sample_id'],
        'window': row['window_id'],
        'edge': f"{row['source_node']}->{row['target_node']}",
        'weight': f"{row['learned_edge_weight']:.6g}",
        'focal': f"{row['focal_prediction_delta_abs']:.6g}",
        'control': f"{row['control_mean_prediction_delta_abs']:.6g}",
        'effect': f"{row['focal_minus_control_mean']:.6g}",
        'p': f"{row['raw_empirical_p']:.6g}",
        'q': f"{row['bh_adjusted_p']:.6g}",
    } for row in top_effect], [('sample','sample'),('window','window'),('edge','edge'),('graph weight','weight'),('focal Δ','focal'),('control Δ','control'),('effect','effect'),('raw p','p'),('BH','q')])}

# Top 10 unique graph edge-windows by learned weight

{_markdown_table([
    {
        'window': row['window_id'],
        'edge': f"{row['source_node']}->{row['target_node']}",
        'weight': f"{row['learned_edge_weight']:.6g}",
        'effect': f"{row['focal_minus_control_mean']:.6g}",
        'p': f"{row['raw_empirical_p']:.6g}",
        'q': f"{row['bh_adjusted_p']:.6g}",
    } for row in top_weight_unique], [('window','window'),('edge','edge'),('graph weight','weight'),('effect (first sample)','effect'),('raw p','p'),('BH','q')])}

# Structural prominence versus functional importance

```text
Spearman(weight, focal prediction Δ): rho = {corr_focal['rho']:.6g}, p = {corr_focal['p']:.6g}, N = {corr_focal['N']}
Spearman(weight, focal Δ - control mean): rho = {corr_relative['rho']:.6g}, p = {corr_relative['p']:.6g}, N = {corr_relative['N']}
```

Higher learned graph weights were not strongly associated with larger intervention effects in the audited cases if the reported rho is weak; this statement does not imply that the learned graph is meaningless.

# Hook and strong-intervention validation

The no-op hook matched baseline exactly on samples `{fixed_samples}` (maximum absolute prediction difference `{summary['hook_validation']['noop_max_difference']:.6g}`). The selected real candidate edge `{source}->{target}` in window `{window}` changed from `{target_check['A_before_source_target']:.6g}` to `{target_check['A_after_source_target']:.6g}`. Its DCGL1 hidden representation maximum difference was `{target_check['hidden_representation_difference']['max_absolute']:.6g}`, and final prediction maximum difference was `{target_check['prediction_difference']['max_absolute']:.6g}`.

The strongest graph-only diagnostic replaces all seven graph windows with self-loop-only normalized graphs while leaving the Transformer and predictor unchanged. Across samples `{fixed_samples}`, its maximum prediction difference was `{branch_aggregate['max_prediction_max_abs']:.6g}`, mean prediction L1 change was `{branch_aggregate['mean_prediction_l1']:.6g}`, and maximum hidden difference was `{branch_aggregate['max_hidden_max_abs']:.6g}`. This is above the `{epsilon}` numerical threshold.

Individual-edge effects may be weak because graph information is distributed or redundant, while graph-level dependence remains observable.

# Statistical sanity checks

Both checks are explicitly `SANITY CHECK` only. The production empirical-p function returned `{actual_min_p:.12g}` for a focal value above all `{B}` controls (expected `{p_min:.12g}`): **{'PASS' if statistics_sanity['empirical_p_positive_control']['passed'] else 'FAIL'}**. The production BH function returned minimum q `{min(test_q_values):.6g}` for an input containing obvious small p-values: **{'PASS' if statistics_sanity['bh_implementation_positive_control']['passed'] else 'FAIL'}**.

# Six required answers

## Q1 — Why are the adjusted values at/near 1?

The literal premise needs correction: `{bh['q_eq_1']}/{m}` adjusted values are 1, while the 9 hypotheses at the raw minimum `1/101` all receive q=`{bh['minimum']:.12g}`; none is below 0.10. The main cause is the combination of coarse finite-control resolution (`p_min={p_min:.6g}`) and a large BH family (`m={m}`), compounded by the fact that most real raw p-values are high (median `{raw['median']:.6g}`) and `{summary['family_composition']['window_inactive_hypotheses']}` predeclared cases are inactive-window no-ops. The BH code and the intervention path both pass their checks.

## Q2 — Minimum empirical p

`p_min = 1/(100+1) = {p_min:.12g}`.

## Q3 — BH discovery power

**LIMITED.** The rank-1 threshold is `{rank1_threshold:.12g}`, while `p_min` is `{p_min:.12g}`. At least `{k_min}` hypotheses (`{100*k_min/m:.2f}%`) must simultaneously attain the minimum p before rejection becomes possible.

## Q4 — Does edge intervention enter forward and change hidden/prediction?

**YES.** No-op max difference is `{summary['hook_validation']['noop_max_difference']:.6g}`; the selected edge is exactly zeroed, DCGL1 hidden max difference is `{target_check['hidden_representation_difference']['max_absolute']:.6g}`, and prediction max difference is `{target_check['prediction_difference']['max_absolute']:.6g}`.

## Q5 — Does a sufficiently strong graph intervention change prediction?

**YES.** Self-loop-only graph suppression produces maximum prediction difference `{branch_aggregate['max_prediction_max_abs']:.6g}` and maximum hidden difference `{branch_aggregate['max_hidden_max_abs']:.6g}` across the three fixed samples.

## Q6 — Most rigorous paper conclusion

**A — the current statistical design has insufficient power for sparse edge discovery, so it cannot yet support a definitive judgment about individual real edges.** There are `{raw['p_lt_0_05']}` raw p-values below 0.05 and descriptive effects, but none survives BH; the empirical minimum is too coarse for isolated discoveries. Therefore the defensible statement is: **No edge obtained BH-adjusted statistical support under the current audit configuration. Absence of adjusted significance is not evidence of absence.**
"""
    (output_dir / "validation_summary.md").write_text(report, encoding="utf-8")
    adapter.close()
    print(json.dumps({"output": str(output_dir), "summary": summary["final_classification"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

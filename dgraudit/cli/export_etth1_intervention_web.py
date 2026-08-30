from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


def json_safe(value):
    """Preserve undefined numeric results as JSON null, never non-standard NaN."""
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        return None
    return value


def diagnostic_localization(absolute_delta, baseline_absolute_error, intervention_absolute_error, variables):
    step_impact = absolute_delta.mean(axis=1)
    positive = step_impact[step_impact > 0]
    threshold = float(np.quantile(positive, 0.75)) if positive.size else None
    marked = (step_impact >= threshold) if threshold is not None else np.zeros_like(step_impact, dtype=bool)
    intervals = []
    start = None
    for index, active in enumerate(np.append(marked, False)):
        if active and start is None:
            start = index
        elif not active and start is not None:
            segment = step_impact[start:index]
            intervals.append({
                "start_step": start + 1,
                "end_step": index,
                "peak_step": start + int(np.argmax(segment)) + 1,
                "peak_impact": float(segment.max()),
                "share_of_total_impact": float(segment.sum() / step_impact.sum()) if step_impact.sum() else 0.0,
            })
            start = None
    variable_rows = []
    for variable_index, variable in enumerate(variables):
        variable_delta = absolute_delta[:, variable_index]
        error_delta = intervention_absolute_error[:, variable_index] - baseline_absolute_error[:, variable_index]
        variable_rows.append({
            "variable": variable,
            "mean_absolute_prediction_delta": float(variable_delta.mean()),
            "max_absolute_prediction_delta": float(variable_delta.max()),
            "peak_step": int(np.argmax(variable_delta)) + 1,
            "mean_absolute_error_delta": float(error_delta.mean()),
        })
    variable_rows.sort(key=lambda row: (-row["mean_absolute_prediction_delta"], row["variable"]))
    intervals.sort(key=lambda row: (-row["share_of_total_impact"], row["start_step"]))
    return {
        "response_interval_rule": "contiguous forecast steps at or above the within-case 75th percentile of positive mean absolute prediction response",
        "response_threshold": threshold,
        "variable_ranking": variable_rows,
        "response_intervals": intervals,
    }


def window_exposure(sample_index, test_border, seq_len=96, numpoint_win=24, window_count=7):
    """Reproduce Dataset_ETT_hour time_index and DGraFormer modulo window selection."""
    indices = (np.arange(test_border + sample_index, test_border + sample_index + seq_len) // numpoint_win) % window_count
    values, counts = np.unique(indices, return_counts=True)
    return {int(window): int(count) for window, count in zip(values, counts)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-run", required=True)
    parser.add_argument("--intervention-run", required=True)
    parser.add_argument("--dataset", default="ETTh1")
    parser.add_argument("--test-border", type=int, default=11424)
    parser.add_argument("--output", default="legacy/v1/artifacts/public-data/evidence/etth1_intervention_catalog.json")
    args = parser.parse_args()
    root = Path("artifacts/runs")
    evidence_root = root / args.evidence_run
    intervention_root = root / args.intervention_run
    evidence = json.loads((evidence_root / "evidence_catalog.json").read_text(encoding="utf-8"))
    intervention = json.loads((intervention_root / f"catalog/{args.dataset}.json").read_text(encoding="utf-8"))
    if evidence["dataset"] != args.dataset or intervention["dataset"] != args.dataset:
        raise ValueError("Dataset argument does not match source catalogs")

    normalized_masks = {}
    for record in intervention["records"]:
        protocol = record["protocol"]
        if protocol["type"] != "normalized_channel_mask":
            continue
        key = (record["test_sample_index"], protocol["window"], protocol["source"], protocol["target"])
        normalized_masks[key] = record["metrics"]

    cases = []
    array_cache = {}
    for case in evidence["cases"]:
        sample = int(case["sample"]["original_index"])
        window = int(case["graph"]["window"])
        source = int(case["graph"]["source"])
        target = int(case["graph"]["target"])
        prediction_path = evidence_root / case["raw_operands"]["predictions"]
        if prediction_path not in array_cache:
            array_cache[prediction_path] = np.load(prediction_path)
        arrays = array_cache[prediction_path]
        baseline = arrays["baseline"]
        truth = arrays["truth"]
        intervention_prediction = arrays["retained_edge_predictions"][int(case["raw_operands"]["focal_prediction_row"])]
        absolute_delta = np.abs(intervention_prediction - baseline)
        baseline_absolute_error = np.abs(baseline - truth)
        intervention_absolute_error = np.abs(intervention_prediction - truth)
        key = (sample, window, source, target)
        localization = diagnostic_localization(
            absolute_delta, baseline_absolute_error, intervention_absolute_error,
            ["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL", "OT"],
        )
        exposure_counts = window_exposure(sample, args.test_border)
        cases.append({
            "conclusion_id": case["conclusion_id"],
            "sample_index": sample,
            "window": window,
            "window_active": window in exposure_counts,
            "window_exposure_count": exposure_counts.get(window, 0),
            "active_windows": sorted(exposure_counts),
            "edge": {
                "source": source, "target": target,
                "source_name": case["graph"]["source_name"],
                "target_name": case["graph"]["target_name"],
                "topk_score": case["graph"]["topk_score"],
                "normalized_weight": case["graph"]["normalized_weight"],
                "retained_edge_rank": case["graph"]["retained_edge_rank"],
            },
            "schedule": case["model"]["schedule"],
            "time_range": case["sample"],
            "structural_metrics": case["metrics"],
            "structural_metric_status": case["metric_status"],
            "channel_mask_metrics": normalized_masks[key],
            "step_impact": absolute_delta.mean(axis=1).tolist(),
            "step_error_delta": (intervention_absolute_error.mean(axis=1) - baseline_absolute_error.mean(axis=1)).tolist(),
            "variable_impact": absolute_delta.mean(axis=0).tolist(),
            "diagnostic_localization": localization,
            "baseline_prediction": baseline.tolist(),
            "intervention_prediction": intervention_prediction.tolist(),
            "ground_truth": truth.tolist(),
            "controls": case["controls"],
            "raw_operands": case["raw_operands"],
            "limitations": case["limitations"],
        })

    unique_edges = {}
    for case in cases:
        edge = case["edge"]
        key = f"{edge['source']}->{edge['target']}"
        record = unique_edges.setdefault(key, {**edge, "windows": set()})
        record["windows"].add(case["window"])
    edges = [{**record, "edge_id": key, "windows": sorted(record["windows"])}
             for key, record in sorted(unique_edges.items())]
    output = {
        "status": "complete",
        "dataset": args.dataset,
        "claim_label": "Candidate Pattern",
        "source_runs": {"intervention": args.intervention_run, "evidence": args.evidence_run},
        "schedule": {"state": "final", "current_epoch_equivalent": 5, "static_weight": 0.1, "learned_weight": 0.9},
        "variables": ["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL", "OT"],
        "samples": sorted({case["sample_index"] for case in cases}),
        "edges": edges,
        "cases": cases,
        "cross_run": evidence["cross_run"],
        "notice": f"All values are precomputed from the real {args.dataset} checkpoint. Selection retrieves stored evidence and does not rerun the model in the browser."
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(json_safe(output), ensure_ascii=False, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output_path), "cases": len(cases), "edges": len(edges)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

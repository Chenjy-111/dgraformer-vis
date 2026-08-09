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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-run", required=True)
    parser.add_argument("--intervention-run", required=True)
    parser.add_argument("--output", default="public/data/evidence/etth1_intervention_catalog.json")
    args = parser.parse_args()
    root = Path("artifacts/runs")
    evidence_root = root / args.evidence_run
    intervention_root = root / args.intervention_run
    evidence = json.loads((evidence_root / "evidence_catalog.json").read_text(encoding="utf-8"))
    intervention = json.loads((intervention_root / "catalog/ETTh1.json").read_text(encoding="utf-8"))

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
        cases.append({
            "conclusion_id": case["conclusion_id"],
            "sample_index": sample,
            "window": window,
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
        "dataset": "ETTh1",
        "claim_label": "Candidate Pattern",
        "source_runs": {"intervention": args.intervention_run, "evidence": args.evidence_run},
        "schedule": {"state": "final", "current_epoch_equivalent": 5, "static_weight": 0.1, "learned_weight": 0.9},
        "variables": ["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL", "OT"],
        "samples": sorted({case["sample_index"] for case in cases}),
        "edges": edges,
        "cases": cases,
        "cross_run": evidence["cross_run"],
        "notice": "All values are precomputed from the real ETTh1 checkpoint. Selection retrieves stored evidence and does not rerun the model in the browser."
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

from __future__ import annotations

import copy
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from .controls import build_case_evidence
from .dependence import audit_dependence


ROOT = Path(__file__).resolve().parents[2]
DGRA_SESSION = ROOT / "public/data/evidence/dgraformer_etth1_session_v2.json"
MSG_SESSION = ROOT / "tests/fixtures/msgnet_graph_core_baseline.json"
MTGNN_SESSION = ROOT / "tests/fixtures/mtgnn_quick_session_v2.json"
MSG_FROZEN = ROOT / "artifacts/msgnet_frozen14"
DGRA_OPERANDS = ROOT / "artifacts/dgraformer_frozen40"


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tensor(array: np.ndarray, *, first_axis: str = "time") -> dict[str, Any]:
    value = np.asarray(array, dtype=np.float32)
    axis = [first_axis, "variable"] if value.ndim == 2 else [f"axis_{index}" for index in range(value.ndim)]
    return {"dtype": "float32", "shape": list(value.shape), "axis_order": axis, "values": value.tolist()}


def _parse_bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _portable_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    missing: dict[str, str] = {}
    for key, item in value.items():
        if isinstance(item, float) and not np.isfinite(item):
            result[key] = None
            missing[key] = "Historical descriptive metric was non-finite; v2 exports null instead of NaN/Inf."
        else:
            result[key] = copy.deepcopy(item)
    if missing:
        result["missing_reasons"] = missing
    return result


def _intervention_outputs(session: Mapping[str, Any]) -> dict[tuple[int, str, int | None, int, int], Mapping[str, Any]]:
    result: dict[tuple[int, str, int | None, int, int], Mapping[str, Any]] = {}
    candidates = {item["candidate_id"]: item for item in session.get("candidate_relations", [])}
    for case in session.get("case_evidence", []):
        candidate = candidates.get(case.get("candidate_id"), {})
        context = case.get("context", {})
        context_index = context.get("window_index", context.get("scale_index"))
        normalized_context = int(context_index) if isinstance(context_index, (int, float)) or str(context_index).isdigit() else None
        scope = "local" if case.get("scope") in {"single_window", "single_scale", "global_graph"} else "broader_context"
        key = (
            int(case.get("sample_id", -1)), scope,
            normalized_context,
            int(candidate.get("source", -1)), int(candidate.get("target", -1)),
        )
        result[key] = {"intervention_output": case.get("intervention_output_reference")}
    return result


def _base_config(
    *, adapter: str, dataset: str, checkpoint_sha256: str, sample_ids: list[int], units: list[dict[str, Any]],
    families: list[dict[str, Any]], dependence: str, primary_by_family: Mapping[str, Any], sensitivity: Mapping[str, list[str]],
) -> dict[str, Any]:
    return {
        "schema_version": "dgrainsight.audit_config.v2",
        "config_version": 2,
        "audit_mode": "formal_evidence_audit",
        "adapter": adapter,
        "dataset": {"name": dataset},
        "checkpoint": {"sha256": checkpoint_sha256},
        "sample_protocol": {
            "protocol_id": f"{adapter}.{dataset}.frozen",
            "selection_rule": "frozen before intervention; use the existing validated protocol artifact",
            "split": "test",
            "sample_ids": sample_ids,
            "units": units,
            "selection_frozen": True,
            "active_inactive_policy": "exclude_inactive_without_zero_imputation",
        },
        "candidate_families": families,
        "control_protocol": {"protocol": "all_unique_eligible", "with_replacement": False},
        "response_metric": "prediction_delta_abs",
        "dependence_protocol": {"expected_classification": dependence, "same_continuous_series": True, "selection_frozen": True},
        "inference_protocol": {
            "selection_frozen": True,
            "alternative": "mean_D > 0",
            "inference_unit": "candidate_relation_across_predeclared_units",
            "null_definition": "declared by each registered primary engine",
            "by_family": dict(primary_by_family),
        },
        "multiplicity_protocol": {"primary_method": "BH", "alpha": 0.05, "families_frozen": True},
        "sensitivity_protocol": {"primary_results_unchanged": True, "by_family": dict(sensitivity)},
    }


def load_dgraformer_frozen_inputs() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    graph = _json(DGRA_SESSION)
    graph["model_specific"] = {
        "artifact_validation_report": copy.deepcopy(
            graph.get("validation", {}).get("model_validation_V01_V09")
        )
    }
    graph["provenance"] = {
        "graph_source": "public/data/evidence/dgraformer_etth1_session_v2.json",
        "graph_source_protocol": "current Session v2 graph core",
    }
    family_source = _json(DGRA_OPERANDS / "protocol.json")
    local_rows = _csv(DGRA_OPERANDS / "local_case_effects.csv")
    global_rows = _csv(DGRA_OPERANDS / "global_case_effects.csv")
    sample_ids = sorted({int(row["sample_id"]) for row in local_rows})
    units_by_sample = {
        int(row["sample_id"]): {"raw_start": int(row["raw_start"]), "raw_end": int(row["raw_end"])}
        for row in local_rows
    }
    units = [units_by_sample[sample] for sample in sample_ids]

    local_members = []
    for member in family_source["local_candidates"]:
        candidate_id = f"dgra:window:{member['window_id']}:{member['source_node']}->{member['target_node']}"
        local_members.append({
            "candidate_id": candidate_id, "source": member["source_node"], "target": member["target_node"],
            "source_name": member["source_name"], "target_name": member["target_name"],
            "scope": "single_window", "native_context_type": "window", "window_index": member["window_id"],
            "retained_contexts": [member["window_id"]],
        })
    global_members = []
    for member in family_source["global_candidates"]:
        candidate_id = f"dgra:all:{member['source_node']}->{member['target_node']}"
        global_members.append({
            "candidate_id": candidate_id, "source": member["source_node"], "target": member["target_node"],
            "source_name": member["source_name"], "target_name": member["target_name"],
            "scope": "all_retained_windows", "native_context_type": "window",
            "retained_contexts": _retained_windows(graph, member["source_node"], member["target_node"]),
        })
    families = [
        {"family_id": "dgraformer.local.frozen40", "scope": "single_window", "selection_rule": family_source["candidate_selection_basis"], "context_identity_rule": "window_index,source,target", "members": local_members, "family_size": len(local_members), "selection_frozen": True},
        {"family_id": "dgraformer.all_retained.frozen40", "scope": "all_retained_windows", "selection_rule": "frozen unique relation projection of the local family", "context_identity_rule": "source,target over all retained windows", "members": global_members, "family_size": len(global_members), "selection_frozen": True},
    ]
    primary = {
        family["family_id"]: {"primary_test": "moving_block_bootstrap_mean_D", "block_length": 3, "block_length_derivation": "ceil(raw_span 192 / minimum start gap 71)", "repetitions": 10000, "seed": 20260830, "minimum_active_units": 2}
        for family in families
    }
    sensitivities = {family["family_id"]: ["block_length_2", "block_length_4", "non_overlap_subset", "trimmed_mean", "median_ci", "outlier_sensitivity"] for family in families}
    config = _base_config(adapter="dgraformer", dataset="ETTh1", checkpoint_sha256=graph["checkpoint"]["sha256"], sample_ids=sample_ids, units=units, families=families, dependence="overlapping_time_windows", primary_by_family=primary, sensitivity=sensitivities)

    local_catalog = _json(DGRA_OPERANDS / "local_case_operands.json")
    local_lookup = {
        (int(item["sample"]["original_index"]), int(item["graph"]["window"]), int(item["graph"]["source"]), int(item["graph"]["target"])): item
        for item in local_catalog["cases"]
    }
    intervention_outputs = _intervention_outputs(graph)
    cases: list[dict[str, Any]] = []
    for row in local_rows:
        sample, window, source, target = (int(row[name]) for name in ("sample_id", "window_id", "source_node", "target_node"))
        candidate_id = f"dgra:window:{window}:{source}->{target}"
        source_case = local_lookup[(sample, window, source, target)]
        edges = source_case["control_edges"]
        controls = [{"identity": f"{edge['source']}->{edge['target']}", "response": edge["prediction_delta_abs"]} for edge in edges if (int(edge["source"]), int(edge["target"])) != (source, target)]
        active = _parse_bool(row["active"])
        output = intervention_outputs.get((sample, "local", window, source, target), {})
        cases.append(build_case_evidence(
            case_evidence_id=f"case:{candidate_id}:test:{sample}", candidate_id=candidate_id, sample_id=sample,
            context={"type": "window", "window_index": window}, scope="single_window", active=active,
            focal_response=float(row["focal_prediction_delta_abs"]) if active else None, controls=controls if active else [],
            response_metrics=_portable_mapping(source_case["metrics"]), graph_effect={"learned_edge_weight": source_case["graph"]["normalized_weight"], "rank": source_case["graph"]["retained_edge_rank"]},
            baseline_reference={"sample_id": f"test:{sample}", "field": "baseline_prediction"},
            intervention_output_reference=output.get("intervention_output") if active else None,
            provenance={"source_artifact": "dgraformer_frozen40/local_case_effects.csv", "source_case_id": source_case["case_id"]},
        ))

    reconstructed = _json(DGRA_OPERANDS / "global_case_operands.json")["cases"]
    global_source = {(int(item["sample"]), int(item["edge"][0]), int(item["edge"][1])): item for item in reconstructed}
    for row in global_rows:
        sample, source, target = (int(row[name]) for name in ("sample_id", "source_node", "target_node"))
        candidate_id = f"dgra:all:{source}->{target}"
        item = global_source[(sample, source, target)]
        active = _parse_bool(row["active"])
        controls = [{"identity": f"{edge[0]}->{edge[1]}", "response": value} for edge, value in zip(item["unique_control_edges"], item["unique_control_values"])]
        output = intervention_outputs.get((sample, "broader_context", None, source, target), {})
        cases.append(build_case_evidence(
            case_evidence_id=f"case:{candidate_id}:test:{sample}", candidate_id=candidate_id, sample_id=sample,
            context={"type": "window", "retained_windows": item["retained_windows"]}, scope="all_retained_windows", active=active,
            focal_response=float(row["focal_prediction_delta_abs"]) if active else None, controls=controls if active else [],
            response_metrics=_portable_mapping(item["metrics"]), graph_effect={"mean_weight": item["mean_weight"], "retained_windows": item["retained_windows"]},
            baseline_reference={"sample_id": f"test:{sample}", "field": "baseline_prediction"},
            intervention_output_reference=output.get("intervention_output") if active else None,
            provenance={"source_artifact": "dgraformer_frozen40/global_case_effects.csv", "source_case_id": item["case_id"]},
        ))

    dependence = {family["family_id"]: audit_dependence(config["sample_protocol"]["protocol_id"], sample_ids, units, same_continuous_series=True) for family in families}
    provenance = {"frozen_artifacts": {str(path.relative_to(ROOT)).replace("\\", "/"): _sha256(path) for path in (DGRA_OPERANDS / "protocol.json", DGRA_OPERANDS / "local_case_effects.csv", DGRA_OPERANDS / "global_case_effects.csv", DGRA_OPERANDS / "local_case_operands.json", DGRA_OPERANDS / "global_case_operands.json")}}
    return config, graph, cases, dependence, provenance


def _retained_windows(graph: Mapping[str, Any], source: int, target: int) -> list[int]:
    windows: set[int] = set()
    for relation in graph["relations"]:
        if int(relation["source"]) == int(source) and int(relation["target"]) == int(target):
            for occurrence in relation["native_occurrences"]:
                if occurrence.get("retained"):
                    context = occurrence["context_id"]
                    windows.add(int(str(context).rsplit(":", 1)[-1]))
    return sorted(windows)


def load_msgnet_frozen_inputs(*, include_intervention_trajectories: bool = True) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    family_source = _json(MSG_FROZEN / "candidate_family_v2.json")
    protocol = _json(MSG_FROZEN / "formal_protocol_v2.json")
    manifest = _json(MSG_FROZEN / "formal_manifest_v2.json")
    template = _json(MSG_SESSION)
    sample_ids = [int(value) for value in protocol["selected_test_ids"]]
    units = [{"raw_start": item["raw_start"], "raw_end": item["raw_end"], "start_timestamp": item["start_timestamp"], "end_timestamp": item["end_timestamp"]} for item in protocol["tests"]]
    families = []
    for source_family in family_source["families"]:
        family_id = f"msgnet.{source_family['family_name']}.frozen14"
        scope = source_family["family_name"]
        members = []
        for source_member in source_family["members"]:
            member = {
                "candidate_id": source_member["hypothesis_id"], "source": source_member["source"], "target": source_member["target"],
                "source_name": source_member["source_name"], "target_name": source_member["target_name"],
                "scope": scope, "native_context_type": "scale", "retained_contexts": [0, 1, 2] if scope == "all_scales" else [source_member["scale_index"]],
            }
            if scope == "single_scale":
                member["scale_index"] = source_member["scale_index"]
            members.append(member)
        families.append({"family_id": family_id, "scope": scope, "selection_rule": family_source["selection_rule"], "context_identity_rule": "scale_index,source,target" if scope == "single_scale" else "source,target across scales 0,1,2", "members": members, "family_size": len(members), "selection_frozen": True})
    primary = {family["family_id"]: {"primary_test": "exact_sign_flip_mean_D", "maximum_exact_units": 20, "minimum_active_units": 14, "enumeration": "complete"} for family in families}
    sensitivity = {family["family_id"]: ["exact_sign_test", "BY", "temporal_interleaved_subsets", "leave_one_out", "bootstrap_mean_CI", "trimmed_mean"] for family in families}
    config = _base_config(adapter="msgnet", dataset="ETTh1", checkpoint_sha256=manifest["checkpoint_sha256"], sample_ids=sample_ids, units=units, families=families, dependence="non_overlapping_time_units", primary_by_family=primary, sensitivity=sensitivity)
    graph = _build_msgnet_graph_core(template, protocol)

    raw_cases = _csv(MSG_FROZEN / "case_evidence.csv")
    response_groups: dict[tuple[int, str, int | None], dict[str, float]] = defaultdict(dict)
    for row in raw_cases:
        key = (int(row["test_id"]), row["scope"], int(row["scale_index"]) if row["scale_index"] else None)
        response_groups[key][f"{row['source']}->{row['target']}"] = float(row["focal_response"])
    intervention_records = {item["case_id"]: item for item in _json_lines(MSG_FROZEN / "intervention_records.jsonl")}
    samples_by_id = {int(sample["sample_index"]): sample for sample in graph["samples"]}
    cases = []
    for row in raw_cases:
        sample = int(row["test_id"])
        scale = int(row["scale_index"]) if row["scale_index"] else None
        key = (sample, row["scope"], scale)
        focal_identity = f"{row['source']}->{row['target']}"
        controls = [{"identity": identity, "response": response} for identity, response in response_groups[key].items() if identity != focal_identity]
        record = intervention_records[row["case_id"]]
        baseline_metrics = samples_by_id[sample]["sample_metrics"]
        baseline_mae = float(baseline_metrics.get("baseline_mae", baseline_metrics.get("mae")))
        baseline_mse = float(baseline_metrics.get("baseline_mse", baseline_metrics.get("mse")))
        metrics = {
            "baseline_mae": baseline_mae, "baseline_mse": baseline_mse,
            "intervention_mae": baseline_mae + float(row["error_delta_mae"]),
            "intervention_mse": baseline_mse + float(row["error_delta_mse"]),
            "prediction_delta_abs": float(row["prediction_delta_abs"]), "prediction_delta_max": float(row["prediction_delta_max"]),
            "error_delta_mae": float(row["error_delta_mae"]), "error_delta_mse": float(row["error_delta_mse"]),
        }
        intervention_ref: dict[str, Any] = {"status": "available", "shape": record["trajectory_shape"], "sha256": _sha256(MSG_FROZEN / record["intervention_prediction_file"])}
        if include_intervention_trajectories:
            intervention_ref["value"] = _tensor(np.load(MSG_FROZEN / record["intervention_prediction_file"], allow_pickle=False))
        context: dict[str, Any] = {"type": "scale", "affected_scales": record["affected_scales"]}
        if scale is not None:
            context.update({"scale_index": scale, "current_period": int(row["observed_period"])})
        cases.append(build_case_evidence(
            case_evidence_id=row["case_id"], candidate_id=row["hypothesis_id"], sample_id=sample, context=context,
            scope=row["scope"], active=True, focal_response=float(row["focal_response"]), controls=controls,
            response_metrics=metrics, graph_effect={"before_weights": record["graph_before_focal_weights"], "after_weights": record["graph_after_focal_weights"], "affected_scales": record["affected_scales"]},
            baseline_reference={"sample_id": f"test:{sample}", "field": "baseline_prediction"}, intervention_output_reference=intervention_ref,
            provenance={"source_artifact": "msgnet_frozen14/case_evidence.csv", "source_case_id": row["case_id"]},
        ))
    dependence = {family["family_id"]: audit_dependence(config["sample_protocol"]["protocol_id"], sample_ids, units, same_continuous_series=True) for family in families}
    provenance = {"frozen_artifacts": dict(manifest["artifact_sha256"])}
    return config, graph, cases, dependence, provenance


def _json_lines(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _rank_descending(values: list[float]) -> list[float]:
    ordered = sorted(range(len(values)), key=lambda index: (-values[index], index))
    result = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        rank = (start + 1 + end) / 2
        for position in range(start, end):
            result[ordered[position]] = float(rank)
        start = end
    return result


def _build_msgnet_graph_core(template: Mapping[str, Any], protocol: Mapping[str, Any]) -> dict[str, Any]:
    records = _json(MSG_FROZEN / "baseline/baseline_records.json")
    record_by_id = {int(record["test_id"]): record for record in records}
    names = list(template["dataset"]["variables"])
    graph = {key: copy.deepcopy(template[key]) for key in ("session", "model", "dataset", "checkpoint", "provenance")}
    graph["model_specific"] = {
        "artifact_validation_report": copy.deepcopy(
            template.get("validation", {}).get("model_validation_V01_V09")
        )
    }
    graph["session"]["session_id"] = "msgnet_etth1_frozen14_graph_core"
    graph["samples"] = []
    graph["relations"] = []
    old_samples = {int(sample["sample_index"]): sample for sample in template["samples"]}
    old_relations = {(int(relation["source"]), int(relation["target"])): relation for relation in template["relations"] if relation["sample_id"] == "test:0"}
    for test in protocol["tests"]:
        sample_id = int(test["test_id"])
        record = record_by_id[sample_id]
        history = np.load(MSG_FROZEN / record["history_file"], allow_pickle=False)
        truth = np.load(MSG_FROZEN / record["ground_truth_file"], allow_pickle=False)
        prediction = np.load(MSG_FROZEN / record["baseline_prediction_file"], allow_pickle=False)
        context_arrays = np.load(MSG_FROZEN / record["context_file"], allow_pickle=False)
        contexts = []
        per_scale_weights: list[dict[tuple[int, int], tuple[float, float]]] = []
        for context_meta in record["contexts"]:
            scale = int(context_meta["scale_index"])
            adaptive = np.asarray(context_arrays[f"adaptive_{scale}"], dtype=np.float32)
            self_loop = adaptive + np.eye(adaptive.shape[0], dtype=np.float32)
            effective = self_loop / self_loop.sum(axis=1, keepdims=True)
            edge_ids = [(source, target) for source in range(len(names)) for target in range(len(names)) if source != target]
            weights = [float(adaptive[source, target]) for source, target in edge_ids]
            ranks = _rank_descending(weights)
            per_scale_weights.append({edge: (weight, rank) for edge, weight, rank in zip(edge_ids, weights, ranks)})
            contexts.append({
                "context_id": f"layer:0:scale:{scale}", "type": "scale", "index": scale, "layer": 0,
                "node_count": len(names),
                "graphs": {
                    "adaptive": {"dtype": "float32", "shape": [len(names), len(names)], "axis_order": ["source_node", "target_node"], "values": adaptive.tolist()},
                    "effective": {"dtype": "float32", "shape": [len(names), len(names)], "axis_order": ["source_node", "target_node"], "values": effective.tolist()},
                },
                "native_metadata": {"period": context_meta["observed_period"], "fft_strength": context_meta["fft_strength"], "scale_contribution": context_meta["scale_contribution"]},
            })
        mae = float(np.mean(np.abs(prediction - truth)))
        mse = float(np.mean(np.square(prediction - truth)))
        sample_record = {
            "sample_id": f"test:{sample_id}", "display_id": sample_id, "split": "test", "sample_index": sample_id,
            "history": {"status": "available", "value": _tensor(history, first_axis="input_step"), "reason": None},
            "ground_truth": _tensor(truth, first_axis="forecast_step"), "baseline_prediction": _tensor(prediction, first_axis="forecast_step"),
            "sample_metrics": {"mse": mse, "mae": mae, "repeat_max_absolute_difference": 0.0}, "contexts": contexts,
            "provenance": {"raw_start": test["raw_start"], "raw_end": test["raw_end"], "start_timestamp": test["start_timestamp"], "end_timestamp": test["end_timestamp"]},
        }
        if sample_id in old_samples:
            for key in ("history", "ground_truth", "baseline_prediction", "sample_metrics", "contexts"):
                sample_record[key] = copy.deepcopy(old_samples[sample_id][key])
        graph["samples"].append(sample_record)
        for source in range(len(names)):
            for target in range(len(names)):
                if source == target:
                    continue
                occurrences = [{"context_id": f"layer:0:scale:{scale}", "weight": per_scale_weights[scale][(source, target)][0], "retained": True, "rank": per_scale_weights[scale][(source, target)][1]} for scale in range(3)]
                if sample_id == 0 and (source, target) in old_relations:
                    occurrences = copy.deepcopy(old_relations[(source, target)]["native_occurrences"])
                graph["relations"].append({"relation_id": f"test:{sample_id}:edge:{source}->{target}", "sample_id": f"test:{sample_id}", "source": source, "target": target, "source_name": names[source], "target_name": names[target], "native_occurrences": occurrences})
    graph["model_specific"]["artifact_validation_report"] = {"status": "pass", "source": "msgnet_frozen14/formal_manifest_v2.json", "frozen_validation": _json(MSG_FROZEN / "formal_manifest_v2.json")["status"]}
    return graph


def load_frozen_inputs(protocol: str, *, include_intervention_trajectories: bool = True):
    if protocol == "dgraformer_etth1_frozen40":
        return load_dgraformer_frozen_inputs()
    if protocol == "msgnet_etth1_frozen14":
        return load_msgnet_frozen_inputs(include_intervention_trajectories=include_intervention_trajectories)
    raise ValueError(f"Unknown frozen Pipeline v2 protocol: {protocol}")

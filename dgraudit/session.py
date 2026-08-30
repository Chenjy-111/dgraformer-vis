# LEGACY SESSION V1 COMPATIBILITY ONLY.
# Not used by the current Session v2 formal inference path.
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import platform
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable, Mapping, Sequence


SESSION_SCHEMA_VERSION = "dgrainsight.audit_session.v1"
EXPORT_CONFIG_VERSION = "dgrainsight.session_export.v1"
GENERATOR_NAME = "DGraInsight offline audit pipeline"
GENERATOR_VERSION = "1.0"


class AuditSessionError(ValueError):
    """Raised when source artifacts cannot produce a valid portable session."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _value_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AuditSessionError(f"Required source artifact does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AuditSessionError(f"Invalid JSON source artifact {path}: {exc}") from exc


def _resolve(config_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = config_path.parent / path
    return path.resolve()


def _source_relative_path(run_dir: Path, raw_path: str) -> Path:
    # Catalogs were produced on Windows, so their relative paths use backslashes.
    parts = PureWindowsPath(raw_path).parts
    candidate = run_dir.joinpath(*parts).resolve()
    try:
        candidate.relative_to(run_dir.resolve())
    except ValueError as exc:
        raise AuditSessionError(f"Source artifact escapes its declared run directory: {raw_path}") from exc
    return candidate


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise AuditSessionError(f"{field} must be a lowercase SHA-256 string")
    return value


def _shape(values: Any) -> list[int]:
    if not isinstance(values, list):
        return []
    if not values:
        return [0]
    child_shapes = [_shape(item) for item in values]
    if any(shape != child_shapes[0] for shape in child_shapes[1:]):
        raise AuditSessionError("Tensor values are ragged")
    return [len(values), *child_shapes[0]]


def _ensure_finite(value: Any, path: str) -> None:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise AuditSessionError(f"Non-finite numeric value at {path}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _ensure_finite(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _ensure_finite(item, f"{path}.{key}")


def _tensor(values: list[Any], axes: Sequence[str], dtype: str = "float32") -> dict[str, Any]:
    shape = _shape(values)
    if len(shape) != len(axes):
        raise AuditSessionError(f"Tensor rank {len(shape)} does not match axis count {len(axes)}")
    _ensure_finite(values, "tensor.values")
    return {
        "dtype": dtype,
        "shape": shape,
        "axis_order": list(axes),
        "values": values,
    }


def _transpose_variable_step(values: Sequence[Sequence[float]]) -> list[list[float]]:
    if not values:
        return []
    width = len(values[0])
    if any(len(row) != width for row in values):
        raise AuditSessionError("Cannot transpose a ragged variable-by-step array")
    return [[values[variable][step] for variable in range(len(values))] for step in range(width)]


def _available_tensor(values: list[Any], axes: Sequence[str]) -> dict[str, Any]:
    return {"status": "available", "value": _tensor(values, axes), "reason": None}


def _missing_tensor(reason: str) -> dict[str, Any]:
    return {"status": "missing", "value": None, "reason": reason}


def _metric_status(source: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in source.items():
        if not isinstance(value, Mapping):
            raise AuditSessionError(f"Metric status {key} must be an object")
        result[key] = {"status": value.get("status", "undefined"), "reason": value.get("reason")}
    return result


STATISTIC_FIELDS = {
    "control_mean_prediction_delta_abs",
    "control_median_prediction_delta_abs",
    "control_percentile",
    "control_percentile_midrank",
    "empirical_p",
    "bh_adjusted_p",
    "standardized_effect_size",
    "candidate_minus_control_mean_bootstrap_ci_95",
    "effect_difference_bootstrap_ci",
    "bootstrap_repetitions",
    "bootstrap_seed",
}


def _split_metrics(source: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    metrics: dict[str, Any] = {}
    statistics: dict[str, Any] = {}
    for key, value in source.items():
        (statistics if key in STATISTIC_FIELDS else metrics)[key] = value
    return metrics, statistics


def _control_summary(statistics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in statistics.items()
        if key.startswith("control_") or key.startswith("candidate_minus_control_")
    }


def _load_manifest(run_dir: Path) -> tuple[str, dict[str, Any]]:
    path = run_dir / "manifest.json"
    manifest = _read_json(path)
    if not isinstance(manifest, dict) or manifest.get("status") != "complete":
        raise AuditSessionError(f"Source run manifest is not complete: {path}")
    return _file_sha256(path), manifest


def _source_run(role: str, run_id: str, repo_root: Path) -> dict[str, Any]:
    run_dir = repo_root / "artifacts" / "runs" / run_id
    manifest_path = run_dir / "manifest.json"
    if manifest_path.is_file():
        return {
            "role": role,
            "run_id": run_id,
            "artifact_status": "available",
            "manifest_sha256": _file_sha256(manifest_path),
            "artifact_sha256": None,
        }
    return {
        "role": role,
        "run_id": run_id,
        "artifact_status": "referenced_not_present",
        "manifest_sha256": None,
        "artifact_sha256": None,
    }


def _source_artifact(role: str, path: Path, configured_path: str) -> dict[str, Any]:
    return {
        "role": role,
        "path": configured_path.replace("\\", "/"),
        "sha256": _file_sha256(path),
        "status": "available",
    }


def _validation_report(adapter_id: str, dataset: str, artifacts: Sequence[dict[str, Any]], checks: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": "artifact_roundtrip_validation",
        "status": "passed",
        "adapter_id": adapter_id,
        "dataset": dataset,
        "source_artifacts": [
            {"role": item["role"], "sha256": item["sha256"], "status": item["status"]}
            for item in artifacts
        ],
        "checks": dict(checks),
    }


def _common_session(
    *,
    config: Mapping[str, Any],
    config_path: Path,
    model: dict[str, Any],
    dataset: dict[str, Any],
    checkpoint: dict[str, Any],
    audit_plan: dict[str, Any],
    samples: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    evidence_records: list[dict[str, Any]],
    evidence_summary: dict[str, Any],
    cross_run_evidence: dict[str, Any],
    source_runs: list[dict[str, Any]],
    source_artifacts: list[dict[str, Any]],
    validation_report: dict[str, Any],
    limitations: list[str],
    created_at: str | None,
) -> dict[str, Any]:
    config_sha256 = _file_sha256(config_path)
    run_material = {
        "generator_version": GENERATOR_VERSION,
        "config_sha256": config_sha256,
        "source_artifacts": [(item["role"], item["sha256"]) for item in source_artifacts],
    }
    run_id = _value_sha256(run_material)
    timestamp = created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": SESSION_SCHEMA_VERSION,
        "session": {
            "session_id": f"{model['adapter_id']}:{dataset['name']}:{run_id[:16]}",
            "created_at": timestamp,
            "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION, "run_id": run_id},
            "source_mode": "offline_audit",
            "inference_classification": "Legacy single-case / legacy inference session",
            "title": config.get("session", {}).get("title"),
        },
        "model": model,
        "dataset": dataset,
        "checkpoint": checkpoint,
        "audit_plan": audit_plan,
        "samples": samples,
        "relations": relations,
        "evidence_records": evidence_records,
        "evidence_summary": evidence_summary,
        "cross_run_evidence": cross_run_evidence,
        "provenance": {
            "session_generation_run_id": run_id,
            "validation": {
                "kind": "artifact_roundtrip_validation",
                "status": "passed",
                "report_sha256": _value_sha256(validation_report),
            },
            "config_sha256": config_sha256,
            "source_runs": source_runs,
            "commands": [f"python -m dgraudit.cli.export_audit_session --config {config_path.name}"],
            "environment": {"python": platform.python_version(), "platform": platform.platform()},
            "code_references": [
                "dgraudit/session.py",
                "schemas/dgrainsight_audit_session_v1.schema.json",
            ],
            "source_artifacts": source_artifacts,
        },
        "limitations": limitations,
        "model_specific": {"artifact_validation_report": validation_report},
    }


def _dgra_graph_contexts(run_dir: Path) -> list[dict[str, Any]]:
    graph_dir = run_dir / "graphs"
    paths = sorted(graph_dir.glob("window_*.json"), key=lambda path: int(path.stem.split("_")[-1]))
    if not paths:
        raise AuditSessionError(f"No DGraFormer graph-stage artifacts found under {graph_dir}")
    contexts: list[dict[str, Any]] = []
    for path in paths:
        graph = _read_json(path)
        index = int(graph["window"])
        stages = {
            key: _tensor(graph[key], ("source_node", "target_node"))
            for key in (
                "static_prior", "raw_score", "activated", "diagonal_removed",
                "topk_mask", "topk_graph", "self_loop_graph", "normalized",
            )
        }
        contexts.append(
            {
                "context_id": f"window:{index}",
                "type": "window",
                "index": index,
                "node_count": len(graph["normalized"]),
                "graphs": stages,
                "native_metadata": {
                    "topk_slots": graph["topk_slots"],
                    "blend_proportion": graph["blend_proportion"],
                    "source_graph_sha256": _file_sha256(path),
                },
            }
        )
    return contexts


def _load_dgra_histories(sample_dir: Path) -> dict[int, dict[str, Any]]:
    histories: dict[int, dict[str, Any]] = {}
    if not sample_dir.is_dir():
        return histories
    for path in sorted(sample_dir.glob("ETTh1_*_h96.json")):
        sample = _read_json(path)
        sample_index = sample.get("provenance", {}).get("testSampleIndex")
        if not isinstance(sample_index, int) or sample_index in histories:
            continue
        histories[sample_index] = {
            "history": _transpose_variable_step(sample["history"]),
            "provenance": sample.get("provenance", {}),
            "source_path": str(path),
        }
    return histories


def _hydrate_controls(
    run_dir: Path,
    raw_path: str,
    *,
    expected_sha256: str | None = None,
    seed: int | None,
    default_protocol: str | None,
) -> dict[str, Any]:
    path = _source_relative_path(run_dir, raw_path)
    actual_hash = _file_sha256(path)
    if expected_sha256 is not None and actual_hash != expected_sha256:
        raise AuditSessionError(
            f"Control record hash mismatch for {path}: expected {expected_sha256}, found {actual_hash}"
        )
    records = _read_json(path)
    if not isinstance(records, list):
        raise AuditSessionError(f"Control record artifact must contain a list: {path}")
    protocol = default_protocol
    if records and isinstance(records[0], dict):
        protocol = records[0].get("sampling", protocol)
    values: list[float] = []
    for record in records:
        if "prediction_delta_abs" in record:
            values.append(record["prediction_delta_abs"])
        elif isinstance(record.get("metrics"), dict) and "prediction_delta_abs" in record["metrics"]:
            values.append(record["metrics"]["prediction_delta_abs"])
        else:
            raise AuditSessionError(f"Control record lacks prediction_delta_abs: {path}")
    return {
        "status": "available",
        "protocol": protocol,
        "count": len(records),
        "random_seed": seed,
        "values": {"status": "available", "value": values, "reason": None},
        "records": records,
        "summary": {},
        "records_sha256": actual_hash,
        "model_specific": {"source_path": raw_path.replace("\\", "/")},
    }


def _dgra_selection(
    *, sample_index: int, edge: Mapping[str, Any], scope: str, window: int | None = None
) -> dict[str, Any]:
    local = scope == "local"
    return {
        "model": "DGraFormer",
        "dataset": "ETTh1",
        "sample_id": f"test:{sample_index}",
        "sample_index": sample_index,
        "context_type": "window" if local else "window_set",
        "context_id": f"window:{window}" if local else "window_set:all_applicable",
        "context_index": window if local else "all_applicable",
        "source": edge["source"],
        "target": edge["target"],
        "source_name": edge["source_name"],
        "target_name": edge["target_name"],
        "scope": scope,
    }


def _build_dgraformer_session(
    config: Mapping[str, Any], config_path: Path, repo_root: Path, created_at: str | None
) -> dict[str, Any]:
    source = config["source"]
    local_path = _resolve(config_path, source["local_catalog"])
    global_path = _resolve(config_path, source["broader_catalog"])
    local_run_dir = _resolve(config_path, source["local_run_dir"])
    global_run_dir = _resolve(config_path, source["broader_run_dir"])
    sample_dir = _resolve(config_path, source["sample_directory"])
    local = _read_json(local_path)
    broader = _read_json(global_path)
    if local.get("dataset") != "ETTh1" or broader.get("dataset") != "ETTh1":
        raise AuditSessionError("DGraFormer exporter only accepts the declared ETTh1 source catalogs")
    if local.get("samples") != broader.get("samples") or local.get("variables") != broader.get("variables"):
        raise AuditSessionError("DGraFormer local and broader catalogs disagree on samples or variables")

    local_manifest_hash, local_manifest = _load_manifest(local_run_dir)
    global_manifest_hash, global_manifest = _load_manifest(global_run_dir)
    if local["source_runs"]["evidence"] != local_run_dir.name or broader["run_id"] != global_run_dir.name:
        raise AuditSessionError("DGraFormer source run IDs do not match configured run directories")
    dataset_hash = _require_sha256(local_manifest["data_sha256"], "DGraFormer dataset hash")
    checkpoint_hash = _require_sha256(local_manifest["checkpoint_sha256"], "DGraFormer checkpoint hash")
    if dataset_hash != global_manifest["data_sha256"] or checkpoint_hash != global_manifest["checkpoint_sha256"]:
        raise AuditSessionError("DGraFormer local and broader manifests disagree on dataset/checkpoint hashes")

    contexts = _dgra_graph_contexts(local_run_dir)
    context_ids = {item["context_id"] for item in contexts}
    histories = _load_dgra_histories(sample_dir)
    local_by_sample: dict[int, list[dict[str, Any]]] = defaultdict(list)
    global_by_sample: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for case in local["cases"]:
        local_by_sample[case["sample_index"]].append(case)
    for case in broader["cases"]:
        global_by_sample[case["sample"]].append(case)

    samples: list[dict[str, Any]] = []
    for display_id, sample_index in enumerate(local["samples"]):
        cases = local_by_sample[sample_index]
        if not cases:
            raise AuditSessionError(f"No DGraFormer local cases for sample {sample_index}")
        baseline = cases[0]["baseline_prediction"]
        truth = cases[0]["ground_truth"]
        if any(case["baseline_prediction"] != baseline or case["ground_truth"] != truth for case in cases[1:]):
            raise AuditSessionError(f"DGraFormer local cases disagree on sample {sample_index} outputs")
        for case in global_by_sample[sample_index]:
            if case["baseline_prediction"] != baseline or case["ground_truth"] != truth:
                raise AuditSessionError(f"DGraFormer broader case disagrees on sample {sample_index} outputs")
        history = histories.get(sample_index)
        samples.append(
            {
                "sample_id": f"test:{sample_index}",
                "display_id": display_id,
                "split": "test",
                "sample_index": sample_index,
                "history": (
                    _available_tensor(history["history"], ("input_step", "variable"))
                    if history
                    else _missing_tensor(
                        "The legacy DGraFormer 40-grid evidence artifacts do not retain history for this sample."
                    )
                ),
                "ground_truth": _tensor(truth, ("forecast_step", "variable")),
                "baseline_prediction": _tensor(baseline, ("forecast_step", "variable")),
                "sample_metrics": {
                    "mae": cases[0]["structural_metrics"]["baseline_mae"],
                    "mse": cases[0]["structural_metrics"]["baseline_mse"],
                },
                "contexts": copy.deepcopy(contexts),
                "provenance": {
                    "local_evidence_run_id": local_run_dir.name,
                    "broader_evidence_run_id": global_run_dir.name,
                    "built_in_sample": history["provenance"] if history else None,
                },
            }
        )

    evidence: list[dict[str, Any]] = []
    relation_evidence: dict[str, list[str]] = defaultdict(list)
    relation_occurrences: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    relation_edges: dict[str, dict[str, Any]] = {}

    for case in local["cases"]:
        sample_index = case["sample_index"]
        edge = case["edge"]
        relation_id = f"test:{sample_index}:edge:{edge['source']}->{edge['target']}"
        evidence_id = case["conclusion_id"]
        controls = _hydrate_controls(
            local_run_dir,
            case["controls"]["records"],
            expected_sha256=case["controls"]["records_sha256"],
            seed=case["controls"]["random_seed"],
            default_protocol=None,
        )
        metrics, statistics = _split_metrics(case["structural_metrics"])
        controls["summary"] = _control_summary(statistics)
        context_id = f"window:{case['window']}"
        if context_id not in context_ids:
            raise AuditSessionError(f"DGraFormer case references unavailable graph context {context_id}")
        relation_edges[relation_id] = edge
        relation_evidence[relation_id].append(evidence_id)
        relation_occurrences[relation_id][context_id] = {
            "context_id": context_id,
            "weight": edge["normalized_weight"],
            "retained": True,
            "rank": edge.get("retained_edge_rank"),
        }
        evidence.append(
            {
                "evidence_id": evidence_id,
                "relation_id": relation_id,
                "selection": _dgra_selection(
                    sample_index=sample_index, edge=edge, scope="local", window=case["window"]
                ),
                "status": "available" if case["window_active"] else "not_exposed",
                "reason": None if case["window_active"] else (
                    "The selected window was not exposed in this sample computation path; stored replay values are preserved."
                ),
                "value": {
                    "baseline_output_ref": f"test:{sample_index}:baseline",
                    "intervention_output": _available_tensor(
                        case["intervention_prediction"], ("forecast_step", "variable")
                    ),
                    "metrics": metrics,
                    "statistics": statistics,
                    "metric_status": _metric_status(case.get("structural_metric_status", {})),
                    "controls": controls,
                    "graph_effect": {
                        "window_active": case["window_active"],
                        "active_windows": case["active_windows"],
                        "window_exposure_count": case["window_exposure_count"],
                        "topk_score": edge["topk_score"],
                        "normalized_weight": edge["normalized_weight"],
                        "retained_edge_rank": edge.get("retained_edge_rank"),
                    },
                    "diagnostic_localization": {
                        "summary": case["diagnostic_localization"],
                        "step_error_delta": case["step_error_delta"],
                        "step_impact": case["step_impact"],
                        "variable_impact": case["variable_impact"],
                    },
                    "limitations": case.get("limitations", []),
                    "provenance": {
                        "source_run_id": local_run_dir.name,
                        "raw_operands": case.get("raw_operands", {}),
                    },
                    "model_specific": {"channel_mask_metrics": case.get("channel_mask_metrics", {})},
                },
            }
        )

    edge_lookup = {
        (edge["source"], edge["target"]): edge
        for edge in local["edges"]
    }
    for case in broader["cases"]:
        sample_index = case["sample"]
        source_index, target_index = case["edge"]
        edge = edge_lookup.get((source_index, target_index)) or {
            "source": source_index,
            "target": target_index,
            "source_name": local["variables"][source_index],
            "target_name": local["variables"][target_index],
            "normalized_weight": case["mean_weight"],
            "retained_edge_rank": None,
            "topk_score": case["mean_weight"],
        }
        relation_id = f"test:{sample_index}:edge:{source_index}->{target_index}"
        evidence_id = case["id"]
        controls = _hydrate_controls(
            global_run_dir,
            case["controls_file"],
            seed=case["control_seed"],
            default_protocol=broader["protocol"],
        )
        metrics, statistics = _split_metrics(case["metrics"])
        controls["summary"] = _control_summary(statistics)
        relation_edges.setdefault(relation_id, edge)
        relation_evidence[relation_id].append(evidence_id)
        for window in case["retained_windows"]:
            context_id = f"window:{window}"
            if context_id in context_ids:
                relation_occurrences[relation_id].setdefault(
                    context_id,
                    {
                        "context_id": context_id,
                        "weight": case["mean_weight"],
                        "retained": True,
                        "rank": edge.get("retained_edge_rank"),
                    },
                )
        evidence.append(
            {
                "evidence_id": evidence_id,
                "relation_id": relation_id,
                "selection": _dgra_selection(sample_index=sample_index, edge=edge, scope="broader_context"),
                "status": "available",
                "reason": None,
                "value": {
                    "baseline_output_ref": f"test:{sample_index}:baseline",
                    "intervention_output": _available_tensor(
                        case["intervention_prediction"], ("forecast_step", "variable")
                    ),
                    "metrics": metrics,
                    "statistics": statistics,
                    "metric_status": {},
                    "controls": controls,
                    "graph_effect": {
                        "retained_contexts": case["retained_windows"],
                        "exposed_contexts": case["exposed_windows"],
                        "affected_contexts": case["affected_exposed_windows"],
                        "mean_weight": case["mean_weight"],
                    },
                    "diagnostic_localization": {"variable_ranking": case["variable_ranking"]},
                    "limitations": [],
                    "provenance": {
                        "source_run_id": global_run_dir.name,
                        "prediction_file": case["prediction_file"].replace("\\", "/"),
                        "controls_file": case["controls_file"].replace("\\", "/"),
                    },
                },
            }
        )

    relations: list[dict[str, Any]] = []
    for relation_id in sorted(relation_edges):
        edge = relation_edges[relation_id]
        sample_id = relation_id.split(":edge:", 1)[0]
        relations.append(
            {
                "relation_id": relation_id,
                "sample_id": sample_id,
                "source": edge["source"],
                "target": edge["target"],
                "source_name": edge["source_name"],
                "target_name": edge["target_name"],
                "native_occurrences": sorted(
                    relation_occurrences[relation_id].values(), key=lambda item: item["context_id"]
                ),
                "evidence_ids": relation_evidence[relation_id],
                "model_specific": {
                    key: edge[key]
                    for key in ("topk_score", "normalized_weight", "retained_edge_rank")
                    if key in edge
                },
            }
        )

    configured_artifacts = [
        _source_artifact("local_catalog", local_path, source["local_catalog"]),
        _source_artifact("broader_catalog", global_path, source["broader_catalog"]),
        _source_artifact("local_run_manifest", local_run_dir / "manifest.json", f"{source['local_run_dir']}/manifest.json"),
        _source_artifact("broader_run_manifest", global_run_dir / "manifest.json", f"{source['broader_run_dir']}/manifest.json"),
    ]
    report = _validation_report(
        "dgraformer",
        "ETTh1",
        configured_artifacts,
        {
            "local_case_count": len(local["cases"]),
            "broader_context_case_count": len(broader["cases"]),
            "sample_outputs_consistent": True,
            "control_record_hashes_verified": True,
            "local_manifest_sha256": local_manifest_hash,
            "broader_manifest_sha256": global_manifest_hash,
        },
    )
    local_supported = sum(
        1
        for case in local["cases"]
        if case["window_active"] and case["structural_metrics"].get("bh_adjusted_p", 1.0) < 0.05
    )
    broader_supported = sum(
        1 for case in broader["cases"] if case["metrics"].get("bh_adjusted_p", 1.0) < 0.05
    )
    return _common_session(
        config=config,
        config_path=config_path,
        model={
            "name": "DGraFormer",
            "adapter": "DGraFormerAdapter",
            "adapter_id": "dgraformer",
            "native_context_type": "window",
            "source_repository": config.get("model", {}).get("source_repository"),
            "source_commit": config.get("model", {}).get("source_commit"),
            "configuration": {"schedule": local["schedule"]},
        },
        dataset={
            "name": "ETTh1",
            "format": "ETT CSV with date plus seven ordered variables",
            "sha256": dataset_hash,
            "variables": local["variables"],
            "date_column": "date",
            "features": "M",
            "target": "OT",
            "frequency": "h",
            "seq_len": 96,
            "label_len": 48,
            "pred_len": 96,
            "original_path": None,
        },
        checkpoint={
            "sha256": checkpoint_hash,
            "format": "PyTorch state_dict",
            "load_status": "validated",
            "original_path": None,
        },
        audit_plan={
            "split": "test",
            "sample_indices": local["samples"],
            "relation_count": len(relations),
            "local_scope": "exact_native_context",
            "broader_context_scope": "all_applicable_native_contexts",
            "candidate_protocol": config.get("audit", {}).get("candidate_protocol"),
            "control_protocol": config.get("audit", {}).get("control_protocol"),
            "multiple_comparison_protocol": config.get("audit", {}).get("multiple_comparison_protocol"),
        },
        samples=samples,
        relations=relations,
        evidence_records=evidence,
        evidence_summary={
            "local_case_count": len(local["cases"]),
            "broader_context_case_count": len(broader["cases"]),
            "local_bh_supported_count": local_supported,
            "broader_context_bh_supported_count": broader_supported,
            "negative_evidence_preserved": True,
            "not_exposed_case_count": sum(1 for case in local["cases"] if not case["window_active"]),
            "missing_case_count": 0,
        },
        cross_run_evidence={
            "status": local["cross_run"]["status"],
            "value": local["cross_run"]["metrics"],
            "reason": local["cross_run"]["reason"],
        },
        source_runs=[
            _source_run("intervention", local["source_runs"]["intervention"], repo_root),
            _source_run("local_evidence", local["source_runs"]["evidence"], repo_root),
            _source_run("broader_context_evidence", broader["run_id"], repo_root),
        ],
        source_artifacts=configured_artifacts,
        validation_report=report,
        limitations=[local["notice"], broader["notice"], local["cross_run"]["reason"]],
        created_at=created_at,
    )


def _msgnet_selection(
    *, sample_index: int, edge: Mapping[str, Any], scope: str, layer: int = 0
) -> dict[str, Any]:
    local = scope == "local"
    scale_index = edge.get("scale_index")
    return {
        "model": "MSGNet",
        "dataset": "ETTh1",
        "sample_id": f"test:{sample_index}",
        "sample_index": sample_index,
        "context_type": "scale" if local else "scale_set",
        "context_id": f"layer:{layer}:scale:{scale_index}" if local else f"layer:{layer}:scale_set:all_applicable",
        "context_index": scale_index if local else "all_applicable",
        "layer": layer,
        "source": edge["source"],
        "target": edge["target"],
        "source_name": edge["source_name"],
        "target_name": edge["target_name"],
        "scope": scope,
    }


def _build_msgnet_session(
    config: Mapping[str, Any], config_path: Path, repo_root: Path, created_at: str | None
) -> dict[str, Any]:
    source = config["source"]
    catalog_path = _resolve(config_path, source["catalog"])
    model_config_path = _resolve(config_path, source["model_config"])
    catalog = _read_json(catalog_path)
    model_config = _read_json(model_config_path)
    if catalog.get("model") != "MSGNet" or catalog.get("dataset") != "ETTh1":
        raise AuditSessionError("MSGNet exporter only accepts the official ETTh1 catalog")
    if model_config.get("model") != "MSGNet" or model_config.get("dataset", {}).get("name") != "ETTh1":
        raise AuditSessionError("MSGNet source config does not identify the official ETTh1 integration")
    variables = catalog["variables"]
    samples: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []

    for display_id, source_sample in enumerate(catalog["samples"]):
        sample_index = source_sample["sample_index"]
        contexts = []
        for context in source_sample["contexts"]:
            contexts.append(
                {
                    "context_id": f"layer:{context['layer']}:scale:{context['scale_index']}",
                    "type": "scale",
                    "index": context["scale_index"],
                    "layer": context["layer"],
                    "node_count": len(variables),
                    "graphs": {
                        "adaptive": _tensor(context["adaptive"], ("source_node", "target_node")),
                        "effective": _tensor(context["effective"], ("source_node", "target_node")),
                    },
                    "native_metadata": {
                        "period": context["period"],
                        "fft_strength": context["fft_strength"],
                        "scale_contribution": context["scale_contribution"],
                    },
                }
            )
        samples.append(
            {
                "sample_id": f"test:{sample_index}",
                "display_id": display_id,
                "split": "test",
                "sample_index": sample_index,
                "history": _available_tensor(
                    _transpose_variable_step(source_sample["history"]), ("input_step", "variable")
                ),
                "ground_truth": _tensor(
                    _transpose_variable_step(source_sample["ground_truth"]), ("forecast_step", "variable")
                ),
                "baseline_prediction": _tensor(
                    _transpose_variable_step(source_sample["prediction"]), ("forecast_step", "variable")
                ),
                "sample_metrics": {
                    key: value for key, value in source_sample["metrics"].items() if key != "sample_index"
                },
                "contexts": contexts,
                "provenance": {
                    "baseline_run_id": catalog["baseline_run_id"],
                    "graph_run_id": catalog["graph_run_id"],
                },
            }
        )

        local_by_edge: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
        for item in source_sample["edge_impacts"]:
            local_by_edge[(item["source"], item["target"])].append(item)
            metrics = {
                key: item[key]
                for key in ("prediction_delta_abs", "prediction_delta_max", "error_delta_mae", "error_delta_mse")
            }
            controls_source = item["controls"]
            controls = {
                "status": "available",
                "protocol": controls_source["sampling"],
                "count": controls_source["count"],
                "random_seed": None,
                "values": {
                    "status": "available",
                    "value": controls_source["prediction_delta_abs"],
                    "reason": None,
                },
                "records": [],
                "summary": _control_summary(item["statistics"]),
                "records_sha256": None,
                "model_specific": {
                    "raw_records_not_stored": True,
                    "values_source": "source catalog controls.prediction_delta_abs",
                },
            }
            relation_id = f"test:{sample_index}:edge:{item['source']}->{item['target']}"
            evidence.append(
                {
                    "evidence_id": item["conclusion_id"],
                    "relation_id": relation_id,
                    "selection": _msgnet_selection(
                        sample_index=sample_index, edge=item, scope="local", layer=item["layer"]
                    ),
                    "status": "available",
                    "reason": None,
                    "value": {
                        "baseline_output_ref": f"test:{sample_index}:baseline",
                        "intervention_output": _missing_tensor(
                            "The source MSGNet local evidence catalog stores response metrics but not the intervention prediction trajectory."
                        ),
                        "metrics": metrics,
                        "statistics": item["statistics"],
                        "metric_status": {},
                        "controls": controls,
                        "graph_effect": {
                            "adaptive_weight": item["adaptive_weight"],
                            "weight_rank": item["graph"]["weight_rank"],
                            "weight_impact_spearman_rho": item["graph"]["weight_impact_spearman_rho"],
                            "weight_impact_spearman_p": item["graph"]["weight_impact_spearman_p"],
                            "period": item["period"],
                            "scale_contribution": item["scale_contribution"],
                        },
                        "diagnostic_localization": None,
                        "limitations": item["limitations"],
                        "provenance": {"source_run_id": catalog["evidence_run_id"]},
                        "model_specific": {
                            "source_status": item["status"],
                            "claim_level": item["claim_level"],
                        },
                    },
                }
            )

        global_by_edge = {
            (item["source"], item["target"]): item for item in source_sample["global_edge_impacts"]
        }
        if len(global_by_edge) != len(variables) * (len(variables) - 1):
            raise AuditSessionError(f"MSGNet sample {sample_index} does not contain every directed non-self global edge")
        for key in sorted(local_by_edge):
            local_items = sorted(local_by_edge[key], key=lambda item: (item["layer"], item["scale_index"]))
            global_item = global_by_edge.get(key)
            if global_item is None:
                raise AuditSessionError(f"MSGNet sample {sample_index} lacks global evidence for relation {key}")
            relation_id = f"test:{sample_index}:edge:{key[0]}->{key[1]}"
            global_evidence_id = f"msgnet_global_s{sample_index}_edge_{key[0]}_{key[1]}"
            relations.append(
                {
                    "relation_id": relation_id,
                    "sample_id": f"test:{sample_index}",
                    "source": key[0],
                    "target": key[1],
                    "source_name": variables[key[0]],
                    "target_name": variables[key[1]],
                    "native_occurrences": [
                        {
                            "context_id": f"layer:{item['layer']}:scale:{item['scale_index']}",
                            "weight": item["adaptive_weight"],
                            "retained": item["adaptive_weight"] > 0,
                            "rank": item["graph"].get("weight_rank"),
                        }
                        for item in local_items
                    ],
                    "evidence_ids": [item["conclusion_id"] for item in local_items] + [global_evidence_id],
                }
            )
            control_values = [
                global_by_edge[other]["prediction_delta_abs"]
                for other in sorted(global_by_edge)
                if other != key
            ]
            stored_mean = global_item["statistics"]["control_mean_prediction_delta_abs"]
            selected_mean = sum(control_values) / len(control_values)
            if not math.isclose(selected_mean, stored_mean, rel_tol=0.0, abs_tol=1e-15):
                raise AuditSessionError(
                    f"MSGNet global controls for sample {sample_index}, relation {key} disagree with stored mean"
                )
            evidence.append(
                {
                    "evidence_id": global_evidence_id,
                    "relation_id": relation_id,
                    "selection": _msgnet_selection(sample_index=sample_index, edge=global_item, scope="broader_context"),
                    "status": "available",
                    "reason": None,
                    "value": {
                        "baseline_output_ref": f"test:{sample_index}:baseline",
                        "intervention_output": _available_tensor(
                            _transpose_variable_step(global_item["intervention_prediction"]),
                            ("forecast_step", "variable"),
                        ),
                        "metrics": {
                            key_name: global_item[key_name]
                            for key_name in (
                                "prediction_delta_abs", "prediction_delta_max", "error_delta_mae", "error_delta_mse"
                            )
                        },
                        "statistics": global_item["statistics"],
                        "metric_status": {},
                        "controls": {
                            "status": "available",
                            "protocol": global_item["controls"]["sampling"],
                            "count": global_item["controls"]["count"],
                            "random_seed": None,
                            "values": {"status": "available", "value": control_values, "reason": None},
                            "records": [],
                            "summary": _control_summary(global_item["statistics"]),
                            "records_sha256": None,
                            "model_specific": {
                                "values_source": "all other stored same-sample global edge impacts in source-target order"
                            },
                        },
                        "graph_effect": {
                            "affected_contexts": global_item["affected_scales"],
                            "scale_weights": global_item["scale_weights"],
                        },
                        "diagnostic_localization": None,
                        "limitations": [catalog["global_intervention_notice"]],
                        "provenance": {"source_run_id": catalog["global_intervention_run_id"]},
                    },
                }
            )

    configured_artifacts = [
        _source_artifact("msgnet_catalog", catalog_path, source["catalog"]),
        _source_artifact("msgnet_model_config", model_config_path, source["model_config"]),
    ]
    report = _validation_report(
        "msgnet",
        "ETTh1",
        configured_artifacts,
        {
            "local_case_count": catalog["case_count"],
            "broader_context_case_count": catalog["global_case_count"],
            "global_control_sets_materialized": catalog["global_case_count"],
            "global_control_means_verified": True,
            "negative_evidence_counts_preserved": (
                catalog["bh_supported_count"] == 0 and catalog["global_bh_supported_count"] == 0
            ),
        },
    )
    dataset_config = model_config["dataset"]
    return _common_session(
        config=config,
        config_path=config_path,
        model={
            "name": "MSGNet",
            "adapter": "MSGNetAdapter",
            "adapter_id": "msgnet",
            "native_context_type": "scale",
            "source_repository": model_config.get("source_repository"),
            "source_commit": model_config.get("source_commit"),
            "configuration": model_config["model_config"],
        },
        dataset={
            "name": "ETTh1",
            "format": "ETT CSV with date plus seven ordered variables",
            "sha256": _require_sha256(dataset_config["sha256"], "MSGNet dataset hash"),
            "variables": variables,
            "date_column": "date",
            "features": dataset_config["features"],
            "target": dataset_config["target"],
            "frequency": dataset_config["frequency"],
            "seq_len": dataset_config["seq_len"],
            "label_len": dataset_config["label_len"],
            "pred_len": dataset_config["pred_len"],
            "original_path": None,
        },
        checkpoint={
            "sha256": _require_sha256(catalog["checkpoint_sha256"], "MSGNet checkpoint hash"),
            "format": "PyTorch state_dict",
            "load_status": "validated",
            "original_path": None,
        },
        audit_plan={
            "split": "test",
            "sample_indices": [sample["sample_index"] for sample in catalog["samples"]],
            "relation_count": len(relations),
            "local_scope": "exact_native_context",
            "broader_context_scope": "all_applicable_native_contexts",
            "candidate_protocol": "all directed non-self relations at every stored native scale",
            "control_protocol": "all other directed non-self relations in the same sample and scope",
            "multiple_comparison_protocol": "stored Benjamini-Hochberg adjustment for each evidence family",
        },
        samples=samples,
        relations=relations,
        evidence_records=evidence,
        evidence_summary={
            "local_case_count": catalog["case_count"],
            "broader_context_case_count": catalog["global_case_count"],
            "local_bh_supported_count": catalog["bh_supported_count"],
            "broader_context_bh_supported_count": catalog["global_bh_supported_count"],
            "negative_evidence_preserved": True,
            "not_exposed_case_count": 0,
            "missing_case_count": 0,
        },
        cross_run_evidence={
            "status": "not_evaluated",
            "value": None,
            "reason": "Only one locally trained MSGNet checkpoint lineage is represented by the source catalog.",
        },
        source_runs=[
            _source_run("baseline", catalog["baseline_run_id"], repo_root),
            _source_run("graph", catalog["graph_run_id"], repo_root),
            _source_run("local_evidence", catalog["evidence_run_id"], repo_root),
            _source_run("broader_context_evidence", catalog["global_intervention_run_id"], repo_root),
        ],
        source_artifacts=configured_artifacts,
        validation_report=report,
        limitations=[catalog["notice"], catalog["global_intervention_notice"]],
        created_at=created_at,
    )


def load_export_config(config_path: str | Path) -> tuple[Path, dict[str, Any]]:
    path = Path(config_path).resolve()
    config = _read_json(path)
    if not isinstance(config, dict):
        raise AuditSessionError("Session export config must be a JSON object")
    if config.get("schema_version") != EXPORT_CONFIG_VERSION:
        raise AuditSessionError(f"Unsupported session export config version: {config.get('schema_version')!r}")
    if config.get("adapter") not in {"dgraformer", "msgnet"}:
        raise AuditSessionError(f"Unsupported official adapter: {config.get('adapter')!r}")
    if config.get("dataset") != "ETTh1":
        raise AuditSessionError("Session exporter v1 currently supports the official ETTh1 mappings only")
    if not isinstance(config.get("source"), dict) or not isinstance(config.get("output"), str):
        raise AuditSessionError("Session export config requires source and output fields")
    return path, config


def build_audit_session(config_path: str | Path, *, created_at: str | None = None) -> dict[str, Any]:
    path, config = load_export_config(config_path)
    repo_root = path.parent.parent.resolve()
    if config["adapter"] == "dgraformer":
        session = _build_dgraformer_session(config, path, repo_root, created_at)
    else:
        session = _build_msgnet_session(config, path, repo_root, created_at)
    errors = validate_audit_session(session)
    if errors:
        raise AuditSessionError("Generated Audit Session failed semantic validation:\n- " + "\n- ".join(errors))
    return session


def _validate_tensor(tensor: Any, path: str, errors: list[str]) -> None:
    if not isinstance(tensor, dict):
        errors.append(f"{path} must be a tensor object")
        return
    required = {"dtype", "shape", "axis_order", "values"}
    if not required.issubset(tensor):
        errors.append(f"{path} is missing tensor fields {sorted(required - set(tensor))}")
        return
    try:
        actual_shape = _shape(tensor["values"])
    except AuditSessionError as exc:
        errors.append(f"{path}: {exc}")
        return
    if tensor["shape"] != actual_shape:
        errors.append(f"{path} declares shape {tensor['shape']} but values have shape {actual_shape}")
    if len(tensor["axis_order"]) != len(tensor["shape"]):
        errors.append(f"{path} axis count does not match tensor rank")
    try:
        _ensure_finite(tensor["values"], path)
    except AuditSessionError as exc:
        errors.append(str(exc))


def _validate_nullable_tensor(wrapper: Any, path: str, errors: list[str]) -> None:
    if not isinstance(wrapper, dict) or set(wrapper) != {"status", "value", "reason"}:
        errors.append(f"{path} must be a strict nullable tensor wrapper")
        return
    if wrapper["status"] == "available":
        if wrapper["reason"] is not None:
            errors.append(f"{path}.reason must be null when available")
        _validate_tensor(wrapper["value"], f"{path}.value", errors)
    elif wrapper["status"] in {"missing", "unavailable"}:
        if wrapper["value"] is not None or not isinstance(wrapper["reason"], str) or not wrapper["reason"]:
            errors.append(f"{path} missing/unavailable state requires null value and a reason")
    else:
        errors.append(f"{path}.status is unsupported")


def validate_audit_session(session: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(session, dict):
        return ["Session must be a JSON object"]
    required = {
        "schema_version", "session", "model", "dataset", "checkpoint", "audit_plan", "samples",
        "relations", "evidence_records", "evidence_summary", "cross_run_evidence", "provenance", "limitations",
    }
    allowed = required | {"model_specific"}
    if set(session) - allowed:
        errors.append(f"Unsupported top-level fields: {sorted(set(session) - allowed)}")
    missing = required - set(session)
    if missing:
        return [*errors, f"Missing top-level fields: {sorted(missing)}"]
    if session["schema_version"] != SESSION_SCHEMA_VERSION:
        errors.append(f"Unsupported schema_version {session['schema_version']!r}")

    model = session["model"]
    expected_model = {
        "dgraformer": ("DGraFormer", "DGraFormerAdapter", "window"),
        "msgnet": ("MSGNet", "MSGNetAdapter", "scale"),
        "mtgnn": ("MTGNN", "MTGNNAdapter", "global_graph"),
    }.get(model.get("adapter_id")) if isinstance(model, dict) else None
    if expected_model is not None and (model.get("name"), model.get("adapter"), model.get("native_context_type")) != expected_model:
        errors.append("Model, adapter, adapter_id, and native context type are inconsistent")
    if not isinstance(model, dict) or not all(isinstance(model.get(field), str) and model.get(field) for field in (
        "name", "adapter", "adapter_id", "native_context_type"
    )):
        errors.append("Model must declare a non-empty self-describing adapter contract")
    elif not re.fullmatch(r"[a-z][a-z0-9_-]*", model["adapter_id"]):
        errors.append("Model adapter_id has an invalid portable identifier")

    dataset = session["dataset"]
    variables = dataset.get("variables", []) if isinstance(dataset, dict) else []
    if not variables or len(set(variables)) != len(variables):
        errors.append("Dataset variables must be a non-empty unique list")
    for owner, field in ((dataset, "sha256"), (session["checkpoint"], "sha256")):
        try:
            _require_sha256(owner.get(field), field)
        except AuditSessionError as exc:
            errors.append(str(exc))

    sample_by_id: dict[str, dict[str, Any]] = {}
    sample_indices: set[int] = set()
    contexts_by_sample: dict[str, dict[str, dict[str, Any]]] = {}
    for index, sample in enumerate(session["samples"]):
        path = f"samples[{index}]"
        sample_id = sample.get("sample_id")
        sample_index = sample.get("sample_index")
        if sample_id in sample_by_id or sample_index in sample_indices:
            errors.append(f"{path} duplicates a sample ID or index")
            continue
        if sample_id != f"test:{sample_index}":
            errors.append(f"{path} sample_id does not canonically encode sample_index")
        sample_by_id[sample_id] = sample
        sample_indices.add(sample_index)
        _validate_nullable_tensor(sample.get("history"), f"{path}.history", errors)
        _validate_tensor(sample.get("ground_truth"), f"{path}.ground_truth", errors)
        _validate_tensor(sample.get("baseline_prediction"), f"{path}.baseline_prediction", errors)
        context_map: dict[str, dict[str, Any]] = {}
        for context_index, context in enumerate(sample.get("contexts", [])):
            context_path = f"{path}.contexts[{context_index}]"
            context_id = context.get("context_id")
            if context_id in context_map:
                errors.append(f"{context_path} duplicates context_id {context_id}")
            context_map[context_id] = context
            if context.get("type") != model.get("native_context_type"):
                errors.append(f"{context_path} changes the model-native context semantics")
            if context.get("node_count") != len(variables):
                errors.append(f"{context_path} node_count differs from dataset variable count")
            for graph_name, graph in context.get("graphs", {}).items():
                _validate_tensor(graph, f"{context_path}.graphs.{graph_name}", errors)
                if graph.get("shape") != [len(variables), len(variables)]:
                    errors.append(f"{context_path}.graphs.{graph_name} is not a variable-by-variable graph")
                if graph.get("axis_order") != ["source_node", "target_node"]:
                    errors.append(f"{context_path}.graphs.{graph_name} has incompatible axes")
        if not context_map:
            errors.append(f"{path} has no native graph contexts")
        contexts_by_sample[sample_id] = context_map

    plan_indices = session["audit_plan"].get("sample_indices")
    if plan_indices != [sample["sample_index"] for sample in session["samples"]]:
        errors.append("audit_plan.sample_indices does not match exported sample order")

    relation_by_id: dict[str, dict[str, Any]] = {}
    for index, relation in enumerate(session["relations"]):
        path = f"relations[{index}]"
        relation_id = relation.get("relation_id")
        if relation_id in relation_by_id:
            errors.append(f"{path} duplicates relation_id {relation_id}")
            continue
        relation_by_id[relation_id] = relation
        sample = sample_by_id.get(relation.get("sample_id"))
        if sample is None:
            errors.append(f"{path} references an unknown sample")
            continue
        source_index, target_index = relation.get("source"), relation.get("target")
        if not isinstance(source_index, int) or not isinstance(target_index, int) or not (
            0 <= source_index < len(variables) and 0 <= target_index < len(variables) and source_index != target_index
        ):
            errors.append(f"{path} source/target is not a valid directed non-self relation")
        elif relation.get("source_name") != variables[source_index] or relation.get("target_name") != variables[target_index]:
            errors.append(f"{path} source/target names disagree with dataset variables")
        for occurrence in relation.get("native_occurrences", []):
            if occurrence.get("context_id") not in contexts_by_sample[relation["sample_id"]]:
                errors.append(f"{path} occurrence references an unknown context")

    evidence_by_id: dict[str, dict[str, Any]] = {}
    evidence_for_relation: dict[str, list[str]] = defaultdict(list)
    exact_keys: set[tuple[Any, ...]] = set()
    local_count = broader_count = not_exposed_count = missing_count = 0
    local_supported = broader_supported = 0
    for index, record in enumerate(session["evidence_records"]):
        path = f"evidence_records[{index}]"
        evidence_id = record.get("evidence_id")
        if evidence_id in evidence_by_id:
            errors.append(f"{path} duplicates evidence_id {evidence_id}")
            continue
        evidence_by_id[evidence_id] = record
        relation = relation_by_id.get(record.get("relation_id"))
        if relation is None:
            errors.append(f"{path} references an unknown relation")
            continue
        evidence_for_relation[record["relation_id"]].append(evidence_id)
        selection = record.get("selection", {})
        scope = selection.get("scope")
        if scope == "local":
            local_count += 1
        elif scope == "broader_context":
            broader_count += 1
            if model.get("native_context_type") == "global_graph":
                errors.append(f"{path} global_graph model cannot declare a broader context")
        else:
            errors.append(f"{path} has an unsupported evidence scope")
        expected_selection = {
            "model": model.get("name"),
            "dataset": dataset.get("name"),
            "sample_id": relation.get("sample_id"),
            "source": relation.get("source"),
            "target": relation.get("target"),
            "source_name": relation.get("source_name"),
            "target_name": relation.get("target_name"),
        }
        for field, expected in expected_selection.items():
            if selection.get(field) != expected:
                errors.append(f"{path}.selection.{field} disagrees with its relation/session")
        sample = sample_by_id.get(relation.get("sample_id"))
        if sample and selection.get("sample_index") != sample.get("sample_index"):
            errors.append(f"{path}.selection.sample_index disagrees with its sample")
        if scope == "local":
            if selection.get("context_id") not in contexts_by_sample.get(relation.get("sample_id"), {}):
                errors.append(f"{path} local selection references an unknown exact context")
            if selection.get("context_index") == "all_applicable":
                errors.append(f"{path} local selection cannot use all_applicable")
        elif selection.get("context_index") != "all_applicable":
            errors.append(f"{path} broader selection must use all_applicable")
        exact_key = tuple(selection.get(field) for field in (
            "model", "dataset", "sample_id", "sample_index", "context_type", "context_id", "context_index",
            "layer", "source", "target", "source_name", "target_name", "scope",
        ))
        if exact_key in exact_keys:
            errors.append(f"{path} duplicates an exact evidence selection")
        exact_keys.add(exact_key)

        status = record.get("status")
        value = record.get("value")
        if status in {"missing", "unavailable"}:
            missing_count += 1
            if value is not None or not record.get("reason"):
                errors.append(f"{path} missing/unavailable evidence requires null value and a reason")
            continue
        if status == "not_exposed":
            not_exposed_count += 1
            if not record.get("reason"):
                errors.append(f"{path} not_exposed evidence requires a reason")
        elif status != "available" or record.get("reason") is not None:
            errors.append(f"{path} has inconsistent available evidence status/reason")
        if not isinstance(value, dict):
            errors.append(f"{path} available/not_exposed evidence requires a payload")
            continue
        if value.get("baseline_output_ref") != f"{relation['sample_id']}:baseline":
            errors.append(f"{path} baseline_output_ref does not resolve to its sample")
        _validate_nullable_tensor(value.get("intervention_output"), f"{path}.value.intervention_output", errors)
        controls = value.get("controls", {})
        control_values = controls.get("values", {})
        if controls.get("status") == "available":
            if control_values.get("status") != "available" or not isinstance(control_values.get("value"), list):
                errors.append(f"{path} available controls require stored values")
            elif controls.get("count") != len(control_values["value"]):
                errors.append(f"{path} control count does not match stored values")
        p_value = value.get("statistics", {}).get("bh_adjusted_p")
        if isinstance(p_value, (int, float)) and p_value < 0.05:
            if scope == "local":
                local_supported += 1
            else:
                broader_supported += 1
        try:
            _ensure_finite(value, f"{path}.value")
        except AuditSessionError as exc:
            errors.append(str(exc))

    for relation_id, relation in relation_by_id.items():
        declared_ids = relation.get("evidence_ids", [])
        actual_ids = evidence_for_relation.get(relation_id, [])
        if len(declared_ids) != len(set(declared_ids)) or set(declared_ids) != set(actual_ids):
            errors.append(f"Relation {relation_id} evidence_ids do not exactly match stored evidence records")
    if session["audit_plan"].get("relation_count") != len(session["relations"]):
        errors.append("audit_plan.relation_count does not match relations")
    summary = session["evidence_summary"]
    expected_counts = {
        "local_case_count": local_count,
        "broader_context_case_count": broader_count,
        "local_bh_supported_count": local_supported,
        "broader_context_bh_supported_count": broader_supported,
        "not_exposed_case_count": not_exposed_count,
        "missing_case_count": missing_count,
    }
    for field, expected in expected_counts.items():
        if summary.get(field) != expected:
            errors.append(f"evidence_summary.{field}={summary.get(field)!r}, expected {expected}")
    if summary.get("negative_evidence_preserved") is not True:
        errors.append("Negative evidence must be preserved")

    cross_run = session["cross_run_evidence"]
    if cross_run.get("status") in {"missing", "not_evaluated", "unavailable"} and (
        cross_run.get("value") is not None or not cross_run.get("reason")
    ):
        errors.append("Missing cross-run evidence requires null value and a reason")
    report = session.get("model_specific", {}).get("artifact_validation_report")
    validation_hash = session["provenance"].get("validation", {}).get("report_sha256")
    if report is None or _value_sha256(report) != validation_hash:
        errors.append("Embedded artifact validation report does not match provenance hash")
    if session["session"].get("generator", {}).get("run_id") != session["provenance"].get("session_generation_run_id"):
        errors.append("Session generator run ID and provenance run ID disagree")
    return errors


def write_audit_session(
    config_path: str | Path,
    *,
    output_path: str | Path | None = None,
    created_at: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    path, config = load_export_config(config_path)
    session = build_audit_session(path, created_at=created_at)
    output = Path(output_path).resolve() if output_path else _resolve(path, config["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(session, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return output, session

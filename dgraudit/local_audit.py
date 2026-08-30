from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import torch

from dgraudit.session import (
    GENERATOR_NAME,
    SESSION_SCHEMA_VERSION,
    AuditSessionError,
    _file_sha256,
    _value_sha256,
    validate_audit_session,
)
from dgraudit.validation import OFFICIAL_ADAPTER_REGISTRY, render_validation_report, validate_audit_config


Progress = Callable[[str], None]
LOCAL_AUDIT_GENERATOR_VERSION = "1.2"


class LocalAuditError(AuditSessionError):
    """Raised when supported local inputs cannot produce an audit session."""


def _resolve(base: Path, raw: str) -> Path:
    path = Path(raw)
    return (base / path).resolve() if not path.is_absolute() else path.resolve()


def _array(value: Any, *, squeeze_batch: bool = False) -> np.ndarray:
    if isinstance(value, torch.Tensor):
        result = value.detach().cpu().numpy()
    else:
        result = np.asarray(value)
    if squeeze_batch and result.ndim == 3 and result.shape[0] == 1:
        result = result[0]
    if not np.isfinite(result).all():
        raise LocalAuditError("The offline audit produced a non-finite tensor.")
    return result


def _tensor(value: Any, axes: Sequence[str], *, squeeze_batch: bool = False) -> dict[str, Any]:
    array = _array(value, squeeze_batch=squeeze_batch)
    if array.ndim != len(axes):
        raise LocalAuditError(f"Tensor rank {array.ndim} does not match axes {list(axes)}.")
    return {
        "dtype": str(array.dtype),
        "shape": list(array.shape),
        "axis_order": list(axes),
        "values": array.tolist(),
    }


def _available_tensor(value: Any, axes: Sequence[str], *, squeeze_batch: bool = False) -> dict[str, Any]:
    return {"status": "available", "value": _tensor(value, axes, squeeze_batch=squeeze_batch), "reason": None}


def _metrics(baseline: Any, intervention: Any, truth: Any) -> dict[str, float]:
    base = _array(baseline)
    changed = _array(intervention)
    target = _array(truth)
    if base.shape != changed.shape or base.shape != target.shape:
        raise LocalAuditError(
            f"Prediction/target shape mismatch: baseline={base.shape}, intervention={changed.shape}, truth={target.shape}."
        )
    delta = changed - base
    base_error = base - target
    changed_error = changed - target
    return {
        "baseline_mae": float(np.abs(base_error).mean()),
        "baseline_mse": float(np.square(base_error).mean()),
        "intervention_mae": float(np.abs(changed_error).mean()),
        "intervention_mse": float(np.square(changed_error).mean()),
        "prediction_delta_abs": float(np.abs(delta).mean()),
        "prediction_delta_max": float(np.abs(delta).max()),
        "error_delta_mae": float(np.abs(changed_error).mean() - np.abs(base_error).mean()),
        "error_delta_mse": float(np.square(changed_error).mean() - np.square(base_error).mean()),
    }


def _average_ranks_descending(matrix: np.ndarray) -> dict[tuple[int, int], float]:
    entries = [
        (float(matrix[source, target]), source, target)
        for source in range(matrix.shape[0])
        for target in range(matrix.shape[1])
        if source != target
    ]
    entries.sort(key=lambda item: (-item[0], item[1], item[2]))
    result: dict[tuple[int, int], float] = {}
    cursor = 0
    while cursor < len(entries):
        end = cursor + 1
        while end < len(entries) and entries[end][0] == entries[cursor][0]:
            end += 1
        rank = ((cursor + 1) + end) / 2.0
        for _, source, target in entries[cursor:end]:
            result[(source, target)] = rank
        cursor = end
    return result


def _bh_adjust(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    order = np.argsort(np.asarray(values, dtype=float))
    adjusted = np.empty(len(values), dtype=float)
    running = 1.0
    for reverse_position in range(len(values) - 1, -1, -1):
        original_index = int(order[reverse_position])
        rank = reverse_position + 1
        running = min(running, float(values[original_index]) * len(values) / rank)
        adjusted[original_index] = min(1.0, running)
    return adjusted.tolist()


def _statistics(values: Sequence[float], focal: float, bootstrap: int, seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    controls = np.asarray(values, dtype=float)
    if controls.size == 0:
        raise LocalAuditError("No eligible real intervention remains for the matched-control family.")
    empirical_p = float((1 + np.sum(controls >= focal)) / (controls.size + 1))
    percentile = float(100 * (np.mean(controls < focal) + 0.5 * np.mean(controls == focal)))
    standard_deviation = float(controls.std(ddof=1)) if controls.size > 1 else 0.0
    effect = None if standard_deviation == 0 else float((focal - controls.mean()) / standard_deviation)
    rng = np.random.default_rng(seed)
    sampled_means = rng.choice(controls, size=(bootstrap, controls.size), replace=True).mean(axis=1)
    interval = np.quantile(focal - sampled_means, [0.025, 0.975]).tolist()
    statistics = {
        "control_mean_prediction_delta_abs": float(controls.mean()),
        "control_median_prediction_delta_abs": float(np.median(controls)),
        "control_percentile_midrank": percentile,
        "empirical_p": empirical_p,
        "bh_adjusted_p": None,
        "standardized_effect_size": effect,
        "candidate_minus_control_mean_bootstrap_ci_95": [float(interval[0]), float(interval[1])],
        "bootstrap_repetitions": int(bootstrap),
        "bootstrap_seed": int(seed),
    }
    metric_status = {
        "standardized_effect_size": {
            "status": "available" if effect is not None else "undefined",
            "reason": None if effect is not None else "The matched-control standard deviation is zero.",
        }
    }
    return statistics, metric_status


def _context_id(adapter_id: str, context: Mapping[str, Any]) -> str:
    if adapter_id == "dgraformer":
        return f"window:{int(context['window'])}"
    if adapter_id == "mtgnn":
        return f"global_graph:{int(context['index'])}"
    return f"layer:{int(context['layer'])}:scale:{int(context['scale_index'])}"


def _context_weight(adapter_id: str, context: Mapping[str, Any]) -> np.ndarray:
    if adapter_id == "dgraformer":
        return _array(context["normalized"])
    if adapter_id == "mtgnn":
        return _array(context["learned_adjacency"])
    return _array(context["adaptive"])


def _portable_context(adapter_id: str, context: Mapping[str, Any], node_count: int) -> dict[str, Any]:
    if adapter_id == "dgraformer":
        graph_names = (
            "static_prior", "raw_score", "activated", "diagonal_removed", "topk_mask",
            "topk_graph", "self_loop_graph", "normalized",
        )
        return {
            "context_id": _context_id(adapter_id, context),
            "type": "window",
            "index": int(context["window"]),
            "node_count": node_count,
            "graphs": {name: _tensor(context[name], ("source_node", "target_node")) for name in graph_names},
            "native_metadata": {
                "topk_slots": int(context["topk_slots"]),
                "blend_proportion": float(context["blend_proportion"]),
            },
        }
    if adapter_id == "mtgnn":
        graph_names = ("learned_adjacency", "transpose_adjacency")
        return {
            "context_id": _context_id(adapter_id, context),
            "type": "global_graph",
            "index": int(context["index"]),
            "node_count": node_count,
            "graphs": {name: _tensor(context[name], ("source_node", "target_node")) for name in graph_names},
            "native_metadata": {
                "edge_count": int(context["edge_count"]),
                "subgraph_size": int(context["subgraph_size"]),
                "gcn_layer_count": int(context["gcn_layer_count"]),
                "construction": str(context["construction"]),
            },
        }
    graph_names = ("raw_affinity", "activated", "adaptive", "self_loop_graph", "effective")
    return {
        "context_id": _context_id(adapter_id, context),
        "type": "scale",
        "index": int(context["scale_index"]),
        "layer": int(context["layer"]),
        "node_count": node_count,
        "graphs": {name: _tensor(context[name], ("source_node", "target_node")) for name in graph_names},
        "native_metadata": {
            "period": int(context["period"]),
            "fft_strength": float(context["fft_strength"]),
            "scale_contribution": float(context["scale_contribution"]),
        },
    }


def _find_context(adapter_id: str, contexts: Sequence[Mapping[str, Any]], requested: Mapping[str, Any]) -> Mapping[str, Any]:
    if adapter_id == "dgraformer":
        match = next((item for item in contexts if int(item["window"]) == int(requested["index"])), None)
    elif adapter_id == "mtgnn":
        match = next((item for item in contexts if int(item["index"]) == int(requested["index"])), None)
    else:
        layer = int(requested.get("layer", 0))
        match = next(
            (item for item in contexts if int(item["layer"]) == layer and int(item["scale_index"]) == int(requested["index"])),
            None,
        )
    if match is None:
        raise LocalAuditError(f"The exact requested native context is unavailable: {dict(requested)}")
    return match


def _eligible_edges(adapter_id: str, contexts: Sequence[Mapping[str, Any]], requested: Mapping[str, Any], broader: bool) -> list[tuple[int, int]]:
    matrices = [_context_weight(adapter_id, item) for item in contexts]
    if not broader:
        matrices = [_context_weight(adapter_id, _find_context(adapter_id, contexts, requested))]
    node_count = matrices[0].shape[0]
    return [
        (source, target)
        for source in range(node_count)
        for target in range(node_count)
        if source != target and any(float(matrix[source, target]) > 0 for matrix in matrices)
    ]


def _control_edges(
    adapter_id: str,
    contexts: Sequence[Mapping[str, Any]],
    requested: Mapping[str, Any],
    focal: tuple[int, int],
    broader: bool,
    seed: int,
) -> tuple[list[tuple[int, int]], str]:
    eligible = [edge for edge in _eligible_edges(adapter_id, contexts, requested, broader) if edge != focal]
    if not eligible:
        return [], "no eligible controls"
    if adapter_id in {"msgnet", "mtgnn"}:
        return eligible, "all other real directed non-self edge removals in the same sample and scope"
    rng = np.random.default_rng(seed)
    if not broader:
        sampled = [eligible[int(rng.integers(0, len(eligible)))] for _ in range(100)]
        return sampled, "100 seeded draws from retained same-window non-self edges excluding the focal edge"
    matrices = [_context_weight(adapter_id, item) for item in contexts]

    def signature(edge: tuple[int, int]) -> tuple[int, float]:
        values = [float(matrix[edge]) for matrix in matrices]
        positive = [value for value in values if value > 0]
        return len(positive), float(np.mean(positive)) if positive else 0.0

    focal_count, focal_weight = signature(focal)
    eligible.sort(key=lambda edge: (
        abs(signature(edge)[0] - focal_count),
        abs(signature(edge)[1] - focal_weight),
        edge,
    ))
    pool = eligible[:10]
    sampled = [pool[int(rng.integers(0, len(pool)))] for _ in range(100)]
    return sampled, (
        "100 seeded draws from the 10 nearest retained relations, matched by retained-context count "
        "then mean normalized weight"
    )


def _selection(
    adapter_id: str,
    model_name: str,
    dataset_name: str,
    relation: Mapping[str, Any],
    variables: Sequence[str],
    broader: bool,
) -> dict[str, Any]:
    sample_index = int(relation["sample"])
    source, target = int(relation["source"]), int(relation["target"])
    context = relation["context"]
    if adapter_id == "dgraformer":
        context_type = "window_set" if broader else "window"
        context_id = "window-set:all" if broader else f"window:{int(context['index'])}"
        result: dict[str, Any] = {
            "model": model_name,
            "dataset": dataset_name,
            "sample_id": f"test:{sample_index}",
            "sample_index": sample_index,
            "context_type": context_type,
            "context_id": context_id,
            "context_index": "all_applicable" if broader else int(context["index"]),
            "source": source,
            "target": target,
            "source_name": variables[source],
            "target_name": variables[target],
            "scope": "broader_context" if broader else "local",
        }
    elif adapter_id == "msgnet":
        layer = int(context.get("layer", 0))
        context_type = "scale_set" if broader else "scale"
        context_id = f"layer:{layer}:scale-set:all" if broader else f"layer:{layer}:scale:{int(context['index'])}"
        result = {
            "model": model_name,
            "dataset": dataset_name,
            "sample_id": f"test:{sample_index}",
            "sample_index": sample_index,
            "context_type": context_type,
            "context_id": context_id,
            "context_index": "all_applicable" if broader else int(context["index"]),
            "layer": layer,
            "source": source,
            "target": target,
            "source_name": variables[source],
            "target_name": variables[target],
            "scope": "broader_context" if broader else "local",
        }
    else:
        if broader:
            raise LocalAuditError("MTGNN exposes only one global learned graph; broader context is unavailable.")
        result = {
            "model": model_name,
            "dataset": dataset_name,
            "sample_id": f"test:{sample_index}",
            "sample_index": sample_index,
            "context_type": "global_graph",
            "context_id": f"global_graph:{int(context['index'])}",
            "context_index": int(context["index"]),
            "source": source,
            "target": target,
            "source_name": variables[source],
            "target_name": variables[target],
            "scope": "local",
        }
    return result


def _seed_for(base_seed: int, selection: Mapping[str, Any]) -> int:
    material = json.dumps(selection, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return int(base_seed) + int(hashlib.sha256(material).hexdigest()[:7], 16)


def _embedded_preflight(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": "adapter_preflight",
        "status": "passed",
        "schema_version": report.get("schema_version"),
        "adapter": report.get("adapter"),
        "checks": [
            {
                key: check.get(key)
                for key in ("id", "name", "label", "status", "code", "message")
                if check.get(key) is not None
            }
            for check in report.get("checks", [])
        ],
        "measurements": report.get("measurements", {}),
        "runtime": report.get("runtime", {}),
        "dataset_sha256": report.get("dataset", {}).get("sha256"),
        "checkpoint_sha256": report.get("checkpoint", {}).get("sha256"),
    }


def run_local_audit(
    config_path: str | Path,
    *,
    output_path: str | Path = "dgrainsight_session.json",
    bootstrap_repetitions: int = 2000,
    progress: Progress | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Run a supported checkpoint audit locally and write one portable JSON session."""

    announce = progress or (lambda _message: None)
    if bootstrap_repetitions < 1:
        raise LocalAuditError("bootstrap_repetitions must be at least 1.")
    config_file = Path(config_path).resolve()
    destination = Path(output_path)
    if not destination.is_absolute():
        destination = (Path.cwd() / destination).resolve()
    announce("Running required V01-V09 adapter preflight")
    preflight = validate_audit_config(config_file)
    if preflight.get("status") != "ready_for_audit":
        raise LocalAuditError(render_validation_report(preflight))

    config = json.loads(config_file.read_text(encoding="utf-8"))
    spec = OFFICIAL_ADAPTER_REGISTRY[config["adapter"]]
    resolved = {
        "source_root": _resolve(config_file.parent, config["source_root"]),
        "dataset": _resolve(config_file.parent, config["dataset"]["path"]),
        "checkpoint": _resolve(config_file.parent, config["checkpoint"]["path"]),
    }
    adapter = spec.create_adapter(config, resolved)
    samples_runtime: dict[int, dict[str, Any]] = {}
    portable_samples: list[dict[str, Any]] = []
    adapter_id = spec.adapter_id
    variables = list(config["dataset"]["variables"])
    pred_len = int(config["dataset"]["pred_len"])
    try:
        announce(f"Loading validated {spec.model_name} checkpoint")
        adapter.load_checkpoint(str(resolved["checkpoint"]))
        for display_id, raw_index in enumerate(config["audit"]["samples"]):
            sample_index = int(raw_index)
            announce(f"Computing baseline and native graph for test sample {sample_index}")
            raw_batch = adapter.load_sample(config["audit"]["split"], sample_index)
            batch = spec.prepare_batch(raw_batch, config)
            baseline = adapter.predict(batch)
            truth = torch.as_tensor(batch["y"][-pred_len:, :], dtype=torch.float32).unsqueeze(0)
            extracted = adapter.extract_graph_stages(batch)
            contexts = list(extracted["windows"] if adapter_id == "dgraformer" else extracted["contexts"])
            sample_metrics = _metrics(baseline, baseline, truth)
            portable_samples.append({
                "sample_id": f"test:{sample_index}",
                "display_id": display_id,
                "split": "test",
                "sample_index": sample_index,
                "history": _available_tensor(batch["x"], ("input_step", "variable")),
                "ground_truth": _tensor(truth, ("forecast_step", "variable"), squeeze_batch=True),
                "baseline_prediction": _tensor(baseline, ("forecast_step", "variable"), squeeze_batch=True),
                "sample_metrics": {
                    "baseline_mae": sample_metrics["baseline_mae"],
                    "baseline_mse": sample_metrics["baseline_mse"],
                },
                "contexts": [_portable_context(adapter_id, item, len(variables)) for item in contexts],
                "provenance": {"source": "direct validated checkpoint replay"},
            })
            samples_runtime[sample_index] = {
                "batch": batch,
                "baseline": baseline,
                "truth": truth,
                "contexts": contexts,
            }

        prediction_cache: dict[tuple[Any, ...], tuple[Any, Mapping[str, Any], dict[str, float]]] = {}

        def replay(relation: Mapping[str, Any], source: int, target: int, broader: bool):
            sample_index = int(relation["sample"])
            context = relation["context"]
            context_key = (
                int(context.get("layer", 0)), int(context["index"])
            ) if adapter_id == "msgnet" else int(context["index"])
            key = (sample_index, "broader" if broader else "local", context_key, source, target)
            if key not in prediction_cache:
                probe = {**dict(relation), "source": source, "target": target}
                override = spec.intervention_override(probe, config, broader=broader)
                runtime = samples_runtime[sample_index]
                outcome = adapter.predict_with_graph_override(runtime["batch"], override)
                prediction = outcome["prediction"]
                prediction_cache[key] = (
                    prediction,
                    outcome,
                    _metrics(runtime["baseline"], prediction, runtime["truth"]),
                )
            return prediction_cache[key]

        relation_map: dict[tuple[int, int, int], dict[str, Any]] = {}
        relation_configs: dict[tuple[int, int, int], list[Mapping[str, Any]]] = {}
        for requested in config["audit"]["relations"]:
            key = (int(requested["sample"]), int(requested["source"]), int(requested["target"]))
            relation_configs.setdefault(key, []).append(requested)
        for (sample_index, source, target), requested_relations in relation_configs.items():
            relation_id = f"test:{sample_index}:edge:{source}->{target}"
            occurrences = []
            for context in samples_runtime[sample_index]["contexts"]:
                weights = _context_weight(adapter_id, context)
                ranks = _average_ranks_descending(weights)
                weight = float(weights[source, target])
                occurrences.append({
                    "context_id": _context_id(adapter_id, context),
                    "weight": weight,
                    "retained": weight > 0,
                    "rank": ranks[(source, target)],
                })
            relation_map[(sample_index, source, target)] = {
                "relation_id": relation_id,
                "sample_id": f"test:{sample_index}",
                "source": source,
                "target": target,
                "source_name": variables[source],
                "target_name": variables[target],
                "native_occurrences": occurrences,
                "evidence_ids": [],
            }

        evidence_records: list[dict[str, Any]] = []
        seen_exact: set[tuple[Any, ...]] = set()
        for requested in config["audit"]["relations"]:
            sample_index = int(requested["sample"])
            source, target = int(requested["source"]), int(requested["target"])
            relation_key = (sample_index, source, target)
            runtime = samples_runtime[sample_index]
            for broader in ([False, True] if requested.get("include_broader_context") else [False]):
                selection = _selection(adapter_id, spec.model_name, config["dataset"]["name"], requested, variables, broader)
                exact_key = tuple(selection.get(field) for field in (
                    "model", "dataset", "sample_id", "sample_index", "context_type", "context_id",
                    "context_index", "layer", "source", "target", "scope",
                ))
                if exact_key in seen_exact:
                    continue
                seen_exact.add(exact_key)
                scope_label = "broader context" if broader else "exact native context"
                announce(
                    f"Auditing test sample {sample_index}, {variables[source]}->{variables[target]}, {scope_label}"
                )
                focal_prediction, focal_outcome, focal_metrics = replay(requested, source, target, broader)
                seed = _seed_for(int(config["adapter_config"]["random_seed"]), selection)
                selected_controls, control_protocol = _control_edges(
                    adapter_id,
                    runtime["contexts"],
                    requested["context"],
                    (source, target),
                    broader,
                    seed,
                )
                control_records: list[dict[str, Any]] = []
                control_values: list[float] = []
                for repetition, (control_source, control_target) in enumerate(selected_controls):
                    _, _, control_metrics = replay(requested, control_source, control_target, broader)
                    control_values.append(control_metrics["prediction_delta_abs"])
                    control_records.append({
                        "repetition": repetition,
                        "source": control_source,
                        "target": control_target,
                        "source_name": variables[control_source],
                        "target_name": variables[control_target],
                        "prediction_delta_abs": control_metrics["prediction_delta_abs"],
                    })
                statistics, metric_status = _statistics(
                    control_values, focal_metrics["prediction_delta_abs"], bootstrap_repetitions, seed
                )
                if broader:
                    weights = [float(_context_weight(adapter_id, item)[source, target]) for item in runtime["contexts"]]
                    graph_effect = {
                        "native_context_weights": weights,
                        "affected_context_ids": [
                            _context_id(adapter_id, item)
                            for item, weight in zip(runtime["contexts"], weights)
                            if weight > 0
                        ],
                    }
                else:
                    context = _find_context(adapter_id, runtime["contexts"], requested["context"])
                    matrix = _context_weight(adapter_id, context)
                    model_metadata = ({
                        "period": int(context["period"]),
                        "fft_strength": float(context["fft_strength"]),
                        "scale_contribution": float(context["scale_contribution"]),
                    } if adapter_id == "msgnet" else ({
                        "blend_proportion": float(context["blend_proportion"]),
                        "topk_slots": int(context["topk_slots"]),
                    } if adapter_id == "dgraformer" else {
                        "edge_count": int(context["edge_count"]),
                        "subgraph_size": int(context["subgraph_size"]),
                        "shared_across_gcn_layers": True,
                    }))
                    graph_effect = {
                        "native_weight": float(matrix[source, target]),
                        "weight_rank": _average_ranks_descending(matrix)[(source, target)],
                        **model_metadata,
                    }
                context_token = str(selection["context_id"]).replace(":", "_").replace("-", "_")
                evidence_id = f"local_{adapter_id}_s{sample_index}_{context_token}_e{source}_{target}"
                evidence = {
                    "evidence_id": evidence_id,
                    "relation_id": relation_map[relation_key]["relation_id"],
                    "selection": selection,
                    "status": "available",
                    "reason": None,
                    "value": {
                        "baseline_output_ref": f"test:{sample_index}:baseline",
                        "intervention_output": _available_tensor(
                            focal_prediction, ("forecast_step", "variable"), squeeze_batch=True
                        ),
                        "metrics": focal_metrics,
                        "statistics": statistics,
                        "metric_status": metric_status,
                        "controls": {
                            "status": "available",
                            "protocol": control_protocol,
                            "count": len(control_values),
                            "random_seed": seed,
                            "values": {"status": "available", "value": control_values, "reason": None},
                            "records": control_records,
                            "summary": {
                                key: value for key, value in statistics.items()
                                if key.startswith("control_") or key.startswith("candidate_minus_control_")
                            },
                            "records_sha256": None,
                        },
                        "graph_effect": graph_effect,
                        "diagnostic_localization": None,
                        "limitations": [
                            "Checkpoint-internal intervention evidence only; not a real-world causal claim.",
                            "Cross-checkpoint replication was not evaluated in this single-checkpoint local session.",
                        ],
                        "provenance": {
                            "adapter": spec.adapter_name,
                            "intervention_protocol": focal_outcome.get("protocol"),
                        },
                    },
                }
                evidence_records.append(evidence)
                relation_map[relation_key]["evidence_ids"].append(evidence_id)

        for scope in ("local", "broader_context"):
            family = [record for record in evidence_records if record["selection"]["scope"] == scope]
            adjusted = _bh_adjust([record["value"]["statistics"]["empirical_p"] for record in family])
            for record, value in zip(family, adjusted):
                record["value"]["statistics"]["bh_adjusted_p"] = value

        config_hash = _file_sha256(config_file)
        dataset_hash = _file_sha256(resolved["dataset"])
        checkpoint_hash = _file_sha256(resolved["checkpoint"])
        package_root = Path(__file__).resolve().parent
        repository_root = package_root.parent
        code_paths = {
            "local_audit": Path(__file__).resolve(),
            "adapters": package_root / "adapters.py",
            "validation": package_root / "validation.py",
            "session_schema": repository_root / "schemas" / "dgrainsight_audit_session_v1.schema.json",
        }
        code_hashes = {role: _file_sha256(path) for role, path in code_paths.items()}
        run_id = _value_sha256({
            "generator_version": LOCAL_AUDIT_GENERATOR_VERSION,
            "config_sha256": config_hash,
            "dataset_sha256": dataset_hash,
            "checkpoint_sha256": checkpoint_hash,
            "bootstrap_repetitions": bootstrap_repetitions,
            "code_sha256": code_hashes,
        })
        embedded_preflight = _embedded_preflight(preflight)
        local_count = sum(record["selection"]["scope"] == "local" for record in evidence_records)
        broader_count = len(evidence_records) - local_count
        local_supported = sum(
            record["selection"]["scope"] == "local" and record["value"]["statistics"]["bh_adjusted_p"] < 0.05
            for record in evidence_records
        )
        broader_supported = sum(
            record["selection"]["scope"] == "broader_context" and record["value"]["statistics"]["bh_adjusted_p"] < 0.05
            for record in evidence_records
        )
        model_configuration = {
            **dict(config["adapter_config"]["model"]),
            "random_seed": int(config["adapter_config"]["random_seed"]),
        }
        if "current_epoch" in config["adapter_config"]:
            model_configuration["current_epoch"] = int(config["adapter_config"]["current_epoch"])
        broader_requested = any(item.get("include_broader_context") for item in config["audit"]["relations"])
        session = {
            "schema_version": SESSION_SCHEMA_VERSION,
            "session": {
                "session_id": f"{adapter_id}:{config['dataset']['name']}:{run_id[:16]}",
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "generator": {"name": GENERATOR_NAME, "version": LOCAL_AUDIT_GENERATOR_VERSION, "run_id": run_id},
                "source_mode": "offline_audit",
                "title": f"{spec.model_name} {config['dataset']['name']} local audit",
            },
            "model": {
                "name": spec.model_name,
                "adapter": spec.adapter_name,
                "adapter_id": adapter_id,
                "native_context_type": spec.native_context_type,
                "source_repository": None,
                "source_commit": None,
                "configuration": model_configuration,
            },
            "dataset": {
                "name": config["dataset"]["name"],
                "format": config["dataset"]["format"],
                "sha256": dataset_hash,
                "variables": variables,
                "date_column": config["dataset"]["date_column"],
                "features": config["dataset"]["features"],
                "target": config["dataset"]["target"],
                "frequency": config["dataset"]["frequency"],
                "seq_len": int(config["dataset"]["seq_len"]),
                "label_len": int(config["dataset"]["label_len"]),
                "pred_len": pred_len,
                "original_path": None,
            },
            "checkpoint": {
                "sha256": checkpoint_hash,
                "format": "PyTorch state_dict",
                "load_status": "validated",
                "original_path": None,
            },
            "audit_plan": {
                "split": "test",
                "sample_indices": [int(item) for item in config["audit"]["samples"]],
                "relation_count": len(relation_map),
                "local_scope": "exact_native_context",
                "broader_context_scope": "all_applicable_native_contexts" if broader_requested else "not_requested",
                "candidate_protocol": "exact relations declared in DGraInsight Audit Config v1",
                "control_protocol": (
                    "DGraFormer seeded retained-edge controls with broader-context exposure/weight matching"
                    if adapter_id == "dgraformer"
                    else "all other real directed non-self interventions in the same sample and scope"
                ),
                "multiple_comparison_protocol": "Benjamini-Hochberg within local and broader-context evidence families",
            },
            "samples": portable_samples,
            "relations": list(relation_map.values()),
            "evidence_records": evidence_records,
            "evidence_summary": {
                "local_case_count": local_count,
                "broader_context_case_count": broader_count,
                "local_bh_supported_count": local_supported,
                "broader_context_bh_supported_count": broader_supported,
                "negative_evidence_preserved": True,
                "not_exposed_case_count": 0,
                "missing_case_count": 0,
            },
            "cross_run_evidence": {
                "status": "not_evaluated",
                "value": None,
                "reason": "This portable session was generated from one user-supplied checkpoint.",
            },
            "provenance": {
                "session_generation_run_id": run_id,
                "validation": {
                    "kind": "adapter_preflight",
                    "status": "passed",
                    "report_sha256": _value_sha256(embedded_preflight),
                },
                "config_sha256": config_hash,
                "source_runs": [{
                    "role": "local_audit",
                    "run_id": run_id,
                    "artifact_status": "available",
                    "manifest_sha256": None,
                    "artifact_sha256": None,
                }],
                "commands": [
                    f"python -m dgraudit audit --config {config_file.name} --output dgrainsight_session.json"
                ],
                "environment": {
                    "python": platform.python_version(),
                    "platform": platform.platform(),
                    "torch": torch.__version__,
                    "numpy": np.__version__,
                    "cuda": torch.version.cuda,
                    "cuda_available": torch.cuda.is_available(),
                },
                "code_references": [
                    "dgraudit/local_audit.py",
                    "dgraudit/adapters.py",
                    "dgraudit/validation.py",
                    "schemas/dgrainsight_audit_session_v1.schema.json",
                ],
                "source_artifacts": [
                    {"role": "audit_config", "path": None, "sha256": config_hash, "status": "available"},
                    {"role": "dataset", "path": None, "sha256": dataset_hash, "status": "available"},
                    {"role": "checkpoint", "path": None, "sha256": checkpoint_hash, "status": "available"},
                    *[
                        {
                            "role": role,
                            "path": str(path.relative_to(repository_root)).replace("\\", "/"),
                            "sha256": code_hashes[role],
                            "status": "available",
                        }
                        for role, path in code_paths.items()
                    ],
                ],
            },
            "limitations": [
                "Evidence describes model-internal behavior for the declared checkpoint, dataset, samples, and graph interventions.",
                "It does not establish real-world causality.",
                "Additional architectures require a model-specific adapter.",
            ],
            "model_specific": {
                "artifact_validation_report": embedded_preflight,
                "local_audit": {
                    "bootstrap_repetitions": bootstrap_repetitions,
                    "prediction_replay_count": len(prediction_cache),
                },
            },
        }
        errors = validate_audit_session(session)
        if errors:
            raise LocalAuditError("Generated Audit Session failed validation:\n- " + "\n- ".join(errors))
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                    json.dump(session, handle, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
                    handle.write("\n")
                os.replace(temporary_name, destination)
            except Exception:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass
                raise
        except OSError as exc:
            raise LocalAuditError(f"Could not write portable Audit Session to {destination}: {exc}") from exc
        announce(f"Portable Audit Session written to {destination}")
        return destination, session
    finally:
        adapter.close()

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import torch

from dgraudit.v2.quick import build_quick_session_v2
from dgraudit.v2.session import write_audit_session_v2
from dgraudit.validation import (
    AdapterValidationSpec, OFFICIAL_ADAPTER_REGISTRY, render_validation_report,
    resolve_adapter_spec, validate_audit_config,
)


Progress = Callable[[str], None]
QUICK_AUDIT_GENERATOR_VERSION = "2.0"


class QuickAuditError(ValueError):
    """Raised when supported local inputs cannot produce a Quick Inspection v2."""


def _resolve(base: Path, raw: str) -> Path:
    path = Path(raw)
    return (base / path).resolve() if not path.is_absolute() else path.resolve()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _value_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _array(value: Any, *, squeeze_batch: bool = False) -> np.ndarray:
    result = value.detach().cpu().numpy() if isinstance(value, torch.Tensor) else np.asarray(value)
    if squeeze_batch and result.ndim == 3 and result.shape[0] == 1:
        result = result[0]
    if not np.isfinite(result).all():
        raise QuickAuditError("The offline audit produced a non-finite tensor.")
    return result


def _tensor(value: Any, axes: Sequence[str], *, squeeze_batch: bool = False) -> dict[str, Any]:
    array = _array(value, squeeze_batch=squeeze_batch)
    if array.ndim != len(axes):
        raise QuickAuditError(f"Tensor rank {array.ndim} does not match axes {list(axes)}.")
    return {"dtype": str(array.dtype), "shape": list(array.shape), "axis_order": list(axes), "values": array.tolist()}


def _available_tensor(value: Any, axes: Sequence[str], *, squeeze_batch: bool = False) -> dict[str, Any]:
    return {"status": "available", "value": _tensor(value, axes, squeeze_batch=squeeze_batch), "reason": None}


def _metrics(baseline: Any, intervention: Any, truth: Any) -> dict[str, float]:
    base, changed, target = _array(baseline), _array(intervention), _array(truth)
    if base.shape != changed.shape or base.shape != target.shape:
        raise QuickAuditError(
            f"Prediction/target shape mismatch: baseline={base.shape}, intervention={changed.shape}, truth={target.shape}."
        )
    delta, base_error, changed_error = changed - base, base - target, changed - target
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


def _context_id(spec: AdapterValidationSpec, context: Mapping[str, Any]) -> str:
    return spec.context_id(context)


def _context_weight(spec: AdapterValidationSpec, context: Mapping[str, Any]) -> np.ndarray:
    return _array(spec.context_weight(context))


def _portable_context(spec: AdapterValidationSpec, context: Mapping[str, Any], node_count: int) -> dict[str, Any]:
    result = {
        "context_id": _context_id(spec, context), "type": spec.native_context_type,
        "index": spec.context_index(context), "node_count": node_count,
        "graphs": {name: _tensor(value, ("source_node", "target_node")) for name, value in spec.context_graphs(context).items()},
        "native_metadata": dict(spec.context_metadata(context)),
    }
    if "layer" in context:
        result["layer"] = int(context["layer"])
    if context.get("display_label"):
        result["display_label"] = str(context["display_label"])
    return result


def _find_context(spec: AdapterValidationSpec, contexts: Sequence[Mapping[str, Any]], requested: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        return spec.find_context(contexts, requested)
    except Exception as exc:
        raise QuickAuditError(f"The exact requested native context is unavailable: {dict(requested)} ({exc})") from exc


def _eligible_edges(
    spec: AdapterValidationSpec,
    contexts: Sequence[Mapping[str, Any]],
    requested: Mapping[str, Any],
    broader: bool,
) -> list[tuple[int, int]]:
    matrices = [_context_weight(spec, item) for item in contexts]
    if not broader:
        matrices = [_context_weight(spec, _find_context(spec, contexts, requested))]
    node_count = matrices[0].shape[0]
    return [
        (source, target)
        for source in range(node_count)
        for target in range(node_count)
        if source != target and any(float(matrix[source, target]) > 0 for matrix in matrices)
    ]


def _control_edges(
    spec: AdapterValidationSpec,
    contexts: Sequence[Mapping[str, Any]],
    requested: Mapping[str, Any],
    focal: tuple[int, int],
    broader: bool,
) -> tuple[list[tuple[int, int]], str]:
    eligible = [edge for edge in _eligible_edges(spec, contexts, requested, broader) if edge != focal]
    if not eligible:
        raise QuickAuditError("No eligible unique real intervention remains for the matched-control family.")
    return eligible, "all unique eligible directed non-self edge removals in the same sample and scope"


def _selection(
    spec: AdapterValidationSpec,
    model_name: str,
    dataset_name: str,
    relation: Mapping[str, Any],
    variables: Sequence[str],
    context: Mapping[str, Any],
    broader: bool,
) -> dict[str, Any]:
    return spec.selection(model_name, dataset_name, relation, variables, context, broader)


def _embedded_preflight(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": "adapter_preflight", "status": "passed", "schema_version": report.get("schema_version"),
        "adapter": report.get("adapter"),
        "checks": [
            {key: check.get(key) for key in ("id", "name", "label", "status", "code", "message") if check.get(key) is not None}
            for check in report.get("checks", [])
        ],
        "measurements": report.get("measurements", {}), "runtime": report.get("runtime", {}),
        "dataset_sha256": report.get("dataset", {}).get("sha256"),
        "checkpoint_sha256": report.get("checkpoint", {}).get("sha256"),
    }


def run_quick_audit(
    config_path: str | Path,
    *,
    output_path: str | Path = "dgrainsight_session_v2.json",
    progress: Progress | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Replay a supported checkpoint and write a native Quick Inspection Session v2."""
    announce = progress or (lambda _message: None)
    config_file = Path(config_path).resolve()
    destination = Path(output_path).expanduser()
    if not destination.is_absolute():
        destination = (Path.cwd() / destination).resolve()
    announce("Running required V01-V09 adapter preflight")
    preflight = validate_audit_config(config_file)
    if preflight.get("status") != "ready_for_audit":
        raise QuickAuditError(render_validation_report(preflight))

    config = json.loads(config_file.read_text(encoding="utf-8"))
    spec = resolve_adapter_spec(config, config_file, OFFICIAL_ADAPTER_REGISTRY)
    if spec is None:
        raise QuickAuditError(f"Adapter could not be resolved after conformance validation: {config.get('adapter')}")
    resolved = {
        "source_root": _resolve(config_file.parent, config["source_root"]),
        "dataset": _resolve(config_file.parent, config["dataset"]["path"]),
        "checkpoint": _resolve(config_file.parent, config["checkpoint"]["path"]),
    }
    adapter = spec.create_adapter(config, resolved)
    samples_runtime: dict[int, dict[str, Any]] = {}
    portable_samples: list[dict[str, Any]] = []
    adapter_id, variables = spec.adapter_id, list(config["dataset"]["variables"])
    pred_len = int(config["dataset"]["pred_len"])
    try:
        announce(f"Loading validated {spec.model_name} checkpoint")
        adapter.load_checkpoint(str(resolved["checkpoint"]))
        metadata_callback = getattr(adapter, "get_metadata", None)
        adapter_metadata = dict(metadata_callback()) if callable(metadata_callback) else {}
        for display_id, raw_index in enumerate(config["audit"]["samples"]):
            sample_index = int(raw_index)
            announce(f"Computing baseline and native graph for test sample {sample_index}")
            raw_batch = adapter.load_sample(config["audit"]["split"], sample_index)
            batch = spec.prepare_batch(raw_batch, config)
            baseline = adapter.predict(batch)
            truth = torch.as_tensor(batch["y"][-pred_len:, :], dtype=torch.float32).unsqueeze(0)
            extracted = adapter.extract_graph_stages(batch)
            contexts = spec.contexts(extracted)
            sample_metrics = _metrics(baseline, baseline, truth)
            portable_samples.append({
                "sample_id": f"test:{sample_index}", "display_id": display_id, "split": "test",
                "sample_index": sample_index,
                "history": _available_tensor(batch["x"], ("input_step", "variable")),
                "ground_truth": _tensor(truth, ("forecast_step", "variable"), squeeze_batch=True),
                "baseline_prediction": _tensor(baseline, ("forecast_step", "variable"), squeeze_batch=True),
                "sample_metrics": {"baseline_mae": sample_metrics["baseline_mae"], "baseline_mse": sample_metrics["baseline_mse"]},
                "contexts": [_portable_context(spec, item, len(variables)) for item in contexts],
                "provenance": {"source": "direct validated checkpoint replay"},
            })
            samples_runtime[sample_index] = {"batch": batch, "baseline": baseline, "truth": truth, "contexts": contexts}

        prediction_cache: dict[tuple[Any, ...], tuple[Any, Mapping[str, Any], dict[str, float]]] = {}

        def replay(relation: Mapping[str, Any], source: int, target: int, broader: bool):
            sample_index = int(relation["sample"])
            context = relation["context"]
            native_context = _find_context(spec, samples_runtime[sample_index]["contexts"], context)
            context_key = spec.context_cache_key(native_context)
            key = (sample_index, "broader" if broader else "local", context_key, source, target)
            if key not in prediction_cache:
                probe = {**dict(relation), "source": source, "target": target}
                outcome = adapter.predict_with_graph_override(
                    samples_runtime[sample_index]["batch"],
                    spec.intervention_override_for_context(probe, config, native_context, broader=broader),
                )
                prediction = outcome["prediction"]
                runtime = samples_runtime[sample_index]
                prediction_cache[key] = (prediction, outcome, _metrics(runtime["baseline"], prediction, runtime["truth"]))
            return prediction_cache[key]

        relation_map: dict[tuple[int, int, int], dict[str, Any]] = {}
        for requested in config["audit"]["relations"]:
            sample_index, source, target = int(requested["sample"]), int(requested["source"]), int(requested["target"])
            key = (sample_index, source, target)
            if key in relation_map:
                continue
            occurrences = []
            for context in samples_runtime[sample_index]["contexts"]:
                weights = _context_weight(spec, context)
                weight = float(weights[source, target])
                occurrences.append({
                    "context_id": _context_id(spec, context), "weight": weight, "retained": weight > 0,
                    "rank": _average_ranks_descending(weights)[(source, target)],
                })
            relation_map[key] = {
                "relation_id": f"test:{sample_index}:edge:{source}->{target}", "sample_id": f"test:{sample_index}",
                "source": source, "target": target, "source_name": variables[source], "target_name": variables[target],
                "native_occurrences": occurrences,
            }

        quick_records: list[dict[str, Any]] = []
        seen_exact: set[tuple[Any, ...]] = set()
        for requested in config["audit"]["relations"]:
            sample_index, source, target = int(requested["sample"]), int(requested["source"]), int(requested["target"])
            runtime = samples_runtime[sample_index]
            selected_context = _find_context(spec, runtime["contexts"], requested["context"])
            for broader in ([False, True] if requested.get("include_broader_context") else [False]):
                selection = _selection(spec, spec.model_name, config["dataset"]["name"], requested, variables, selected_context, broader)
                exact_key = tuple(selection.get(field) for field in (
                    "model", "dataset", "sample_id", "context_type", "context_id", "source", "target", "scope"
                ))
                if exact_key in seen_exact:
                    continue
                seen_exact.add(exact_key)
                announce(f"Auditing test sample {sample_index}, {variables[source]}->{variables[target]}")
                focal_prediction, focal_outcome, focal_metrics = replay(requested, source, target, broader)
                selected_controls, control_protocol = _control_edges(
                    spec, runtime["contexts"], requested["context"], (source, target), broader
                )
                controls = []
                for control_source, control_target in selected_controls:
                    _, _, control_metrics = replay(requested, control_source, control_target, broader)
                    controls.append({
                        "identity": f"{control_source}->{control_target}",
                        "response": control_metrics["prediction_delta_abs"],
                    })
                if broader:
                    weights = [float(_context_weight(spec, item)[source, target]) for item in runtime["contexts"]]
                    graph_effect = {
                        "native_context_weights": weights,
                        "affected_context_ids": [
                            _context_id(spec, item) for item, weight in zip(runtime["contexts"], weights) if weight > 0
                        ],
                    }
                else:
                    context = _find_context(spec, runtime["contexts"], requested["context"])
                    matrix = _context_weight(spec, context)
                    metadata = dict(spec.graph_effect_metadata(context))
                    graph_effect = {
                        "native_weight": float(matrix[source, target]),
                        "weight_rank": _average_ranks_descending(matrix)[(source, target)],
                        **metadata,
                    }
                quick_records.append({
                    "selection": selection,
                    "intervention_output": _available_tensor(focal_prediction, ("forecast_step", "variable"), squeeze_batch=True),
                    "metrics": focal_metrics,
                    "controls": controls,
                    "control_protocol": control_protocol,
                    "graph_effect": graph_effect,
                    "provenance": {"adapter": spec.adapter_name, "intervention_protocol": focal_outcome.get("protocol")},
                })

        config_hash, dataset_hash, checkpoint_hash = (
            _file_sha256(config_file), _file_sha256(resolved["dataset"]), _file_sha256(resolved["checkpoint"])
        )
        run_id = _value_sha256({
            "generator_version": QUICK_AUDIT_GENERATOR_VERSION,
            "config_sha256": config_hash,
            "dataset_sha256": dataset_hash,
            "checkpoint_sha256": checkpoint_hash,
            "control_protocol": "all_unique_eligible",
        })
        model_configuration = dict(spec.model_configuration(config))
        graph_core = {
            "session": {
                "session_id": f"{adapter_id}:{config['dataset']['name']}:{run_id[:16]}",
                "generator": {"name": "DGraInsight offline audit pipeline", "version": QUICK_AUDIT_GENERATOR_VERSION, "run_id": run_id},
                "title": f"{spec.model_name} {config['dataset']['name']} Quick Inspection",
            },
            "model": {
                "name": spec.model_name, "adapter": spec.adapter_name, "adapter_id": adapter_id,
                "native_context_type": spec.native_context_type, "source_repository": None, "source_commit": None,
                "configuration": model_configuration,
                **({
                    "adapter_module": config["custom_adapter"]["module"],
                    "adapter_class": config["custom_adapter"]["class"],
                    "adapter_version": adapter_metadata.get("adapter_version"),
                } if config.get("adapter") == "custom" else {}),
            },
            "dataset": {
                "name": config["dataset"]["name"], "format": config["dataset"]["format"], "sha256": dataset_hash,
                "variables": variables, "date_column": config["dataset"]["date_column"],
                "features": config["dataset"]["features"], "target": config["dataset"]["target"],
                "frequency": config["dataset"]["frequency"], "seq_len": int(config["dataset"]["seq_len"]),
                "label_len": int(config["dataset"]["label_len"]), "pred_len": pred_len, "original_path": None,
            },
            "checkpoint": {"sha256": checkpoint_hash, "format": str(adapter_metadata.get("checkpoint_format", "PyTorch state_dict")), "load_status": "validated", "original_path": None},
            "samples": portable_samples,
            "relations": list(relation_map.values()),
            "provenance": {
                "session_generation_run_id": run_id,
                "validation": {"kind": "adapter_preflight", "status": "passed", "report_sha256": _value_sha256(_embedded_preflight(preflight))},
                "config_sha256": config_hash,
                "commands": [f"python -m dgraudit audit --config {config_file.name} --output dgrainsight_session_v2.json"],
                "environment": {
                    "python": platform.python_version(), "platform": platform.platform(), "torch": torch.__version__,
                    "numpy": np.__version__, "cuda": torch.version.cuda, "cuda_available": torch.cuda.is_available(),
                },
                "code_references": ["dgraudit/quick_audit.py", "dgraudit/adapters.py", "dgraudit/validation.py", "schemas/dgrainsight_audit_session_v2.schema.json"],
                "source_artifacts": [
                    {"role": "audit_config", "path": None, "sha256": config_hash, "status": "available"},
                    {"role": "dataset", "path": None, "sha256": dataset_hash, "status": "available"},
                    {"role": "checkpoint", "path": None, "sha256": checkpoint_hash, "status": "available"},
                ],
            },
            "model_specific": {
                "artifact_validation_report": _embedded_preflight(preflight),
                "quick_audit": {"prediction_replay_count": len(prediction_cache), "control_protocol": "all_unique_eligible"},
            },
        }
        session = build_quick_session_v2(graph_core, quick_records)
        output = write_audit_session_v2(destination, session)
        announce(f"Quick Inspection Session v2 written to {output}")
        return output, session
    finally:
        adapter.close()

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence


CONFIG_SCHEMA_VERSION = "dgrainsight.audit_config.v1"
REPORT_SCHEMA_VERSION = "dgrainsight.adapter_validation.v1"
IDENTITY_ATOL = 1e-6
IDENTITY_RTOL = 1e-5

CHECK_DEFINITIONS = [
    ("V01", "config_and_adapter", "Config and official adapter"),
    ("V02", "input_existence", "Input files located and hashed"),
    ("V03", "dataset_compatibility", "Dataset schema validated"),
    ("V04", "sample_construction", "Samples constructed"),
    ("V05", "checkpoint_loading", "Checkpoint loaded"),
    ("V06", "baseline_forward", "Baseline forward passed"),
    ("V07", "native_graph_extraction", "Native graph extracted"),
    ("V08", "identity_intervention", "Identity intervention matched baseline"),
    ("V09", "intervention_availability", "Exact intervention hook available"),
]


@dataclass
class ValidationFailure(Exception):
    code: str
    message: str
    expected: Any = None
    found: Any = None
    details: Mapping[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


class AdapterValidationSpec:
    adapter_id = ""
    adapter_name = ""
    model_name = ""
    native_context_type = ""
    supported_formats: tuple[str, ...] = ()
    required_source_files: tuple[str, ...] = ()
    required_model_fields: tuple[str, ...] = ()

    def validate_adapter_config(self, config: Mapping[str, Any]) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        adapter_config = config.get("adapter_config")
        if not isinstance(adapter_config, Mapping):
            return [_issue("CONFIG_FIELD_INVALID", "adapter_config must be an object.", "object", type(adapter_config).__name__)]
        model = adapter_config.get("model")
        if not isinstance(model, Mapping):
            issues.append(_issue("CONFIG_FIELD_INVALID", "adapter_config.model must be an object.", "object", type(model).__name__))
            return issues
        for field in self.required_model_fields:
            if field not in model:
                issues.append(_issue("CONFIG_FIELD_MISSING", f"Missing adapter_config.model.{field}.", field, None))
        unknown_model = sorted(set(model) - set(self.required_model_fields))
        if unknown_model:
            issues.append(_issue(
                "CONFIG_FIELD_INVALID",
                "adapter_config.model contains fields not consumed by the official adapter.",
                list(self.required_model_fields),
                unknown_model,
            ))
        if not isinstance(adapter_config.get("random_seed"), int):
            issues.append(_issue("CONFIG_FIELD_INVALID", "adapter_config.random_seed must be an integer.", "integer", adapter_config.get("random_seed")))
        return issues

    def create_adapter(self, config: Mapping[str, Any], resolved: Mapping[str, Path]) -> Any:
        raise NotImplementedError

    def prepare_batch(self, batch: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
        return dict(batch)

    def validate_sample(self, batch: Mapping[str, Any], config: Mapping[str, Any]) -> Mapping[str, Any]:
        raise NotImplementedError

    def validate_graph(
        self, extracted: Mapping[str, Any], probe: Mapping[str, Any], config: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        raise NotImplementedError

    def identity_override(self, probe: Mapping[str, Any], config: Mapping[str, Any]) -> Mapping[str, Any]:
        raise NotImplementedError

    def intervention_override(
        self, probe: Mapping[str, Any], config: Mapping[str, Any], broader: bool = False
    ) -> Mapping[str, Any]:
        raise NotImplementedError


class DGraFormerValidationSpec(AdapterValidationSpec):
    adapter_id = "dgraformer"
    adapter_name = "DGraFormerAdapter"
    model_name = "DGraFormer"
    native_context_type = "window"
    supported_formats = ("ett_hour",)
    required_source_files = ("exp/exp_main.py", "models/DGraFormer.py")
    required_model_fields = (
        "numpoint_win", "w_bias", "d_graph", "d_gcn", "w_ratio", "mp_layers",
        "predictor_dropout", "patch_len", "stride", "revin", "affine", "subtract_last",
        "d_model", "n_heads", "e_layers", "d_ff", "dropout", "embed", "activation",
    )

    def validate_adapter_config(self, config: Mapping[str, Any]) -> list[dict[str, Any]]:
        issues = super().validate_adapter_config(config)
        adapter_config = config.get("adapter_config")
        if isinstance(adapter_config, Mapping) and not isinstance(adapter_config.get("current_epoch"), int):
            issues.append(_issue(
                "CONFIG_FIELD_INVALID",
                "adapter_config.current_epoch is required and must be an integer.",
                "integer",
                adapter_config.get("current_epoch"),
            ))
        return issues

    def create_adapter(self, config: Mapping[str, Any], resolved: Mapping[str, Path]) -> Any:
        from dgraudit.adapters import DGraFormerAdapter

        dataset = config["dataset"]
        adapter_config = config["adapter_config"]
        common = {
            "seq_len": dataset["seq_len"],
            "label_len": dataset["label_len"],
            "pred_len": dataset["pred_len"],
            **dict(adapter_config["model"]),
        }
        dataset_config = {
            "data": dataset["name"],
            "root_path": str(resolved["dataset"].parent),
            "data_path": resolved["dataset"].name,
            "freq": dataset["frequency"],
            "n_vars": len(dataset["variables"]),
        }
        adapter = DGraFormerAdapter(
            str(resolved["source_root"]),
            dataset["name"],
            common,
            dataset_config,
            int(adapter_config["random_seed"]),
        )
        adapter.current_epoch = int(adapter_config["current_epoch"])
        return adapter

    def prepare_batch(self, batch: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
        return {**batch, "current_epoch": int(config["adapter_config"]["current_epoch"])}

    def validate_sample(self, batch: Mapping[str, Any], config: Mapping[str, Any]) -> Mapping[str, Any]:
        dataset = config["dataset"]
        expected_x = [dataset["seq_len"], len(dataset["variables"])]
        x_shape = list(_shape(batch.get("x")))
        y_shape = list(_shape(batch.get("y")))
        if x_shape != expected_x:
            raise ValidationFailure("SAMPLE_SHAPE_MISMATCH", "DGraFormer input shape is incompatible.", expected_x, x_shape)
        if len(y_shape) != 2 or y_shape[0] < dataset["pred_len"] or y_shape[1] != len(dataset["variables"]):
            raise ValidationFailure(
                "SAMPLE_SHAPE_MISMATCH",
                "DGraFormer target container shape is incompatible.",
                [f">={dataset['pred_len']}", len(dataset["variables"])],
                y_shape,
            )
        for key in ("x", "y", "time_index"):
            if key not in batch:
                raise ValidationFailure("SAMPLE_CONSTRUCTION_FAILED", f"DGraFormer sample is missing {key}.")
            if not _is_finite(batch[key]):
                raise ValidationFailure("SAMPLE_NONFINITE", f"DGraFormer sample field {key} contains non-finite values.")
        return {"x_shape": x_shape, "y_shape": y_shape, "time_index_shape": list(_shape(batch["time_index"]))}

    def validate_graph(
        self, extracted: Mapping[str, Any], probe: Mapping[str, Any], config: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        windows = extracted.get("windows")
        if not isinstance(windows, Sequence) or not windows:
            raise ValidationFailure("GRAPH_EXTRACTION_FAILED", "DGraFormer did not return native window contexts.")
        requested = next((item for item in windows if int(item.get("window", -1)) == int(probe["context"]["index"])), None)
        if requested is None:
            raise ValidationFailure(
                "GRAPH_CONTEXT_MISSING",
                "Requested DGraFormer window does not exist.",
                probe["context"]["index"],
                [item.get("window") for item in windows],
            )
        n = len(config["dataset"]["variables"])
        source, target = int(probe["source"]), int(probe["target"])
        normalized = requested.get("normalized")
        _validate_square_finite_matrix(normalized, n, "DGraFormer normalized graph")
        rows = _matrix_rows(normalized)
        max_row_error = max(abs(sum(row) - 1.0) for row in rows)
        if max_row_error > 1e-5:
            raise ValidationFailure("GRAPH_SHAPE_MISMATCH", "DGraFormer normalized graph rows do not sum to one.", "<=1e-5", max_row_error)
        weight = float(rows[source][target])
        if weight <= 0:
            raise ValidationFailure(
                "RELATION_NOT_PRESENT",
                "Declared DGraFormer relation is not retained in the exact requested window.",
                "positive normalized weight",
                weight,
            )
        if probe.get("include_broader_context"):
            broader_weights = []
            for item in windows:
                matrix = _matrix_rows(item.get("normalized"))
                broader_weights.append(float(matrix[source][target]))
            if not any(value > 0 for value in broader_weights):
                raise ValidationFailure("RELATION_NOT_PRESENT", "Declared relation is absent from every DGraFormer window.")
        return {
            "context_count": len(windows),
            "requested_window": int(probe["context"]["index"]),
            "matrix_shape": [n, n],
            "requested_weight": weight,
            "normalized_row_sum_max_error": max_row_error,
        }

    def identity_override(self, probe: Mapping[str, Any], config: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "type": "identity",
            "window": int(probe["context"]["index"]),
            "current_epoch": int(config["adapter_config"]["current_epoch"]),
        }

    def intervention_override(
        self, probe: Mapping[str, Any], config: Mapping[str, Any], broader: bool = False
    ) -> Mapping[str, Any]:
        common = {
            "source": int(probe["source"]),
            "target": int(probe["target"]),
            "current_epoch": int(config["adapter_config"]["current_epoch"]),
        }
        if broader:
            return {"type": "global_structural_edge_removal", **common}
        return {"type": "structural_edge_removal", "window": int(probe["context"]["index"]), **common}


class MSGNetValidationSpec(AdapterValidationSpec):
    adapter_id = "msgnet"
    adapter_name = "MSGNetAdapter"
    model_name = "MSGNet"
    native_context_type = "scale"
    supported_formats = ("ett_hour",)
    required_source_files = ("models/MSGNet.py", "data_provider/data_loader.py")
    required_model_fields = (
        "task_name", "top_k", "enc_in", "c_out", "e_layers", "d_model", "n_heads",
        "d_ff", "conv_channel", "skip_channel", "node_dim", "gcn_depth", "propalpha",
        "dropout", "embed", "individual",
    )

    def create_adapter(self, config: Mapping[str, Any], resolved: Mapping[str, Path]) -> Any:
        from dgraudit.adapters import MSGNetAdapter

        dataset = config["dataset"]
        adapter_config = config["adapter_config"]
        legacy_config = {
            "random_seed": adapter_config["random_seed"],
            "dataset": {
                "name": dataset["name"],
                "path": str(resolved["dataset"]),
                "features": dataset["features"],
                "target": dataset["target"],
                "frequency": dataset["frequency"],
                "seq_len": dataset["seq_len"],
                "label_len": dataset["label_len"],
                "pred_len": dataset["pred_len"],
            },
            "model_config": dict(adapter_config["model"]),
        }
        return MSGNetAdapter(str(resolved["source_root"]), legacy_config)

    def validate_sample(self, batch: Mapping[str, Any], config: Mapping[str, Any]) -> Mapping[str, Any]:
        dataset = config["dataset"]
        n = len(dataset["variables"])
        expected_x = [dataset["seq_len"], n]
        expected_y = [dataset["label_len"] + dataset["pred_len"], n]
        x_shape, y_shape = list(_shape(batch.get("x"))), list(_shape(batch.get("y")))
        x_mark_shape, y_mark_shape = list(_shape(batch.get("x_mark"))), list(_shape(batch.get("y_mark")))
        if x_shape != expected_x or y_shape != expected_y:
            raise ValidationFailure(
                "SAMPLE_SHAPE_MISMATCH",
                "MSGNet sample tensor shapes are incompatible.",
                {"x": expected_x, "y": expected_y},
                {"x": x_shape, "y": y_shape},
            )
        if not x_mark_shape or x_mark_shape[0] != dataset["seq_len"] or not y_mark_shape or y_mark_shape[0] != expected_y[0]:
            raise ValidationFailure(
                "SAMPLE_SHAPE_MISMATCH",
                "MSGNet time-mark lengths are incompatible.",
                {"x_mark_rows": dataset["seq_len"], "y_mark_rows": expected_y[0]},
                {"x_mark": x_mark_shape, "y_mark": y_mark_shape},
            )
        for key in ("x", "y", "x_mark", "y_mark"):
            if key not in batch:
                raise ValidationFailure("SAMPLE_CONSTRUCTION_FAILED", f"MSGNet sample is missing {key}.")
            if not _is_finite(batch[key]):
                raise ValidationFailure("SAMPLE_NONFINITE", f"MSGNet sample field {key} contains non-finite values.")
        return {"x_shape": x_shape, "y_shape": y_shape, "x_mark_shape": x_mark_shape, "y_mark_shape": y_mark_shape}

    def validate_graph(
        self, extracted: Mapping[str, Any], probe: Mapping[str, Any], config: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        contexts = extracted.get("contexts")
        if not isinstance(contexts, Sequence) or not contexts:
            raise ValidationFailure("GRAPH_EXTRACTION_FAILED", "MSGNet did not return native scale contexts.")
        layer = int(probe["context"].get("layer", 0))
        scale = int(probe["context"]["index"])
        requested = next(
            (item for item in contexts if int(item.get("layer", -1)) == layer and int(item.get("scale_index", -1)) == scale),
            None,
        )
        if requested is None:
            raise ValidationFailure(
                "GRAPH_CONTEXT_MISSING",
                "Requested MSGNet layer/scale context does not exist.",
                {"layer": layer, "scale_index": scale},
                [{"layer": item.get("layer"), "scale_index": item.get("scale_index")} for item in contexts],
            )
        n = len(config["dataset"]["variables"])
        _validate_square_finite_matrix(requested.get("adaptive"), n, "MSGNet adaptive graph")
        _validate_square_finite_matrix(requested.get("effective"), n, "MSGNet effective graph")
        period = int(requested.get("period", 0))
        fft_strength = float(requested.get("fft_strength", math.nan))
        contribution = float(requested.get("scale_contribution", math.nan))
        if period <= 0 or not math.isfinite(fft_strength) or not math.isfinite(contribution):
            raise ValidationFailure(
                "GRAPH_NONFINITE",
                "MSGNet native scale metadata is invalid.",
                "positive period and finite FFT/mixing values",
                {"period": period, "fft_strength": fft_strength, "scale_contribution": contribution},
            )
        adaptive = _matrix_rows(requested["adaptive"])
        return {
            "context_count": len(contexts),
            "requested_layer": layer,
            "requested_scale": scale,
            "period": period,
            "fft_strength": fft_strength,
            "scale_contribution": contribution,
            "requested_weight": float(adaptive[int(probe["source"])][int(probe["target"])]),
            "matrix_shape": [n, n],
        }

    def identity_override(self, probe: Mapping[str, Any], config: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "type": "identity",
            "layer": int(probe["context"].get("layer", 0)),
            "scale_index": int(probe["context"]["index"]),
        }

    def intervention_override(
        self, probe: Mapping[str, Any], config: Mapping[str, Any], broader: bool = False
    ) -> Mapping[str, Any]:
        result = {
            "type": "structural_edge_removal",
            "layer": int(probe["context"].get("layer", 0)),
            "scale_index": int(probe["context"]["index"]),
            "source": int(probe["source"]),
            "target": int(probe["target"]),
        }
        if broader:
            result["scope"] = "global"
        return result


OFFICIAL_ADAPTER_REGISTRY: dict[str, AdapterValidationSpec] = {
    "dgraformer": DGraFormerValidationSpec(),
    "msgnet": MSGNetValidationSpec(),
}


def validate_audit_config(
    config_path: str | Path,
    registry: Mapping[str, AdapterValidationSpec] | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    path = Path(config_path).resolve()
    registry = registry or OFFICIAL_ADAPTER_REGISTRY
    report = _new_report(path)
    config: Mapping[str, Any] | None = None
    spec: AdapterValidationSpec | None = None
    adapter: Any = None
    cached_samples: dict[int, Mapping[str, Any]] = {}
    baselines: dict[int, Any] = {}
    extracted_graphs: dict[int, Mapping[str, Any]] = {}

    def execute(check_id: str, callback, fallback_code: str) -> bool:
        definition = next(item for item in CHECK_DEFINITIONS if item[0] == check_id)
        try:
            details = callback() or {}
            report["checks"].append(_check(definition, "pass", details=details))
            return True
        except ValidationFailure as exc:
            report["checks"].append(_check(
                definition,
                "fail",
                code=exc.code,
                message=exc.message,
                expected=exc.expected,
                found=exc.found,
                details=dict(exc.details or {}),
            ))
        except ModuleNotFoundError as exc:
            report["checks"].append(_check(
                definition,
                "fail",
                code="RUNTIME_DEPENDENCY_MISSING",
                message=f"Required runtime dependency is unavailable: {exc.name}.",
                expected="compatible adapter runtime",
                found=exc.name,
            ))
        except Exception as exc:  # converted to phase-specific, explainable failure
            details = {"exception_class": type(exc).__name__}
            if debug:
                details["exception"] = repr(exc)
            report["checks"].append(_check(
                definition,
                "fail",
                code=fallback_code,
                message=f"{definition[2]} failed: {exc}",
                details=details,
            ))
        _append_not_run(report, check_id)
        return False

    def v01() -> Mapping[str, Any]:
        nonlocal config, spec
        if not path.is_file():
            raise ValidationFailure("CONFIG_PARSE_ERROR", "Audit config file does not exist.", "existing JSON file", str(path))
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValidationFailure("CONFIG_PARSE_ERROR", f"Audit config is not valid readable JSON: {exc}") from exc
        if not isinstance(parsed, Mapping):
            raise ValidationFailure("CONFIG_FIELD_INVALID", "Audit config root must be an object.", "object", type(parsed).__name__)
        adapter_id = parsed.get("adapter")
        candidate_spec = registry.get(str(adapter_id))
        issues = _validate_common_config(parsed, candidate_spec)
        if issues:
            first = issues[0]
            raise ValidationFailure(
                first["code"],
                first["message"],
                first.get("expected"),
                first.get("found"),
                {"issues": issues},
            )
        config = parsed
        spec = candidate_spec
        report["adapter"] = {
            "id": spec.adapter_id,
            "name": spec.adapter_name,
            "model": spec.model_name,
            "native_context_type": spec.native_context_type,
        }
        report["probe"] = _probe_from_relation(config["audit"]["relations"][0])
        return {"adapter": spec.adapter_name, "model": spec.model_name, "native_context_type": spec.native_context_type}

    if not execute("V01", v01, "CONFIG_PARSE_ERROR"):
        return _finish_report(report)
    assert config is not None and spec is not None

    resolved: dict[str, Path] = {}

    def v02() -> Mapping[str, Any]:
        nonlocal resolved
        resolved = {
            "source_root": _resolve_path(path.parent, config["source_root"]),
            "dataset": _resolve_path(path.parent, config["dataset"]["path"]),
            "checkpoint": _resolve_path(path.parent, config["checkpoint"]["path"]),
        }
        if not resolved["source_root"].is_dir():
            raise ValidationFailure("SOURCE_ROOT_NOT_FOUND", "Model source root does not exist.", "directory", str(resolved["source_root"]))
        missing_source = [item for item in spec.required_source_files if not (resolved["source_root"] / item).is_file()]
        if missing_source:
            raise ValidationFailure(
                "MODEL_SOURCE_INCOMPATIBLE",
                "Official adapter source files are missing.",
                list(spec.required_source_files),
                missing_source,
            )
        if not resolved["dataset"].is_file():
            raise ValidationFailure("DATASET_NOT_FOUND", "Dataset file does not exist.", "regular file", str(resolved["dataset"]))
        if not resolved["checkpoint"].is_file():
            raise ValidationFailure("CHECKPOINT_NOT_FOUND", "Checkpoint file does not exist.", "regular file", str(resolved["checkpoint"]))
        config_hash = _sha256(path)
        dataset_hash = _sha256(resolved["dataset"])
        checkpoint_hash = _sha256(resolved["checkpoint"])
        _check_declared_hash(config["dataset"].get("sha256"), dataset_hash, "dataset")
        _check_declared_hash(config["checkpoint"].get("sha256"), checkpoint_hash, "checkpoint")
        report["config_sha256"] = config_hash
        report["dataset"] = {"name": config["dataset"]["name"], "sha256": dataset_hash, "path": str(resolved["dataset"])}
        report["checkpoint"] = {"sha256": checkpoint_hash, "path": str(resolved["checkpoint"])}
        return {"source_root": str(resolved["source_root"]), "dataset_sha256": dataset_hash, "checkpoint_sha256": checkpoint_hash}

    if not execute("V02", v02, "INPUT_VALIDATION_FAILED"):
        return _finish_report(report)

    def v03() -> Mapping[str, Any]:
        dataset = config["dataset"]
        if dataset["format"] not in spec.supported_formats:
            raise ValidationFailure(
                "DATASET_FORMAT_UNSUPPORTED",
                "Dataset format is not supported by the selected adapter.",
                list(spec.supported_formats),
                dataset["format"],
            )
        expected_columns = [dataset["date_column"], *dataset["variables"]]
        row_count = 0
        try:
            with resolved["dataset"].open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
                if header != expected_columns:
                    raise ValidationFailure(
                        "DATASET_COLUMNS_MISMATCH",
                        "Dataset columns do not match the supported schema and exact variable order.",
                        expected_columns,
                        header,
                    )
                for line_number, row in enumerate(reader, start=2):
                    row_count += 1
                    if len(row) != len(expected_columns):
                        raise ValidationFailure(
                            "DATASET_COLUMNS_MISMATCH",
                            f"Dataset row {line_number} has an incompatible column count.",
                            len(expected_columns),
                            len(row),
                        )
                    try:
                        datetime.fromisoformat(row[0])
                        values = [float(value) for value in row[1:]]
                    except (ValueError, TypeError) as exc:
                        raise ValidationFailure(
                            "DATASET_VALUE_INVALID",
                            f"Dataset row {line_number} cannot be parsed using the declared schema.",
                            details={"line": line_number, "reason": str(exc)},
                        ) from exc
                    if not all(math.isfinite(value) for value in values):
                        raise ValidationFailure("DATASET_VALUE_INVALID", f"Dataset row {line_number} contains non-finite values.")
        except ValidationFailure:
            raise
        except (OSError, UnicodeError, csv.Error) as exc:
            raise ValidationFailure("DATASET_LOAD_FAILED", f"Dataset could not be read: {exc}") from exc
        if row_count == 0:
            raise ValidationFailure("DATASET_LOAD_FAILED", "Dataset contains no data rows.")
        return {"format": dataset["format"], "columns": expected_columns, "row_count": row_count}

    if not execute("V03", v03, "DATASET_LOAD_FAILED"):
        return _finish_report(report)

    def v04() -> Mapping[str, Any]:
        nonlocal adapter
        adapter = spec.create_adapter(config, resolved)
        details: dict[str, Any] = {"samples": []}
        for sample_index in config["audit"]["samples"]:
            try:
                raw = adapter.load_sample(config["audit"]["split"], int(sample_index))
            except IndexError as exc:
                raise ValidationFailure(
                    "SAMPLE_OUT_OF_RANGE",
                    "Declared sample index is outside the selected split.",
                    "valid split index",
                    sample_index,
                ) from exc
            except Exception as exc:
                raise ValidationFailure(
                    "SAMPLE_CONSTRUCTION_FAILED",
                    f"Official adapter could not construct sample {sample_index}: {exc}",
                    details={"sample_index": sample_index, "exception_class": type(exc).__name__},
                ) from exc
            batch = spec.prepare_batch(raw, config)
            sample_details = dict(spec.validate_sample(batch, config))
            sample_details["sample_index"] = int(sample_index)
            details["samples"].append(sample_details)
            cached_samples[int(sample_index)] = batch
        return details

    if not execute("V04", v04, "SAMPLE_CONSTRUCTION_FAILED"):
        _close_adapter(adapter)
        return _finish_report(report)

    def v05() -> Mapping[str, Any]:
        try:
            adapter.load_checkpoint(str(resolved["checkpoint"]))
        except RuntimeError as exc:
            raise ValidationFailure(
                "CHECKPOINT_STATE_MISMATCH",
                f"Checkpoint state does not match the configured model: {exc}",
                details={"exception_class": type(exc).__name__},
            ) from exc
        except Exception as exc:
            raise ValidationFailure(
                "CHECKPOINT_DESERIALIZE_FAILED",
                f"Checkpoint could not be loaded: {exc}",
                details={"exception_class": type(exc).__name__},
            ) from exc
        metadata = dict(adapter.get_metadata())
        metadata.pop("source_root", None)
        report["runtime"] = {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "device": metadata.get("device"),
        }
        return {"metadata": metadata}

    if not execute("V05", v05, "CHECKPOINT_DESERIALIZE_FAILED"):
        _close_adapter(adapter)
        return _finish_report(report)

    def v06() -> Mapping[str, Any]:
        results = []
        for sample_index in config["audit"]["samples"]:
            try:
                baseline = adapter.predict(cached_samples[int(sample_index)])
            except Exception as exc:
                raise ValidationFailure(
                    "BASELINE_FORWARD_FAILED",
                    f"Real checkpoint baseline forward failed for sample {sample_index}: {exc}",
                    details={"sample_index": int(sample_index), "exception_class": type(exc).__name__},
                ) from exc
            shape = _validate_prediction(baseline, config, "BASELINE_OUTPUT_INVALID", "Baseline prediction")
            digest = _value_sha256(baseline)
            baselines[int(sample_index)] = baseline
            results.append({"sample_index": int(sample_index), "prediction_shape": shape, "prediction_sha256": digest})
        report["measurements"]["baseline_predictions"] = results
        report["measurements"]["baseline_shape"] = results[0]["prediction_shape"]
        report["measurements"]["baseline_prediction_sha256"] = results[0]["prediction_sha256"]
        return {"samples": results}

    if not execute("V06", v06, "BASELINE_FORWARD_FAILED"):
        _close_adapter(adapter)
        return _finish_report(report)

    def v07() -> Mapping[str, Any]:
        results = []
        for relation_index, relation in enumerate(config["audit"]["relations"]):
            sample_index = int(relation["sample"])
            if sample_index not in extracted_graphs:
                try:
                    extracted_graphs[sample_index] = adapter.extract_graph_stages(cached_samples[sample_index])
                except Exception as exc:
                    raise ValidationFailure(
                        "GRAPH_EXTRACTION_FAILED",
                        f"Native graph extraction failed for sample {sample_index}: {exc}",
                        details={"sample_index": sample_index, "exception_class": type(exc).__name__},
                    ) from exc
            details = dict(spec.validate_graph(extracted_graphs[sample_index], relation, config))
            results.append({"relation_index": relation_index, "sample_index": sample_index, **details})
        return {"relations": results, "sample_graph_count": len(extracted_graphs)}

    if not execute("V07", v07, "GRAPH_EXTRACTION_FAILED"):
        _close_adapter(adapter)
        return _finish_report(report)

    def v08() -> Mapping[str, Any]:
        results = []
        seen: set[tuple[Any, ...]] = set()
        maximum = 0.0
        for relation_index, relation in enumerate(config["audit"]["relations"]):
            context = relation["context"]
            identity_key = (
                int(relation["sample"]), context["type"], int(context.get("layer", 0)), int(context["index"])
            )
            if identity_key in seen:
                continue
            seen.add(identity_key)
            sample_index = int(relation["sample"])
            override = spec.identity_override(relation, config)
            try:
                outcome = adapter.predict_with_graph_override(cached_samples[sample_index], override)
                identity = outcome["prediction"]
            except Exception as exc:
                raise ValidationFailure(
                    "IDENTITY_FORWARD_FAILED",
                    f"Identity intervention replay failed for relation {relation_index}: {exc}",
                    details={"relation_index": relation_index, "sample_index": sample_index, "exception_class": type(exc).__name__},
                ) from exc
            _validate_prediction(identity, config, "IDENTITY_FORWARD_FAILED", "Identity prediction")
            matched, max_abs = _allclose(baselines[sample_index], identity, IDENTITY_ATOL, IDENTITY_RTOL)
            maximum = max(maximum, max_abs)
            if not matched:
                raise ValidationFailure(
                    "IDENTITY_MISMATCH",
                    "Identity/no-change intervention does not match baseline.",
                    {"atol": IDENTITY_ATOL, "rtol": IDENTITY_RTOL},
                    {"max_absolute_difference": max_abs},
                    {"relation_index": relation_index, "sample_index": sample_index},
                )
            results.append({"relation_index": relation_index, "sample_index": sample_index, "max_absolute_difference": max_abs})
        report["measurements"]["identity_max_absolute_difference"] = maximum
        report["measurements"]["identity_atol"] = IDENTITY_ATOL
        report["measurements"]["identity_rtol"] = IDENTITY_RTOL
        return {"contexts": results, "max_absolute_difference": maximum, "atol": IDENTITY_ATOL, "rtol": IDENTITY_RTOL}

    if not execute("V08", v08, "IDENTITY_FORWARD_FAILED"):
        _close_adapter(adapter)
        return _finish_report(report)

    def v09() -> Mapping[str, Any]:
        results = []
        for relation_index, relation in enumerate(config["audit"]["relations"]):
            sample_index = int(relation["sample"])
            scopes = [False, True] if relation.get("include_broader_context") else [False]
            for broader in scopes:
                override = spec.intervention_override(relation, config, broader=broader)
                try:
                    outcome = adapter.predict_with_graph_override(cached_samples[sample_index], override)
                    prediction = outcome["prediction"]
                except (KeyError, IndexError, AttributeError) as exc:
                    raise ValidationFailure(
                        "INTERVENTION_POINT_UNAVAILABLE",
                        f"Exact intervention point is unavailable for relation {relation_index}: {exc}",
                        details={"relation_index": relation_index, "sample_index": sample_index, "scope": "broader" if broader else "local", "exception_class": type(exc).__name__},
                    ) from exc
                except Exception as exc:
                    raise ValidationFailure(
                        "INTERVENTION_FORWARD_FAILED",
                        f"Exact intervention replay failed for relation {relation_index}: {exc}",
                        details={"relation_index": relation_index, "sample_index": sample_index, "scope": "broader" if broader else "local", "exception_class": type(exc).__name__},
                    ) from exc
                shape = _validate_prediction(prediction, config, "INTERVENTION_OUTPUT_INVALID", "Intervention prediction")
                if outcome.get("graph_before") is None or outcome.get("graph_after") is None:
                    raise ValidationFailure(
                        "INTERVENTION_POINT_UNAVAILABLE",
                        "Intervention adapter did not return graph-before and graph-after metadata.",
                        "non-null graph metadata",
                        {"graph_before": outcome.get("graph_before"), "graph_after": outcome.get("graph_after")},
                    )
                protocol = outcome.get("protocol", {})
                if int(protocol.get("source", -1)) != int(relation["source"]) or int(protocol.get("target", -1)) != int(relation["target"]):
                    raise ValidationFailure(
                        "INTERVENTION_POINT_UNAVAILABLE",
                        "Adapter intervention protocol does not preserve the exact requested relation.",
                        {"source": relation["source"], "target": relation["target"]},
                        {"source": protocol.get("source"), "target": protocol.get("target")},
                    )
                results.append({
                    "relation_index": relation_index,
                    "sample_index": sample_index,
                    "scope": "broader" if broader else "local",
                    "prediction_shape": shape,
                    "protocol": _json_safe(protocol),
                })
        return {"replays": results, "nonzero_effect_required": False}

    try:
        execute("V09", v09, "INTERVENTION_FORWARD_FAILED")
    finally:
        _close_adapter(adapter)
    return _finish_report(report)


def render_validation_report(report: Mapping[str, Any]) -> str:
    lines = ["DGraInsight Adapter Validation", ""]
    adapter = report.get("adapter") or {}
    if adapter.get("name"):
        lines.append(f"Adapter: {adapter['name']} · {adapter.get('model')} · {adapter.get('native_context_type')} graph")
        lines.append("")
    for check in report.get("checks", []):
        marker = {"pass": "✓", "fail": "✗", "not_run": "–"}.get(check["status"], "?")
        line = f"{marker} {check['label']}"
        if check.get("code"):
            line += f" [{check['code']}]"
        lines.append(line)
        if check["status"] == "fail":
            lines.append(f"  {check['message']}")
            if check.get("expected") is not None:
                lines.append(f"  Expected: {_compact(check['expected'])}")
            if check.get("found") is not None:
                lines.append(f"  Found: {_compact(check['found'])}")
            issues = check.get("details", {}).get("issues", [])
            for issue in issues[1:]:
                lines.append(f"  - [{issue['code']}] {issue['message']}")
    lines.extend(["", f"Status: {'READY FOR AUDIT' if report.get('status') == 'ready_for_audit' else 'NOT READY'}"])
    return "\n".join(lines)


def _validate_common_config(config: Mapping[str, Any], spec: AdapterValidationSpec | None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    _reject_unknown_fields(
        issues,
        "config",
        config,
        {"schema_version", "adapter", "source_root", "checkpoint", "dataset", "audit", "adapter_config"},
    )
    if config.get("schema_version") != CONFIG_SCHEMA_VERSION:
        issues.append(_issue("CONFIG_SCHEMA_UNSUPPORTED", "Unsupported audit config schema version.", CONFIG_SCHEMA_VERSION, config.get("schema_version")))
    if spec is None:
        issues.append(_issue("ADAPTER_UNSUPPORTED", "Adapter is not registered as an official v1 adapter.", sorted(OFFICIAL_ADAPTER_REGISTRY), config.get("adapter")))
    if not isinstance(config.get("source_root"), str) or not config.get("source_root"):
        issues.append(_issue("CONFIG_FIELD_INVALID", "source_root must be a non-empty path string.", "path string", config.get("source_root")))
    checkpoint = config.get("checkpoint")
    if not isinstance(checkpoint, Mapping) or not isinstance(checkpoint.get("path"), str):
        issues.append(_issue("CONFIG_FIELD_INVALID", "checkpoint.path must be a path string.", "path string", checkpoint))
    elif isinstance(checkpoint, Mapping):
        _reject_unknown_fields(issues, "checkpoint", checkpoint, {"path", "sha256"})
    dataset = config.get("dataset")
    dataset_fields = {
        "name": str, "path": str, "format": str, "date_column": str, "variables": list,
        "features": str, "target": str, "frequency": str, "seq_len": int, "label_len": int, "pred_len": int,
    }
    if not isinstance(dataset, Mapping):
        issues.append(_issue("CONFIG_FIELD_INVALID", "dataset must be an object.", "object", type(dataset).__name__))
    else:
        _reject_unknown_fields(issues, "dataset", dataset, set(dataset_fields) | {"sha256"})
        for field, expected_type in dataset_fields.items():
            if not isinstance(dataset.get(field), expected_type):
                issues.append(_issue("CONFIG_FIELD_INVALID", f"dataset.{field} has an invalid type.", expected_type.__name__, dataset.get(field)))
        variables = dataset.get("variables")
        if isinstance(variables, list) and (not variables or not all(isinstance(value, str) and value for value in variables)):
            issues.append(_issue("CONFIG_FIELD_INVALID", "dataset.variables must contain non-empty strings.", "non-empty string array", variables))
        if isinstance(variables, list) and isinstance(dataset.get("target"), str) and dataset["target"] not in variables:
            issues.append(_issue("CONFIG_FIELD_INVALID", "dataset.target must be one of dataset.variables.", variables, dataset["target"]))
        for field in ("seq_len", "label_len", "pred_len"):
            if isinstance(dataset.get(field), int) and dataset[field] <= 0:
                issues.append(_issue("CONFIG_FIELD_INVALID", f"dataset.{field} must be positive.", "> 0", dataset[field]))
    audit = config.get("audit")
    if not isinstance(audit, Mapping):
        issues.append(_issue("CONFIG_FIELD_INVALID", "audit must be an object.", "object", type(audit).__name__))
    else:
        _reject_unknown_fields(issues, "audit", audit, {"split", "samples", "relations"})
        samples = audit.get("samples")
        relations = audit.get("relations")
        if audit.get("split") != "test":
            issues.append(_issue("CONFIG_FIELD_INVALID", "Audit Config v1 supports only the test split.", "test", audit.get("split")))
        if not isinstance(samples, list) or not samples or not all(isinstance(value, int) and value >= 0 for value in samples):
            issues.append(_issue("CONFIG_FIELD_INVALID", "audit.samples must be a non-empty array of non-negative real split indices.", "integer array", samples))
            samples = []
        if not isinstance(relations, list) or not relations:
            issues.append(_issue("CONFIG_FIELD_INVALID", "audit.relations must be a non-empty array.", "relation array", relations))
        else:
            for index, relation in enumerate(relations):
                if not isinstance(relation, Mapping):
                    issues.append(_issue("CONFIG_FIELD_INVALID", f"audit.relations[{index}] must be an object.", "object", relation))
                    continue
                _reject_unknown_fields(
                    issues,
                    f"audit.relations[{index}]",
                    relation,
                    {"sample", "context", "source", "target", "include_broader_context"},
                )
                for field in ("sample", "source", "target"):
                    if not isinstance(relation.get(field), int) or relation[field] < 0:
                        issues.append(_issue("CONFIG_FIELD_INVALID", f"audit.relations[{index}].{field} must be a non-negative integer.", "integer", relation.get(field)))
                if isinstance(relation.get("sample"), int) and relation["sample"] not in samples:
                    issues.append(_issue("CONFIG_FIELD_INVALID", f"audit.relations[{index}].sample is not declared in audit.samples.", samples, relation["sample"]))
                if relation.get("source") == relation.get("target"):
                    issues.append(_issue("CONFIG_FIELD_INVALID", f"audit.relations[{index}] must be a directed non-self relation.", "source != target", relation.get("source")))
                context = relation.get("context")
                if not isinstance(context, Mapping):
                    issues.append(_issue("CONFIG_FIELD_INVALID", f"audit.relations[{index}].context must be an object.", "object", context))
                elif spec is not None:
                    context_fields = {"type", "index", "layer"} if spec.native_context_type == "scale" else {"type", "index"}
                    _reject_unknown_fields(issues, f"audit.relations[{index}].context", context, context_fields)
                    if context.get("type") != spec.native_context_type:
                        issues.append(_issue("CONTEXT_TYPE_MISMATCH", f"Relation context does not match {spec.adapter_name} native semantics.", spec.native_context_type, context.get("type")))
                    if not isinstance(context.get("index"), int) or context["index"] < 0:
                        issues.append(_issue("CONFIG_FIELD_INVALID", "Relation context index must be a non-negative integer.", "integer", context.get("index")))
                    if spec.native_context_type == "scale" and (not isinstance(context.get("layer", 0), int) or context.get("layer", 0) < 0):
                        issues.append(_issue("CONFIG_FIELD_INVALID", "MSGNet context layer must be a non-negative integer.", "integer", context.get("layer")))
                if isinstance(dataset, Mapping) and isinstance(dataset.get("variables"), list):
                    node_count = len(dataset["variables"])
                    for field in ("source", "target"):
                        value = relation.get(field)
                        if isinstance(value, int) and value >= node_count:
                            issues.append(_issue(
                                "RELATION_OUT_OF_RANGE",
                                f"audit.relations[{index}].{field} is outside the declared variable range.",
                                f"0..{node_count - 1}",
                                value,
                            ))
                if "include_broader_context" in relation and not isinstance(relation["include_broader_context"], bool):
                    issues.append(_issue("CONFIG_FIELD_INVALID", "include_broader_context must be boolean.", "boolean", relation["include_broader_context"]))
    if spec is not None:
        adapter_config = config.get("adapter_config")
        if isinstance(adapter_config, Mapping):
            allowed_adapter_fields = {"random_seed", "model"}
            if spec.adapter_id == "dgraformer":
                allowed_adapter_fields.add("current_epoch")
            _reject_unknown_fields(issues, "adapter_config", adapter_config, allowed_adapter_fields)
        issues.extend(spec.validate_adapter_config(config))
        if isinstance(dataset, Mapping) and isinstance(dataset.get("variables"), list):
            model = config.get("adapter_config", {}).get("model", {}) if isinstance(config.get("adapter_config"), Mapping) else {}
            expected_input = model.get("enc_in") if spec.adapter_id == "msgnet" else len(dataset["variables"])
            if spec.adapter_id == "msgnet" and isinstance(expected_input, int) and expected_input != len(dataset["variables"]):
                issues.append(_issue("CONFIG_FIELD_INVALID", "MSGNet enc_in must equal dataset variable count.", len(dataset["variables"]), expected_input))
            output_count = model.get("c_out") if spec.adapter_id == "msgnet" else None
            if spec.adapter_id == "msgnet" and isinstance(output_count, int) and output_count != len(dataset["variables"]):
                issues.append(_issue("CONFIG_FIELD_INVALID", "MSGNet c_out must equal dataset variable count.", len(dataset["variables"]), output_count))
    return issues


def _new_report(config_path: Path) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "not_ready",
        "adapter": None,
        "dataset": None,
        "checkpoint": None,
        "config_path": str(config_path),
        "config_sha256": None,
        "checks": [],
        "probe": None,
        "measurements": {},
        "runtime": {"python": platform.python_version(), "platform": platform.platform()},
    }


def _finish_report(report: MutableMapping[str, Any]) -> dict[str, Any]:
    report["status"] = "ready_for_audit" if len(report["checks"]) == len(CHECK_DEFINITIONS) and all(
        item["status"] == "pass" for item in report["checks"]
    ) else "not_ready"
    canonical = json.dumps(_json_safe(report), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    report["report_sha256"] = hashlib.sha256(canonical).hexdigest()
    return dict(report)


def _check(
    definition: tuple[str, str, str],
    status: str,
    code: str | None = None,
    message: str | None = None,
    expected: Any = None,
    found: Any = None,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": definition[0],
        "name": definition[1],
        "label": definition[2],
        "status": status,
        "code": code,
        "message": message or (f"{definition[2]} passed." if status == "pass" else f"{definition[2]} was not run."),
        "expected": _json_safe(expected),
        "found": _json_safe(found),
        "details": _json_safe(dict(details or {})),
    }


def _append_not_run(report: MutableMapping[str, Any], failed_id: str) -> None:
    existing = {item["id"] for item in report["checks"]}
    for definition in CHECK_DEFINITIONS:
        if definition[0] not in existing:
            report["checks"].append(_check(
                definition,
                "not_run",
                code="BLOCKED_BY_PREVIOUS_FAILURE",
                message=f"Not run because {failed_id} failed.",
                details={"blocked_by": failed_id},
            ))


def _issue(code: str, message: str, expected: Any = None, found: Any = None) -> dict[str, Any]:
    return {"code": code, "message": message, "expected": _json_safe(expected), "found": _json_safe(found)}


def _reject_unknown_fields(
    issues: list[dict[str, Any]], path: str, value: Mapping[str, Any], allowed: set[str]
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        issues.append(_issue(
            "CONFIG_FIELD_INVALID",
            f"{path} contains unsupported fields; v1 does not silently accept scientific configuration.",
            sorted(allowed),
            unknown,
        ))


def _probe_from_relation(relation: Mapping[str, Any]) -> dict[str, Any]:
    context = relation["context"]
    result = {
        "sample_index": int(relation["sample"]),
        "context_type": context["type"],
        "context_index": int(context["index"]),
        "source": int(relation["source"]),
        "target": int(relation["target"]),
        "include_broader_context": bool(relation.get("include_broader_context", False)),
    }
    if "layer" in context:
        result["layer"] = int(context["layer"])
    return result


def _resolve_path(base: Path, value: str) -> Path:
    candidate = Path(value)
    return (candidate if candidate.is_absolute() else base / candidate).resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_declared_hash(declared: Any, actual: str, label: str) -> None:
    if declared is not None and declared != actual:
        raise ValidationFailure("HASH_MISMATCH", f"Declared {label} SHA-256 does not match the file.", declared, actual)


def _shape(value: Any) -> tuple[int, ...]:
    if value is None:
        return ()
    shape = getattr(value, "shape", None)
    if shape is not None:
        return tuple(int(item) for item in shape)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if not value:
            return (0,)
        child = _shape(value[0])
        if any(_shape(item) != child for item in value):
            return (len(value),)
        return (len(value), *child)
    return ()


def _as_list(value: Any) -> Any:
    current = value
    for method in ("detach", "cpu"):
        callback = getattr(current, method, None)
        if callable(callback):
            current = callback()
    callback = getattr(current, "tolist", None)
    return callback() if callable(callback) else current


def _flatten(value: Any) -> list[float]:
    value = _as_list(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        result: list[float] = []
        for item in value:
            result.extend(_flatten(item))
        return result
    return [float(value)]


def _is_finite(value: Any) -> bool:
    try:
        return all(math.isfinite(item) for item in _flatten(value))
    except (TypeError, ValueError):
        return False


def _matrix_rows(value: Any) -> list[list[float]]:
    converted = _as_list(value)
    if not isinstance(converted, Sequence):
        raise ValidationFailure("GRAPH_SHAPE_MISMATCH", "Graph value is not a matrix.")
    return [[float(cell) for cell in row] for row in converted]


def _validate_square_finite_matrix(value: Any, n: int, label: str) -> None:
    shape = list(_shape(value))
    if shape != [n, n]:
        raise ValidationFailure("GRAPH_SHAPE_MISMATCH", f"{label} shape is incompatible.", [n, n], shape)
    if not _is_finite(value):
        raise ValidationFailure("GRAPH_NONFINITE", f"{label} contains non-finite values.")


def _validate_prediction(value: Any, config: Mapping[str, Any], code: str, label: str) -> list[int]:
    expected = [1, int(config["dataset"]["pred_len"]), len(config["dataset"]["variables"])]
    shape = list(_shape(value))
    if shape != expected:
        raise ValidationFailure(code, f"{label} shape is incompatible.", expected, shape)
    if not _is_finite(value):
        raise ValidationFailure(code, f"{label} contains non-finite values.")
    return shape


def _value_sha256(value: Any) -> str:
    current = value
    for method in ("detach", "cpu", "contiguous"):
        callback = getattr(current, method, None)
        if callable(callback):
            current = callback()
    array = getattr(current, "numpy", None)
    if callable(array):
        converted = array()
        raw = converted.tobytes(order="C")
        header = json.dumps(
            {"shape": list(_shape(value)), "dtype": str(getattr(value, "dtype", converted.dtype))},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(header + b"\0" + raw).hexdigest()
    payload = {"shape": list(_shape(value)), "dtype": "python-float", "values": _flatten(value)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _allclose(left: Any, right: Any, atol: float, rtol: float) -> tuple[bool, float]:
    a, b = _flatten(left), _flatten(right)
    if len(a) != len(b):
        return False, math.inf
    differences = [abs(x - y) for x, y in zip(a, b)]
    matched = all(diff <= atol + rtol * abs(x) for diff, x in zip(differences, a))
    return matched, max(differences, default=0.0)


def _close_adapter(adapter: Any) -> None:
    if adapter is None:
        return
    close = getattr(adapter, "close", None)
    if callable(close):
        close()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_safe(item) for item in value]
    converted = _as_list(value)
    if converted is not value:
        return _json_safe(converted)
    return str(value)


def _compact(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

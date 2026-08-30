from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

from dgraudit.validation import (
    AdapterValidationSpec,
    CONFIG_SCHEMA_VERSION,
    ValidationFailure,
    render_validation_report,
    validate_audit_config,
)


class FakeAdapter:
    def __init__(self, mode: str = "success"):
        self.mode = mode
        self.closed = False

    def load_sample(self, split: str, sample_index: int) -> Mapping[str, Any]:
        if self.mode == "sample_out_of_range":
            raise IndexError(sample_index)
        return {
            "x": [[1.0, 2.0], [3.0, 4.0]],
            "y": [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
            "time_index": [0.0, 1.0],
            "sample_index": sample_index,
            "split": split,
        }

    def load_checkpoint(self, path: str) -> None:
        if self.mode == "checkpoint_mismatch":
            raise RuntimeError("size mismatch for model.weight")

    def predict(self, batch: Mapping[str, Any]) -> Any:
        if self.mode == "baseline_failure":
            raise RuntimeError("forward unavailable")
        return [[[1.0, 2.0], [3.0, 4.0]]]

    def extract_graph_stages(self, batch: Mapping[str, Any]) -> Mapping[str, Any]:
        if self.mode == "graph_failure":
            raise RuntimeError("graph hook unavailable")
        return {"windows": [{"window": 0, "normalized": [[0.5, 0.5], [0.25, 0.75]]}]}

    def predict_with_graph_override(self, batch: Mapping[str, Any], override: Mapping[str, Any]) -> Mapping[str, Any]:
        if override["type"] == "identity":
            prediction = [[[1.0, 2.0], [3.0, 4.1]]] if self.mode == "identity_mismatch" else self.predict(batch)
            return {
                "prediction": prediction,
                "graph_before": [[0.5, 0.5], [0.25, 0.75]],
                "graph_after": [[0.5, 0.5], [0.25, 0.75]],
                "protocol": dict(override),
            }
        if self.mode == "intervention_unavailable" or (
            self.mode == "second_intervention_unavailable" and override.get("source") == 1
        ):
            raise KeyError("exact graph hook")
        # Deliberately return the baseline. Zero intervention response is valid
        # negative evidence and must not make preflight fail.
        return {
            "prediction": self.predict(batch),
            "graph_before": [[0.5, 0.5], [0.25, 0.75]],
            "graph_after": [[1.0, 0.0], [0.25, 0.75]],
            "protocol": dict(override),
        }

    def get_metadata(self) -> Mapping[str, Any]:
        return {"adapter": "FakeAdapter", "dataset": "Fixture", "device": "cpu", "source_root": "fixture"}

    def close(self) -> None:
        self.closed = True


class FakeSpec(AdapterValidationSpec):
    adapter_id = "fake"
    adapter_name = "FakeAdapter"
    model_name = "FakeModel"
    native_context_type = "window"
    supported_formats = ("test_csv",)

    def __init__(self, adapter: FakeAdapter):
        self.adapter = adapter

    def create_adapter(self, config: Mapping[str, Any], resolved: Mapping[str, Path]) -> Any:
        if self.adapter.mode == "missing_runtime":
            raise ModuleNotFoundError("No module named 'torch'", name="torch")
        return self.adapter

    def validate_sample(self, batch: Mapping[str, Any], config: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"x_shape": [2, 2], "y_shape": [3, 2], "time_index_shape": [2]}

    def validate_graph(
        self, extracted: Mapping[str, Any], probe: Mapping[str, Any], config: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        windows = extracted.get("windows")
        if not windows:
            raise ValidationFailure("GRAPH_EXTRACTION_FAILED", "Fixture graph is missing.")
        graph = windows[0]["normalized"]
        if graph[probe["source"]][probe["target"]] <= 0:
            raise ValidationFailure("RELATION_NOT_PRESENT", "Fixture relation is not present.")
        return {"context_count": 1, "requested_window": 0, "matrix_shape": [2, 2]}

    def identity_override(self, probe: Mapping[str, Any], config: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"type": "identity", "window": probe["context"]["index"]}

    def intervention_override(
        self, probe: Mapping[str, Any], config: Mapping[str, Any], broader: bool = False
    ) -> Mapping[str, Any]:
        return {
            "type": "global_structural_edge_removal" if broader else "structural_edge_removal",
            "window": probe["context"]["index"],
            "source": probe["source"],
            "target": probe["target"],
        }


class PreflightValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.dataset = self.root / "fixture.csv"
        self.dataset.write_text("date,A,B\n2026-01-01 00:00:00,1,2\n2026-01-01 01:00:00,3,4\n", encoding="utf-8")
        self.checkpoint = self.root / "checkpoint.pth"
        self.checkpoint.write_bytes(b"fixture checkpoint")
        self.config_path = self.root / "audit_config.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def config(self) -> dict[str, Any]:
        return {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "adapter": "fake",
            "source_root": str(self.source),
            "checkpoint": {"path": str(self.checkpoint)},
            "dataset": {
                "name": "Fixture",
                "path": str(self.dataset),
                "format": "test_csv",
                "date_column": "date",
                "variables": ["A", "B"],
                "features": "M",
                "target": "B",
                "frequency": "h",
                "seq_len": 2,
                "label_len": 1,
                "pred_len": 2,
            },
            "audit": {
                "split": "test",
                "samples": [0],
                "relations": [{
                    "sample": 0,
                    "context": {"type": "window", "index": 0},
                    "source": 0,
                    "target": 1,
                    "include_broader_context": True,
                }],
            },
            "adapter_config": {"random_seed": 1, "model": {}},
        }

    def run_validation(self, mode: str = "success", patch=None):
        config = self.config()
        if patch:
            patch(config)
        self.config_path.write_text(json.dumps(config), encoding="utf-8")
        adapter = FakeAdapter(mode)
        report = validate_audit_config(self.config_path, registry={"fake": FakeSpec(adapter)})
        return report, adapter

    @staticmethod
    def failed_code(report: Mapping[str, Any]) -> str | None:
        failed = next((item for item in report["checks"] if item["status"] == "fail"), None)
        return failed["code"] if failed else None

    def test_success_runs_all_checks_and_accepts_zero_effect(self):
        report, adapter = self.run_validation()
        self.assertEqual(report["status"], "ready_for_audit")
        self.assertEqual([item["status"] for item in report["checks"]], ["pass"] * 9)
        self.assertEqual(report["measurements"]["identity_max_absolute_difference"], 0.0)
        self.assertTrue(adapter.closed)
        self.assertIn("Status: READY FOR AUDIT", render_validation_report(report))

    def test_missing_checkpoint_fails_before_adapter_creation(self):
        report, adapter = self.run_validation(patch=lambda value: value["checkpoint"].update(path=str(self.root / "missing.pth")))
        self.assertEqual(self.failed_code(report), "CHECKPOINT_NOT_FOUND")
        self.assertFalse(adapter.closed)

    def test_malformed_config_is_explicit_and_blocks_all_later_checks(self):
        self.config_path.write_text("{not json", encoding="utf-8")
        report = validate_audit_config(self.config_path, registry={"fake": FakeSpec(FakeAdapter())})
        self.assertEqual(self.failed_code(report), "CONFIG_PARSE_ERROR")
        self.assertEqual(report["status"], "not_ready")
        self.assertEqual(report["checks"][0]["status"], "fail")
        self.assertTrue(all(item["status"] == "not_run" for item in report["checks"][1:]))
        self.assertTrue(all(item["code"] == "BLOCKED_BY_PREVIOUS_FAILURE" for item in report["checks"][1:]))

    def test_unknown_adapter_is_rejected_without_runtime_creation(self):
        config = self.config()
        config["adapter"] = "arbitrary_model"
        self.config_path.write_text(json.dumps(config), encoding="utf-8")
        report = validate_audit_config(self.config_path, registry={"fake": FakeSpec(FakeAdapter())})
        self.assertEqual(self.failed_code(report), "ADAPTER_UNSUPPORTED")
        self.assertEqual(report["status"], "not_ready")
        self.assertTrue(all(item["status"] == "not_run" for item in report["checks"][1:]))

    def test_dataset_column_mismatch_is_explicit(self):
        self.dataset.write_text("date,A,C\n2026-01-01 00:00:00,1,2\n", encoding="utf-8")
        report, _ = self.run_validation()
        self.assertEqual(self.failed_code(report), "DATASET_COLUMNS_MISMATCH")

    def test_sample_out_of_range_is_explicit(self):
        report, adapter = self.run_validation("sample_out_of_range")
        self.assertEqual(self.failed_code(report), "SAMPLE_OUT_OF_RANGE")
        self.assertTrue(adapter.closed)

    def test_missing_runtime_dependency_is_structured(self):
        report, _ = self.run_validation("missing_runtime")
        self.assertEqual(self.failed_code(report), "RUNTIME_DEPENDENCY_MISSING")

    def test_checkpoint_mismatch_is_explicit(self):
        report, adapter = self.run_validation("checkpoint_mismatch")
        self.assertEqual(self.failed_code(report), "CHECKPOINT_STATE_MISMATCH")
        self.assertTrue(adapter.closed)

    def test_baseline_failure_is_explicit(self):
        report, _ = self.run_validation("baseline_failure")
        self.assertEqual(self.failed_code(report), "BASELINE_FORWARD_FAILED")

    def test_graph_extraction_failure_is_explicit(self):
        report, _ = self.run_validation("graph_failure")
        self.assertEqual(self.failed_code(report), "GRAPH_EXTRACTION_FAILED")

    def test_identity_mismatch_is_explicit(self):
        report, _ = self.run_validation("identity_mismatch")
        self.assertEqual(self.failed_code(report), "IDENTITY_MISMATCH")

    def test_intervention_unavailable_is_explicit(self):
        report, _ = self.run_validation("intervention_unavailable")
        self.assertEqual(self.failed_code(report), "INTERVENTION_POINT_UNAVAILABLE")

    def test_every_declared_relation_is_preflighted(self):
        def patch_config(config):
            config["audit"]["relations"].append({
                "sample": 0,
                "context": {"type": "window", "index": 0},
                "source": 1,
                "target": 0,
                "include_broader_context": False,
            })

        report, _ = self.run_validation("second_intervention_unavailable", patch_config)
        self.assertEqual(self.failed_code(report), "INTERVENTION_POINT_UNAVAILABLE")
        failed = next(item for item in report["checks"] if item["status"] == "fail")
        self.assertEqual(failed["details"]["relation_index"], 1)

    def test_runtime_failure_never_reports_partial_success(self):
        report, _ = self.run_validation("graph_failure")
        failed_index = next(index for index, item in enumerate(report["checks"]) if item["status"] == "fail")
        self.assertEqual(report["status"], "not_ready")
        self.assertTrue(all(item["status"] == "not_run" for item in report["checks"][failed_index + 1:]))
        self.assertTrue(
            all(item["code"] == "BLOCKED_BY_PREVIOUS_FAILURE" for item in report["checks"][failed_index + 1:])
        )

    def test_context_semantics_mismatch_fails_config(self):
        def patch(config):
            config["audit"]["relations"][0]["context"]["type"] = "scale"

        report, _ = self.run_validation(patch=patch)
        self.assertEqual(self.failed_code(report), "CONTEXT_TYPE_MISMATCH")

    def test_relation_out_of_range_fails_config(self):
        def patch(config):
            config["audit"]["relations"][0]["target"] = 2

        report, _ = self.run_validation(patch=patch)
        self.assertEqual(self.failed_code(report), "RELATION_OUT_OF_RANGE")


if __name__ == "__main__":
    unittest.main()

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from dgraudit.local_audit import LocalAuditError, _bh_adjust, run_local_audit
from dgraudit.session import validate_audit_session


class _FakeAdapter:
    def __init__(self, source_root: Path):
        self.source_root = source_root
        self.previous_cwd = Path.cwd()
        os.chdir(source_root)

    def load_checkpoint(self, _path):
        return None

    def load_sample(self, _split, sample_index):
        return {
            "x": np.zeros((4, 3), dtype=np.float32),
            "y": np.zeros((3, 3), dtype=np.float32),
            "sample_index": sample_index,
        }

    def predict(self, _batch):
        return np.zeros((1, 2, 3), dtype=np.float32)

    def extract_graph_stages(self, _batch):
        matrix = np.asarray([
            [0.5, 0.3, 0.2],
            [0.2, 0.5, 0.3],
            [0.3, 0.2, 0.5],
        ], dtype=np.float32)
        return {"windows": [{
            "window": 0,
            "static_prior": matrix,
            "raw_score": matrix,
            "activated": matrix,
            "diagonal_removed": matrix,
            "topk_mask": np.ones((3, 3), dtype=np.float32),
            "topk_graph": matrix,
            "self_loop_graph": matrix,
            "normalized": matrix,
            "topk_slots": 6,
            "blend_proportion": 1.0,
        }]}

    def predict_with_graph_override(self, batch, override):
        effect = (int(override["source"]) * 3 + int(override["target"]) + 1) / 100
        prediction = self.predict(batch) + effect
        matrix = self.extract_graph_stages(batch)["windows"][0]["normalized"]
        return {
            "prediction": prediction,
            "graph_before": matrix,
            "graph_after": matrix,
            "protocol": dict(override),
        }

    def close(self):
        os.chdir(self.previous_cwd)


class _FakeSpec:
    adapter_id = "dgraformer"
    adapter_name = "DGraFormerAdapter"
    model_name = "DGraFormer"
    native_context_type = "window"

    def create_adapter(self, _config, resolved):
        return _FakeAdapter(resolved["source_root"])

    def prepare_batch(self, batch, _config):
        return dict(batch)

    def intervention_override(self, probe, _config, broader=False):
        result = {
            "type": "structural_edge_removal",
            "source": int(probe["source"]),
            "target": int(probe["target"]),
        }
        if broader:
            result["type"] = "global_structural_edge_removal"
        else:
            result["window"] = int(probe["context"]["index"])
        return result


class LocalAuditTests(unittest.TestCase):
    def test_bh_adjustment_is_monotone_in_rank_order(self):
        self.assertEqual(_bh_adjust([0.01, 0.04, 0.03]), [0.03, 0.04, 0.04])

    def test_direct_audit_writes_valid_session_despite_adapter_cwd_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            source = root / "upstream"
            workspace.mkdir()
            source.mkdir()
            dataset = workspace / "data.csv"
            checkpoint = workspace / "checkpoint.pth"
            dataset.write_text("date,A,B,C\n2026-01-01,1,2,3\n", encoding="utf-8")
            checkpoint.write_bytes(b"real-test-checkpoint-placeholder")
            config = {
                "schema_version": "dgrainsight.audit_config.v1",
                "adapter": "dgraformer",
                "source_root": str(source),
                "checkpoint": {"path": str(checkpoint)},
                "dataset": {
                    "name": "Fixture",
                    "path": str(dataset),
                    "format": "ett_hour",
                    "date_column": "date",
                    "variables": ["A", "B", "C"],
                    "features": "M",
                    "target": "C",
                    "frequency": "h",
                    "seq_len": 4,
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
                "adapter_config": {"random_seed": 7, "current_epoch": 5, "model": {}},
            }
            config_path = workspace / "audit.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            preflight = {
                "schema_version": "dgrainsight.adapter_validation.v1",
                "status": "ready_for_audit",
                "adapter": {"id": "dgraformer", "name": "DGraFormerAdapter"},
                "checks": [{"id": f"V{index:02d}", "name": "fixture", "label": "fixture", "status": "pass"}
                           for index in range(1, 10)],
                "measurements": {},
                "runtime": {"device": "cpu"},
                "dataset": {"sha256": "0" * 64},
                "checkpoint": {"sha256": "1" * 64},
            }
            previous = Path.cwd()
            try:
                os.chdir(workspace)
                with patch("dgraudit.local_audit.validate_audit_config", return_value=preflight), patch.dict(
                    "dgraudit.local_audit.OFFICIAL_ADAPTER_REGISTRY", {"dgraformer": _FakeSpec()}, clear=True
                ):
                    output, session = run_local_audit(
                        config_path,
                        output_path="generated/dgrainsight_session.json",
                        bootstrap_repetitions=20,
                    )
            finally:
                os.chdir(previous)
            self.assertEqual(output, workspace / "generated" / "dgrainsight_session.json")
            self.assertTrue(output.is_file())
            self.assertEqual(validate_audit_session(session), [])
            self.assertEqual(session["evidence_summary"]["local_case_count"], 1)
            self.assertEqual(session["evidence_summary"]["broader_context_case_count"], 1)
            self.assertEqual(session["model_specific"]["local_audit"]["prediction_replay_count"], 12)

    def test_failed_preflight_creates_no_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "dgrainsight_session.json"
            report = {"status": "not_ready", "checks": []}
            with patch("dgraudit.local_audit.validate_audit_config", return_value=report):
                with self.assertRaises(LocalAuditError):
                    run_local_audit(Path(temporary) / "missing.json", output_path=output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()

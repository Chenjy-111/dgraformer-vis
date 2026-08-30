from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from dgraudit.session import build_audit_session, validate_audit_session, write_audit_session


ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = "2026-08-29T00:00:00Z"


class AuditSessionExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dgra = build_audit_session(
            ROOT / "configs/export_session_dgraformer_etth1.json", created_at=FIXED_TIME
        )
        cls.msgnet = build_audit_session(
            ROOT / "configs/export_session_msgnet_etth1.json", created_at=FIXED_TIME
        )

    def test_dgraformer_export_preserves_real_case_families_and_missing_cross_run(self):
        self.assertEqual(len(self.dgra["samples"]), 40)
        self.assertEqual(len(self.dgra["relations"]), 160)
        self.assertEqual(len(self.dgra["evidence_records"]), 480)
        self.assertEqual(self.dgra["evidence_summary"]["local_case_count"], 320)
        self.assertEqual(self.dgra["evidence_summary"]["broader_context_case_count"], 160)
        self.assertEqual(self.dgra["evidence_summary"]["not_exposed_case_count"], 95)
        self.assertEqual(self.dgra["cross_run_evidence"]["status"], "missing")
        self.assertIsNone(self.dgra["cross_run_evidence"]["value"])

    def test_dgraformer_controls_are_hydrated_and_hash_verified(self):
        record = next(item for item in self.dgra["evidence_records"] if item["selection"]["scope"] == "local")
        controls = record["value"]["controls"]
        self.assertEqual(controls["status"], "available")
        self.assertEqual(controls["count"], 100)
        self.assertEqual(len(controls["records"]), 100)
        self.assertEqual(len(controls["values"]["value"]), 100)
        self.assertEqual(len(controls["records_sha256"]), 64)

    def test_dgraformer_history_is_not_borrowed_for_unstored_samples(self):
        available = [sample for sample in self.dgra["samples"] if sample["history"]["status"] == "available"]
        missing = [sample for sample in self.dgra["samples"] if sample["history"]["status"] == "missing"]
        self.assertEqual([sample["sample_index"] for sample in available], [0])
        self.assertEqual(len(missing), 39)
        self.assertTrue(all(sample["history"]["value"] is None for sample in missing))

    def test_msgnet_export_preserves_negative_evidence_and_native_scales(self):
        self.assertEqual(len(self.msgnet["samples"]), 5)
        self.assertEqual(len(self.msgnet["relations"]), 210)
        self.assertEqual(len(self.msgnet["evidence_records"]), 840)
        self.assertEqual(self.msgnet["evidence_summary"]["local_case_count"], 630)
        self.assertEqual(self.msgnet["evidence_summary"]["broader_context_case_count"], 210)
        self.assertEqual(self.msgnet["evidence_summary"]["local_bh_supported_count"], 0)
        self.assertEqual(self.msgnet["evidence_summary"]["broader_context_bh_supported_count"], 0)
        self.assertEqual({context["type"] for context in self.msgnet["samples"][0]["contexts"]}, {"scale"})

    def test_msgnet_local_trajectory_missing_and_global_controls_materialized(self):
        local = next(item for item in self.msgnet["evidence_records"] if item["selection"]["scope"] == "local")
        broader = next(
            item for item in self.msgnet["evidence_records"] if item["selection"]["scope"] == "broader_context"
        )
        self.assertEqual(local["value"]["intervention_output"]["status"], "missing")
        self.assertIsNone(local["value"]["intervention_output"]["value"])
        self.assertEqual(broader["value"]["intervention_output"]["status"], "available")
        self.assertEqual(broader["value"]["controls"]["count"], 41)
        self.assertEqual(len(broader["value"]["controls"]["values"]["value"]), 41)

    def test_msgnet_axis_canonicalization_preserves_values(self):
        source = json.loads(
            (ROOT / "legacy/v1/artifacts/public-data/models/msgnet/etth1/catalog.json").read_text(encoding="utf-8")
        )["samples"][0]
        exported = self.msgnet["samples"][0]
        self.assertEqual(exported["history"]["value"]["axis_order"], ["input_step", "variable"])
        self.assertEqual(exported["history"]["value"]["values"][3][2], source["history"][2][3])
        self.assertEqual(exported["ground_truth"]["values"][7][4], source["ground_truth"][4][7])
        self.assertEqual(exported["baseline_prediction"]["values"][11][6], source["prediction"][6][11])

    def test_semantic_validator_rejects_reference_and_shape_corruption(self):
        broken_reference = copy.deepcopy(self.msgnet)
        broken_reference["evidence_records"][0]["selection"]["sample_id"] = "test:999999"
        self.assertTrue(any("sample_id" in error for error in validate_audit_session(broken_reference)))

        broken_shape = copy.deepcopy(self.msgnet)
        broken_shape["samples"][0]["baseline_prediction"]["shape"] = [1, 1]
        self.assertTrue(any("declares shape" in error for error in validate_audit_session(broken_shape)))

    def test_writer_emits_one_parseable_json_document(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "dgrainsight_session.json"
            written, source = write_audit_session(
                ROOT / "configs/export_session_msgnet_etth1.json",
                output_path=output,
                created_at=FIXED_TIME,
            )
            loaded = json.loads(written.read_text(encoding="utf-8"))
            self.assertEqual(loaded, source)
            self.assertEqual(validate_audit_session(loaded), [])


if __name__ == "__main__":
    unittest.main()

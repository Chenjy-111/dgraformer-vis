from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AuditSessionSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads((ROOT / "schemas/dgrainsight_audit_session_v1.schema.json").read_text(encoding="utf-8"))
        cls.dgra_local = json.loads((ROOT / "legacy/v1/artifacts/public-data/evidence/etth1_intervention_catalog.json").read_text(encoding="utf-8"))
        cls.dgra_global = json.loads((ROOT / "legacy/v1/artifacts/public-data/evidence/etth1_global_intervention_catalog.json").read_text(encoding="utf-8"))
        cls.msgnet = json.loads((ROOT / "legacy/v1/artifacts/public-data/models/msgnet/etth1/catalog.json").read_text(encoding="utf-8"))

    def test_schema_has_strict_portable_envelope(self):
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], "dgrainsight.audit_session.v1")
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual(
            set(self.schema["required"]),
            {
                "schema_version", "session", "model", "dataset", "checkpoint", "audit_plan",
                "samples", "relations", "evidence_records", "evidence_summary",
                "cross_run_evidence", "provenance", "limitations",
            },
        )

    def test_missing_evidence_contract_requires_null(self):
        variants = self.schema["$defs"]["nullableEvidence"]["oneOf"]
        missing = next(item for item in variants if "missing" in item["properties"]["status"].get("enum", []))
        self.assertEqual(missing["properties"]["value"]["type"], "null")
        self.assertEqual(missing["properties"]["reason"]["minLength"], 1)

    def test_dgraformer_catalog_counts_and_missing_cross_run_are_preserved(self):
        self.assertEqual(len(self.dgra_local["cases"]), 320)
        self.assertEqual(len(self.dgra_global["cases"]), 160)
        self.assertEqual(self.dgra_local["cross_run"]["status"], "missing")
        self.assertIsNone(self.dgra_local["cross_run"]["metrics"])
        self.assertEqual(self.dgra_global["cross_run"]["status"], "missing")
        self.assertIsNone(self.dgra_global["cross_run"]["metrics"])

    def test_dgraformer_not_exposed_values_are_real_source_fields(self):
        record = next(item for item in self.dgra_local["cases"] if item["window_active"] is False)
        self.assertEqual(record["structural_metrics"]["prediction_delta_abs"], 0.0)
        self.assertEqual(record["structural_metrics"]["empirical_p"], 1.0)
        self.assertIsNone(record["structural_metrics"]["standardized_effect_size"])
        self.assertEqual(record["structural_metric_status"]["standardized_effect_size"]["status"], "undefined")

    def test_msgnet_negative_evidence_counts_remain_zero(self):
        self.assertEqual(self.msgnet["case_count"], 630)
        self.assertEqual(self.msgnet["global_case_count"], 210)
        self.assertEqual(self.msgnet["bh_supported_count"], 0)
        self.assertEqual(self.msgnet["global_bh_supported_count"], 0)

    def test_msgnet_local_and_global_availability_are_not_conflated(self):
        local = self.msgnet["samples"][0]["edge_impacts"][0]
        broader = self.msgnet["samples"][0]["global_edge_impacts"][0]
        self.assertNotIn("intervention_prediction", local)
        self.assertIn("intervention_prediction", broader)
        self.assertEqual(len(local["controls"]["prediction_delta_abs"]), 41)
        self.assertNotIn("prediction_delta_abs", broader["controls"])
        self.assertIn("control_mean_prediction_delta_abs", broader["statistics"])

    def test_msgnet_global_controls_are_losslessly_selectable_from_stored_cases(self):
        sample = self.msgnet["samples"][0]
        focal = sample["global_edge_impacts"][0]
        controls = [
            item["prediction_delta_abs"]
            for item in sample["global_edge_impacts"]
            if (item["source"], item["target"]) != (focal["source"], focal["target"])
        ]
        self.assertEqual(len(controls), 41)
        self.assertAlmostEqual(
            sum(controls) / len(controls),
            focal["statistics"]["control_mean_prediction_delta_abs"],
            places=15,
        )


if __name__ == "__main__":
    unittest.main()

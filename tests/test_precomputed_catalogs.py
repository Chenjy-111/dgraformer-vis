import json
import unittest
from pathlib import Path


class PrecomputedCatalogTests(unittest.TestCase):
    INTERVENTION_RUN = "db40ee6d94c577e978a06b6aaba50cee209ea13f98b4a6d03a7ed5f4d39e107c"
    EVIDENCE_RUN = "3e6ed8ca27a3f6fd83dec960f0a0091c9497d4ea8cdc1cbeafa1ae88d7161cc3"

    def load(self, run_id, relative):
        path = Path("artifacts") / "runs" / run_id / relative
        if not path.exists():
            self.skipTest("skipped_missing_real_artifact")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_intervention_catalog_is_etth1_only(self):
        manifest = self.load(self.INTERVENTION_RUN, "manifest.json")
        self.assertEqual([item["dataset"] for item in manifest["datasets"]], ["ETTh1"])
        self.assertEqual(manifest["datasets"][0]["record_count"], 80)
        self.assertEqual(manifest["schedule"]["current_epoch_equivalent"], 5)

    def test_catalog_entries_do_not_claim_statistical_validation(self):
        catalog = self.load(self.INTERVENTION_RUN, "catalog/ETTh1.json")
        self.assertTrue(all(record["statistical_validation"]["status"] == "not_evaluated"
                            for record in catalog["records"]))

    def test_evidence_catalog_has_complete_predeclared_family(self):
        catalog = self.load(self.EVIDENCE_RUN, "evidence_catalog.json")
        self.assertEqual(catalog["dataset"], "ETTh1")
        self.assertEqual(catalog["case_count"], 40)
        self.assertEqual(catalog["multiple_comparison_family_size"], 40)
        self.assertTrue(all(case["status"] == "complete" for case in catalog["cases"]))
        self.assertTrue(all(case["metrics"]["bh_adjusted_p"] is not None for case in catalog["cases"]))

    def test_undefined_effect_sizes_have_explicit_reason(self):
        catalog = self.load(self.EVIDENCE_RUN, "evidence_catalog.json")
        for case in catalog["cases"]:
            effect = case["metrics"]["standardized_effect_size"]
            status = case["metric_status"]["standardized_effect_size"]
            if effect is None:
                self.assertEqual(status["status"], "undefined")
                self.assertTrue(status["reason"])
            else:
                self.assertEqual(status["status"], "complete")
                self.assertIsNone(status["reason"])

    def test_cross_run_remains_missing_null(self):
        catalog = self.load(self.EVIDENCE_RUN, "evidence_catalog.json")
        self.assertEqual(catalog["cross_run"]["status"], "missing")
        self.assertIsNone(catalog["cross_run"]["metrics"])


if __name__ == "__main__":
    unittest.main()

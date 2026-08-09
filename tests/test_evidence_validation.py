import unittest
import json
from pathlib import Path

import torch

from dgraudit.cli.validate_pattern import benjamini_hochberg, impact_metrics


class EvidenceValidationTests(unittest.TestCase):
    RUN_ID = "9b3eeeeb8ef2967cc7fe44a09ac41f214ce9442a890b74d112341cbec0c6f708"

    def real_evidence(self):
        paths = list((Path("artifacts") / "runs" / self.RUN_ID / "evidence").glob("*.json"))
        if not paths:
            self.skipTest("skipped_missing_real_artifact")
        return json.loads(paths[0].read_text(encoding="utf-8"))

    def test_metrics_match_formulas(self):
        baseline = torch.tensor([[[1.0, 2.0]]])
        intervention = torch.tensor([[[2.0, 0.0]]])
        truth = torch.tensor([[[0.0, 1.0]]])
        result = impact_metrics(baseline, intervention, truth)
        self.assertAlmostEqual(result["prediction_delta_abs"], 1.5)
        self.assertAlmostEqual(result["prediction_delta_rel"], 1.0)
        self.assertAlmostEqual(result["baseline_mae"], 1.0)
        self.assertAlmostEqual(result["intervention_mae"], 1.5)
        self.assertAlmostEqual(result["error_delta_mae"], 0.5)

    def test_bh_adjustment_is_monotone_in_rank(self):
        adjusted = benjamini_hochberg([0.01, 0.04, 0.03])
        self.assertEqual([round(value, 3) for value in adjusted], [0.03, 0.04, 0.04])

    def test_evidence_contains_hashes(self):
        evidence = self.real_evidence()
        self.assertEqual(len(evidence["dataset"]["sha256"]), 64)
        self.assertEqual(len(evidence["model"]["checkpoint_sha256"]), 64)
        self.assertEqual(len(evidence["model"]["config_sha256"]), 64)

    def test_reproduction_command_saved(self):
        evidence = self.real_evidence()
        run_dir = Path("artifacts") / "runs" / evidence["reproduction"]["run_id"]
        self.assertTrue((run_dir / evidence["reproduction"]["command"]).read_text(encoding="utf-8").strip())

    def test_no_placeholder_marked_complete(self):
        evidence = self.real_evidence()
        serialized = json.dumps(evidence).lower()
        for forbidden in ["placeholder", "dummy", "mock", "fake"]:
            self.assertNotIn(forbidden, serialized)

    def test_null_is_not_used_for_computed_metrics(self):
        evidence = self.real_evidence()
        self.assertTrue(all(value is not None for value in evidence["metrics"].values()))


if __name__ == "__main__":
    unittest.main()

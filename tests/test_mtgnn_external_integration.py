from __future__ import annotations

import tempfile
import unittest
import warnings
from pathlib import Path

import numpy as np

from dgraudit.cli.validate_session_v2 import validate_json_schema
from dgraudit.quick_audit import run_quick_audit
from dgraudit.v2.session import validate_audit_session_v2
from dgraudit.validation import OFFICIAL_ADAPTER_REGISTRY


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_CONFIG = ROOT / "configs/local_audit_mtgnn_exchange.json"
CUSTOM_CONFIG = ROOT / "configs/custom_adapter_mtgnn_exchange.json"


class ExternalMTGNNIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        required_assets = [
            ROOT / "third_party/MTGNN/net.py",
            ROOT / "third_party/MTGNN/util.py",
            ROOT / "third_party/MTGNN/data/exchange_rate.txt",
            ROOT / "artifacts/mtgnn_exchange/mtgnn_exchange_h3_seed42_state_dict.pt",
        ]
        missing = [str(path.relative_to(ROOT)) for path in required_assets if not path.is_file()]
        if missing:
            raise unittest.SkipTest(
                "Real MTGNN integration assets are intentionally not bundled: " + ", ".join(missing)
            )
        cls.temporary = tempfile.TemporaryDirectory()
        destination = Path(cls.temporary.name)
        # Public MTGNN DataLoaderS leaves its local read handle to garbage collection.
        # Preserve upstream source and keep this integration regression output focused.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            _, cls.official = run_quick_audit(
                OFFICIAL_CONFIG, output_path=destination / "official-session-v2.json"
            )
            _, cls.custom = run_quick_audit(
                CUSTOM_CONFIG, output_path=destination / "custom-session-v2.json"
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_custom_mtgnn_is_external_and_uses_the_common_session_contract(self):
        self.assertEqual(set(OFFICIAL_ADAPTER_REGISTRY), {"dgraformer", "msgnet", "mtgnn"})
        self.assertNotIn("mtgnn_external", OFFICIAL_ADAPTER_REGISTRY)
        self.assertEqual(self.custom["model"]["adapter_id"], "mtgnn_external")
        self.assertEqual(self.custom["model"]["adapter_module"], "mtgnn_external_adapter")
        self.assertEqual(self.custom["model"]["adapter_class"], "ExternalMTGNNAdapter")
        self.assertEqual(validate_audit_session_v2(self.custom), [])
        self.assertEqual(validate_json_schema(self.custom), [])
        self.assertEqual(self.custom["case_evidence"][0]["controls"]["unique_count"], 27)
        self.assertEqual(self.custom["case_evidence"][0]["formal_inference"]["status"], "not_evaluated")

    def test_custom_mtgnn_exactly_matches_the_official_execution_on_the_same_device(self):
        official_case = self.official["case_evidence"][0]
        custom_case = self.custom["case_evidence"][0]
        comparisons = {
            "baseline_prediction": (
                self.official["samples"][0]["baseline_prediction"]["values"],
                self.custom["samples"][0]["baseline_prediction"]["values"],
            ),
            "learned_adjacency": (
                self.official["samples"][0]["contexts"][0]["graphs"]["learned_adjacency"]["values"],
                self.custom["samples"][0]["contexts"][0]["graphs"]["learned_adjacency"]["values"],
            ),
            "intervention_prediction": (
                official_case["intervention_output_reference"]["value"]["values"],
                custom_case["intervention_output_reference"]["value"]["values"],
            ),
            "control_responses": (
                official_case["controls"]["responses"], custom_case["controls"]["responses"],
            ),
        }
        for label, (official, custom) in comparisons.items():
            np.testing.assert_array_equal(np.asarray(official), np.asarray(custom), err_msg=label)
        self.assertEqual(official_case["focal_response"], custom_case["focal_response"])
        self.assertEqual(official_case["D"], custom_case["D"])
        self.assertEqual(self.official["checkpoint"]["sha256"], self.custom["checkpoint"]["sha256"])
        self.assertEqual(self.official["dataset"]["sha256"], self.custom["dataset"]["sha256"])


if __name__ == "__main__":
    unittest.main()

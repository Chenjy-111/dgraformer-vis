from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dgraudit.cli.validate_session_v2 import validate_json_schema
from dgraudit.quick_audit import run_quick_audit
from dgraudit.registry import CustomAdapterLoadError, load_custom_adapter_class
from dgraudit.v2.session import validate_audit_session_v2
from dgraudit.validation import validate_audit_config


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/custom_adapter_fixture.json"
SOURCE = ROOT / "tests/fixtures/custom_adapter"


class CustomAdapterExtensibilityTests(unittest.TestCase):
    def test_explicit_external_adapter_conformance_and_common_quick_core(self):
        report = validate_audit_config(CONFIG, debug=True)
        self.assertEqual(report["status"], "ready_for_audit")
        self.assertEqual([item["status"] for item in report["checks"]], ["pass"] * 9)
        self.assertEqual(report["adapter"]["id"], "tiny_external_fixture")
        self.assertEqual(report["measurements"]["identity_max_absolute_difference"], 0.0)

        with tempfile.TemporaryDirectory() as temporary:
            output, session = run_quick_audit(CONFIG, output_path=Path(temporary) / "session.json")
            self.assertTrue(output.is_file())
            self.assertEqual(validate_audit_session_v2(session), [])
            self.assertEqual(validate_json_schema(session), [])

        self.assertEqual(session["model"]["adapter_id"], "tiny_external_fixture")
        self.assertEqual(session["model"]["adapter_module"], "tiny_custom_adapter")
        self.assertEqual(session["model"]["adapter_class"], "TinyDeterministicGraphAdapter")
        for actual, expected in zip(session["samples"][0]["baseline_prediction"]["values"][0], [0.9, 0.95, 1.15]):
            self.assertAlmostEqual(actual, expected, places=6)
        self.assertEqual(session["samples"][0]["contexts"][0]["type"], "global")
        self.assertEqual(session["case_evidence"][0]["controls"]["unique_count"], 5)
        self.assertEqual(session["case_evidence"][0]["formal_inference"]["status"], "not_evaluated")
        self.assertIsNone(session["cross_sample_evidence"][0]["primary_inference"]["raw_p"])
        self.assertIsNone(session["cross_sample_evidence"][0]["multiplicity"]["adjusted_q"])

    def test_loader_fails_closed_without_fallback(self):
        with self.assertRaises(CustomAdapterLoadError) as caught:
            load_custom_adapter_class({"module": "module_that_does_not_exist", "class": "Missing"}, SOURCE)
        self.assertEqual(caught.exception.code, "CUSTOM_ADAPTER_IMPORT_FAILED")
        self.assertIn("could not be imported", str(caught.exception))

        with self.assertRaises(CustomAdapterLoadError) as missing:
            load_custom_adapter_class({"module": "tiny_custom_adapter", "class": "MissingAdapter"}, SOURCE)
        self.assertEqual(missing.exception.code, "CUSTOM_ADAPTER_CLASS_NOT_FOUND")

        with self.assertRaises(CustomAdapterLoadError) as wrong_type:
            load_custom_adapter_class({"module": "tiny_custom_adapter", "class": "GraphContext"}, SOURCE)
        self.assertEqual(wrong_type.exception.code, "CUSTOM_ADAPTER_TYPE_INVALID")

        with tempfile.TemporaryDirectory() as temporary:
            module_name = "incomplete_custom_adapter_fixture"
            Path(temporary, f"{module_name}.py").write_text(
                "from dgraudit.adapters import DynamicGraphForecastAdapter\n"
                "class Incomplete(DynamicGraphForecastAdapter):\n    pass\n",
                encoding="utf-8",
            )
            with self.assertRaises(CustomAdapterLoadError) as incomplete:
                load_custom_adapter_class({"module": module_name, "class": "Incomplete"}, Path(temporary))
            self.assertEqual(incomplete.exception.code, "CUSTOM_ADAPTER_CONTRACT_INCOMPLETE")

    def test_audit_core_contains_no_fixture_or_model_name_special_case(self):
        sources = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in ("dgraudit/quick_audit.py", "dgraudit/v2/quick.py", "dgraudit/edge_discovery.py")
        )
        self.assertNotIn("TinyDeterministicGraph", sources)
        self.assertNotIn("tiny_external_fixture", sources)
        self.assertNotIn("adapter_id ==", sources)


if __name__ == "__main__":
    unittest.main()

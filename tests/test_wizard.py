from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dgraudit.cli.wizard import run_wizard


class WizardTests(unittest.TestCase):
    def test_wizard_selects_context_and_edge_without_mutating_template(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            checkpoint = root / "checkpoint.pt"
            checkpoint.write_bytes(b"checkpoint")
            dataset = root / "dataset.csv"
            dataset.write_text("1,2\n", encoding="utf-8")
            template = {
                "schema_version": "dgrainsight.audit_config.v1",
                "adapter": "fake",
                "source_root": "source",
                "checkpoint": {"path": "checkpoint.pt"},
                "dataset": {"path": "dataset.csv"},
                "audit": {"split": "test", "samples": [0], "relations": []},
            }
            template_path = root / "template.json"
            template_path.write_text(json.dumps(template), encoding="utf-8")
            original_text = template_path.read_text(encoding="utf-8")
            output_path = root / "output" / "dgrainsight_session.json"
            report = {
                "model": "FakeModel",
                "adapter": "FakeAdapter",
                "dataset": "Fixture",
                "sample_index": 7,
                "native_context_type": "window",
                "native_context_count": 2,
                "displayed_context_count": 2,
                "contexts": [
                    {
                        "context_id": "window:0", "type": "window", "index": 0, "layer": None,
                        "retained_edge_count": 1,
                        "top_edges": [{"source": 0, "target": 1, "source_name": "A", "target_name": "B", "weight": 0.8}],
                    },
                    {
                        "context_id": "window:1", "type": "window", "index": 1, "layer": None,
                        "retained_edge_count": 2,
                        "top_edges": [
                            {"source": 1, "target": 0, "source_name": "B", "target_name": "A", "weight": 0.9},
                            {"source": 0, "target": 1, "source_name": "A", "target_name": "B", "weight": 0.7},
                        ],
                    },
                ],
            }
            answers = iter(["2", "1", "y", "y"])
            captured: dict[str, object] = {}

            def fake_audit(config_path, *, output_path, bootstrap_repetitions, progress):
                captured["config"] = json.loads(Path(config_path).read_text(encoding="utf-8"))
                captured["bootstrap"] = bootstrap_repetitions
                Path(output_path).write_text("{}", encoding="utf-8")
                return Path(output_path), {"session": {"session_id": "fixture"}}

            with patch("dgraudit.cli.wizard.inspect_native_edges", return_value=report), patch(
                "dgraudit.cli.wizard.render_edge_inspection", return_value="fixture graph report"
            ), patch("dgraudit.cli.wizard.run_local_audit", side_effect=fake_audit):
                written, selected_config, _ = run_wizard(
                    template_path,
                    output_path=output_path,
                    bootstrap_repetitions=25,
                    input_fn=lambda _prompt: next(answers),
                    print_fn=lambda _message: None,
                )

            self.assertEqual(written, output_path)
            self.assertTrue(selected_config.is_file())
            self.assertEqual(template_path.read_text(encoding="utf-8"), original_text)
            relation = captured["config"]["audit"]["relations"][0]
            self.assertEqual(relation["sample"], 7)
            self.assertEqual(relation["context"], {"type": "window", "index": 1})
            self.assertEqual((relation["source"], relation["target"]), (1, 0))
            self.assertTrue(relation["include_broader_context"])
            self.assertEqual(captured["bootstrap"], 25)


if __name__ == "__main__":
    unittest.main()

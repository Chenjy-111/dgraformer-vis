from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path

from dgraudit.cli.validate_audit import validate_config_file
from dgraudit.cli.validate_session_v2 import validate_json_schema
from dgraudit.v2.config import validate_audit_config_v2
from dgraudit.v2.controls import ControlProtocolError, build_case_evidence
from dgraudit.v2.families import canonical_hash
from dgraudit.v2.frozen import load_dgraformer_frozen_inputs, load_msgnet_frozen_inputs
from dgraudit.v2.inference import infer_candidate
from dgraudit.v2.session import build_audit_session_v2, validate_audit_session_v2, write_audit_session_v2


ROOT = Path(__file__).resolve().parents[1]


class ConfigV2CliTests(unittest.TestCase):
    def test_public_config_v2_validates_through_default_cli_route(self) -> None:
        report, _ = validate_config_file(ROOT / "configs/formal_audit_v2_dgraformer_etth1_frozen40.json")
        self.assertEqual(report["status"], "ready_for_audit")
        self.assertEqual([check["status"] for check in report["checks"]], ["pass", "pass"])


def graph_snapshot(session: dict) -> dict:
    samples = []
    for sample in session["samples"]:
        core = {key: sample[key] for key in ("sample_id", "display_id", "split", "sample_index", "history", "ground_truth", "baseline_prediction", "sample_metrics", "contexts")}
        samples.append({
            "sample_id": sample["sample_id"], "sample_index": sample["sample_index"], "context_count": len(sample["contexts"]),
            "node_counts": [context["node_count"] for context in sample["contexts"]],
            "graph_shapes": [{name: tensor["shape"] for name, tensor in context["graphs"].items()} for context in sample["contexts"]],
            "graph_core_sha256": canonical_hash(core), "baseline_prediction_sha256": canonical_hash(sample["baseline_prediction"]), "contexts_sha256": canonical_hash(sample["contexts"]),
        })
    relations = [{key: relation[key] for key in ("relation_id", "sample_id", "source", "target", "native_occurrences")} for relation in session["relations"]]
    return {"sample_count": len(session["samples"]), "relation_count": len(session["relations"]), "samples": samples, "relation_core_sha256": canonical_hash(relations)}


class GraphRegressionTests(unittest.TestCase):
    def test_current_graph_core_is_exactly_preserved_for_all_adapters(self) -> None:
        fixture = json.loads((ROOT / "tests/fixtures/pipeline_v2_graph_baseline.json").read_text(encoding="utf-8"))["models"]
        sources = {"DGraFormer": ROOT / fixture["DGraFormer"]["source"], "MSGNet": ROOT / fixture["MSGNet"]["source"], "MTGNN": ROOT / fixture["MTGNN"]["source"]}
        for model, path in sources.items():
            with self.subTest(model=model):
                session = json.loads(path.read_text(encoding="utf-8"))
                expected = {key: fixture[model][key] for key in ("sample_count", "relation_count", "samples", "relation_core_sha256")}
                self.assertEqual(graph_snapshot(session), expected)

    def test_msgnet_frozen14_shared_test_zero_graph_core_is_exact(self) -> None:
        old = json.loads((ROOT / "tests/fixtures/msgnet_graph_core_baseline.json").read_text(encoding="utf-8"))
        new = load_msgnet_frozen_inputs(include_intervention_trajectories=False)[1]
        old_sample = next(sample for sample in old["samples"] if sample["sample_index"] == 0)
        new_sample = next(sample for sample in new["samples"] if sample["sample_index"] == 0)
        for key in ("history", "ground_truth", "baseline_prediction", "sample_metrics", "contexts"):
            self.assertEqual(new_sample[key], old_sample[key])
        old_relations = [{key: relation[key] for key in ("relation_id", "sample_id", "source", "target", "native_occurrences")} for relation in old["relations"] if relation["sample_id"] == "test:0"]
        new_relations = [{key: relation[key] for key in ("relation_id", "sample_id", "source", "target", "native_occurrences")} for relation in new["relations"] if relation["sample_id"] == "test:0"]
        self.assertEqual(new_relations, old_relations)


class FrozenStatisticalReproductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        dgra = load_dgraformer_frozen_inputs()
        cls.dgra_session = build_audit_session_v2(config=dgra[0], graph_core=dgra[1], case_evidence=dgra[2], dependence_by_family=dgra[3], generator={"name": "regression"})
        msg = load_msgnet_frozen_inputs(include_intervention_trajectories=False)
        cls.msg_session = build_audit_session_v2(config=msg[0], graph_core=msg[1], case_evidence=msg[2], dependence_by_family=msg[3], generator={"name": "regression"})

    def test_dgraformer_frozen_D_p_and_q(self) -> None:
        with (ROOT / "artifacts/dgraformer_frozen40/local_case_effects.csv").open(encoding="utf-8", newline="") as handle:
            local_rows = list(csv.DictReader(handle))
        by_candidate = {item["candidate_id"]: item for item in self.dgra_session["cross_sample_evidence"]}
        candidate = by_candidate["dgra:window:6:0->4"]
        frozen_active = [float(row["paired_effect_mean"]) for row in local_rows if row["window_id"] == "6" and row["source_node"] == "0" and row["target_node"] == "4" and row["active"] == "True"]
        self.assertEqual([value for value in candidate["D_values"] if value is not None], frozen_active)
        self.assertAlmostEqual(candidate["primary_inference"]["raw_p"], 0.0010998900109989002, places=15)
        self.assertAlmostEqual(candidate["multiplicity"]["adjusted_q"], 0.008799120087991202, places=15)
        global_candidate = by_candidate["dgra:all:0->2"]
        self.assertAlmostEqual(global_candidate["primary_inference"]["raw_p"], 0.00009999000099990002, places=16)
        self.assertAlmostEqual(global_candidate["multiplicity"]["adjusted_q"], 0.00039996000399960006, places=16)
        self.assertFalse(any(value == 0 for value, sample in zip(candidate["D_values"], candidate["planned_samples"]) if sample in candidate["inactive_samples"] and value is not None))

    def test_msgnet_frozen_exact_inference_and_families(self) -> None:
        sizes = {family["scope"]: family["size"] for family in self.msg_session["hypothesis_families"]}
        self.assertEqual(sizes, {"single_scale": 126, "all_scales": 42})
        self.assertTrue(all(case["controls"]["unique_count"] == 41 for case in self.msg_session["case_evidence"]))
        self.assertTrue(all(item["primary_inference"]["settings"]["sign_configurations"] == 16384 for item in self.msg_session["cross_sample_evidence"]))
        supported = {family["scope"]: sum(item["multiplicity"]["supported"] is True for item in self.msg_session["cross_sample_evidence"] if item["family_id"] == family["family_id"]) for family in self.msg_session["hypothesis_families"]}
        self.assertEqual(supported, {"single_scale": 27, "all_scales": 14})
        self.assertFalse(any("period" in item or "current_period" in item for item in self.msg_session["candidate_relations"]))

    def test_python_and_json_schema_validators(self) -> None:
        for session in (self.dgra_session, self.msg_session):
            self.assertEqual(validate_audit_session_v2(session), [])
            self.assertEqual(validate_json_schema(session), [])


class NegativeAndRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.session = json.loads(
            (ROOT / "tests/fixtures/mtgnn_quick_session_v2.json").read_text(encoding="utf-8")
        )

    def test_one_sample_formal_requires_explicit_unavailable(self) -> None:
        family_id = "mtgnn.global"
        config = {
            "schema_version": "dgrainsight.audit_config.v2", "config_version": 2, "audit_mode": "formal_evidence_audit", "adapter": "mtgnn", "dataset": {}, "checkpoint": {},
            "sample_protocol": {"protocol_id": "one", "selection_rule": "predeclared", "split": "test", "sample_ids": [0], "selection_frozen": True, "active_inactive_policy": "exclude_inactive_without_zero_imputation"},
            "candidate_families": [{"family_id": family_id, "scope": "global_graph", "selection_rule": "predeclared", "context_identity_rule": "global_graph,source,target", "members": [{"candidate_id": "m", "source": 0, "target": 1}], "family_size": 1, "selection_frozen": True}],
            "control_protocol": {"protocol": "all_unique_eligible", "with_replacement": False}, "response_metric": "prediction_delta_abs", "dependence_protocol": {"expected_classification": "unknown_dependence"},
            "inference_protocol": {"selection_frozen": True, "alternative": "mean_D > 0", "by_family": {family_id: {"primary_test": "unavailable"}}},
            "multiplicity_protocol": {"primary_method": "BH", "alpha": 0.05}, "sensitivity_protocol": {},
        }
        self.assertEqual(validate_audit_config_v2(config), [])
        result = infer_candidate([0.5], {"primary_test": "unavailable"}, {"classification": "unknown_dependence"})
        self.assertEqual(result["status"], "unavailable")

    def test_empty_and_duplicate_controls_fail(self) -> None:
        base = dict(case_evidence_id="x", candidate_id="c", sample_id=0, context={}, scope="global_graph", active=True, focal_response=1.0, response_metrics={}, graph_effect={}, baseline_reference={}, intervention_output_reference={}, provenance={})
        with self.assertRaises(ControlProtocolError):
            build_case_evidence(**base, controls=[])
        with self.assertRaises(ControlProtocolError):
            build_case_evidence(**base, controls=[{"identity": "a", "response": 0.1}, {"identity": "a", "response": 0.1}])

    def _errors_after(self, mutation) -> list[str]:
        session = copy.deepcopy(self.session)
        mutation(session)
        return validate_audit_session_v2(session)

    def test_family_removed_after_inference_fails(self) -> None:
        errors = self._errors_after(lambda session: session["hypothesis_families"][0].update({"members": [], "size": 0}))
        self.assertTrue(any("family size/membership" in error or "exactly one" in error for error in errors))

    def test_inactive_zero_family_mismatch_missing_tensor_invalid_q_and_old_p_fail(self) -> None:
        mutations = [
            lambda session: session["case_evidence"][0].update({"status": "inactive", "focal_response": 0.0, "D": 0.0}),
            lambda session: session["hypothesis_families"][0].update({"size": 99}),
            lambda session: session["samples"][0].pop("ground_truth"),
            lambda session: session["cross_sample_evidence"][0]["multiplicity"].update({"adjusted_q": 1.5}),
            lambda session: session["cross_sample_evidence"][0].update({"empirical_p": 0.01}),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.assertTrue(self._errors_after(mutation))

    def test_unknown_dependence_is_unavailable(self) -> None:
        result = infer_candidate([0.1, 0.2], {"primary_test": "exact_sign_flip_mean_D"}, {"classification": "unknown_dependence"})
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["raw_p"])
        self.assertTrue(result["reason"])

    def test_round_trip_preserves_all_v2_layers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = write_audit_session_v2(Path(directory) / "session.json", self.session)
            parsed = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(parsed, self.session)
        self.assertEqual(validate_json_schema(parsed), [])
        self.assertEqual(validate_audit_session_v2(parsed), [])
        for key in ("samples", "case_evidence", "candidate_relations", "cross_sample_evidence", "hypothesis_families", "dependence_audit", "provenance"):
            self.assertEqual(parsed[key], self.session[key])


if __name__ == "__main__":
    unittest.main()

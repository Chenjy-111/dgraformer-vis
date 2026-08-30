from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from typing import Any, Mapping

from dgraudit.session import validate_audit_session, write_audit_session


ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = "2026-08-30T00:00:00Z"

STATISTIC_FIELDS = {
    "control_mean_prediction_delta_abs",
    "control_median_prediction_delta_abs",
    "control_percentile",
    "control_percentile_midrank",
    "empirical_p",
    "bh_adjusted_p",
    "standardized_effect_size",
    "candidate_minus_control_mean_bootstrap_ci_95",
    "effect_difference_bootstrap_ci",
    "bootstrap_repetitions",
    "bootstrap_seed",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def transpose_variable_step(values: list[list[float]]) -> list[list[float]]:
    return [list(row) for row in zip(*values)]


def split_metrics(source: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    metrics = {key: value for key, value in source.items() if key not in STATISTIC_FIELDS}
    statistics = {key: value for key, value in source.items() if key in STATISTIC_FIELDS}
    return metrics, statistics


def control_summary(statistics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in statistics.items()
        if key.startswith("control_") or key.startswith("candidate_minus_control_")
    }


def run_relative_path(run_dir: Path, raw_path: str) -> Path:
    return run_dir.joinpath(*PureWindowsPath(raw_path).parts)


def stored_control_value(record: Mapping[str, Any]) -> float:
    if "prediction_delta_abs" in record:
        return record["prediction_delta_abs"]
    return record["metrics"]["prediction_delta_abs"]


class AuditSessionRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_directory = tempfile.TemporaryDirectory()
        temp_root = Path(cls.temp_directory.name)
        _, cls.dgra_exported = write_audit_session(
            ROOT / "configs/export_session_dgraformer_etth1.json",
            output_path=temp_root / "dgraformer" / "dgrainsight_session.json",
            created_at=FIXED_TIME,
        )
        _, cls.msgnet_exported = write_audit_session(
            ROOT / "configs/export_session_msgnet_etth1.json",
            output_path=temp_root / "msgnet" / "dgrainsight_session.json",
            created_at=FIXED_TIME,
        )
        cls.dgra = read_json(temp_root / "dgraformer" / "dgrainsight_session.json")
        cls.msgnet = read_json(temp_root / "msgnet" / "dgrainsight_session.json")
        cls.dgra_local = read_json(ROOT / "legacy/v1/artifacts/public-data/evidence/etth1_intervention_catalog.json")
        cls.dgra_broader = read_json(ROOT / "legacy/v1/artifacts/public-data/evidence/etth1_global_intervention_catalog.json")
        cls.msgnet_catalog = read_json(ROOT / "legacy/v1/artifacts/public-data/models/msgnet/etth1/catalog.json")
        cls.dgra_local_run = ROOT / "artifacts/runs" / cls.dgra_local["source_runs"]["evidence"]
        cls.dgra_broader_run = ROOT / "artifacts/runs" / cls.dgra_broader["run_id"]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_directory.cleanup()

    def test_exported_json_is_a_lossless_session_document(self):
        self.assertEqual(self.dgra, self.dgra_exported)
        self.assertEqual(self.msgnet, self.msgnet_exported)
        self.assertEqual(validate_audit_session(self.dgra), [])
        self.assertEqual(validate_audit_session(self.msgnet), [])

    def test_dgraformer_samples_windows_and_relations_round_trip_exactly(self):
        samples = {sample["sample_index"]: sample for sample in self.dgra["samples"]}
        local_cases: dict[int, list[dict[str, Any]]] = {}
        for case in self.dgra_local["cases"]:
            local_cases.setdefault(case["sample_index"], []).append(case)

        self.assertEqual(list(samples), self.dgra_local["samples"])
        for display_id, sample_index in enumerate(self.dgra_local["samples"]):
            exported = samples[sample_index]
            source = local_cases[sample_index][0]
            self.assertEqual(exported["sample_id"], f"test:{sample_index}")
            self.assertEqual(exported["display_id"], display_id)
            self.assertEqual(exported["ground_truth"]["values"], source["ground_truth"])
            self.assertEqual(exported["baseline_prediction"]["values"], source["baseline_prediction"])
            self.assertEqual(
                exported["sample_metrics"],
                {
                    "mae": source["structural_metrics"]["baseline_mae"],
                    "mse": source["structural_metrics"]["baseline_mse"],
                },
            )

        contexts = {item["index"]: item for item in self.dgra["samples"][0]["contexts"]}
        graph_paths = sorted(
            (self.dgra_local_run / "graphs").glob("window_*.json"),
            key=lambda path: int(path.stem.split("_")[-1]),
        )
        self.assertEqual(set(contexts), {int(path.stem.split("_")[-1]) for path in graph_paths})
        graph_stages = (
            "static_prior",
            "raw_score",
            "activated",
            "diagonal_removed",
            "topk_mask",
            "topk_graph",
            "self_loop_graph",
            "normalized",
        )
        for path in graph_paths:
            source = read_json(path)
            exported = contexts[source["window"]]
            self.assertEqual(exported["context_id"], f"window:{source['window']}")
            self.assertEqual(exported["type"], "window")
            for stage in graph_stages:
                self.assertEqual(exported["graphs"][stage]["values"], source[stage])
            self.assertEqual(exported["native_metadata"]["topk_slots"], source["topk_slots"])
            self.assertEqual(exported["native_metadata"]["blend_proportion"], source["blend_proportion"])
            self.assertEqual(exported["native_metadata"]["source_graph_sha256"], file_sha256(path))

        relations = {item["relation_id"]: item for item in self.dgra["relations"]}
        for case in self.dgra_local["cases"]:
            edge = case["edge"]
            relation_id = f"test:{case['sample_index']}:edge:{edge['source']}->{edge['target']}"
            exported = relations[relation_id]
            self.assertEqual(
                (exported["source"], exported["target"], exported["source_name"], exported["target_name"]),
                (edge["source"], edge["target"], edge["source_name"], edge["target_name"]),
            )
            occurrence = next(
                item for item in exported["native_occurrences"] if item["context_id"] == f"window:{case['window']}"
            )
            self.assertEqual(occurrence["weight"], edge["normalized_weight"])
            self.assertEqual(occurrence["rank"], edge.get("retained_edge_rank"))

    def test_dgraformer_local_and_broader_evidence_round_trip_exactly(self):
        evidence = {item["evidence_id"]: item for item in self.dgra["evidence_records"]}
        samples = {sample["sample_index"]: sample for sample in self.dgra["samples"]}

        for case in self.dgra_local["cases"]:
            exported = evidence[case["conclusion_id"]]
            edge = case["edge"]
            metrics, statistics = split_metrics(case["structural_metrics"])
            controls_path = run_relative_path(self.dgra_local_run, case["controls"]["records"])
            control_records = read_json(controls_path)
            self.assertEqual(
                exported["selection"],
                {
                    "model": "DGraFormer",
                    "dataset": "ETTh1",
                    "sample_id": f"test:{case['sample_index']}",
                    "sample_index": case["sample_index"],
                    "context_type": "window",
                    "context_id": f"window:{case['window']}",
                    "context_index": case["window"],
                    "source": edge["source"],
                    "target": edge["target"],
                    "source_name": edge["source_name"],
                    "target_name": edge["target_name"],
                    "scope": "local",
                },
            )
            self.assertEqual(exported["status"], "available" if case["window_active"] else "not_exposed")
            value = exported["value"]
            self.assertEqual(value["intervention_output"]["value"]["values"], case["intervention_prediction"])
            self.assertEqual(samples[case["sample_index"]]["ground_truth"]["values"], case["ground_truth"])
            self.assertEqual(value["metrics"], metrics)
            self.assertEqual(value["statistics"], statistics)
            self.assertEqual(
                value["metric_status"],
                {
                    key: {"status": item.get("status", "undefined"), "reason": item.get("reason")}
                    for key, item in case.get("structural_metric_status", {}).items()
                },
            )
            self.assertEqual(value["controls"]["records"], control_records)
            self.assertEqual(
                value["controls"]["values"]["value"],
                [stored_control_value(item) for item in control_records],
            )
            self.assertEqual(value["controls"]["records_sha256"], file_sha256(controls_path))
            self.assertEqual(value["controls"]["summary"], control_summary(statistics))
            self.assertEqual(
                value["graph_effect"],
                {
                    "window_active": case["window_active"],
                    "active_windows": case["active_windows"],
                    "window_exposure_count": case["window_exposure_count"],
                    "topk_score": edge["topk_score"],
                    "normalized_weight": edge["normalized_weight"],
                    "retained_edge_rank": edge.get("retained_edge_rank"),
                },
            )
            self.assertEqual(
                value["diagnostic_localization"],
                {
                    "summary": case["diagnostic_localization"],
                    "step_error_delta": case["step_error_delta"],
                    "step_impact": case["step_impact"],
                    "variable_impact": case["variable_impact"],
                },
            )
            self.assertEqual(value["provenance"]["source_run_id"], self.dgra_local_run.name)
            self.assertEqual(value["provenance"]["raw_operands"], case.get("raw_operands", {}))
            self.assertEqual(value["model_specific"]["channel_mask_metrics"], case.get("channel_mask_metrics", {}))

        edge_lookup = {
            (edge["source"], edge["target"]): edge for edge in self.dgra_local["edges"]
        }
        for case in self.dgra_broader["cases"]:
            exported = evidence[case["id"]]
            source_index, target_index = case["edge"]
            edge = edge_lookup[(source_index, target_index)]
            metrics, statistics = split_metrics(case["metrics"])
            controls_path = run_relative_path(self.dgra_broader_run, case["controls_file"])
            control_records = read_json(controls_path)
            self.assertEqual(exported["selection"]["sample_index"], case["sample"])
            self.assertEqual(exported["selection"]["context_type"], "window_set")
            self.assertEqual(exported["selection"]["context_index"], "all_applicable")
            self.assertEqual(
                (exported["selection"]["source"], exported["selection"]["target"]),
                (source_index, target_index),
            )
            self.assertEqual(exported["selection"]["source_name"], edge["source_name"])
            self.assertEqual(exported["selection"]["target_name"], edge["target_name"])
            value = exported["value"]
            self.assertEqual(value["intervention_output"]["value"]["values"], case["intervention_prediction"])
            self.assertEqual(value["metrics"], metrics)
            self.assertEqual(value["statistics"], statistics)
            self.assertEqual(value["controls"]["records"], control_records)
            self.assertEqual(
                value["controls"]["values"]["value"],
                [stored_control_value(item) for item in control_records],
            )
            self.assertEqual(value["controls"]["records_sha256"], file_sha256(controls_path))
            self.assertEqual(value["controls"]["summary"], control_summary(statistics))
            self.assertEqual(
                value["graph_effect"],
                {
                    "retained_contexts": case["retained_windows"],
                    "exposed_contexts": case["exposed_windows"],
                    "affected_contexts": case["affected_exposed_windows"],
                    "mean_weight": case["mean_weight"],
                },
            )
            self.assertEqual(value["diagnostic_localization"], {"variable_ranking": case["variable_ranking"]})
            self.assertEqual(value["provenance"]["source_run_id"], self.dgra_broader_run.name)
            self.assertEqual(value["provenance"]["prediction_file"], case["prediction_file"].replace("\\", "/"))
            self.assertEqual(value["provenance"]["controls_file"], case["controls_file"].replace("\\", "/"))

        self.assertEqual(self.dgra["cross_run_evidence"]["status"], self.dgra_local["cross_run"]["status"])
        self.assertEqual(self.dgra["cross_run_evidence"]["value"], self.dgra_local["cross_run"]["metrics"])
        self.assertEqual(self.dgra["cross_run_evidence"]["reason"], self.dgra_local["cross_run"]["reason"])
        self.assertEqual(
            self.dgra["evidence_summary"]["not_exposed_case_count"],
            sum(not case["window_active"] for case in self.dgra_local["cases"]),
        )

    def test_msgnet_samples_scales_and_relations_round_trip_exactly(self):
        samples = {sample["sample_index"]: sample for sample in self.msgnet["samples"]}
        relations = {item["relation_id"]: item for item in self.msgnet["relations"]}
        for display_id, source_sample in enumerate(self.msgnet_catalog["samples"]):
            sample_index = source_sample["sample_index"]
            exported = samples[sample_index]
            self.assertEqual(exported["display_id"], display_id)
            self.assertEqual(exported["history"]["value"]["values"], transpose_variable_step(source_sample["history"]))
            self.assertEqual(exported["ground_truth"]["values"], transpose_variable_step(source_sample["ground_truth"]))
            self.assertEqual(
                exported["baseline_prediction"]["values"],
                transpose_variable_step(source_sample["prediction"]),
            )
            self.assertEqual(
                exported["sample_metrics"],
                {key: value for key, value in source_sample["metrics"].items() if key != "sample_index"},
            )
            contexts = {item["context_id"]: item for item in exported["contexts"]}
            for source_context in source_sample["contexts"]:
                context_id = f"layer:{source_context['layer']}:scale:{source_context['scale_index']}"
                context = contexts[context_id]
                self.assertEqual(context["type"], "scale")
                self.assertEqual(context["graphs"]["adaptive"]["values"], source_context["adaptive"])
                self.assertEqual(context["graphs"]["effective"]["values"], source_context["effective"])
                self.assertEqual(
                    context["native_metadata"],
                    {
                        "period": source_context["period"],
                        "fft_strength": source_context["fft_strength"],
                        "scale_contribution": source_context["scale_contribution"],
                    },
                )

            local_by_relation: dict[tuple[int, int], list[dict[str, Any]]] = {}
            for item in source_sample["edge_impacts"]:
                local_by_relation.setdefault((item["source"], item["target"]), []).append(item)
            for key, local_items in local_by_relation.items():
                relation_id = f"test:{sample_index}:edge:{key[0]}->{key[1]}"
                relation = relations[relation_id]
                self.assertEqual((relation["source"], relation["target"]), key)
                self.assertEqual(relation["source_name"], local_items[0]["source_name"])
                self.assertEqual(relation["target_name"], local_items[0]["target_name"])
                occurrences = {item["context_id"]: item for item in relation["native_occurrences"]}
                for item in local_items:
                    occurrence = occurrences[f"layer:{item['layer']}:scale:{item['scale_index']}"]
                    self.assertEqual(occurrence["weight"], item["adaptive_weight"])
                    self.assertEqual(occurrence["rank"], item["graph"]["weight_rank"])

    def test_msgnet_local_and_broader_evidence_round_trip_exactly(self):
        evidence = {item["evidence_id"]: item for item in self.msgnet["evidence_records"]}
        for source_sample in self.msgnet_catalog["samples"]:
            sample_index = source_sample["sample_index"]
            global_by_edge = {
                (item["source"], item["target"]): item for item in source_sample["global_edge_impacts"]
            }
            for item in source_sample["edge_impacts"]:
                exported = evidence[item["conclusion_id"]]
                self.assertEqual(exported["selection"]["sample_index"], sample_index)
                self.assertEqual(exported["selection"]["context_type"], "scale")
                self.assertEqual(exported["selection"]["context_index"], item["scale_index"])
                self.assertEqual(exported["selection"]["layer"], item["layer"])
                self.assertEqual(
                    (exported["selection"]["source"], exported["selection"]["target"]),
                    (item["source"], item["target"]),
                )
                value = exported["value"]
                self.assertEqual(
                    value["metrics"],
                    {
                        key: item[key]
                        for key in (
                            "prediction_delta_abs",
                            "prediction_delta_max",
                            "error_delta_mae",
                            "error_delta_mse",
                        )
                    },
                )
                self.assertEqual(value["statistics"], item["statistics"])
                self.assertEqual(value["intervention_output"]["status"], "missing")
                self.assertIsNone(value["intervention_output"]["value"])
                self.assertEqual(value["controls"]["values"]["value"], item["controls"]["prediction_delta_abs"])
                self.assertEqual(value["controls"]["summary"], control_summary(item["statistics"]))
                self.assertEqual(
                    value["graph_effect"],
                    {
                        "adaptive_weight": item["adaptive_weight"],
                        "weight_rank": item["graph"]["weight_rank"],
                        "weight_impact_spearman_rho": item["graph"]["weight_impact_spearman_rho"],
                        "weight_impact_spearman_p": item["graph"]["weight_impact_spearman_p"],
                        "period": item["period"],
                        "scale_contribution": item["scale_contribution"],
                    },
                )
                self.assertEqual(value["provenance"]["source_run_id"], self.msgnet_catalog["evidence_run_id"])

            for key, item in global_by_edge.items():
                evidence_id = f"msgnet_global_s{sample_index}_edge_{key[0]}_{key[1]}"
                exported = evidence[evidence_id]
                value = exported["value"]
                self.assertEqual(exported["selection"]["context_type"], "scale_set")
                self.assertEqual(exported["selection"]["context_index"], "all_applicable")
                self.assertEqual(
                    value["intervention_output"]["value"]["values"],
                    transpose_variable_step(item["intervention_prediction"]),
                )
                self.assertEqual(
                    value["metrics"],
                    {
                        metric: item[metric]
                        for metric in (
                            "prediction_delta_abs",
                            "prediction_delta_max",
                            "error_delta_mae",
                            "error_delta_mse",
                        )
                    },
                )
                self.assertEqual(value["statistics"], item["statistics"])
                expected_controls = [
                    global_by_edge[other]["prediction_delta_abs"]
                    for other in sorted(global_by_edge)
                    if other != key
                ]
                self.assertEqual(len(expected_controls), 41)
                self.assertEqual(value["controls"]["values"]["value"], expected_controls)
                self.assertEqual(value["controls"]["summary"], control_summary(item["statistics"]))
                self.assertEqual(
                    value["graph_effect"],
                    {"affected_contexts": item["affected_scales"], "scale_weights": item["scale_weights"]},
                )
                self.assertEqual(
                    value["provenance"]["source_run_id"],
                    self.msgnet_catalog["global_intervention_run_id"],
                )

        self.assertEqual(self.msgnet["evidence_summary"]["local_bh_supported_count"], 0)
        self.assertEqual(self.msgnet["evidence_summary"]["broader_context_bh_supported_count"], 0)
        self.assertEqual(self.msgnet["cross_run_evidence"]["status"], "not_evaluated")
        self.assertIsNone(self.msgnet["cross_run_evidence"]["value"])

    def test_provenance_hashes_and_source_run_statuses_round_trip_exactly(self):
        expected_dgra_runs = {
            "intervention": self.dgra_local["source_runs"]["intervention"],
            "local_evidence": self.dgra_local["source_runs"]["evidence"],
            "broader_context_evidence": self.dgra_broader["run_id"],
        }
        expected_msgnet_runs = {
            "baseline": self.msgnet_catalog["baseline_run_id"],
            "graph": self.msgnet_catalog["graph_run_id"],
            "local_evidence": self.msgnet_catalog["evidence_run_id"],
            "broader_context_evidence": self.msgnet_catalog["global_intervention_run_id"],
        }
        for session, expected in (
            (self.dgra, expected_dgra_runs),
            (self.msgnet, expected_msgnet_runs),
        ):
            source_runs = {item["role"]: item for item in session["provenance"]["source_runs"]}
            self.assertEqual({role: item["run_id"] for role, item in source_runs.items()}, expected)
            for role, run_id in expected.items():
                manifest = ROOT / "artifacts/runs" / run_id / "manifest.json"
                if manifest.is_file():
                    self.assertEqual(source_runs[role]["artifact_status"], "available")
                    self.assertEqual(source_runs[role]["manifest_sha256"], file_sha256(manifest))
                else:
                    self.assertEqual(source_runs[role]["artifact_status"], "referenced_not_present")
                    self.assertIsNone(source_runs[role]["manifest_sha256"])
            for artifact in session["provenance"]["source_artifacts"]:
                configured_path = ROOT / "configs" / artifact["path"]
                self.assertEqual(artifact["status"], "available")
                self.assertEqual(artifact["sha256"], file_sha256(configured_path.resolve()))
            self.assertEqual(session["provenance"]["validation"]["status"], "passed")
            self.assertEqual(session["provenance"]["validation"]["kind"], "artifact_roundtrip_validation")
            self.assertEqual(
                session["session"]["generator"]["run_id"],
                session["provenance"]["session_generation_run_id"],
            )

    def test_self_describing_external_adapter_does_not_require_a_frontend_model_enum(self):
        external = copy.deepcopy(self.msgnet)
        external["model"].update({
            "name": "ExternalGraphNet",
            "adapter": "ExternalGraphNetAdapter",
            "adapter_id": "external_graph_net",
            "native_context_type": "learned_context",
        })
        for sample in external["samples"]:
            for context in sample["contexts"]:
                context["type"] = "learned_context"
        for record in external["evidence_records"]:
            selection = record["selection"]
            selection["model"] = "ExternalGraphNet"
            selection["context_type"] = (
                "learned_context" if selection["scope"] == "local" else "learned_context_set"
            )
        self.assertEqual(validate_audit_session(external), [])


if __name__ == "__main__":
    unittest.main()

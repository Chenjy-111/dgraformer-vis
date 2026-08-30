from __future__ import annotations

from typing import Any, Mapping

from .controls import build_case_evidence
from .dependence import audit_dependence
from .session import build_audit_session_v2


def upgrade_quick_session_v1(session_v1: Mapping[str, Any], *, evidence_id: str | None = None) -> dict[str, Any]:
    """Preserve a v1 graph/case result while removing its legacy inferential interpretation."""
    records = [record for record in session_v1.get("evidence_records", []) if record.get("status") == "available"]
    if evidence_id is not None:
        records = [record for record in records if record.get("evidence_id") == evidence_id]
    if not records:
        raise ValueError("Quick Inspection requires one available v1 case record")
    record = records[0]
    selection = record["selection"]
    value = record["value"]
    sample = int(selection["sample_index"])
    adapter = str(session_v1["model"]["adapter_id"])
    source, target = int(selection["source"]), int(selection["target"])
    scope, member = _candidate_identity(adapter, selection, source, target)
    candidate_id = member["candidate_id"]
    control_records = value.get("controls", {}).get("records", [])
    unique: dict[str, float] = {}
    for control in control_records:
        identity = f"{int(control['source'])}->{int(control['target'])}"
        response_value = control.get("prediction_delta_abs", control.get("metrics", {}).get("prediction_delta_abs"))
        if response_value is None:
            raise ValueError(f"Control {identity} is missing prediction_delta_abs")
        response = float(response_value)
        if identity in unique and unique[identity] != response:
            raise ValueError(f"Control {identity} has conflicting repeated responses")
        unique[identity] = response
    if not unique:
        values = value.get("controls", {}).get("values", {}).get("value") or []
        if adapter == "msgnet" and len(values) == 41:
            node_count = int(session_v1["samples"][0]["contexts"][0]["node_count"])
            identities = [f"{left}->{right}" for left in range(node_count) for right in range(node_count) if left != right and (left, right) != (source, target)]
            unique = {identity: float(response) for identity, response in zip(identities, values)}
    controls = [{"identity": identity, "response": response} for identity, response in unique.items()]
    case = build_case_evidence(
        case_evidence_id=f"quick:{candidate_id}:test:{sample}", candidate_id=candidate_id, sample_id=sample,
        context={"type": selection["context_type"], "context_id": selection["context_id"], "context_index": selection.get("context_index")},
        scope=scope, active=True, focal_response=float(value["metrics"]["prediction_delta_abs"]), controls=controls,
        response_metrics=value["metrics"], graph_effect=value.get("graph_effect", {}),
        baseline_reference={"sample_id": selection["sample_id"], "field": "baseline_prediction"},
        intervention_output_reference=value.get("intervention_output"),
        provenance={"source_schema_version": session_v1.get("schema_version"), "source_evidence_id": record["evidence_id"], "legacy_statistics_excluded": True},
    )
    family_id = f"quick.{adapter}.{scope}"
    family = {"family_id": family_id, "scope": scope, "selection_rule": "one user-selected graph edge for descriptive inspection", "context_identity_rule": member["native_context_type"], "members": [member], "family_size": 1, "selection_frozen": True}
    config = {
        "schema_version": "dgrainsight.audit_config.v2", "config_version": 2, "audit_mode": "quick_inspection",
        "adapter": adapter, "dataset": {"name": session_v1["dataset"]["name"]}, "checkpoint": {"sha256": session_v1["checkpoint"]["sha256"]},
        "sample_protocol": {"protocol_id": f"quick.test.{sample}", "selection_rule": "explicit user selection", "split": selection.get("split", "test"), "sample_ids": [sample], "selection_frozen": True, "active_inactive_policy": "exclude_inactive_without_zero_imputation"},
        "candidate_families": [family], "control_protocol": {"protocol": "all_unique_eligible", "with_replacement": False}, "response_metric": "prediction_delta_abs",
        "dependence_protocol": {"expected_classification": "unknown_dependence", "same_continuous_series": None},
        "inference_protocol": {"selection_frozen": True, "alternative": "mean_D > 0", "inference_unit": "candidate_relation_across_predeclared_units", "null_definition": None, "by_family": {family_id: {"primary_test": "unavailable", "reason": "Single-case inspection does not constitute cross-sample statistical evidence."}}},
        "multiplicity_protocol": {"primary_method": "BH", "alpha": 0.05, "families_frozen": True},
        "sensitivity_protocol": {"primary_results_unchanged": True, "by_family": {family_id: []}},
    }
    dependence = {family_id: audit_dependence(config["sample_protocol"]["protocol_id"], [sample], None, same_continuous_series=None)}
    return build_audit_session_v2(config=config, graph_core_session_v1=session_v1, case_evidence=[case], dependence_by_family=dependence, generator={"name": "dgraudit.quick.v2"}, additional_provenance={"legacy_v1_inference": "excluded"})


def _candidate_identity(adapter: str, selection: Mapping[str, Any], source: int, target: int) -> tuple[str, dict[str, Any]]:
    original_scope = str(selection.get("scope", "local"))
    if adapter == "dgraformer":
        if original_scope == "local":
            window = int(selection["context_index"])
            return "single_window", {"candidate_id": f"quick:dgra:window:{window}:{source}->{target}", "source": source, "target": target, "source_name": selection["source_name"], "target_name": selection["target_name"], "scope": "single_window", "native_context_type": "window", "window_index": window, "retained_contexts": [window]}
        return "all_retained_windows", {"candidate_id": f"quick:dgra:all:{source}->{target}", "source": source, "target": target, "source_name": selection["source_name"], "target_name": selection["target_name"], "scope": "all_retained_windows", "native_context_type": "window", "retained_contexts": []}
    if adapter == "msgnet":
        if original_scope == "local":
            scale = int(selection["context_index"])
            return "single_scale", {"candidate_id": f"quick:msgnet:scale:{scale}:{source}->{target}", "source": source, "target": target, "source_name": selection["source_name"], "target_name": selection["target_name"], "scope": "single_scale", "native_context_type": "scale", "scale_index": scale, "retained_contexts": [scale]}
        return "all_scales", {"candidate_id": f"quick:msgnet:all:{source}->{target}", "source": source, "target": target, "source_name": selection["source_name"], "target_name": selection["target_name"], "scope": "all_scales", "native_context_type": "scale", "retained_contexts": [0, 1, 2]}
    return "global_graph", {"candidate_id": f"quick:mtgnn:global:{source}->{target}", "source": source, "target": target, "source_name": selection["source_name"], "target_name": selection["target_name"], "scope": "global_graph", "native_context_type": "global_graph", "retained_contexts": [0]}

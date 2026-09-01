from __future__ import annotations

from typing import Any, Mapping, Sequence

from .controls import build_case_evidence
from .dependence import audit_dependence
from .session import build_audit_session_v2


def build_quick_session_v2(
    graph_core: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a native Session v2 Quick Inspection without case-level inference."""
    if not records:
        raise ValueError("Quick Inspection requires at least one available case record")

    adapter = str(graph_core["model"]["adapter_id"])
    dataset = str(graph_core["dataset"]["name"])
    checkpoint = str(graph_core["checkpoint"]["sha256"])
    cases: list[dict[str, Any]] = []
    families: list[dict[str, Any]] = []
    family_protocols: dict[str, dict[str, Any]] = {}
    sensitivity: dict[str, list[str]] = {}
    sample_ids: list[int] = []

    for record in records:
        selection = record["selection"]
        sample = int(selection["sample_index"])
        if sample not in sample_ids:
            sample_ids.append(sample)
        source, target = int(selection["source"]), int(selection["target"])
        scope, member = candidate_identity(adapter, selection, source, target)
        candidate_id = member["candidate_id"]
        family_id = f"quick.{adapter}.{scope}.{source}.{target}.{len(families)}"
        cases.append(build_case_evidence(
            case_evidence_id=f"quick:{candidate_id}:test:{sample}",
            candidate_id=candidate_id,
            sample_id=sample,
            context={
                "type": selection["context_type"],
                "context_id": selection["context_id"],
                "context_index": selection.get("context_index"),
            },
            scope=scope,
            active=True,
            focal_response=float(record["metrics"]["prediction_delta_abs"]),
            controls=list(record.get("controls", [])),
            response_metrics=record["metrics"],
            graph_effect=record.get("graph_effect", {}),
            baseline_reference={"sample_id": selection["sample_id"], "field": "baseline_prediction"},
            intervention_output_reference=record.get("intervention_output"),
            provenance=dict(record.get("provenance", {})),
        ))
        families.append({
            "family_id": family_id,
            "scope": scope,
            "selection_rule": "one user-selected graph edge for descriptive inspection",
            "context_identity_rule": member["native_context_type"],
            "members": [member],
            "family_size": 1,
            "selection_frozen": True,
        })
        family_protocols[family_id] = {
            "primary_test": "unavailable",
            "reason": "Single-case inspection does not constitute cross-sample statistical evidence.",
        }
        sensitivity[family_id] = []

    config = {
        "schema_version": "dgrainsight.audit_config.v2",
        "config_version": 2,
        "audit_mode": "quick_inspection",
        "adapter": adapter,
        "dataset": {"name": dataset},
        "checkpoint": {"sha256": checkpoint},
        "sample_protocol": {
            "protocol_id": "quick." + ".".join(str(value) for value in sample_ids),
            "selection_rule": "explicit user selection",
            "split": "test",
            "sample_ids": sample_ids,
            "selection_frozen": True,
            "active_inactive_policy": "exclude_inactive_without_zero_imputation",
        },
        "candidate_families": families,
        "control_protocol": {"protocol": "all_unique_eligible", "with_replacement": False},
        "response_metric": "prediction_delta_abs",
        "dependence_protocol": {"expected_classification": "unknown_dependence", "same_continuous_series": None},
        "inference_protocol": {
            "selection_frozen": True,
            "alternative": "mean_D > 0",
            "inference_unit": "candidate_relation_across_predeclared_units",
            "null_definition": None,
            "by_family": family_protocols,
        },
        "multiplicity_protocol": {"primary_method": "BH", "alpha": 0.05, "families_frozen": True},
        "sensitivity_protocol": {"primary_results_unchanged": True, "by_family": sensitivity},
    }
    dependence = {
        family["family_id"]: audit_dependence(
            config["sample_protocol"]["protocol_id"], sample_ids, None, same_continuous_series=None
        )
        for family in families
    }
    return build_audit_session_v2(
        config=config,
        graph_core=graph_core,
        case_evidence=cases,
        dependence_by_family=dependence,
        generator={"name": "dgraudit.quick.v2", "version": "pipeline-v2"},
        additional_provenance={"quick_inspection": True},
    )


def candidate_identity(
    adapter: str,
    selection: Mapping[str, Any],
    source: int,
    target: int,
) -> tuple[str, dict[str, Any]]:
    common = {
        "source": source,
        "target": target,
        "source_name": selection["source_name"],
        "target_name": selection["target_name"],
    }
    required = (
        "candidate_scope", "candidate_id", "candidate_native_context_type", "candidate_retained_contexts"
    )
    missing = [field for field in required if field not in selection]
    if missing:
        raise ValueError(f"Adapter selection is missing candidate identity fields: {missing}")
    scope = str(selection["candidate_scope"])
    identity = selection.get("candidate_identity", {})
    if not isinstance(identity, Mapping):
        raise ValueError("candidate_identity must be a mapping")
    return scope, {
        **common,
        "candidate_id": str(selection["candidate_id"]),
        "scope": scope,
        "native_context_type": str(selection["candidate_native_context_type"]),
        "retained_contexts": list(selection["candidate_retained_contexts"]),
        **dict(identity),
    }

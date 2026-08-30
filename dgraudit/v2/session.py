from __future__ import annotations

import copy
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .config import statistical_protocol_checks
from .pipeline import aggregate_candidate_evidence, protocol_provenance


SESSION_SCHEMA_VERSION_V2 = "2.0"
FORMAL_STATUSES = {
    "AUDIT COMPLETE", "PARTIAL AUDIT", "INPUT / ADAPTER ERROR", "MODEL VALIDATION FAILED",
    "STATISTICAL PROTOCOL FAILED", "FORMAL INFERENCE UNAVAILABLE",
}
FORBIDDEN_CASE_FIELDS = {"case_raw_p", "case_bh_q", "case_significant", "empirical_p", "bh_adjusted_p"}


def build_audit_session_v2(
    *,
    config: Mapping[str, Any],
    graph_core_session_v1: Mapping[str, Any],
    case_evidence: Sequence[Mapping[str, Any]],
    dependence_by_family: Mapping[str, Mapping[str, Any]],
    generator: Mapping[str, Any],
    additional_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    checks = statistical_protocol_checks(config, dependence_by_family)
    if any(check["status"] != "pass" for check in checks):
        raise ValueError("V10/V11 validation failed: " + json.dumps(checks, ensure_ascii=False))
    candidate_relations, families, cross = aggregate_candidate_evidence(config, case_evidence, dependence_by_family)
    dependence_records = []
    for family_id, audit in dependence_by_family.items():
        current = dict(audit)
        protocol = config["inference_protocol"]["by_family"][family_id]
        current["inference_engine_selected"] = protocol["primary_test"] if current["classification"] != "unknown_dependence" else "unavailable"
        dependence_records.append(current)
    complete = all(item["primary_inference"]["status"] == "complete" for item in cross)
    formal_available = any(item["primary_inference"]["status"] == "complete" for item in cross)
    status = "AUDIT COMPLETE" if complete else "PARTIAL AUDIT" if formal_available else "FORMAL INFERENCE UNAVAILABLE"
    if config.get("audit_mode") == "quick_inspection":
        status = "PARTIAL AUDIT"
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    v1_validation = copy.deepcopy(graph_core_session_v1.get("model_specific", {}).get("artifact_validation_report"))
    session = {
        "schema_version": SESSION_SCHEMA_VERSION_V2,
        "session": {
            **copy.deepcopy(graph_core_session_v1["session"]),
            "created_at": now,
            "generator": dict(generator),
            "source_mode": "offline_audit_v2",
            "status": status,
        },
        "model": copy.deepcopy(graph_core_session_v1["model"]),
        "dataset": copy.deepcopy(graph_core_session_v1["dataset"]),
        "checkpoint": copy.deepcopy(graph_core_session_v1["checkpoint"]),
        "audit_plan": {
            "audit_mode": config["audit_mode"],
            "sample_protocol": copy.deepcopy(config["sample_protocol"]),
            "candidate_family_ids": [family["family_id"] for family in config["candidate_families"]],
            "control_protocol": copy.deepcopy(config["control_protocol"]),
            "response_metric": config["response_metric"],
            "dependence_protocol": copy.deepcopy(config["dependence_protocol"]),
            "inference_protocol": copy.deepcopy(config["inference_protocol"]),
            "multiplicity_protocol": copy.deepcopy(config["multiplicity_protocol"]),
            "sensitivity_protocol": copy.deepcopy(config["sensitivity_protocol"]),
        },
        "samples": copy.deepcopy(graph_core_session_v1["samples"]),
        "relations": [
            {key: copy.deepcopy(value) for key, value in relation.items() if key != "evidence_ids"}
            for relation in graph_core_session_v1["relations"]
        ],
        "case_evidence": copy.deepcopy(list(case_evidence)),
        "candidate_relations": candidate_relations,
        "hypothesis_families": families,
        "cross_sample_evidence": cross,
        "dependence_audit": dependence_records,
        "validation": {"model_validation_V01_V09": v1_validation, "statistical_validation": checks},
        "provenance": {
            **copy.deepcopy(graph_core_session_v1.get("provenance", {})),
            **protocol_provenance(config, families, dependence_records),
            **dict(additional_provenance or {}),
        },
        "limitations": [
            "Results describe functional evidence within the audited model and frozen protocol.",
            "Case evidence is descriptive and carries no formal case-level p-value or BH result.",
        ],
    }
    errors = validate_audit_session_v2(session)
    if errors:
        raise ValueError("Session v2 semantic validation failed:\n- " + "\n- ".join(errors))
    return session


def validate_audit_session_v2(session: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(session, Mapping):
        return ["Session v2 must be an object"]
    required = {
        "schema_version", "session", "model", "dataset", "checkpoint", "audit_plan", "samples",
        "relations", "case_evidence", "candidate_relations", "hypothesis_families",
        "cross_sample_evidence", "dependence_audit", "validation", "provenance", "limitations",
    }
    missing = sorted(required - set(session))
    if missing:
        return [f"Missing top-level fields: {missing}"]
    if session.get("schema_version") != SESSION_SCHEMA_VERSION_V2:
        errors.append("schema_version must be 2.0")
    if session.get("session", {}).get("status") not in FORMAL_STATUSES:
        errors.append("session.status is invalid")
    sample_ids = [sample.get("sample_index") for sample in session.get("samples", [])]
    if len(sample_ids) != len(set(sample_ids)):
        errors.append("sample IDs must be unique")
    for index, sample in enumerate(session.get("samples", [])):
        for field in ("ground_truth", "baseline_prediction"):
            _validate_tensor(sample.get(field), f"samples[{index}].{field}", errors)
        history = sample.get("history")
        if isinstance(history, Mapping) and history.get("status") == "available":
            _validate_tensor(history.get("value"), f"samples[{index}].history.value", errors)
        for context_index, context in enumerate(sample.get("contexts", [])):
            for name, tensor in context.get("graphs", {}).items():
                _validate_tensor(tensor, f"samples[{index}].contexts[{context_index}].graphs.{name}", errors)
                shape = tensor.get("shape", []) if isinstance(tensor, Mapping) else []
                if len(shape) != 2 or shape[0] != shape[1] or shape[0] != context.get("node_count"):
                    errors.append(f"samples[{index}].contexts[{context_index}].graphs.{name} must be node_count square")

    candidate_ids = [item.get("candidate_id") for item in session.get("candidate_relations", [])]
    if len(candidate_ids) != len(set(candidate_ids)):
        errors.append("candidate IDs must be unique")
    candidates = set(candidate_ids)
    case_ids: set[str] = set()
    cases_by_candidate: dict[str, list[Mapping[str, Any]]] = {}
    for index, case in enumerate(session.get("case_evidence", [])):
        path = f"case_evidence[{index}]"
        forbidden = FORBIDDEN_CASE_FIELDS & set(case)
        if forbidden:
            errors.append(f"{path} contains forbidden case-level inference fields {sorted(forbidden)}")
        case_id = case.get("case_evidence_id")
        if not isinstance(case_id, str) or case_id in case_ids:
            errors.append(f"{path}.case_evidence_id must be unique")
        else:
            case_ids.add(case_id)
        candidate_id = case.get("candidate_id")
        if candidate_id not in candidates:
            errors.append(f"{path}.candidate_id is invalid")
        cases_by_candidate.setdefault(str(candidate_id), []).append(case)
        if case.get("sample_id") not in sample_ids:
            errors.append(f"{path}.sample_id is invalid")
        controls = case.get("controls", {})
        identities = controls.get("identities", [])
        if len(identities) != len(set(identities)):
            errors.append(f"{path} control identities contain duplicates")
        if controls.get("unique_count") != len(identities):
            errors.append(f"{path} control count does not match identities")
        responses = controls.get("responses")
        if case.get("status") == "active" and (not isinstance(responses, list) or len(responses) != len(identities)):
            errors.append(f"{path} active control responses do not match identities")
        if isinstance(responses, list) and responses:
            expected_mean = sum(float(value) for value in responses) / len(responses)
            if not math.isclose(float(controls.get("mean")), expected_mean, rel_tol=1e-9, abs_tol=1e-12):
                errors.append(f"{path} control mean does not match stored unique responses")
        if case.get("status") == "active":
            focal, mean, d_value = case.get("focal_response"), controls.get("mean"), case.get("D")
            if not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in (focal, mean, d_value)):
                errors.append(f"{path} active focal/control/D must be finite")
            elif not math.isclose(float(d_value), float(focal) - float(mean), rel_tol=1e-9, abs_tol=1e-12):
                errors.append(f"{path}.D does not equal focal_response - control mean")
        elif case.get("status") == "inactive":
            if case.get("D") is not None or case.get("focal_response") is not None:
                errors.append(f"{path} inactive case cannot impute D or focal response")
        formal = case.get("formal_inference", {})
        if formal.get("status") != "not_evaluated" or formal.get("raw_p") is not None or formal.get("BH_q") is not None:
            errors.append(f"{path} must not contain formal case-level inference")

    family_ids: set[str] = set()
    expected_membership: dict[str, int] = {}
    for index, family in enumerate(session.get("hypothesis_families", [])):
        path = f"hypothesis_families[{index}]"
        family_id = family.get("family_id")
        if family_id in family_ids:
            errors.append(f"{path}.family_id is duplicated")
        family_ids.add(family_id)
        members = family.get("members", [])
        if family.get("size") != len(members) or len(members) != len(set(members)):
            errors.append(f"{path} family size/membership mismatch")
        for member in members:
            expected_membership[member] = expected_membership.get(member, 0) + 1
    if any(expected_membership.get(candidate) != 1 for candidate in candidates):
        errors.append("every candidate must belong to exactly one declared family")

    candidate_by_id = {item.get("candidate_id"): item for item in session.get("candidate_relations", [])}

    cross_ids: set[str] = set()
    for index, evidence in enumerate(session.get("cross_sample_evidence", [])):
        path = f"cross_sample_evidence[{index}]"
        if evidence.get("candidate_id") not in candidates:
            errors.append(f"{path}.candidate_id is invalid")
        evidence_id = evidence.get("cross_sample_evidence_id")
        if evidence_id in cross_ids:
            errors.append(f"{path}.cross_sample_evidence_id is duplicated")
        cross_ids.add(evidence_id)
        active, inactive, planned = evidence.get("active_samples", []), evidence.get("inactive_samples", []), evidence.get("planned_samples", [])
        if set(active) & set(inactive) or set(active) | set(inactive) != set(planned):
            errors.append(f"{path} active/inactive partition is invalid")
        values = evidence.get("D_values", [])
        if len(values) != len(planned):
            errors.append(f"{path}.D_values length mismatch")
        candidate = candidate_by_id.get(evidence.get("candidate_id"), {})
        expected_case_ids = {case.get("case_evidence_id") for case in cases_by_candidate.get(str(evidence.get("candidate_id")), [])}
        if set(evidence.get("D_case_references", [])) != expected_case_ids or set(candidate.get("case_evidence_ids", [])) != expected_case_ids:
            errors.append(f"{path} case references do not exactly trace the candidate's planned cases")
        for sample, value in zip(planned, values):
            if sample in inactive and value is not None:
                errors.append(f"{path} inactive unit cannot have D=0 or any D value")
        primary = evidence.get("primary_inference", {})
        forbidden_cross = FORBIDDEN_CASE_FIELDS & set(evidence)
        if forbidden_cross:
            errors.append(f"{path} contains forbidden sample-level inference fields {sorted(forbidden_cross)}")
        raw_p = primary.get("raw_p")
        if raw_p is not None and not 0 <= raw_p <= 1:
            errors.append(f"{path}.primary_inference.raw_p is invalid")
        multiplicity = evidence.get("multiplicity", {})
        q_value = multiplicity.get("adjusted_q")
        if q_value is not None:
            if not 0 <= q_value <= 1:
                errors.append(f"{path}.multiplicity.adjusted_q is invalid")
            if multiplicity.get("supported") != (q_value < multiplicity.get("alpha", 0.05)):
                errors.append(f"{path}.multiplicity.supported disagrees with q<alpha")
        _validate_missing(primary, f"{path}.primary_inference", errors)
        if primary.get("status") == "complete":
            settings = primary.get("settings", {})
            method = primary.get("method")
            if method == "one_sided_null_centered_moving_block_bootstrap_on_mean_D" and not all(key in settings for key in ("block_length", "repetitions", "seed", "plus_one_correction")):
                errors.append(f"{path} moving-block settings are incomplete")
            if method == "one_sided_exact_sign_flip_on_mean_D" and settings.get("enumeration") != "complete":
                errors.append(f"{path} exact sign-flip must use complete enumeration")

    model = session.get("model", {}).get("adapter_id")
    if model == "msgnet":
        for index, case in enumerate(session.get("case_evidence", [])):
            if case.get("status") == "active" and case.get("controls", {}).get("unique_count") != 41:
                errors.append(f"case_evidence[{index}] MSGNet formal case requires 41 unique controls")
        for candidate in session.get("candidate_relations", []):
            if candidate.get("scope") == "single_scale" and "scale_index" not in candidate:
                errors.append("MSGNet single-scale candidate identity requires scale_index")
            if "period" in candidate or "current_period" in candidate:
                errors.append("MSGNet candidate identity cannot use FFT period")
    if model == "dgraformer":
        for candidate in session.get("candidate_relations", []):
            if candidate.get("scope") == "all_retained_windows" and "window_index" in candidate:
                errors.append("DGraFormer all-retained candidate identity cannot contain one window index")
    if model == "mtgnn" and any(candidate.get("scope") != "global_graph" for candidate in session.get("candidate_relations", [])):
        errors.append("MTGNN cannot contain a broader-context family")
    dependence_by_protocol = {item.get("protocol_id"): item for item in session.get("dependence_audit", [])}
    for item in dependence_by_protocol.values():
        if item.get("classification") == "unknown_dependence" and item.get("inference_engine_selected") not in {"unavailable", "external"}:
            errors.append("unknown dependence cannot silently select a primary inference engine")
        if item.get("classification") == "unknown_dependence" and not item.get("reason"):
            errors.append("unknown dependence requires a reason")
    return errors


def _validate_tensor(tensor: Any, path: str, errors: list[str]) -> None:
    if not isinstance(tensor, Mapping):
        errors.append(f"{path} must be a tensor object")
        return
    shape, values = tensor.get("shape"), tensor.get("values")
    if not isinstance(shape, list) or not isinstance(values, list):
        errors.append(f"{path} requires shape and values")
        return
    flat = list(_flatten(values))
    expected = math.prod(shape) if shape else 1
    if len(flat) != expected:
        errors.append(f"{path} shape does not match values")
    if not all(math.isfinite(value) for value in flat):
        errors.append(f"{path} contains non-finite values")


def _flatten(value: Any):
    if isinstance(value, list):
        for item in value:
            yield from _flatten(item)
    else:
        yield float(value)


def _validate_missing(value: Mapping[str, Any], path: str, errors: list[str]) -> None:
    if value.get("status") == "unavailable" and not value.get("reason"):
        errors.append(f"{path} unavailable value requires a reason")


def write_audit_session_v2(path: str | Path, session: Mapping[str, Any]) -> Path:
    errors = validate_audit_session_v2(session)
    if errors:
        raise ValueError("Session v2 validation failed:\n- " + "\n- ".join(errors))
    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(session, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return destination

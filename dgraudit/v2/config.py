from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


CONFIG_SCHEMA_VERSION_V2 = "dgrainsight.audit_config.v2"
AUDIT_MODES = {"quick_inspection", "formal_evidence_audit"}
KNOWN_RESPONSE_METRICS = {"prediction_delta_abs"}
KNOWN_CONTROL_PROTOCOLS = {"all_unique_eligible"}
KNOWN_DEPENDENCE = {"overlapping_time_windows", "non_overlapping_time_units", "unknown_dependence"}
KNOWN_PRIMARY_TESTS = {"moving_block_bootstrap_mean_D", "exact_sign_flip_mean_D", "unavailable"}


class AuditConfigV2Error(ValueError):
    pass


def load_audit_config_v2(path: str | Path) -> tuple[Path, dict[str, Any]]:
    resolved = Path(path).expanduser().resolve()
    config = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise AuditConfigV2Error("Audit Config v2 root must be an object.")
    errors = validate_audit_config_v2(config)
    if errors:
        raise AuditConfigV2Error("Audit Config v2 is invalid:\n- " + "\n- ".join(errors))
    return resolved, config


def validate_audit_config_v2(config: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(config, Mapping):
        return ["config must be an object"]
    if config.get("schema_version") != CONFIG_SCHEMA_VERSION_V2 or config.get("config_version") != 2:
        errors.append("schema_version/config_version must declare Audit Config v2")
    mode = config.get("audit_mode")
    if mode not in AUDIT_MODES:
        errors.append(f"audit_mode must be one of {sorted(AUDIT_MODES)}")
    for field in ("adapter", "dataset", "checkpoint", "sample_protocol", "candidate_families",
                  "control_protocol", "response_metric", "dependence_protocol", "inference_protocol",
                  "multiplicity_protocol", "sensitivity_protocol"):
        if field not in config:
            errors.append(f"missing required field: {field}")
    if config.get("response_metric") not in KNOWN_RESPONSE_METRICS:
        errors.append("response_metric must be the predeclared prediction_delta_abs metric")

    sample = config.get("sample_protocol")
    if not isinstance(sample, Mapping):
        errors.append("sample_protocol must be an object")
    else:
        for field in ("protocol_id", "selection_rule", "split", "sample_ids", "selection_frozen", "active_inactive_policy"):
            if field not in sample:
                errors.append(f"sample_protocol.{field} is required")
        ids = sample.get("sample_ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(value, int) and value >= 0 for value in ids):
            errors.append("sample_protocol.sample_ids must be a non-empty integer array")
        elif len(ids) != len(set(ids)):
            errors.append("sample_protocol.sample_ids contains duplicates")
        if sample.get("selection_frozen") is not True:
            errors.append("sample_protocol.selection_frozen must be true")
        if sample.get("active_inactive_policy") != "exclude_inactive_without_zero_imputation":
            errors.append("sample_protocol.active_inactive_policy must exclude inactive units without zero imputation")
        if mode == "formal_evidence_audit" and isinstance(ids, list) and len(ids) < 2:
            declared = config.get("inference_protocol", {}).get("by_family", {})
            if not declared or any(
                not isinstance(protocol, Mapping) or protocol.get("primary_test") != "unavailable"
                for protocol in declared.values()
            ):
                errors.append(
                    "formal evidence audit requires multiple predeclared sample/test units unless every primary inference is explicitly unavailable"
                )

    families = config.get("candidate_families")
    if not isinstance(families, list) or (mode == "formal_evidence_audit" and not families):
        errors.append("candidate_families must be a non-empty array for formal audit")
    elif isinstance(families, list):
        family_ids: list[str] = []
        candidate_ids: list[str] = []
        for index, family in enumerate(families):
            path = f"candidate_families[{index}]"
            if not isinstance(family, Mapping):
                errors.append(f"{path} must be an object")
                continue
            for field in ("family_id", "scope", "selection_rule", "context_identity_rule", "members", "family_size", "selection_frozen"):
                if field not in family:
                    errors.append(f"{path}.{field} is required")
            family_ids.append(str(family.get("family_id")))
            members = family.get("members")
            if not isinstance(members, list) or not members:
                errors.append(f"{path}.members must be non-empty")
                continue
            if family.get("family_size") != len(members):
                errors.append(f"{path}.family_size does not match members")
            if family.get("selection_frozen") is not True:
                errors.append(f"{path}.selection_frozen must be true")
            for member in members:
                if not isinstance(member, Mapping) or not isinstance(member.get("candidate_id"), str):
                    errors.append(f"{path} has a member without candidate_id")
                else:
                    candidate_ids.append(member["candidate_id"])
        if len(family_ids) != len(set(family_ids)):
            errors.append("candidate family IDs must be unique")
        if len(candidate_ids) != len(set(candidate_ids)):
            errors.append("candidate IDs must be unique across formal families")

    controls = config.get("control_protocol")
    if not isinstance(controls, Mapping) or controls.get("protocol") not in KNOWN_CONTROL_PROTOCOLS:
        errors.append("control_protocol.protocol must be all_unique_eligible")
    elif controls.get("with_replacement") is not False:
        errors.append("control_protocol.with_replacement must be false")

    dependence = config.get("dependence_protocol")
    if not isinstance(dependence, Mapping):
        errors.append("dependence_protocol must be an object")
    elif dependence.get("expected_classification") not in KNOWN_DEPENDENCE:
        errors.append("dependence_protocol.expected_classification is invalid")

    inference = config.get("inference_protocol")
    if not isinstance(inference, Mapping):
        errors.append("inference_protocol must be an object")
    else:
        if inference.get("selection_frozen") is not True:
            errors.append("inference_protocol.selection_frozen must be true")
        if inference.get("alternative") != "mean_D > 0":
            errors.append("inference_protocol.alternative must be mean_D > 0")
        by_family = inference.get("by_family")
        if not isinstance(by_family, Mapping):
            errors.append("inference_protocol.by_family must be an object")
        else:
            for family_id, protocol in by_family.items():
                if not isinstance(protocol, Mapping) or protocol.get("primary_test") not in KNOWN_PRIMARY_TESTS:
                    errors.append(f"inference_protocol.by_family.{family_id}.primary_test is invalid")
                if isinstance(protocol, Mapping) and protocol.get("primary_test") == "moving_block_bootstrap_mean_D":
                    if not isinstance(protocol.get("block_length"), int) or protocol["block_length"] < 1:
                        errors.append(f"inference_protocol.by_family.{family_id}.block_length is required")

    multiplicity = config.get("multiplicity_protocol")
    if not isinstance(multiplicity, Mapping) or multiplicity.get("primary_method") != "BH":
        errors.append("multiplicity_protocol.primary_method must be BH")
    elif not isinstance(multiplicity.get("alpha"), (int, float)) or not 0 < float(multiplicity["alpha"]) < 1:
        errors.append("multiplicity_protocol.alpha must be in (0,1)")
    return errors


def statistical_protocol_checks(config: Mapping[str, Any], dependence_audits: Mapping[str, Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Return V10/V11 records without touching V01–V09."""
    config_errors = validate_audit_config_v2(config)
    v10_errors = [error for error in config_errors if not error.startswith("candidate") and "family" not in error]
    v11_errors = [error for error in config_errors if error.startswith("candidate") or "family" in error]
    if dependence_audits:
        by_family = config.get("inference_protocol", {}).get("by_family", {})
        for family_id, audit in dependence_audits.items():
            method = by_family.get(family_id, {}).get("primary_test")
            classification = audit.get("classification")
            if classification == "unknown_dependence" and method != "unavailable":
                v10_errors.append(f"{family_id}: unknown dependence requires unavailable primary inference")
            if classification == "overlapping_time_windows" and method == "exact_sign_flip_mean_D":
                v10_errors.append(f"{family_id}: exact sign-flip is incompatible with overlapping time windows")
            if classification == "non_overlapping_time_units" and method == "moving_block_bootstrap_mean_D":
                v10_errors.append(f"{family_id}: moving-block inference requires a declared overlapping protocol")
    return [
        {"id": "V10", "name": "statistical_protocol_validation", "status": "pass" if not v10_errors else "fail", "errors": v10_errors},
        {"id": "V11", "name": "hypothesis_family_validation", "status": "pass" if not v11_errors else "fail", "errors": v11_errors},
    ]

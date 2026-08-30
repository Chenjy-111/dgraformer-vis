from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from .families import apply_primary_multiplicity, benjamini_yekutieli, canonical_hash
from .inference import effect_summary, infer_candidate, sensitivity_results


def aggregate_candidate_evidence(
    config: Mapping[str, Any],
    case_evidence: Sequence[Mapping[str, Any]],
    dependence_by_family: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    planned = list(config["sample_protocol"]["sample_ids"])
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for case in case_evidence:
        grouped[str(case["candidate_id"])].append(case)
    candidate_relations: list[dict[str, Any]] = []
    cross: list[dict[str, Any]] = []
    family_records: list[dict[str, Any]] = []
    evidence_by_candidate: dict[str, dict[str, Any]] = {}
    family_by_candidate: dict[str, str] = {}

    for family in config["candidate_families"]:
        family_id = str(family["family_id"])
        dependence = dependence_by_family[family_id]
        protocol = config["inference_protocol"]["by_family"][family_id]
        sensitivity_names = config.get("sensitivity_protocol", {}).get("by_family", {}).get(family_id, [])
        for member in family["members"]:
            candidate_id = str(member["candidate_id"])
            family_by_candidate[candidate_id] = family_id
            cases = grouped.get(candidate_id, [])
            by_sample = {int(case["sample_id"]): case for case in cases}
            if len(by_sample) != len(cases):
                raise ValueError(f"Candidate {candidate_id} has duplicate case sample IDs")
            missing = [sample for sample in planned if sample not in by_sample]
            if missing:
                raise ValueError(f"Candidate {candidate_id} is missing planned samples {missing}")
            active = [sample for sample in planned if by_sample[sample]["status"] == "active"]
            inactive = [sample for sample in planned if by_sample[sample]["status"] == "inactive"]
            if set(active) & set(inactive) or len(active) + len(inactive) != len(planned):
                raise ValueError(f"Candidate {candidate_id} has invalid active/inactive partition")
            values = [float(by_sample[sample]["D"]) if sample in active else None for sample in planned]
            primary = infer_candidate(values, protocol, dependence)
            record = {
                "cross_sample_evidence_id": f"cross:{candidate_id}",
                "candidate_id": candidate_id,
                "family_id": family_id,
                "planned_samples": planned,
                "active_samples": active,
                "inactive_samples": inactive,
                "coverage": len(active) / len(planned),
                "D_values": values,
                "D_case_references": [by_sample[sample]["case_evidence_id"] for sample in planned],
                "effect": effect_summary(values),
                "primary_inference": primary,
                "multiplicity": None,
                "sensitivity": sensitivity_results(values, sensitivity_names, protocol, dependence) if primary["status"] == "complete" else [],
                "limitations": ["Functional evidence is limited to the audited model, checkpoint, data, and frozen protocol."],
            }
            evidence_by_candidate[candidate_id] = record
            cross.append(record)
            candidate_relations.append({
                **dict(member),
                "family_id": family_id,
                "case_evidence_ids": [by_sample[sample]["case_evidence_id"] for sample in planned],
                "cross_sample_evidence_id": record["cross_sample_evidence_id"],
            })

    alpha = float(config["multiplicity_protocol"]["alpha"])
    for family in config["candidate_families"]:
        family_id = str(family["family_id"])
        metadata = apply_primary_multiplicity(family, evidence_by_candidate, alpha=alpha)
        family_record = {
            "family_id": family_id,
            "scope": family["scope"],
            "selection_rule": family["selection_rule"],
            "context_identity_rule": family["context_identity_rule"],
            "members": [member["candidate_id"] for member in family["members"]],
            "size": family["family_size"],
            "selection_frozen": True,
            "multiple_testing": {"method": "BH", "alpha": alpha},
            **metadata,
        }
        family_records.append(family_record)

        family_evidence = [evidence_by_candidate[candidate_id] for candidate_id in family_record["members"]]
        complete = [item for item in family_evidence if item["primary_inference"]["status"] == "complete"]
        if complete and "BY" in config.get("sensitivity_protocol", {}).get("by_family", {}).get(family_id, []):
            by_values = benjamini_yekutieli([float(item["primary_inference"]["raw_p"]) for item in complete])
            for item, q_value in zip(complete, by_values):
                item["sensitivity"].append({
                    "name": "BY",
                    "role": "sensitivity",
                    "method": "Benjamini-Yekutieli",
                    "statistic": None,
                    "q": q_value,
                    "settings": {"family_id": family_id, "family_size": family_record["size"], "alpha": alpha},
                    "interpretation_boundary": "Sensitivity multiple testing; does not replace primary BH.",
                })

    return candidate_relations, family_records, cross


def protocol_provenance(config: Mapping[str, Any], family_records: Sequence[Mapping[str, Any]], dependence: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "sample_protocol_hash": canonical_hash(config["sample_protocol"]),
        "candidate_family_hash": canonical_hash(config["candidate_families"]),
        "control_protocol": config["control_protocol"],
        "dependence_audit_result": list(dependence),
        "inference_engine": config["inference_protocol"],
        "inference_config_hash": canonical_hash(config["inference_protocol"]),
        "raw_p_vector_hashes": {record["family_id"]: record["raw_p_vector_hash"] for record in family_records},
        "multiple_testing_method": config["multiplicity_protocol"],
        "family_membership_hashes": {record["family_id"]: record["family_membership_hash"] for record in family_records},
        "sensitivity_settings": config["sensitivity_protocol"],
    }

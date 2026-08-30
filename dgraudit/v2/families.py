from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def benjamini_hochberg(values: Sequence[float]) -> list[float]:
    if any(not 0 <= float(value) <= 1 for value in values):
        raise ValueError("BH raw p-values must be in [0,1]")
    order = sorted(range(len(values)), key=lambda index: float(values[index]))
    adjusted = [1.0] * len(values)
    running = 1.0
    for position in range(len(order) - 1, -1, -1):
        index = order[position]
        running = min(running, float(values[index]) * len(values) / (position + 1))
        adjusted[index] = running
    return adjusted


def benjamini_yekutieli(values: Sequence[float]) -> list[float]:
    factor = sum(1 / index for index in range(1, len(values) + 1))
    return [min(1.0, value * factor) for value in benjamini_hochberg(values)]


def apply_primary_multiplicity(
    family: Mapping[str, Any],
    evidence_by_candidate: Mapping[str, dict[str, Any]],
    *,
    alpha: float,
) -> dict[str, Any]:
    members = [str(member["candidate_id"]) for member in family["members"]]
    if int(family["family_size"]) != len(members) or len(members) != len(set(members)):
        raise ValueError(f"Hypothesis family {family.get('family_id')} failed integrity validation")
    valid_ids = [candidate_id for candidate_id in members if evidence_by_candidate[candidate_id]["primary_inference"]["status"] == "complete"]
    raw = [float(evidence_by_candidate[candidate_id]["primary_inference"]["raw_p"]) for candidate_id in valid_ids]
    adjusted = benjamini_hochberg(raw)
    for candidate_id in members:
        evidence = evidence_by_candidate[candidate_id]
        if candidate_id in valid_ids:
            q = adjusted[valid_ids.index(candidate_id)]
            evidence["multiplicity"] = {
                "family_id": family["family_id"],
                "method": "BH",
                "family_size": len(members),
                "valid_raw_p_count": len(valid_ids),
                "alpha": alpha,
                "adjusted_q": q,
                "supported": q < alpha,
                "reason": None,
            }
        else:
            evidence["multiplicity"] = {
                "family_id": family["family_id"],
                "method": "BH",
                "family_size": len(members),
                "valid_raw_p_count": len(valid_ids),
                "alpha": alpha,
                "adjusted_q": None,
                "supported": None,
                "reason": "Primary inference unavailable for this candidate.",
            }
    return {
        "family_id": family["family_id"],
        "family_size": len(members),
        "member_ids": members,
        "family_membership_hash": canonical_hash(members),
        "raw_p_vector_hash": canonical_hash({"candidate_ids": valid_ids, "raw_p": raw}),
        "multiplicity_method": "BH",
        "alpha": alpha,
        "valid_raw_p_count": len(valid_ids),
    }

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


class ControlProtocolError(ValueError):
    pass


def build_case_evidence(
    *,
    case_evidence_id: str,
    candidate_id: str,
    sample_id: int,
    context: Mapping[str, Any],
    scope: str,
    active: bool,
    focal_response: float | None,
    controls: Sequence[Mapping[str, Any]],
    response_metrics: Mapping[str, Any],
    graph_effect: Mapping[str, Any],
    baseline_reference: Mapping[str, Any],
    intervention_output_reference: Mapping[str, Any] | None,
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Construct descriptive case evidence from all unique eligible controls."""
    if not active:
        if focal_response not in (None,):
            raise ControlProtocolError("Inactive/not-exposed case cannot carry a focal response or D=0")
        return {
            "case_evidence_id": case_evidence_id,
            "candidate_id": candidate_id,
            "sample_id": sample_id,
            "context": dict(context),
            "scope": scope,
            "status": "inactive",
            "focal_response": None,
            "response_metric": "prediction_delta_abs",
            "controls": {"protocol": "all_unique_eligible", "unique_count": 0, "identities": [], "mean": None, "median": None},
            "D": None,
            "rank": None,
            "percentile": None,
            "baseline_reference": dict(baseline_reference),
            "intervention_output_reference": None,
            "response_metrics": dict(response_metrics),
            "graph_effect": dict(graph_effect),
            "formal_inference": {"status": "not_evaluated", "raw_p": None, "BH_q": None, "reason": "Inactive/not-exposed case."},
            "provenance": dict(provenance),
        }
    if focal_response is None or not math.isfinite(float(focal_response)):
        raise ControlProtocolError("Active case requires a finite focal response")
    identities = [str(item.get("identity")) for item in controls]
    if not identities or len(identities) != len(set(identities)):
        raise ControlProtocolError("Controls must be a non-empty set of unique identities")
    values = [float(item["response"]) for item in controls]
    if not all(math.isfinite(value) for value in values):
        raise ControlProtocolError("Control responses must be finite")
    ordered = sorted(values)
    middle = len(ordered) // 2
    median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    mean = sum(values) / len(values)
    greater = sum(value > focal_response for value in values)
    equal = sum(value == focal_response for value in values)
    below = sum(value < focal_response for value in values)
    return {
        "case_evidence_id": case_evidence_id,
        "candidate_id": candidate_id,
        "sample_id": sample_id,
        "context": dict(context),
        "scope": scope,
        "status": "active",
        "focal_response": float(focal_response),
        "response_metric": "prediction_delta_abs",
        "controls": {
            "protocol": "all_unique_eligible",
            "unique_count": len(values),
            "identities": identities,
            "responses": values,
            "mean": mean,
            "median": median,
        },
        "D": float(focal_response - mean),
        "rank": 1 + greater,
        "percentile": 100 * (below + 0.5 * (equal + 1)) / (len(values) + 1),
        "baseline_reference": dict(baseline_reference),
        "intervention_output_reference": dict(intervention_output_reference or {}),
        "response_metrics": dict(response_metrics),
        "graph_effect": dict(graph_effect),
        "formal_inference": {
            "status": "not_evaluated",
            "raw_p": None,
            "BH_q": None,
            "reason": "Case evidence is descriptive; formal inference is candidate-level across samples/tests.",
        },
        "provenance": dict(provenance),
    }

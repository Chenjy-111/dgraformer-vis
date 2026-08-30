from __future__ import annotations

import statistics
from typing import Any, Mapping, Sequence


def audit_dependence(
    protocol_id: str,
    sample_ids: Sequence[int],
    units: Sequence[Mapping[str, Any]] | None,
    *,
    same_continuous_series: bool | None,
    external_protocol: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not units or len(units) != len(sample_ids) or any("raw_start" not in unit or "raw_end" not in unit for unit in units):
        return {
            "protocol_id": protocol_id,
            "sample_ids": list(sample_ids),
            "raw_span": None,
            "start_positions": None,
            "minimum_start_gap": None,
            "median_start_gap": None,
            "adjacent_overlap_count": None,
            "all_pair_overlap_count": None,
            "same_continuous_series": same_continuous_series,
            "classification": "unknown_dependence",
            "derivation": "Raw start/end metadata was unavailable.",
            "inference_engine_selected": "external" if external_protocol else "unavailable",
            "reason": None if external_protocol else "Formal inference is unavailable without raw spans or a declared external dependence protocol.",
        }
    ordered = sorted(({"sample_id": int(sample), "raw_start": int(unit["raw_start"]), "raw_end": int(unit["raw_end"])} for sample, unit in zip(sample_ids, units)), key=lambda item: item["raw_start"])
    starts = [item["raw_start"] for item in ordered]
    gaps = [right - left for left, right in zip(starts, starts[1:])]
    adjacent = sum(ordered[index + 1]["raw_start"] <= ordered[index]["raw_end"] for index in range(len(ordered) - 1))
    all_pairs = sum(ordered[j]["raw_start"] <= ordered[i]["raw_end"] for i in range(len(ordered)) for j in range(i + 1, len(ordered)))
    classification = "overlapping_time_windows" if all_pairs else "non_overlapping_time_units"
    spans = [item["raw_end"] - item["raw_start"] + 1 for item in ordered]
    return {
        "protocol_id": protocol_id,
        "sample_ids": list(sample_ids),
        "raw_span": spans[0] if len(set(spans)) == 1 else spans,
        "start_positions": starts,
        "minimum_start_gap": min(gaps) if gaps else None,
        "median_start_gap": statistics.median(gaps) if gaps else None,
        "adjacent_overlap_count": adjacent,
        "all_pair_overlap_count": all_pairs,
        "same_continuous_series": same_continuous_series,
        "classification": classification,
        "derivation": "Inclusive raw spans compared pairwise in predeclared start order.",
        "inference_engine_selected": None,
        "reason": None,
    }

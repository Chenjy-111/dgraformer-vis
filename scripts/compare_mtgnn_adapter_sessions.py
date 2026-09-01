from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np


def _load(path: str) -> Mapping[str, Any]:
    return json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))


def _maximum_difference(left: Any, right: Any) -> float:
    a, b = np.asarray(left, dtype=np.float64), np.asarray(right, dtype=np.float64)
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch: {list(a.shape)} != {list(b.shape)}")
    return float(np.max(np.abs(a - b))) if a.size else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare official and external-custom MTGNN Quick Inspection numerical operands."
    )
    parser.add_argument("official")
    parser.add_argument("custom")
    parser.add_argument("--atol", type=float, default=0.0, help="Allowed maximum absolute difference.")
    args = parser.parse_args()
    official, custom = _load(args.official), _load(args.custom)
    official_case, custom_case = official["case_evidence"][0], custom["case_evidence"][0]
    comparisons = {
        "baseline_prediction": (
            official["samples"][0]["baseline_prediction"]["values"],
            custom["samples"][0]["baseline_prediction"]["values"],
        ),
        "learned_adjacency": (
            official["samples"][0]["contexts"][0]["graphs"]["learned_adjacency"]["values"],
            custom["samples"][0]["contexts"][0]["graphs"]["learned_adjacency"]["values"],
        ),
        "intervention_prediction": (
            official_case["intervention_output_reference"]["value"]["values"],
            custom_case["intervention_output_reference"]["value"]["values"],
        ),
        "control_responses": (
            official_case["controls"]["responses"], custom_case["controls"]["responses"],
        ),
        "focal_response": (official_case["focal_response"], custom_case["focal_response"]),
        "D": (official_case["D"], custom_case["D"]),
    }
    failures = []
    for label, values in comparisons.items():
        difference = _maximum_difference(*values)
        print(f"{label:<28} max_abs_diff={difference:.12g}")
        if difference > args.atol:
            failures.append((label, difference))
    identities_match = (
        official["checkpoint"]["sha256"] == custom["checkpoint"]["sha256"]
        and official["dataset"]["sha256"] == custom["dataset"]["sha256"]
    )
    print(f"checkpoint_and_dataset_identity match={str(identities_match).lower()}")
    if failures or not identities_match:
        print("MTGNN official/custom comparison: FAIL")
        return 2
    print("MTGNN official/custom comparison: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

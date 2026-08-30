from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ROOT = ROOT / "artifacts/msgnet_cross_test_v1"
EXPECTED_TEST_IDS = [0, 214, 428, 642, 857, 1071, 1285, 1499, 1713, 1927, 2142, 2356, 2570, 2784]
SUBSET_A = EXPECTED_TEST_IDS[0::2]
SUBSET_B = EXPECTED_TEST_IDS[1::2]


# Frozen before any hypothesis names or results are loaded.
CLASSIFICATION_RULE_VERSION = "msgnet_statistical_freeze_v1_uniform"


def classify(row: Mapping[str, Any]) -> str:
    temporal_reversal = (
        float(row["subset_A_mean_D"]) < 0
        or float(row["subset_B_mean_D"]) < 0
        or (
            float(row["subset_A_median_D"]) < 0
            and float(row["subset_B_median_D"]) < 0
        )
    )
    if temporal_reversal:
        return "DEPENDENCE-SENSITIVE"
    fully_stable = (
        bool(row["primary_BY_supported"])
        and bool(row["sign_test_bh_supported"])
        and float(row["subset_A_mean_D"]) > 0
        and float(row["subset_B_mean_D"]) > 0
        and float(row["subset_A_median_D"]) >= 0
        and float(row["subset_B_median_D"]) >= 0
        and float(row["LOO_minimum_mean_D"]) > 0
        and float(row["bootstrap_mean_CI95_low"]) > 0
    )
    return "STABLE UNDER SENSITIVITY" if fully_stable else "MIXED SENSITIVITY"


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields: List[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def bh(values: Sequence[float], factor: float = 1.0) -> List[float]:
    order = np.argsort(np.asarray(values, dtype=float))
    adjusted = np.empty(len(values), dtype=float)
    running = 1.0
    for position in range(len(values) - 1, -1, -1):
        index = int(order[position])
        rank = position + 1
        running = min(running, float(values[index]) * len(values) * factor / rank)
        adjusted[index] = min(1.0, running)
    return adjusted.tolist()


def sign_test_p(values: np.ndarray) -> float:
    positive = int(np.count_nonzero(values > 0))
    negative = int(np.count_nonzero(values < 0))
    n = positive + negative
    if n == 0:
        return 1.0
    return float(sum(math.comb(n, count) for count in range(positive, n + 1)) / (2 ** n))


def signflip_p(values: np.ndarray) -> float:
    n = len(values)
    signs = np.where(
        ((np.arange(2 ** n, dtype=np.uint16)[:, None] >> np.arange(n, dtype=np.uint16)) & 1) == 1,
        1.0,
        -1.0,
    )
    observed = float(np.mean(values))
    statistics = np.mean(signs * values.reshape(1, -1), axis=1)
    return float(np.count_nonzero(statistics >= observed) / (2 ** n))


def subset_metrics(values_by_test: Mapping[int, float], ids: Sequence[int]) -> Dict[str, Any]:
    values = np.asarray([values_by_test[test_id] for test_id in ids], dtype=float)
    return {
        "mean_D": float(np.mean(values)),
        "median_D": float(np.median(values)),
        "positive_count": int(np.count_nonzero(values > 0)),
        "negative_count": int(np.count_nonzero(values < 0)),
        "zero_count": int(np.count_nonzero(values == 0)),
        "signflip_p": signflip_p(values),
        "sign_test_p": sign_test_p(values),
    }


def family_summary(rows: Sequence[Mapping[str, Any]], raw_key: str, q_key: str) -> Dict[str, Any]:
    raw = np.asarray([float(row[raw_key]) for row in rows])
    q = np.asarray([float(row[q_key]) for row in rows])
    return {
        "raw_p_lt_0_05_count": int(np.count_nonzero(raw < 0.05)),
        "q_lt_0_05_count": int(np.count_nonzero(q < 0.05)),
        "minimum_raw_p": float(raw.min()),
        "minimum_q": float(q.min()),
    }


def main() -> int:
    protocol = json.loads((ARTIFACT_ROOT / "test_protocol.json").read_text(encoding="utf-8"))
    if protocol["selected_test_ids"] != EXPECTED_TEST_IDS:
        raise RuntimeError("Frozen test IDs do not match the declared sensitivity protocol")
    if protocol["raw_span"] != 192:
        raise RuntimeError("Unexpected raw span")

    case_rows = read_csv(ARTIFACT_ROOT / "case_evidence.csv")
    primary = {
        "single_scale": read_csv(ARTIFACT_ROOT / "relation_evidence_single_scale.csv"),
        "all_scales": read_csv(ARTIFACT_ROOT / "relation_evidence_all_scale.csv"),
    }
    expected_sizes = {"single_scale": 126, "all_scales": 42}
    primary_supported_expected = {"single_scale": 27, "all_scales": 14}
    cases_by_hypothesis: Dict[str, Dict[int, float]] = {}
    for row in case_rows:
        hypothesis_id = row["hypothesis_id"]
        test_id = int(row["test_id"])
        if test_id in cases_by_hypothesis.setdefault(hypothesis_id, {}):
            raise RuntimeError("Duplicate test D for {}".format(hypothesis_id))
        cases_by_hypothesis[hypothesis_id][test_id] = float(row["D"])

    enriched: Dict[str, List[Dict[str, Any]]] = {}
    for family, rows in primary.items():
        if len(rows) != expected_sizes[family]:
            raise RuntimeError("Unexpected family size")
        family_rows: List[Dict[str, Any]] = []
        for primary_row in rows:
            hypothesis_id = primary_row["hypothesis_id"]
            values_by_test = cases_by_hypothesis[hypothesis_id]
            if sorted(values_by_test) != EXPECTED_TEST_IDS:
                raise RuntimeError("Hypothesis is missing a frozen test")
            full_values = np.asarray([values_by_test[test_id] for test_id in EXPECTED_TEST_IDS])
            saved_primary_p = float(primary_row["raw_p_exact_signflip"])
            if signflip_p(full_values) != saved_primary_p:
                raise RuntimeError("Primary exact sign-flip p does not reproduce")
            item: Dict[str, Any] = dict(primary_row)
            item["sign_test_raw_p"] = sign_test_p(full_values)
            item["primary_signflip_BY_q"] = None
            item["BY_supported"] = None
            for label, ids in (("subset_A", SUBSET_A), ("subset_B", SUBSET_B)):
                metrics = subset_metrics(values_by_test, ids)
                for key, value in metrics.items():
                    item["{}_{}".format(label, key)] = value
            family_rows.append(item)

        sign_q = bh([float(row["sign_test_raw_p"]) for row in family_rows])
        harmonic = sum(1.0 / rank for rank in range(1, len(family_rows) + 1))
        by_q = bh([float(row["raw_p_exact_signflip"]) for row in family_rows], factor=harmonic)
        subset_a_q = bh([float(row["subset_A_signflip_p"]) for row in family_rows])
        subset_b_q = bh([float(row["subset_B_signflip_p"]) for row in family_rows])
        subset_a_sign_q = bh([float(row["subset_A_sign_test_p"]) for row in family_rows])
        subset_b_sign_q = bh([float(row["subset_B_sign_test_p"]) for row in family_rows])
        for index, row in enumerate(family_rows):
            row["sign_test_bh_q"] = sign_q[index]
            row["sign_test_bh_supported"] = sign_q[index] < 0.05
            row["primary_signflip_BY_q"] = by_q[index]
            row["BY_supported"] = by_q[index] < 0.05
            row["subset_A_signflip_bh_q"] = subset_a_q[index]
            row["subset_A_signflip_bh_supported"] = subset_a_q[index] < 0.05
            row["subset_B_signflip_bh_q"] = subset_b_q[index]
            row["subset_B_signflip_bh_supported"] = subset_b_q[index] < 0.05
            row["subset_A_sign_test_bh_q"] = subset_a_sign_q[index]
            row["subset_A_sign_test_bh_supported"] = subset_a_sign_q[index] < 0.05
            row["subset_B_sign_test_bh_q"] = subset_b_sign_q[index]
            row["subset_B_sign_test_bh_supported"] = subset_b_sign_q[index] < 0.05
        enriched[family] = family_rows

    if any(
        sum(str(row["bh_supported"]).lower() == "true" for row in enriched[family])
        != primary_supported_expected[family]
        for family in enriched
    ):
        raise RuntimeError("Primary supported counts changed")

    supported_rows = []
    for family, rows in enriched.items():
        for row in rows:
            if str(row["bh_supported"]).lower() != "true":
                continue
            output_row: Dict[str, Any] = {
                "family": family,
                "hypothesis": row["hypothesis_id"],
                "scale_index": row["scale_index"],
                "source": row["source"],
                "target": row["target"],
                "source_name": row["source_name"],
                "target_name": row["target_name"],
                "primary_mean_D": float(row["mean_D"]),
                "primary_median_D": float(row["median_D"]),
                "primary_positive_count": int(row["positive_count"]),
                "primary_N_tests": 14,
                "primary_exact_signflip_p": float(row["raw_p_exact_signflip"]),
                "primary_BH_q": float(row["bh_q"]),
                "primary_BY_q": float(row["primary_signflip_BY_q"]),
                "primary_BY_supported": bool(row["BY_supported"]),
                "sign_test_raw_p": float(row["sign_test_raw_p"]),
                "sign_test_bh_q": float(row["sign_test_bh_q"]),
                "sign_test_bh_supported": bool(row["sign_test_bh_supported"]),
                "subset_A_mean_D": float(row["subset_A_mean_D"]),
                "subset_A_median_D": float(row["subset_A_median_D"]),
                "subset_A_positive_count": int(row["subset_A_positive_count"]),
                "subset_A_N_tests": 7,
                "subset_A_signflip_p": float(row["subset_A_signflip_p"]),
                "subset_A_BH_q": float(row["subset_A_signflip_bh_q"]),
                "subset_B_mean_D": float(row["subset_B_mean_D"]),
                "subset_B_median_D": float(row["subset_B_median_D"]),
                "subset_B_positive_count": int(row["subset_B_positive_count"]),
                "subset_B_N_tests": 7,
                "subset_B_signflip_p": float(row["subset_B_signflip_p"]),
                "subset_B_BH_q": float(row["subset_B_signflip_bh_q"]),
                "LOO_minimum_mean_D": float(row["LOO_minimum_mean_D"]),
                "bootstrap_mean_CI95_low": float(row["bootstrap_mean_CI95_low"]),
                "bootstrap_mean_CI95_high": float(row["bootstrap_mean_CI95_high"]),
            }
            output_row["audit_classification"] = classify(output_row)
            supported_rows.append(output_row)
    write_csv(ARTIFACT_ROOT / "msgnet_supported_sensitivity.csv", supported_rows)

    sign_summary = {
        family: family_summary(rows, "sign_test_raw_p", "sign_test_bh_q")
        for family, rows in enriched.items()
    }
    by_summary = {
        family: {
            "supported_count": sum(bool(row["BY_supported"]) for row in rows),
            "minimum_q": min(float(row["primary_signflip_BY_q"]) for row in rows),
        }
        for family, rows in enriched.items()
    }
    subset_summary: Dict[str, Dict[str, Any]] = {}
    for label in ("subset_A", "subset_B"):
        subset_summary[label] = {}
        for family, rows in enriched.items():
            subset_summary[label][family] = {
                "signflip_BH_supported_count": sum(bool(row["{}_signflip_bh_supported".format(label)]) for row in rows),
                "minimum_signflip_raw_p": min(float(row["{}_signflip_p".format(label)]) for row in rows),
                "minimum_signflip_BH_q": min(float(row["{}_signflip_bh_q".format(label)]) for row in rows),
                "sign_test_raw_p_lt_0_05_count": sum(float(row["{}_sign_test_p".format(label)]) < 0.05 for row in rows),
                "sign_test_BH_supported_count": sum(bool(row["{}_sign_test_bh_supported".format(label)]) for row in rows),
                "minimum_sign_test_raw_p": min(float(row["{}_sign_test_p".format(label)]) for row in rows),
                "minimum_sign_test_BH_q": min(float(row["{}_sign_test_bh_q".format(label)]) for row in rows),
            }

    gaps_a = np.diff(SUBSET_A).tolist()
    gaps_b = np.diff(SUBSET_B).tolist()
    both_positive = sum(row["subset_A_mean_D"] > 0 and row["subset_B_mean_D"] > 0 for row in supported_rows)
    temporal_reversal_rows = [row for row in supported_rows if row["audit_classification"] == "DEPENDENCE-SENSITIVE"]
    classifications = {
        label: sum(row["audit_classification"] == label for row in supported_rows)
        for label in ("STABLE UNDER SENSITIVITY", "MIXED SENSITIVITY", "DEPENDENCE-SENSITIVE")
    }

    lines = [
        "# MSGNet Statistical Freeze Audit",
        "",
        "> SENSITIVITY / FREEZE AUDIT ONLY. Primary 14-test exact sign-flip p and primary BH results are unchanged.",
        "",
        "## A. Exact sign-test sensitivity",
        "",
        "Zeros are excluded from the binomial trial count and reported separately in the existing relation evidence. H1 is positive sign/median tendency.",
        "",
        "| family | raw p < .05 | sign-test BH q < .05 | minimum raw p | minimum BH q |",
        "|---|---:|---:|---:|---:|",
        "| single-scale | {raw_p_lt_0_05_count} | {q_lt_0_05_count} | {minimum_raw_p:.9g} | {minimum_q:.9g} |".format(**sign_summary["single_scale"]),
        "| all-scale | {raw_p_lt_0_05_count} | {q_lt_0_05_count} | {minimum_raw_p:.9g} | {minimum_q:.9g} |".format(**sign_summary["all_scales"]),
        "",
        "## B. Benjamini–Yekutieli sensitivity",
        "",
        "BY is applied only to the existing primary exact sign-flip raw p, separately within m=126 and m=42. It does not replace primary BH.",
        "",
        "| family | BY-supported | minimum BY q |",
        "|---|---:|---:|",
        "| single-scale | {} | {:.9g} |".format(by_summary["single_scale"]["supported_count"], by_summary["single_scale"]["minimum_q"]),
        "| all-scale | {} | {:.9g} |".format(by_summary["all_scales"]["supported_count"], by_summary["all_scales"]["minimum_q"]),
        "",
        "## C. Temporal-separation sensitivity",
        "",
        "- Subset A IDs: `{}`; gaps `{}`; raw span 192; minimum gap {}; overlaps 0.".format(SUBSET_A, gaps_a, min(gaps_a)),
        "- Subset B IDs: `{}`; gaps `{}`; raw span 192; minimum gap {}; overlaps 0.".format(SUBSET_B, gaps_b, min(gaps_b)),
        "- These are deterministic odd/even positions in the frozen list and are TEMPORAL SENSITIVITY ONLY.",
        "",
        "| subset | family | sign-flip BH supported | min sign-flip p | min sign-flip BH q | sign-test raw p < .05 | sign-test BH supported |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for label in ("subset_A", "subset_B"):
        for family in ("single_scale", "all_scales"):
            item = subset_summary[label][family]
            lines.append("| {} | {} | {} | {:.9g} | {:.9g} | {} | {} |".format(
                "A" if label == "subset_A" else "B", family,
                item["signflip_BH_supported_count"], item["minimum_signflip_raw_p"],
                item["minimum_signflip_BH_q"], item["sign_test_raw_p_lt_0_05_count"],
                item["sign_test_BH_supported_count"],
            ))
    lines += [
        "",
        "Among the 41 primary-supported relations, {} retain mean D > 0 in both subsets.".format(both_positive),
        "Temporal reversal under the uniform rule: {} primary-supported relations.".format(len(temporal_reversal_rows)),
        "",
        "## D. Supported-relation stability table",
        "",
        "The complete 41-row table is [msgnet_supported_sensitivity.csv](msgnet_supported_sensitivity.csv). It contains every requested primary, sign-test, BY, subset, LOO, and bootstrap field.",
        "",
        "## E. Audit-only classification",
        "",
        "Rule version: `{}`. The rule was defined before loading hypothesis names/results:".format(CLASSIFICATION_RULE_VERSION),
        "",
        "1. `DEPENDENCE-SENSITIVE` if either subset mean D is negative, or both subset medians are negative.",
        "2. Otherwise `STABLE UNDER SENSITIVITY` only if primary BY and full-sample sign-test BH are supported, both subset means are positive, both subset medians are nonnegative, LOO minimum mean is positive, and bootstrap mean CI lower bound is positive.",
        "3. All remaining cases are `MIXED SENSITIVITY`.",
        "",
        "| classification | count |",
        "|---|---:|",
        "| STABLE UNDER SENSITIVITY | {} |".format(classifications["STABLE UNDER SENSITIVITY"]),
        "| MIXED SENSITIVITY | {} |".format(classifications["MIXED SENSITIVITY"]),
        "| DEPENDENCE-SENSITIVE | {} |".format(classifications["DEPENDENCE-SENSITIVE"]),
        "",
        "## Freeze conclusion",
        "",
    ]
    if temporal_reversal_rows:
        lines.append("Temporal-half contradictions require review before website migration: `{}`.".format(
            ", ".join(row["hypothesis"] for row in temporal_reversal_rows)
        ))
    else:
        lines.append("No primary-supported relation meets the predeclared severe temporal-reversal rule. Statistics can be frozen for reviewed website migration; sensitivity labels remain audit-only.")
    lines.append("")
    (ARTIFACT_ROOT / "MSGNET_STATISTICAL_FREEZE_AUDIT.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({
        "primary_supported": primary_supported_expected,
        "sign_test": sign_summary,
        "BY": by_summary,
        "subsets": subset_summary,
        "supported_both_subset_means_positive": both_positive,
        "classifications": classifications,
        "temporal_reversal_hypotheses": [row["hypothesis"] for row in temporal_reversal_rows],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

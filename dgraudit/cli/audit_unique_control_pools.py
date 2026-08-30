from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from dgraudit.cli.validate_pattern import benjamini_hochberg, empirical_p_plus_one


DEFAULT_RUN = "a778b2bdac2e3a012177d432ad237ada8dd6d5e24cccb57115c6edceb5cadeb8"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def intervention_identity(
    dataset: str,
    sample_id: int,
    window_id: int,
    source: int,
    target: int,
    current_epoch: int,
) -> str:
    return (
        f"{dataset}|test|sample={sample_id}|window={window_id}|"
        f"structural_edge_removal|source={source}|target={target}|epoch={current_epoch}"
    )


def markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for label, _ in columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(str(row[key]) for _, key in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, divider, *body])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--runs-root", default="artifacts/runs")
    parser.add_argument("--output", default="artifacts/evidence_validation")
    args = parser.parse_args()

    repo = Path.cwd().resolve()
    run_dir = (repo / args.runs_root / args.run).resolve()
    output_dir = (repo / args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog = load_json(run_dir / "evidence_catalog.json")
    manifest = load_json(run_dir / "manifest.json")
    cases = catalog["cases"]
    current_epoch = int(cases[0]["model"]["schedule"]["current_epoch_equivalent"])

    hypothesis_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    eligible_duplicate_total = 0
    b100_duplicate_total = 0
    b100_hypotheses_with_duplicates = 0
    b100_hypotheses_covering_full_pool = 0

    for case in cases:
        hypothesis_id = case["conclusion_id"]
        dataset = case["dataset"]["name"]
        sample_id = int(case["sample"]["original_index"])
        window_id = int(case["graph"]["window"])
        focal_source = int(case["graph"]["source"])
        focal_target = int(case["graph"]["target"])
        focal_effect = float(case["metrics"]["prediction_delta_abs"])
        cached_edges = case["raw_operands"]["weight_impact"]["edges"]

        eligible_by_identity: dict[str, dict[str, Any]] = {}
        raw_eligible_count = 0
        for cached_index, cached in enumerate(cached_edges):
            source = int(cached["source"])
            target = int(cached["target"])
            if source == target or (source == focal_source and target == focal_target):
                continue
            raw_eligible_count += 1
            identity = intervention_identity(
                dataset, sample_id, window_id, source, target, current_epoch
            )
            record = {
                "hypothesis_id": hypothesis_id,
                "dataset": dataset,
                "sample_id": sample_id,
                "window_id": window_id,
                "focal_source": focal_source,
                "focal_target": focal_target,
                "control_identity": identity,
                "protocol": "structural_edge_removal",
                "control_source": source,
                "control_target": target,
                "current_epoch": current_epoch,
                "cached_retained_edge_row": cached_index,
                "control_prediction_delta_abs": float(cached["prediction_delta_abs"]),
                "control_error_delta_mae": float(cached["error_delta_mae"]),
            }
            if identity not in eligible_by_identity:
                eligible_by_identity[identity] = record
        unique_controls = list(eligible_by_identity.values())
        eligible_duplicate_count = raw_eligible_count - len(unique_controls)
        eligible_duplicate_total += eligible_duplicate_count

        stored_controls_path = run_dir / Path(case["controls"]["records"].replace("\\", "/"))
        stored_controls = load_json(stored_controls_path)
        sampled_identities = [
            intervention_identity(
                dataset,
                sample_id,
                window_id,
                int(record["source"]),
                int(record["target"]),
                current_epoch,
            )
            for record in stored_controls
        ]
        unique_sampled_identities = set(sampled_identities)
        sampled_duplicate_count = len(sampled_identities) - len(unique_sampled_identities)
        b100_duplicate_total += sampled_duplicate_count
        b100_hypotheses_with_duplicates += int(sampled_duplicate_count > 0)
        b100_hypotheses_covering_full_pool += int(
            unique_sampled_identities == set(eligible_by_identity)
        )

        control_effects = [
            float(record["control_prediction_delta_abs"]) for record in unique_controls
        ]
        exhaustive_p = empirical_p_plus_one(control_effects, focal_effect)
        count_ge_focal = sum(effect >= focal_effect for effect in control_effects)
        N_h = len(unique_controls)
        for record in unique_controls:
            record["focal_prediction_delta_abs"] = focal_effect
            record["control_ge_focal"] = (
                float(record["control_prediction_delta_abs"]) >= focal_effect
            )
            control_rows.append(record)

        hypothesis_rows.append(
            {
                "hypothesis_id": hypothesis_id,
                "dataset": dataset,
                "sample_id": sample_id,
                "window_id": window_id,
                "window_active": bool(focal_effect > 0),
                "focal_source": focal_source,
                "focal_target": focal_target,
                "focal_prediction_delta_abs": focal_effect,
                "unique_eligible_control_count_N_h": N_h,
                "raw_cached_eligible_count_before_identity_dedup": raw_eligible_count,
                "duplicate_cached_eligible_identities_removed": eligible_duplicate_count,
                "count_unique_control_delta_ge_focal": count_ge_focal,
                "exhaustive_empirical_p": exhaustive_p,
                "exhaustive_bh_q": None,
                "original_B100_empirical_p": float(case["metrics"]["empirical_p"]),
                "original_B100_bh_q": float(case["metrics"]["bh_adjusted_p"]),
                "original_B100_sampled_records": len(sampled_identities),
                "original_B100_unique_sampled_identities": len(unique_sampled_identities),
                "original_B100_duplicate_draws": sampled_duplicate_count,
                "original_B100_covers_full_unique_pool": (
                    unique_sampled_identities == set(eligible_by_identity)
                ),
                "control_seed": int(case["controls"]["random_seed"]),
            }
        )

    exhaustive_q = benjamini_hochberg(
        [float(row["exhaustive_empirical_p"]) for row in hypothesis_rows]
    )
    for row, q_value in zip(hypothesis_rows, exhaustive_q):
        row["exhaustive_bh_q"] = q_value

    controls_csv = output_dir / "unique_matched_control_records.csv"
    with controls_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(control_rows[0]))
        writer.writeheader()
        writer.writerows(control_rows)

    hypotheses_csv = output_dir / "unique_matched_control_pool_audit.csv"
    with hypotheses_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(hypothesis_rows[0]))
        writer.writeheader()
        writer.writerows(hypothesis_rows)

    counts = np.asarray(
        [row["unique_eligible_control_count_N_h"] for row in hypothesis_rows], dtype=int
    )
    p_values = np.asarray(
        [row["exhaustive_empirical_p"] for row in hypothesis_rows], dtype=float
    )
    q_values = np.asarray(
        [row["exhaustive_bh_q"] for row in hypothesis_rows], dtype=float
    )
    original_p = np.asarray(
        [row["original_B100_empirical_p"] for row in hypothesis_rows], dtype=float
    )
    original_q = np.asarray(
        [row["original_B100_bh_q"] for row in hypothesis_rows], dtype=float
    )
    floor_value = 1 / 101
    floor_rows = [
        row for row in hypothesis_rows if float(row["original_B100_empirical_p"]) == floor_value
    ]
    floor_comparison = [
        {
            "hypothesis_id": row["hypothesis_id"],
            "sample_id": row["sample_id"],
            "window_id": row["window_id"],
            "edge": [row["focal_source"], row["focal_target"]],
            "N_h": row["unique_eligible_control_count_N_h"],
            "unique_controls_ge_focal": row["count_unique_control_delta_ge_focal"],
            "B100_raw_p": row["original_B100_empirical_p"],
            "B100_BH_q": row["original_B100_bh_q"],
            "exhaustive_raw_p": row["exhaustive_empirical_p"],
            "exhaustive_BH_q": row["exhaustive_bh_q"],
            "raw_p_change": row["exhaustive_empirical_p"] - row["original_B100_empirical_p"],
        }
        for row in floor_rows
    ]

    summary = {
        "status": "complete",
        "scope": "cache-only exhaustive unique matched-control audit; no model forward executed",
        "dataset": catalog["dataset"],
        "run_id": args.run,
        "checkpoint_sha256": manifest["checkpoint_sha256"],
        "data_sha256": manifest["data_sha256"],
        "hypothesis_family_size": len(hypothesis_rows),
        "candidate_family_modified": False,
        "inactive_cases_removed": False,
        "website_modified": False,
        "model_forward_count": 0,
        "eligibility_rule": (
            "all real retained same-window directed non-self edge interventions excluding the focal edge"
        ),
        "intervention_identity_fields": [
            "dataset",
            "split",
            "sample_id",
            "window_id",
            "protocol",
            "source",
            "target",
            "current_epoch",
        ],
        "effect_metric": "prediction_delta_abs",
        "empirical_tail": "control_prediction_delta_abs >= focal_prediction_delta_abs",
        "production_empirical_function": "dgraudit.cli.validate_pattern.empirical_p_plus_one",
        "production_BH_function": "dgraudit.cli.validate_pattern.benjamini_hochberg",
        "unique_pool_size": {
            "min": int(counts.min()),
            "q25": float(np.quantile(counts, 0.25)),
            "median": float(np.median(counts)),
            "q75": float(np.quantile(counts, 0.75)),
            "max": int(counts.max()),
            "N_h_value_counts": {
                str(value): int(np.sum(counts == value)) for value in sorted(set(counts.tolist()))
            },
            "N_h_lt_20": int(np.sum(counts < 20)),
            "N_h_lt_50": int(np.sum(counts < 50)),
            "N_h_lt_100": int(np.sum(counts < 100)),
            "N_h_ge_100": int(np.sum(counts >= 100)),
            "disjoint_bins": {
                "N_h_lt_20": int(np.sum(counts < 20)),
                "20_le_N_h_lt_50": int(np.sum((counts >= 20) & (counts < 50))),
                "50_le_N_h_lt_100": int(np.sum((counts >= 50) & (counts < 100))),
                "N_h_ge_100": int(np.sum(counts >= 100)),
            },
        },
        "identity_deduplication": {
            "unique_eligible_records_total": len(control_rows),
            "globally_distinct_intervention_identities": len(
                {row["control_identity"] for row in control_rows}
            ),
            "cross_hypothesis_reuse_memberships": len(control_rows)
            - len({row["control_identity"] for row in control_rows}),
            "duplicate_identities_in_cached_eligible_rows": eligible_duplicate_total,
            "B100_sampled_records_total": sum(
                int(row["original_B100_sampled_records"]) for row in hypothesis_rows
            ),
            "B100_duplicate_draws_total": b100_duplicate_total,
            "B100_hypotheses_with_duplicate_draws": b100_hypotheses_with_duplicates,
            "B100_hypotheses_covering_entire_unique_pool": b100_hypotheses_covering_full_pool,
        },
        "exhaustive_results": {
            "min_raw_p": float(p_values.min()),
            "raw_p_lt_0_01": int(np.sum(p_values < 0.01)),
            "raw_p_lt_0_05": int(np.sum(p_values < 0.05)),
            "raw_p_lt_0_10": int(np.sum(p_values < 0.10)),
            "min_BH_q": float(q_values.min()),
            "q_lt_0_05": int(np.sum(q_values < 0.05)),
            "q_lt_0_10": int(np.sum(q_values < 0.10)),
        },
        "B100_results": {
            "min_raw_p": float(original_p.min()),
            "raw_p_lt_0_01": int(np.sum(original_p < 0.01)),
            "raw_p_lt_0_05": int(np.sum(original_p < 0.05)),
            "raw_p_lt_0_10": int(np.sum(original_p < 0.10)),
            "min_BH_q": float(original_q.min()),
            "q_lt_0_05": int(np.sum(original_q < 0.05)),
            "q_lt_0_10": int(np.sum(original_q < 0.10)),
        },
        "all_case_comparison": {
            "exhaustive_raw_p_gt_B100": int(np.sum(p_values > original_p)),
            "exhaustive_raw_p_eq_B100": int(np.sum(p_values == original_p)),
            "exhaustive_raw_p_lt_B100": int(np.sum(p_values < original_p)),
        },
        "B100_floor_value": floor_value,
        "B100_floor_case_count": len(floor_comparison),
        "B100_floor_case_comparison": floor_comparison,
        "conclusion_changed": bool(
            (np.sum(original_q < 0.05) == 0) != (np.sum(q_values < 0.05) == 0)
        ),
        "conclusion": (
            "The exhaustive unique-control analysis does not change the adjusted-significance conclusion: "
            "no hypothesis has BH q < 0.05 or q < 0.10. It removes Monte Carlo floor artifacts and "
            "shows that the finite unique pools are much smaller than B=100."
        ),
    }
    summary_path = output_dir / "exhaustive_matched_control_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    pool = summary["unique_pool_size"]
    exhaustive = summary["exhaustive_results"]
    original = summary["B100_results"]
    identity = summary["identity_deduplication"]
    floor_table = markdown_table(
        [
            {
                "hypothesis": row["hypothesis_id"],
                "N": row["N_h"],
                "ge": row["unique_controls_ge_focal"],
                "old_p": f"{row['B100_raw_p']:.9f}",
                "new_p": f"{row['exhaustive_raw_p']:.9f}",
                "old_q": f"{row['B100_BH_q']:.9f}",
                "new_q": f"{row['exhaustive_BH_q']:.9f}",
            }
            for row in floor_comparison
        ],
        [
            ("Hypothesis", "hypothesis"),
            ("N_h", "N"),
            ("# control ≥ focal", "ge"),
            ("B=100 p", "old_p"),
            ("Exhaustive p", "new_p"),
            ("B=100 q", "old_q"),
            ("Exhaustive q", "new_q"),
        ],
    )
    report = f"""# Exhaustive unique matched-control analysis

No new model forward was executed. The 320-hypothesis candidate family, including inactive cases, is unchanged; the website was not modified.

## Production rule and identity

- Eligibility: all real retained directed non-self edges in the same sample×window, excluding the focal edge.
- Intervention identity: dataset + split + sample + window + `structural_edge_removal` + source + target + current epoch.
- Effect metric: `prediction_delta_abs`.
- Empirical tail: `control prediction_delta_abs >= focal prediction_delta_abs`.
- Empirical p and BH use the existing production functions.

## Unique eligible pool size

| Statistic | N_h |
| --- | ---: |
| min | {pool['min']} |
| q25 | {pool['q25']:.3f} |
| median | {pool['median']:.3f} |
| q75 | {pool['q75']:.3f} |
| max | {pool['max']} |

Requested cumulative thresholds:

| Threshold | Hypotheses |
| --- | ---: |
| N_h < 20 | {pool['N_h_lt_20']} |
| N_h < 50 | {pool['N_h_lt_50']} |
| N_h < 100 | {pool['N_h_lt_100']} |
| N_h >= 100 | {pool['N_h_ge_100']} |

Within each hypothesis, the cached eligible rows contain `{identity['duplicate_identities_in_cached_eligible_rows']}` duplicate intervention identities after applying the true identity key. The `{identity['unique_eligible_records_total']:,}` per-hypothesis eligible memberships correspond to `{identity['globally_distinct_intervention_identities']:,}` globally distinct interventions; reuse across different focal hypotheses is expected and is not treated as a within-hypothesis duplicate. In contrast, the original B=100 sampled lists contain `{identity['B100_duplicate_draws_total']:,}` repeated draws across `{identity['B100_hypotheses_with_duplicate_draws']}` hypotheses. All `{identity['B100_hypotheses_covering_entire_unique_pool']}` hypotheses sampled every member of their unique pool at least once, but with heavy repetition.

## Exhaustive results

| Metric | B=100 Monte Carlo | Exhaustive unique controls |
| --- | ---: | ---: |
| min raw p | {original['min_raw_p']:.12g} | {exhaustive['min_raw_p']:.12g} |
| raw p < .01 | {original['raw_p_lt_0_01']} | {exhaustive['raw_p_lt_0_01']} |
| raw p < .05 | {original['raw_p_lt_0_05']} | {exhaustive['raw_p_lt_0_05']} |
| raw p < .10 | {original['raw_p_lt_0_10']} | {exhaustive['raw_p_lt_0_10']} |
| min BH q | {original['min_BH_q']:.12g} | {exhaustive['min_BH_q']:.12g} |
| q < .05 | {original['q_lt_0_05']} | {exhaustive['q_lt_0_05']} |
| q < .10 | {original['q_lt_0_10']} | {exhaustive['q_lt_0_10']} |

Across all hypotheses, exhaustive raw p is larger than the B=100 estimate for `{summary['all_case_comparison']['exhaustive_raw_p_gt_B100']}` cases, equal for `{summary['all_case_comparison']['exhaustive_raw_p_eq_B100']}`, and smaller for `{summary['all_case_comparison']['exhaustive_raw_p_lt_B100']}`.

## Original nine B=100 floor cases

{floor_table}

## Conclusion

The exhaustive matched-control analysis **does not change the main conclusion**: no real hypothesis survives BH at 0.05 or 0.10. It does change the interpretation of the nine B=100 floor cases: their `1/101` values arose from Monte Carlo resampling with replacement from very small finite pools, not from 100 independent interventions. Exhaustive p-values are bounded by the true pool sizes and eliminate that artificial sampling floor.
"""
    (output_dir / "exhaustive_matched_control_analysis.md").write_text(
        report, encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

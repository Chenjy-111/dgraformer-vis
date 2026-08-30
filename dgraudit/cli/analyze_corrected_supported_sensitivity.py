from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "artifacts" / "cross_sample_validation"
OUTPUT_DIR = INPUT_DIR / "corrected_supported_sensitivity"
BOOTSTRAP_REPETITIONS = 10_000
BOOTSTRAP_SEED = 20260830
BLOCK_LENGTH = 3
TRIM_PROPORTION = 0.10


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def trimmed_mean(values: np.ndarray, proportion: float = TRIM_PROPORTION) -> float:
    data = np.sort(np.asarray(values, dtype=float))
    trim_each_tail = int(math.floor(proportion * data.size))
    if data.size - 2 * trim_each_tail <= 0:
        raise ValueError("Trim proportion removes every observation")
    return float(np.mean(data[trim_each_tail:data.size - trim_each_tail]))


def bootstrap_positions(position_count: int) -> np.ndarray:
    possible_starts = position_count - BLOCK_LENGTH + 1
    blocks_per_replicate = math.ceil(position_count / BLOCK_LENGTH)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    starts = rng.integers(
        0, possible_starts, size=(BOOTSTRAP_REPETITIONS, blocks_per_replicate)
    )
    positions = (starts[..., None] + np.arange(BLOCK_LENGTH)).reshape(BOOTSTRAP_REPETITIONS, -1)
    return positions[:, :position_count]


def statistic_distribution(
    sampled: np.ndarray, statistic: Callable[[np.ndarray], float]
) -> np.ndarray:
    distribution = np.empty(sampled.shape[0], dtype=float)
    for index, replicate in enumerate(sampled):
        active = replicate[~np.isnan(replicate)]
        if active.size == 0:
            raise ValueError(f"Bootstrap replicate {index} has no active observations")
        distribution[index] = statistic(active)
    return distribution


def moving_block_sensitivity(values_by_position: np.ndarray) -> dict[str, Any]:
    positions = bootstrap_positions(values_by_position.size)
    sampled = values_by_position[positions]
    active = values_by_position[~np.isnan(values_by_position)]

    observed_trimmed_mean = trimmed_mean(active)
    trimmed_distribution = statistic_distribution(sampled, trimmed_mean)
    null_trimmed = np.where(
        np.isnan(values_by_position), np.nan, values_by_position - observed_trimmed_mean
    )
    null_trimmed_distribution = statistic_distribution(null_trimmed[positions], trimmed_mean)
    trimmed_exceedances = int(np.sum(null_trimmed_distribution >= observed_trimmed_mean))
    trimmed_p = (1 + trimmed_exceedances) / (BOOTSTRAP_REPETITIONS + 1)
    trimmed_ci = np.quantile(trimmed_distribution, [0.025, 0.975])

    observed_median = float(np.median(active))
    median_distribution = np.nanmedian(sampled, axis=1)
    median_ci = np.quantile(median_distribution, [0.025, 0.975])
    return {
        "block_length": BLOCK_LENGTH,
        "possible_block_count": values_by_position.size - BLOCK_LENGTH + 1,
        "blocks_per_replicate": math.ceil(values_by_position.size / BLOCK_LENGTH),
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "inactive_pattern_preserved": True,
        "trim_proportion_each_tail": TRIM_PROPORTION,
        "trimmed_mean": observed_trimmed_mean,
        "trimmed_mean_ci_low": float(trimmed_ci[0]),
        "trimmed_mean_ci_high": float(trimmed_ci[1]),
        "trimmed_mean_null_centering": "active D minus observed 10% trimmed mean",
        "trimmed_mean_null_exceedance_count": trimmed_exceedances,
        "trimmed_mean_block_p": float(trimmed_p),
        "median_D": observed_median,
        "median_block_ci_low": float(median_ci[0]),
        "median_block_ci_high": float(median_ci[1]),
        "median_block_p": None,
        "median_block_p_status": "not_reported",
        "median_block_p_reason": (
            "A CI is reported, but a null-centered p-value is intentionally omitted because the "
            "non-smooth sample median plus varying active counts needs stronger calibration than this sensitivity check."
        ),
    }


def classification(summary: dict[str, Any]) -> tuple[str, str]:
    removal_robust = (
        summary["mean_after_removing_largest_positive_D"] > 0
        and summary["mean_after_removing_two_largest_positive_D"] > 0
    )
    trimmed_supported = (
        summary["trimmed_mean_10pct"] > 0
        and summary["trimmed_mean_block_p"] < 0.05
    )
    median_supported = summary["median_block_ci_low"] > 0
    if removal_robust and trimmed_supported and median_supported:
        return "ROBUST", "positive after top-1/top-2 removal, trimmed-mean p<.05, and median block CI entirely above zero"
    if removal_robust and summary["trimmed_mean_10pct"] > 0:
        return (
            "SOMEWHAT OUTLIER-SENSITIVE",
            "top-1/top-2 removal and trimming preserve a positive effect, but not every robust criterion is satisfied",
        )
    return (
        "OUTLIER-DRIVEN",
        "the positive mean fails after top-positive removal or the 10% trimmed mean is non-positive",
    )


def analyze_candidate(
    source_rows: list[dict[str, str]],
    family: str,
    candidate: str,
    selector: Callable[[dict[str, str]], bool],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    selected = sorted((row for row in source_rows if selector(row)), key=lambda row: int(row["sample_id"]))
    if len(selected) != 40:
        raise ValueError(f"{family} {candidate}: expected 40 predeclared positions, found {len(selected)}")
    values_by_position = np.asarray([
        float(row["paired_effect_mean"]) if row["active"] == "True" else np.nan
        for row in selected
    ], dtype=float)
    active_pairs = [
        (int(row["sample_id"]), float(row["paired_effect_mean"]))
        for row in selected if row["active"] == "True"
    ]
    active_values = np.asarray([value for _, value in active_pairs], dtype=float)
    sorted_pairs = sorted(active_pairs, key=lambda item: (item[1], item[0]))
    positive_values = sorted((value for value in active_values if value > 0), reverse=True)
    if len(positive_values) < 2:
        raise ValueError(f"{family} {candidate}: fewer than two positive observations")
    largest_positive = positive_values[0]
    second_largest_positive = positive_values[1]
    remove_one = np.delete(active_values, int(np.argmax(active_values)))
    top_two_indices = np.argsort(active_values)[-2:]
    remove_two = np.delete(active_values, top_two_indices)
    sensitivity = moving_block_sensitivity(values_by_position)
    summary = {
        "family": family,
        "candidate": candidate,
        "total_predeclared_positions": len(selected),
        "active_samples": int(active_values.size),
        "inactive_samples": len(selected) - int(active_values.size),
        "min_D": float(np.min(active_values)),
        "max_D": float(np.max(active_values)),
        "mean_D": float(np.mean(active_values)),
        "median_D": float(np.median(active_values)),
        "standard_deviation_sample_ddof1": float(np.std(active_values, ddof=1)),
        "Q1_D": float(np.quantile(active_values, 0.25)),
        "Q3_D": float(np.quantile(active_values, 0.75)),
        "trimmed_mean_10pct": trimmed_mean(active_values),
        "trimmed_count_each_tail": int(math.floor(TRIM_PROPORTION * active_values.size)),
        "largest_positive_D": largest_positive,
        "second_largest_positive_D": second_largest_positive,
        "mean_after_removing_largest_positive_D": float(np.mean(remove_one)),
        "mean_after_removing_two_largest_positive_D": float(np.mean(remove_two)),
        "positive_count": int(np.sum(active_values > 0)),
        "positive_fraction": float(np.mean(active_values > 0)),
        **sensitivity,
    }
    label, reason = classification(summary)
    summary["robustness_classification"] = label
    summary["classification_basis"] = reason
    sorted_rows = [
        {
            "family": family,
            "candidate": candidate,
            "ascending_rank": rank,
            "sample_id": sample_id,
            "D": value,
        }
        for rank, (sample_id, value) in enumerate(sorted_pairs, 1)
    ]
    return summary, sorted_rows


def markdown_report(summaries: list[dict[str, Any]], sorted_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Corrected-Supported Candidate Outlier Sensitivity",
        "",
        "This analysis reads existing paired-effect CSV files only. It does not run model inference and does not alter the formal V2 results or BH families.",
        "",
    ]
    for summary in summaries:
        lines.extend([
            f"## {summary['family']} {summary['candidate']}",
            "",
            f"- Active: {summary['active_samples']}/{summary['total_predeclared_positions']}",
            f"- min / max D: {summary['min_D']:+.10f} / {summary['max_D']:+.10f}",
            f"- mean / median D: {summary['mean_D']:+.10f} / {summary['median_D']:+.10f}",
            f"- sample SD: {summary['standard_deviation_sample_ddof1']:.10f}",
            f"- Q1 / Q3: {summary['Q1_D']:+.10f} / {summary['Q3_D']:+.10f}",
            f"- 10% trimmed mean: {summary['trimmed_mean_10pct']:+.10f} (removed {summary['trimmed_count_each_tail']} from each tail)",
            f"- Mean after removing largest positive D: {summary['mean_after_removing_largest_positive_D']:+.10f}",
            f"- Mean after removing two largest positive D: {summary['mean_after_removing_two_largest_positive_D']:+.10f}",
            f"- D>0: {summary['positive_count']}/{summary['active_samples']} ({summary['positive_fraction']:.1%})",
            f"- Trimmed-mean L=3 block p: {summary['trimmed_mean_block_p']:.10g}",
            f"- Trimmed-mean block CI95: [{summary['trimmed_mean_ci_low']:+.10f}, {summary['trimmed_mean_ci_high']:+.10f}]",
            f"- Median L=3 block CI95: [{summary['median_block_ci_low']:+.10f}, {summary['median_block_ci_high']:+.10f}]",
            "- Median block p: not reported (non-smooth statistic with varying active counts; CI retained).",
            f"- Classification: {summary['robustness_classification']}",
            f"- Basis: {summary['classification_basis']}.",
            "",
            "| Rank | Sample | D |",
            "|---:|---:|---:|",
        ])
        candidate_rows = [
            row for row in sorted_rows
            if row["family"] == summary["family"] and row["candidate"] == summary["candidate"]
        ]
        for row in candidate_rows:
            lines.append(f"| {row['ascending_rank']} | {row['sample_id']} | {row['D']:+.10f} |")
        lines.append("")
    lines.extend([
        "## Final labels",
        "",
        *[f"- {summary['family']} {summary['candidate']}: {summary['robustness_classification']}" for summary in summaries],
        "",
        "SENSITIVITY ONLY — FORMAL V2 RESULTS UNCHANGED",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    local_path = INPUT_DIR / "per_sample_paired_effects.csv"
    global_path = INPUT_DIR / "per_sample_global_paired_effects.csv"
    local_rows = read_csv(local_path)
    global_rows = read_csv(global_path)
    local_summary, local_sorted = analyze_candidate(
        local_rows,
        "Local",
        "w6 0->4",
        lambda row: row["window_id"] == "6" and row["source_node"] == "0" and row["target_node"] == "4",
    )
    global_summary, global_sorted = analyze_candidate(
        global_rows,
        "Global",
        "0->2",
        lambda row: row["source_node"] == "0" and row["target_node"] == "2",
    )
    summaries = [local_summary, global_summary]
    sorted_rows = local_sorted + global_sorted
    write_csv(OUTPUT_DIR / "active_D_sorted.csv", sorted_rows)
    write_csv(OUTPUT_DIR / "sensitivity_summary.csv", summaries)
    result = {
        "status": "complete",
        "scope": "sensitivity only; formal V2 inference and BH unchanged",
        "inputs": {
            str(local_path.relative_to(ROOT)): sha256(local_path),
            str(global_path.relative_to(ROOT)): sha256(global_path),
        },
        "method": {
            "block_length": BLOCK_LENGTH,
            "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
            "seed": BOOTSTRAP_SEED,
            "trim_proportion_each_tail": TRIM_PROPORTION,
            "inactive_pattern_preserved": True,
        },
        "candidates": summaries,
    }
    (OUTPUT_DIR / "sensitivity_results.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (OUTPUT_DIR / "sensitivity_report.md").write_text(
        markdown_report(summaries, sorted_rows), encoding="utf-8"
    )
    print(json.dumps({
        "output_dir": str(OUTPUT_DIR),
        "labels": {summary["candidate"]: summary["robustness_classification"] for summary in summaries},
        "trimmed_mean_block_p": {summary["candidate"]: summary["trimmed_mean_block_p"] for summary in summaries},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

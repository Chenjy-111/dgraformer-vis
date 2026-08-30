from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.stats import binomtest, spearmanr, wilcoxon

from dgraudit.cli.validate_pattern import benjamini_hochberg


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "artifacts" / "cross_sample_validation"
LOCAL_RUN_ID = "3e83451437fe946a975b56fe6528fa2136443b9b08b966d3a9a78041849a6442"
GLOBAL_RUN_ID = "a256ec935997909c43d29acee22fdfccb8650d1db77dadf335c92d8ad63b0f43"
BOOTSTRAP_SEED = 20260830
BOOTSTRAP_REPETITIONS = 10_000
TIE_TOLERANCE = 0.0


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_bool(value: bool) -> str:
    return "true" if value else "false"


def fmt(value: float | int | None, digits: int = 8) -> str:
    if value is None:
        return "NA"
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}g}"


def fmt_effect(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{value:+.8f}"


def exact_sign_test(values: Iterable[float]) -> dict[str, Any]:
    nonzero = [float(value) for value in values if abs(float(value)) > TIE_TOLERANCE]
    positives = sum(value > 0 for value in nonzero)
    p_value = float(binomtest(positives, len(nonzero), 0.5, alternative="greater").pvalue) if nonzero else 1.0
    return {"n": len(nonzero), "positive": positives, "p": p_value}


def signed_rank_test(values: Iterable[float]) -> dict[str, Any]:
    nonzero = np.asarray([float(value) for value in values if abs(float(value)) > TIE_TOLERANCE], dtype=float)
    if nonzero.size < 2:
        return {
            "n": int(nonzero.size), "statistic": None, "p": None,
            "status": "not_applicable", "reason": "fewer than two non-zero paired effects",
        }
    try:
        result = wilcoxon(nonzero, alternative="greater", zero_method="wilcox", method="auto")
    except ValueError as error:
        return {
            "n": int(nonzero.size), "statistic": None, "p": None,
            "status": "not_applicable", "reason": str(error),
        }
    return {
        "n": int(nonzero.size), "statistic": float(result.statistic), "p": float(result.pvalue),
        "status": "complete", "reason": None,
    }


def moving_block_bootstrap(rows: list[dict[str, Any]], block_length: int) -> dict[str, Any]:
    """Dependence-aware bootstrap over the complete ordered 40-position sample grid."""
    ordered = sorted(rows, key=lambda row: int(row["sample_id"]))
    position_count = len(ordered)
    if position_count != 40:
        raise ValueError(f"Moving-block bootstrap requires 40 positions, received {position_count}")
    if not 1 <= block_length <= position_count:
        raise ValueError(f"Invalid block length: {block_length}")

    values = np.asarray([
        float(row["paired_effect_mean"]) if row["active"] else np.nan
        for row in ordered
    ], dtype=float)
    observed_mean = float(np.nanmean(values))
    null_values = np.where(np.isnan(values), np.nan, values - observed_mean)
    possible_starts = position_count - block_length + 1
    blocks_per_replicate = math.ceil(position_count / block_length)

    # Reinitialize with the fixed declared seed for every candidate and L so all
    # candidates use the same time-position resamples (common random numbers).
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    starts = rng.integers(
        0, possible_starts, size=(BOOTSTRAP_REPETITIONS, blocks_per_replicate)
    )
    positions = (starts[..., None] + np.arange(block_length)).reshape(BOOTSTRAP_REPETITIONS, -1)
    positions = positions[:, :position_count]
    sampled = values[positions]
    null_sampled = null_values[positions]
    with np.errstate(invalid="ignore"):
        mean_distribution = np.nanmean(sampled, axis=1)
        median_distribution = np.nanmedian(sampled, axis=1)
        null_mean_distribution = np.nanmean(null_sampled, axis=1)
    if np.isnan(mean_distribution).any() or np.isnan(null_mean_distribution).any():
        raise ValueError(f"A length-{block_length} bootstrap replicate contained no active observations")
    mean_ci = np.quantile(mean_distribution, [0.025, 0.975])
    median_ci = np.quantile(median_distribution, [0.025, 0.975])
    exceedances = int(np.sum(null_mean_distribution >= observed_mean))
    p_value = (1 + exceedances) / (BOOTSTRAP_REPETITIONS + 1)
    return {
        "block_length": block_length,
        "possible_block_count": possible_starts,
        "blocks_per_replicate": blocks_per_replicate,
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "observed_mean_D": observed_mean,
        "mean_ci_low": float(mean_ci[0]),
        "mean_ci_high": float(mean_ci[1]),
        "median_ci_low": float(median_ci[0]),
        "median_ci_high": float(median_ci[1]),
        "null_exceedance_count": exceedances,
        "one_sided_null_centered_p": float(p_value),
    }


def power_flag(n: int) -> str:
    if n >= 10:
        return "adequate"
    if n >= 5:
        return "limited"
    return "very_limited"


def aggregate_candidate(
    rows: list[dict[str, Any]],
    inference_sample_ids: set[int],
    inference_sample_mode: str,
) -> dict[str, Any]:
    active = [row for row in rows if row["active"]]
    effects = np.asarray([row["paired_effect_mean"] for row in active], dtype=float)
    focal = np.asarray([row["focal_prediction_delta_abs"] for row in active], dtype=float)
    control_means = np.asarray([row["control_mean_prediction_delta_abs"] for row in active], dtype=float)
    positives = int(np.sum(effects > TIE_TOLERANCE))
    negatives = int(np.sum(effects < -TIE_TOLERANCE))
    ties = int(effects.size - positives - negatives)
    all_sign = exact_sign_test(effects)
    nonoverlap_rows = [row for row in active if int(row["sample_id"]) in inference_sample_ids]
    nonoverlap_effects = [float(row["paired_effect_mean"]) for row in nonoverlap_rows]
    nonoverlap_sign = exact_sign_test(nonoverlap_effects)
    nonoverlap_wilcoxon = signed_rank_test(nonoverlap_effects)
    block2 = moving_block_bootstrap(rows, 2)
    block3 = moving_block_bootstrap(rows, 3)
    block4 = moving_block_bootstrap(rows, 4)
    result = {
        "total_samples": len(rows),
        "active_samples": len(active),
        "inactive_samples": len(rows) - len(active),
        "coverage": len(active) / len(rows),
        "positive_count": positives,
        "negative_count": negatives,
        "tie_count": ties,
        "positive_rate": positives / (positives + negatives) if positives + negatives else math.nan,
        "mean_focal_response": float(np.mean(focal)) if focal.size else math.nan,
        "median_focal_response": float(np.median(focal)) if focal.size else math.nan,
        "mean_control_response": float(np.mean(control_means)) if control_means.size else math.nan,
        "median_control_response": float(np.median(control_means)) if control_means.size else math.nan,
        "mean_D": float(np.mean(effects)) if effects.size else math.nan,
        "median_D": float(np.median(effects)) if effects.size else math.nan,
        "q25_D": float(np.quantile(effects, 0.25)) if effects.size else math.nan,
        "q75_D": float(np.quantile(effects, 0.75)) if effects.size else math.nan,
        "all_sample_sign_n": all_sign["n"],
        "all_sample_sign_positive": all_sign["positive"],
        "all_sample_sign_p": all_sign["p"],
        "all_sample_exact_sign_p": all_sign["p"],
        "all_sample_sign_status": "DESCRIPTIVE / IID-NAIVE",
        "inference_sample_mode": inference_sample_mode,
        "inference_active_samples": len(active),
        "inference_n": len(active),
        "inference_positive_count": positives,
        "primary_effect": "mean_D",
        "primary_block_length": 3,
        "primary_block_p": block3["one_sided_null_centered_p"],
        "primary_block_bh_q": None,
        "primary_p": block3["one_sided_null_centered_p"],
        "primary_q": None,
        "block2_p": block2["one_sided_null_centered_p"],
        "block3_p": block3["one_sided_null_centered_p"],
        "block4_p": block4["one_sided_null_centered_p"],
        "block_bootstrap_mean_ci_low": block3["mean_ci_low"],
        "block_bootstrap_mean_ci_high": block3["mean_ci_high"],
        "block_bootstrap_median_ci_low": block3["median_ci_low"],
        "block_bootstrap_median_ci_high": block3["median_ci_high"],
        "block3_null_exceedance_count": block3["null_exceedance_count"],
        "nonoverlap_n": nonoverlap_sign["n"],
        "nonoverlap_positive_count": nonoverlap_sign["positive"],
        "nonoverlap_sign_p": nonoverlap_sign["p"],
        "nonoverlap_wilcoxon_n": nonoverlap_wilcoxon["n"],
        "nonoverlap_wilcoxon_statistic": nonoverlap_wilcoxon["statistic"],
        "nonoverlap_wilcoxon_p": nonoverlap_wilcoxon["p"],
        "nonoverlap_wilcoxon_status": nonoverlap_wilcoxon["status"],
        "nonoverlap_wilcoxon_reason": nonoverlap_wilcoxon["reason"],
        "power_flag": power_flag(len(active)),
        "inference_power_flag": power_flag(len(active)),
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_estimator": "moving_block_mean_D",
        "bootstrap_ci_low": block3["mean_ci_low"],
        "bootstrap_ci_high": block3["mean_ci_high"],
        "bootstrap_mean_ci_low": block3["mean_ci_low"],
        "bootstrap_mean_ci_high": block3["mean_ci_high"],
    }
    return result


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def dataloader_spans(registry: dict[str, Any], sample_ids: list[int]) -> tuple[list[dict[str, int]], dict[str, Any]]:
    common = registry["common"]
    dataset = registry["datasets"]["ETTh1"]
    seq_len = int(common["seq_len"])
    pred_len = int(common["pred_len"])
    source_root = Path(registry["source_root"])
    loader_path = source_root / "data_provider" / "data_loader.py"
    data_path = source_root / dataset["root_path"] / dataset["data_path"]
    if dataset["data"] != "ETTh1":
        raise ValueError("This audit is predeclared for Dataset_ETT_hour / ETTh1 only")

    # Mirrors Dataset_ETT_hour.__read_data__: border1s[2]. This is the raw row
    # at which the test dataset's context-inclusive slice begins.
    test_border1 = 12 * 30 * 24 + 4 * 30 * 24 - seq_len
    test_border2 = 12 * 30 * 24 + 8 * 30 * 24
    span_length = seq_len + pred_len
    computed_test_length = (test_border2 - test_border1) - span_length + 1
    declared_test_length = int(
        load_json(ROOT / "configs" / "precomputed_intervention_catalog_etth1_40_grid.json")
        ["sample_selection"]["test_split_length"]
    )
    if computed_test_length != declared_test_length:
        raise ValueError(
            f"Dataloader-derived test length {computed_test_length} differs from predeclared {declared_test_length}"
        )
    spans = [
        {
            "sample_id": sample_id,
            "raw_start": test_border1 + sample_id,
            "raw_end": test_border1 + sample_id + span_length - 1,
        }
        for sample_id in sorted(sample_ids)
    ]
    if spans[-1]["raw_end"] >= test_border2:
        raise ValueError("A predeclared sample extends beyond Dataset_ETT_hour's test border")

    starts = [row["raw_start"] for row in spans]
    gaps = np.diff(starts)
    overlap_pairs = sum(
        spans[j]["raw_start"] <= spans[i]["raw_end"]
        for i in range(len(spans)) for j in range(i + 1, len(spans))
    )
    adjacent_overlaps = sum(
        spans[index + 1]["raw_start"] <= spans[index]["raw_end"]
        for index in range(len(spans) - 1)
    )
    selected: list[dict[str, int]] = []
    for row in spans:
        if not selected or row["raw_start"] > selected[-1]["raw_end"]:
            selected.append(row)
    selected_ids = [row["sample_id"] for row in selected]
    local_manifest = load_json(ROOT / "artifacts" / "runs" / LOCAL_RUN_ID / "manifest.json")
    dataset_hash = sha256(data_path) if data_path.exists() else local_manifest["data_sha256"]
    audit = {
        "dataset": "ETTh1",
        "number_of_predeclared_samples": len(spans),
        "dataloader_class": "Dataset_ETT_hour",
        "dataloader_source": str(loader_path),
        "dataloader_source_sha256": sha256(loader_path),
        "dataset_path": str(data_path),
        "dataset_path_currently_available": data_path.exists(),
        "dataset_sha256": dataset_hash,
        "dataset_sha256_source": "current file" if data_path.exists() else f"formal run manifest {LOCAL_RUN_ID}",
        "test_border_rule": "border1s[2] = 12*30*24 + 4*30*24 - seq_len",
        "test_border1": test_border1,
        "test_border2_exclusive": test_border2,
        "dataloader_derived_test_length": computed_test_length,
        "predeclared_test_length": declared_test_length,
        "seq_len": seq_len,
        "pred_len": pred_len,
        "raw_span_rule": "raw_start=test_border1+sample_id; raw_end=raw_start+seq_len+pred_len-1 (inclusive)",
        "raw_span_length_per_sample": span_length,
        "minimum_start_gap": int(np.min(gaps)),
        "median_start_gap": float(np.median(gaps)),
        "number_of_overlapping_sample_pairs": int(overlap_pairs),
        "number_of_adjacent_overlapping_samples": int(adjacent_overlaps),
        "has_overlap": bool(overlap_pairs),
        "sample_spans": spans,
        "nonoverlap_selection_rule": "sort raw_start ascending; take earliest; repeatedly take first raw_start > previous selected raw_end",
        "non_overlapping_sample_ids": selected_ids,
        "N_nonoverlap": len(selected_ids),
    }
    return spans, audit


def local_analysis(
    spans_by_sample: dict[int, dict[str, int]],
    inference_ids: set[int],
    inference_mode: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    local_run = ROOT / "artifacts" / "runs" / LOCAL_RUN_ID
    catalog = load_json(local_run / "evidence_catalog.json")
    public_catalog = load_json(ROOT / "legacy" / "v1" / "artifacts" / "public-data" / "evidence" / "etth1_intervention_catalog.json")
    active_map = {
        (int(case["sample_index"]), int(case["window"]), int(case["edge"]["source"]), int(case["edge"]["target"])):
        bool(case["window_active"])
        for case in public_catalog["cases"]
    }
    variables = list(public_catalog["variables"])
    grouped: dict[tuple[int, int, int], list[dict[str, Any]]] = defaultdict(list)
    for case in catalog["cases"]:
        graph = case["graph"]
        key = (int(graph["window"]), int(graph["source"]), int(graph["target"]))
        grouped[key].append(case)

    case_rows: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    for candidate_index, (candidate, cases) in enumerate(sorted(grouped.items())):
        window_id, source, target = candidate
        cases.sort(key=lambda item: int(item["sample"]["original_index"]))
        if len(cases) != 40:
            raise ValueError(f"Local candidate {candidate} has {len(cases)} cases instead of 40")
        first = cases[0]
        learned_weight = float(first["graph"]["normalized_weight"])
        topk_score = float(first["graph"]["topk_score"])
        pool_sizes: set[int] = set()
        for case in cases:
            sample_id = int(case["sample"]["original_index"])
            raw_edges = case["raw_operands"]["weight_impact"]["edges"]
            edge_by_id: dict[tuple[int, int], dict[str, Any]] = {}
            for edge in raw_edges:
                edge_id = (int(edge["source"]), int(edge["target"]))
                if edge_id in edge_by_id:
                    raise ValueError(f"Duplicate local cached intervention identity {edge_id} in sample {sample_id}, window {window_id}")
                edge_by_id[edge_id] = edge
            focal_edge = edge_by_id[(source, target)]
            controls = [edge for edge_id, edge in sorted(edge_by_id.items()) if edge_id != (source, target)]
            pool_sizes.add(len(controls))
            focal_response = float(focal_edge["prediction_delta_abs"])
            control_values = np.asarray([float(edge["prediction_delta_abs"]) for edge in controls], dtype=float)
            control_mean = float(np.mean(control_values))
            control_median = float(np.median(control_values))
            is_active = bool(active_map[(sample_id, window_id, source, target)] and learned_weight > 0)
            span = spans_by_sample[sample_id]
            case_rows.append({
                "dataset": "ETTh1", "sample_id": sample_id,
                "window_id": window_id, "source_node": source, "target_node": target,
                "active": is_active,
                "focal_prediction_delta_abs": focal_response,
                "unique_control_count": len(controls),
                "control_mean_prediction_delta_abs": control_mean,
                "control_median_prediction_delta_abs": control_median,
                "paired_effect_mean": focal_response - control_mean,
                "paired_effect_median": focal_response - control_median,
                "focal_rank": f"{1 + int(np.sum(control_values > focal_response))}/{len(controls) + 1}",
                "fraction_controls_below_focal": float(np.mean(control_values < focal_response)),
                "raw_start": span["raw_start"], "raw_end": span["raw_end"],
                "in_nonoverlap_subset": sample_id in inference_ids,
            })
        candidate_rows = [
            row for row in case_rows
            if row["window_id"] == window_id and row["source_node"] == source and row["target_node"] == target
        ]
        summary = aggregate_candidate(candidate_rows, inference_ids, inference_mode)
        family_rows.append({
            "dataset": "ETTh1", "window_id": window_id, "source_node": source, "target_node": target,
            "source_name": variables[source], "target_name": variables[target],
            "learned_edge_weight": learned_weight, "topk_score": topk_score,
            "unique_control_count": min(pool_sizes) if len(pool_sizes) == 1 else None,
            **summary,
        })

    adjusted = benjamini_hochberg([float(row["primary_block_p"]) for row in family_rows])
    for row, q_value in zip(family_rows, adjusted):
        row["primary_block_bh_q"] = float(q_value)
        row["primary_q"] = float(q_value)
    candidates = [
        {
            "window_id": row["window_id"], "source_node": row["source_node"], "target_node": row["target_node"],
            "source_name": row["source_name"], "target_name": row["target_name"],
            "learned_edge_weight": row["learned_edge_weight"], "topk_score": row["topk_score"],
            "unique_control_count": row["unique_control_count"],
        }
        for row in family_rows
    ]
    return case_rows, family_rows, candidates


def reconstruct_global_cache() -> tuple[bool, str | None, list[dict[str, Any]], dict[tuple[int, int], dict[str, Any]]]:
    global_run = ROOT / "artifacts" / "runs" / GLOBAL_RUN_ID
    catalog = load_json(global_run / "evidence_catalog.json")
    config = load_json(ROOT / "configs" / "global_edge_intervention_etth1.json")
    relation_metadata: dict[tuple[int, int], dict[str, Any]] = {}
    sample_metrics: dict[int, dict[tuple[int, int], float]] = defaultdict(dict)
    conflicts: list[str] = []

    def add_relation(edge: tuple[int, int], windows: list[int], mean_weight: float) -> None:
        record = {"edge": edge, "windows": tuple(int(value) for value in windows), "mean_weight": float(mean_weight)}
        prior = relation_metadata.get(edge)
        if prior is not None and (prior["windows"] != record["windows"] or prior["mean_weight"] != record["mean_weight"]):
            conflicts.append(f"metadata conflict for global edge {edge}")
        relation_metadata[edge] = record

    def add_metric(sample: int, edge: tuple[int, int], value: float) -> None:
        prior = sample_metrics[sample].get(edge)
        if prior is not None and prior != float(value):
            conflicts.append(f"metric conflict for global sample {sample}, edge {edge}")
        sample_metrics[sample][edge] = float(value)

    for case in catalog["cases"]:
        sample = int(case["sample"])
        focal_edge = tuple(int(value) for value in case["edge"])
        add_relation(focal_edge, case["retained_windows"], float(case["mean_weight"]))
        add_metric(sample, focal_edge, float(case["metrics"]["prediction_delta_abs"]))
        controls_path = global_run / Path(case["controls_file"].replace("\\", "/"))
        for control in load_json(controls_path):
            edge = tuple(int(value) for value in control["edge"])
            add_relation(edge, control["windows"], float(control["mean_weight"]))
            add_metric(sample, edge, float(control["prediction_delta_abs"]))

    if conflicts:
        return False, "; ".join(sorted(set(conflicts))), [], relation_metadata

    nearest = int(config["control_matching"]["nearest_relations"])
    reconstructed: list[dict[str, Any]] = []
    missing: list[str] = []
    for case in catalog["cases"]:
        sample = int(case["sample"])
        focal_edge = tuple(int(value) for value in case["edge"])
        focal = relation_metadata[focal_edge]
        eligible = [record for edge, record in relation_metadata.items() if edge != focal_edge]
        eligible.sort(key=lambda record: (
            abs(len(record["windows"]) - len(focal["windows"])),
            abs(float(record["mean_weight"]) - float(focal["mean_weight"])),
            record["edge"],
        ))
        pool = eligible[:nearest]
        pool_values = []
        for control in pool:
            edge = control["edge"]
            if edge not in sample_metrics[sample]:
                missing.append(f"sample {sample}, focal {focal_edge}, missing control {edge}")
            else:
                pool_values.append(sample_metrics[sample][edge])
        if len(pool_values) != nearest:
            continue
        reconstructed.append({
            **case,
            "unique_control_edges": [list(record["edge"]) for record in pool],
            "unique_control_values": pool_values,
        })
    if missing:
        return False, "existing cache cannot reconstruct every production-eligible unique control: " + "; ".join(missing), [], relation_metadata
    return True, None, reconstructed, relation_metadata


def global_analysis(
    spans_by_sample: dict[int, dict[str, int]],
    inference_ids: set[int],
    inference_mode: str,
    variables: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    available, reason, reconstructed, _ = reconstruct_global_cache()
    if not available:
        return [], [], reason
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for case in reconstructed:
        edge = tuple(int(value) for value in case["edge"])
        controls = np.asarray(case["unique_control_values"], dtype=float)
        focal = float(case["metrics"]["prediction_delta_abs"])
        sample_id = int(case["sample"])
        span = spans_by_sample[sample_id]
        grouped[edge].append({
            "dataset": "ETTh1", "sample_id": sample_id,
            "source_node": edge[0], "target_node": edge[1],
            "active": bool(case["affected_exposed_windows"] and float(case["mean_weight"]) > 0),
            "focal_prediction_delta_abs": focal,
            "unique_control_count": int(controls.size),
            "control_mean_prediction_delta_abs": float(np.mean(controls)),
            "control_median_prediction_delta_abs": float(np.median(controls)),
            "paired_effect_mean": focal - float(np.mean(controls)),
            "paired_effect_median": focal - float(np.median(controls)),
            "focal_rank": f"{1 + int(np.sum(controls > focal))}/{controls.size + 1}",
            "fraction_controls_below_focal": float(np.mean(controls < focal)),
            "raw_start": span["raw_start"], "raw_end": span["raw_end"],
            "in_nonoverlap_subset": sample_id in inference_ids,
            "mean_weight": float(case["mean_weight"]),
        })
    summaries: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    for index, (edge, rows) in enumerate(sorted(grouped.items())):
        rows.sort(key=lambda row: int(row["sample_id"]))
        all_rows.extend(rows)
        summary = aggregate_candidate(rows, inference_ids, inference_mode)
        summaries.append({
            "dataset": "ETTh1", "source_node": edge[0], "target_node": edge[1],
            "source_name": variables[edge[0]], "target_name": variables[edge[1]],
            "learned_edge_weight": rows[0]["mean_weight"],
            "unique_control_count": rows[0]["unique_control_count"],
            **summary,
        })
    adjusted = benjamini_hochberg([float(row["primary_block_p"]) for row in summaries])
    for row, q_value in zip(summaries, adjusted):
        row["primary_block_bh_q"] = float(q_value)
        row["primary_q"] = float(q_value)
    return summaries, all_rows, None


def correlation_result(x: list[float], y: list[float]) -> dict[str, float]:
    result = spearmanr(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
    return {"rho": float(result.statistic), "p": float(result.pvalue)}


def relation_label(row: dict[str, Any], local: bool) -> str:
    prefix = f"w{row['window_id']} " if local else ""
    return f"{prefix}{row['source_node']}->{row['target_node']}"


def evidence_classification(row: dict[str, Any]) -> str:
    if row["mean_D"] > 0 and row["primary_q"] < 0.05:
        return "cross-sample supported"
    if row["mean_D"] > 0 and row["positive_rate"] > 0.5:
        return "directional but not corrected-supported"
    return "no consistent evidence"


def block_length_stability(rows: list[dict[str, Any]], local: bool) -> tuple[str, list[str]]:
    unstable = []
    for row in rows:
        decisions = [row[f"block{length}_p"] < 0.05 for length in (2, 3, 4)]
        if len(set(decisions)) > 1:
            unstable.append(
                f"{relation_label(row, local)} (L2={fmt(row['block2_p'])}, "
                f"L3={fmt(row['block3_p'])}, L4={fmt(row['block4_p'])})"
            )
    return ("YES" if not unstable else "MIXED"), unstable


def direction_sensitivity(rows: list[dict[str, Any]], local: bool) -> tuple[list[str], list[str]]:
    opposite: list[str] = []
    neutral: list[str] = []
    for row in rows:
        block_direction = 1 if row["mean_D"] > 0 else (-1 if row["mean_D"] < 0 else 0)
        nonoverlap_rate = (
            row["nonoverlap_positive_count"] / row["nonoverlap_n"]
            if row["nonoverlap_n"] else 0.5
        )
        nonoverlap_direction = 1 if nonoverlap_rate > 0.5 else (-1 if nonoverlap_rate < 0.5 else 0)
        if block_direction * nonoverlap_direction == -1:
            opposite.append(
                f"{relation_label(row, local)} (mean D={row['mean_D']:+.8f}; "
                f"non-overlap={row['nonoverlap_positive_count']}/{row['nonoverlap_n']})"
            )
        elif block_direction != nonoverlap_direction:
            neutral.append(
                f"{relation_label(row, local)} (non-overlap direction neutral at "
                f"{row['nonoverlap_positive_count']}/{row['nonoverlap_n']})"
            )
    return opposite, neutral


def markdown_summary(
    local_rows: list[dict[str, Any]],
    global_rows: list[dict[str, Any]],
    global_reason: str | None,
    overlap: dict[str, Any],
    correlations: dict[str, Any],
) -> str:
    ordered = sorted(local_rows, key=lambda row: (-float(row["mean_D"]), row["window_id"], row["source_node"], row["target_node"]))
    lines = [
        "# DGraInsight Cross-Sample Evidence Validation V2",
        "",
        "| Window | Edge | Active | Positive | Mean D | Median D | Block p | BH q | L2 p | L4 p | Non-overlap |",
        "|---:|:---|:---:|:---:|---:|---:|---:|---:|---:|---:|:---|",
    ]
    for row in ordered:
        lines.append(
            f"| {row['window_id']} | {row['source_node']}->{row['target_node']} "
            f"({row['source_name']}→{row['target_name']}) | {row['active_samples']}/{row['total_samples']} | "
            f"{row['positive_count']}/{row['positive_count'] + row['negative_count']} ({row['positive_rate']:.1%}) | "
            f"{row['mean_D']:+.8f} | {row['median_D']:+.8f} | {fmt(row['primary_block_p'])} | "
            f"{fmt(row['primary_block_bh_q'])} | {fmt(row['block2_p'])} | {fmt(row['block4_p'])} | "
            f"{row['nonoverlap_positive_count']}/{row['nonoverlap_n']}; p={fmt(row['nonoverlap_sign_p'])} |"
        )

    local_raw_lt_05 = sum(float(row["primary_block_p"]) < 0.05 for row in local_rows)
    local_q_lt_05 = sum(float(row["primary_block_bh_q"]) < 0.05 for row in local_rows)
    global_raw_lt_05 = sum(float(row["primary_block_p"]) < 0.05 for row in global_rows)
    global_q_lt_05 = sum(float(row["primary_block_bh_q"]) < 0.05 for row in global_rows)
    local_focus = next(
        row for row in local_rows
        if row["window_id"] == 6 and row["source_node"] == 0 and row["target_node"] == 4
    )
    global_focus = next(
        row for row in global_rows if row["source_node"] == 0 and row["target_node"] == 2
    )
    local_stability, local_unstable = block_length_stability(local_rows, True)
    global_stability, global_unstable = block_length_stability(global_rows, False)
    stability = "YES" if local_stability == global_stability == "YES" else "MIXED"
    unstable_text = "; ".join(local_unstable + global_unstable) or "no candidate crosses the raw p=.05 decision boundary"
    local_opposite, local_neutral = direction_sensitivity(local_rows, True)
    global_opposite, global_neutral = direction_sensitivity(global_rows, False)
    opposite = local_opposite + global_opposite
    neutral = local_neutral + global_neutral
    direction_answer = "YES" if not opposite else "MIXED"
    supported_labels = [
        relation_label(row, True) for row in local_rows
        if row["evidence_classification"] == "cross-sample supported"
    ] + [
        relation_label(row, False) for row in global_rows
        if row["evidence_classification"] == "cross-sample supported"
    ]
    if opposite:
        direction_details = (
            f"Corrected-supported relations {', '.join(supported_labels)} retain the same positive direction; "
            f"opposite-direction sensitivity occurs for: {'; '.join(opposite)}"
        )
        if neutral:
            direction_details += f"; neutral cases: {'; '.join(neutral)}"
    else:
        direction_details = "; ".join(neutral) or "all candidate directions agree"
    lines.extend([
        "",
        "## Inference metadata",
        "",
        "- Primary effect: mean D across all active observations in the 40 predeclared positions.",
        "- Robust descriptive effect: median D.",
        "- Primary test: one-sided null-centered moving-block bootstrap.",
        f"- B_bootstrap = {BOOTSTRAP_REPETITIONS}; seed = {BOOTSTRAP_SEED}.",
        f"- Raw span = {overlap['raw_span_length_per_sample']}; minimum sample start gap = {overlap['minimum_start_gap']}.",
        f"- Primary block length = ceil({overlap['raw_span_length_per_sample']}/{overlap['minimum_start_gap']}) = 3 samples.",
        "- Sensitivity block lengths: L=2 and L=4.",
        "- Blocks are non-circular consecutive sample-position blocks; inactive positions stay inactive after resampling and never contribute D=0.",
        f"- Conservative non-overlap sensitivity uses the fixed {overlap['N_nonoverlap']}-sample subset: {overlap['non_overlapping_sample_ids']}.",
        "- All-sample exact sign tests are retained as DESCRIPTIVE / IID-NAIVE only.",
        "",
        "## Structural Weight vs Cross-sample Evidence",
        "",
        f"- rho_weight_vs_median_D = {fmt(correlations['weight_vs_median_D']['rho'])}; p = {fmt(correlations['weight_vs_median_D']['p'])}",
        f"- rho_weight_vs_positive_rate = {fmt(correlations['weight_vs_positive_rate']['rho'])}; p = {fmt(correlations['weight_vs_positive_rate']['p'])}",
        "- These are descriptive associations only.",
        "",
        "## Global family",
        "",
    ])
    if global_reason:
        lines.append(f"GLOBAL ANALYSIS NOT AVAILABLE FROM EXISTING CACHE: {global_reason}")
    else:
        lines.extend([
            "| Edge | Active | Positive | Mean D | Median D | Block p | BH q | L2 p | L4 p | Non-overlap |",
            "|:---|:---:|:---:|---:|---:|---:|---:|---:|---:|:---|",
        ])
        for row in sorted(global_rows, key=lambda item: -float(item["median_D"])):
            lines.append(
                f"| {row['source_node']}->{row['target_node']} ({row['source_name']}→{row['target_name']}) | "
                f"{row['active_samples']}/{row['total_samples']} | "
                f"{row['positive_count']}/{row['positive_count'] + row['negative_count']} ({row['positive_rate']:.1%}) | "
                f"{row['mean_D']:+.8f} | {row['median_D']:+.8f} | {fmt(row['primary_block_p'])} | "
                f"{fmt(row['primary_block_bh_q'])} | {fmt(row['block2_p'])} | {fmt(row['block4_p'])} | "
                f"{row['nonoverlap_positive_count']}/{row['nonoverlap_n']}; p={fmt(row['nonoverlap_sign_p'])} |"
            )

    lines.extend([
        "",
        "## Required answers",
        "",
        f"- Q1: LOCAL raw block p < .05 = {local_raw_lt_05}; BH q < .05 = {local_q_lt_05}.",
        f"- Q2: GLOBAL raw block p < .05 = {global_raw_lt_05}; BH q < .05 = {global_q_lt_05}.",
        f"- Q3: global 0->2: mean D = {global_focus['mean_D']:+.8f}; median D = {global_focus['median_D']:+.8f}; "
        f"positive = {global_focus['positive_count']}/{global_focus['positive_count'] + global_focus['negative_count']}; "
        f"block p = {fmt(global_focus['primary_block_p'])}; BH q = {fmt(global_focus['primary_block_bh_q'])}; "
        f"L2 p = {fmt(global_focus['block2_p'])}; L4 p = {fmt(global_focus['block4_p'])}; "
        f"non-overlap p = {fmt(global_focus['nonoverlap_sign_p'])}; block-mean CI95 = "
        f"[{global_focus['block_bootstrap_mean_ci_low']:+.8f}, {global_focus['block_bootstrap_mean_ci_high']:+.8f}].",
        f"- Q4: local w6 0->4: mean D = {local_focus['mean_D']:+.8f}; median D = {local_focus['median_D']:+.8f}; "
        f"positive = {local_focus['positive_count']}/{local_focus['positive_count'] + local_focus['negative_count']}; "
        f"block p = {fmt(local_focus['primary_block_p'])}; BH q = {fmt(local_focus['primary_block_bh_q'])}; "
        f"L2 p = {fmt(local_focus['block2_p'])}; L4 p = {fmt(local_focus['block4_p'])}; "
        f"non-overlap p = {fmt(local_focus['nonoverlap_sign_p'])}; block-mean CI95 = "
        f"[{local_focus['block_bootstrap_mean_ci_low']:+.8f}, {local_focus['block_bootstrap_mean_ci_high']:+.8f}].",
        f"- Q5: {stability}. {unstable_text}.",
        f"- Q6: {direction_answer}. {direction_details}.",
        "- Q7: classifications are listed below.",
        "",
        "| Family | Relation | Classification |",
        "|:---|:---|:---|",
    ])
    for row in sorted(local_rows, key=lambda item: (item["window_id"], item["source_node"], item["target_node"])):
        lines.append(f"| Local | {relation_label(row, True)} | {row['evidence_classification']} |")
    for row in sorted(global_rows, key=lambda item: (item["source_node"], item["target_node"])):
        lines.append(f"| Global | {relation_label(row, False)} | {row['evidence_classification']} |")
    lines.extend([
        "",
        "RESULTS ONLY",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_path = ROOT / "configs" / "phase1_registry.json"
    local_config_path = ROOT / "configs" / "precomputed_intervention_catalog_etth1_40_grid.json"
    evidence_config_path = ROOT / "configs" / "precomputed_evidence_catalog_etth1_40_grid.json"
    global_config_path = ROOT / "configs" / "global_edge_intervention_etth1.json"
    registry = load_json(registry_path)
    local_config = load_json(local_config_path)
    sample_ids = [int(value) for value in local_config["sample_indices_override"]["ETTh1"]]
    spans, overlap = dataloader_spans(registry, sample_ids)
    spans_by_sample = {row["sample_id"]: row for row in spans}
    inference_ids = set(overlap["non_overlapping_sample_ids"])
    inference_mode = "moving_block_bootstrap_all_predeclared"
    derived_block_length = math.ceil(
        overlap["raw_span_length_per_sample"] / overlap["minimum_start_gap"]
    )
    if derived_block_length != 3:
        raise ValueError(f"Expected the predeclared primary block length 3, derived {derived_block_length}")
    overlap["primary_inference_mode"] = inference_mode
    overlap["primary_effect"] = "mean_D over active observations only"
    overlap["primary_block_length"] = derived_block_length
    overlap["block_length_derivation"] = (
        f"ceil(raw_span_length_per_sample / minimum_start_gap) = "
        f"ceil({overlap['raw_span_length_per_sample']} / {overlap['minimum_start_gap']}) = {derived_block_length}"
    )
    overlap["block_length_sensitivity"] = [2, 4]
    overlap["moving_block_rule"] = (
        "all non-circular consecutive sample-position blocks; sample blocks with replacement, "
        "concatenate and truncate to 40 positions; preserve inactive positions; compute D only for active positions"
    )
    overlap["bootstrap_repetitions"] = BOOTSTRAP_REPETITIONS
    overlap["bootstrap_seed"] = BOOTSTRAP_SEED
    overlap["primary_null"] = "H0: E[D] <= 0"
    overlap["primary_alternative"] = "H1: E[D] > 0"
    overlap["primary_p_formula"] = "(1 + count(T_null_star >= observed_mean_D)) / (B + 1)"

    local_cases, local_rows, candidates = local_analysis(spans_by_sample, inference_ids, inference_mode)
    variables = load_json(ROOT / "legacy" / "v1" / "artifacts" / "public-data" / "evidence" / "etth1_intervention_catalog.json")["variables"]
    global_rows, global_case_rows, global_reason = global_analysis(
        spans_by_sample, inference_ids, inference_mode, variables
    )
    for row in local_rows:
        row["evidence_classification"] = evidence_classification(row)
    for row in global_rows:
        row["evidence_classification"] = evidence_classification(row)

    correlations = {
        "weight_vs_median_D": correlation_result(
            [float(row["learned_edge_weight"]) for row in local_rows],
            [float(row["median_D"]) for row in local_rows],
        ),
        "weight_vs_positive_rate": correlation_result(
            [float(row["learned_edge_weight"]) for row in local_rows],
            [float(row["positive_rate"]) for row in local_rows],
        ),
    }
    candidate_family = {
        "dataset": "ETTh1",
        "old_sample_level_cases": len(local_cases),
        "new_unique_local_edge_window_candidates": len(candidates),
        "candidate_selection_uses_intervention_outcomes": False,
        "candidate_selection_answer": "NO",
        "candidate_selection_basis": "pre-intervention retained-graph frequency and retained learned/top-K score",
        "candidate_selection_config": str(local_config_path),
        "candidate_run_id": local_config["candidate_run_id"],
        "local_evidence_run_id": LOCAL_RUN_ID,
        "local_candidates": candidates,
        "local_hypothesis_identity": ["window_id", "source_node", "target_node"],
        "local_BH_family_size": len(candidates),
        "primary_inference": {
            "effect": "mean_D",
            "method": "one-sided null-centered moving-block bootstrap",
            "block_length": derived_block_length,
            "block_length_reason": overlap["block_length_derivation"],
            "sensitivity_block_lengths": [2, 4],
            "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
            "seed": BOOTSTRAP_SEED,
            "local_BH_input": "eight primary_block_p values",
            "global_BH_input": "four primary_block_p values",
        },
        "nonoverlap_role": "conservative sensitivity analysis",
        "global_evidence_run_id": GLOBAL_RUN_ID,
        "global_analysis_available": global_reason is None,
        "global_unavailable_reason": global_reason,
        "global_hypothesis_identity": ["source_node", "target_node"],
        "global_BH_family_size": len(global_rows),
        "input_fingerprints": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in [registry_path, local_config_path, evidence_config_path, global_config_path]
        },
    }

    (OUTPUT_DIR / "candidate_family.json").write_text(
        json.dumps(candidate_family, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (OUTPUT_DIR / "sample_overlap_audit.json").write_text(
        json.dumps(overlap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_csv(OUTPUT_DIR / "per_sample_paired_effects.csv", local_cases)
    write_csv(OUTPUT_DIR / "cross_sample_local_evidence.csv", local_rows)
    if global_reason:
        write_csv(
            OUTPUT_DIR / "cross_sample_global_evidence.csv",
            [{"status": "GLOBAL ANALYSIS NOT AVAILABLE FROM EXISTING CACHE", "reason": global_reason}],
            ["status", "reason"],
        )
    else:
        write_csv(OUTPUT_DIR / "cross_sample_global_evidence.csv", global_rows)
        write_csv(OUTPUT_DIR / "per_sample_global_paired_effects.csv", global_case_rows)

    summary = markdown_summary(local_rows, global_rows, global_reason, overlap, correlations)
    (OUTPUT_DIR / "cross_sample_validation_summary.md").write_text(summary, encoding="utf-8")
    machine_summary = {
        "version": 2,
        "dataset": "ETTh1",
        "inference_sample_mode": inference_mode,
        "primary_effect": "mean_D",
        "primary_block_length": derived_block_length,
        "block_length_sensitivity": [2, 4],
        "bootstrap_repetitions": BOOTSTRAP_REPETITIONS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "local_family": local_rows,
        "global_family": global_rows,
        "global_unavailable_reason": global_reason,
        "structural_weight_correlations": correlations,
    }
    (OUTPUT_DIR / "cross_sample_validation_results.json").write_text(
        json.dumps(machine_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "output_dir": str(OUTPUT_DIR),
        "local_hypotheses": len(local_rows),
        "global_hypotheses": len(global_rows),
        "N_nonoverlap": overlap["N_nonoverlap"],
        "global_available": global_reason is None,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import math
from typing import Any, Callable, Mapping, Optional, Sequence

import numpy as np


class InferenceUnavailable(ValueError):
    pass


Engine = Callable[[Sequence[Optional[float]], Mapping[str, Any]], dict[str, Any]]
_ENGINES: dict[str, Engine] = {}


def register_engine(name: str) -> Callable[[Engine], Engine]:
    def decorator(function: Engine) -> Engine:
        if name in _ENGINES:
            raise RuntimeError(f"Duplicate inference engine: {name}")
        _ENGINES[name] = function
        return function
    return decorator


def infer_candidate(
    values: Sequence[float | None],
    protocol: Mapping[str, Any],
    dependence_audit: Mapping[str, Any],
) -> dict[str, Any]:
    method = str(protocol.get("primary_test", "unavailable"))
    classification = dependence_audit.get("classification")
    if classification == "unknown_dependence" and method != "unavailable":
        return unavailable_inference("Dependence is unknown; no external protocol was declared.")
    if method == "moving_block_bootstrap_mean_D" and classification != "overlapping_time_windows":
        return unavailable_inference("Moving-block inference requires the matching overlapping-time-window protocol.")
    if method == "exact_sign_flip_mean_D" and classification != "non_overlapping_time_units":
        return unavailable_inference("Exact test-level sign-flip requires predeclared non-overlapping units.")
    if method == "unavailable":
        return unavailable_inference(str(protocol.get("reason") or "No validated primary inference protocol is available."))
    engine = _ENGINES.get(method)
    if engine is None:
        return unavailable_inference(f"Unknown inference engine: {method}")
    active = [float(value) for value in values if value is not None]
    minimum = int(protocol.get("minimum_active_units", 2))
    if len(active) < minimum:
        return unavailable_inference(f"Only {len(active)} active units; at least {minimum} are required.")
    try:
        return engine(values, protocol)
    except (InferenceUnavailable, ValueError, FloatingPointError) as exc:
        return unavailable_inference(str(exc))


def unavailable_inference(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "inference_unit": "candidate_relation_across_predeclared_units",
        "method": None,
        "null": None,
        "alternative": "mean_D > 0",
        "observed_statistic": None,
        "raw_p": None,
        "settings": {},
        "diagnostics": {},
        "reason": reason,
    }


@register_engine("moving_block_bootstrap_mean_D")
def moving_block_bootstrap_mean_D(values: Sequence[float | None], protocol: Mapping[str, Any]) -> dict[str, Any]:
    array = np.asarray([np.nan if value is None else float(value) for value in values], dtype=float)
    block_length = int(protocol["block_length"])
    repetitions = int(protocol.get("repetitions", 10_000))
    seed = int(protocol.get("seed", 20260830))
    if not 1 <= block_length <= array.size:
        raise InferenceUnavailable("Invalid moving-block length")
    observed = float(np.nanmean(array))
    centered = np.where(np.isnan(array), np.nan, array - observed)
    possible_starts = array.size - block_length + 1
    blocks_per_replicate = math.ceil(array.size / block_length)
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, possible_starts, size=(repetitions, blocks_per_replicate))
    positions = (starts[..., None] + np.arange(block_length)).reshape(repetitions, -1)[:, :array.size]
    sampled = array[positions]
    null_sampled = centered[positions]
    with np.errstate(invalid="ignore"):
        means = np.nanmean(sampled, axis=1)
        medians = np.nanmedian(sampled, axis=1)
        null_means = np.nanmean(null_sampled, axis=1)
    if np.isnan(means).any() or np.isnan(null_means).any():
        raise InferenceUnavailable("A block-bootstrap replicate contained no active unit")
    exceedances = int(np.count_nonzero(null_means >= observed))
    return {
        "status": "complete",
        "inference_unit": "candidate_relation_across_predeclared_units",
        "method": "one_sided_null_centered_moving_block_bootstrap_on_mean_D",
        "null": "mean D <= 0 under a null-centered ordered-position resampling distribution",
        "alternative": "mean_D > 0",
        "observed_statistic": observed,
        "raw_p": float((1 + exceedances) / (repetitions + 1)),
        "settings": {"block_length": block_length, "repetitions": repetitions, "seed": seed, "plus_one_correction": True},
        "diagnostics": {
            "planned_positions": int(array.size),
            "active_positions": int(np.count_nonzero(~np.isnan(array))),
            "possible_block_count": possible_starts,
            "blocks_per_replicate": blocks_per_replicate,
            "null_exceedance_count": exceedances,
            "bootstrap_mean_CI95": np.quantile(means, [0.025, 0.975]).astype(float).tolist(),
            "bootstrap_median_CI95": np.quantile(medians, [0.025, 0.975]).astype(float).tolist(),
        },
        "reason": None,
    }


@register_engine("exact_sign_flip_mean_D")
def exact_sign_flip_mean_D(values: Sequence[float | None], protocol: Mapping[str, Any]) -> dict[str, Any]:
    active = np.asarray([float(value) for value in values if value is not None], dtype=float)
    n = int(active.size)
    maximum = int(protocol.get("maximum_exact_units", 20))
    if n > maximum:
        raise InferenceUnavailable(f"Exact enumeration is capped at {maximum} units")
    configurations = 2 ** n
    masks = np.arange(configurations, dtype=np.uint64)[:, None]
    bits = np.arange(n, dtype=np.uint64)
    signs = np.where(((masks >> bits) & 1) == 1, 1.0, -1.0)
    observed = float(np.mean(active))
    distribution = np.mean(signs * active.reshape(1, -1), axis=1)
    exceedances = int(np.count_nonzero(distribution >= observed))
    return {
        "status": "complete",
        "inference_unit": "candidate_relation_across_predeclared_units",
        "method": "one_sided_exact_sign_flip_on_mean_D",
        "null": "sign symmetry of test-level D around zero",
        "alternative": "mean_D > 0",
        "observed_statistic": observed,
        "raw_p": float(exceedances / configurations),
        "settings": {"enumeration": "complete", "sign_configurations": configurations, "plus_one_correction": False},
        "diagnostics": {"active_units": n, "null_exceedance_count": exceedances},
        "reason": None,
    }


def effect_summary(values: Sequence[float | None]) -> dict[str, Any]:
    active = np.asarray([float(value) for value in values if value is not None], dtype=float)
    positive = int(np.count_nonzero(active > 0))
    negative = int(np.count_nonzero(active < 0))
    zero = int(active.size - positive - negative)
    return {
        "mean_D": float(np.mean(active)) if active.size else None,
        "median_D": float(np.median(active)) if active.size else None,
        "positive_count": positive,
        "negative_count": negative,
        "zero_count": zero,
        "positive_fraction": float(positive / active.size) if active.size else None,
        "SD": float(np.std(active, ddof=1)) if active.size > 1 else None,
        "Q1": float(np.quantile(active, 0.25)) if active.size else None,
        "Q3": float(np.quantile(active, 0.75)) if active.size else None,
    }


def exact_sign_test(values: Sequence[float]) -> tuple[int, int, float]:
    nonzero = [value for value in values if value != 0]
    positive = sum(value > 0 for value in nonzero)
    n = len(nonzero)
    p = sum(math.comb(n, count) for count in range(positive, n + 1)) / (2 ** n) if n else 1.0
    return n, positive, float(p)


def sensitivity_results(
    values: Sequence[float | None],
    names: Sequence[str],
    primary_protocol: Mapping[str, Any],
    dependence_audit: Mapping[str, Any],
) -> list[dict[str, Any]]:
    active = np.asarray([float(value) for value in values if value is not None], dtype=float)
    results: list[dict[str, Any]] = []
    for name in names:
        if name.startswith("block_length_"):
            length = int(name.rsplit("_", 1)[1])
            protocol = {**primary_protocol, "block_length": length}
            outcome = infer_candidate(values, protocol, dependence_audit)
            results.append({"name": name, "role": "sensitivity", "method": outcome.get("method"), "statistic": outcome.get("observed_statistic"), "p": outcome.get("raw_p"), "settings": outcome.get("settings", {}), "interpretation_boundary": "Sensitivity only; does not replace the primary result."})
        elif name == "exact_sign_test":
            n, positive, p = exact_sign_test(active.tolist())
            results.append({"name": name, "role": "sensitivity", "method": "one_sided_exact_sign_test", "statistic": positive, "p": p, "settings": {"effective_n": n}, "interpretation_boundary": "Direction-count sensitivity only."})
        elif name == "leave_one_out":
            means = [(float(active.sum()) - value) / (active.size - 1) for value in active] if active.size > 1 else []
            results.append({"name": name, "role": "sensitivity", "method": "leave_one_out_mean_D", "statistic": min(means) if means else None, "value": {"minimum_mean_D": min(means), "maximum_mean_D": max(means)} if means else None, "settings": {}, "interpretation_boundary": "Sensitivity only."})
        elif name == "temporal_interleaved_subsets":
            a, b = active[::2], active[1::2]
            results.append({"name": name, "role": "sensitivity", "method": "interleaved_subset_mean_D", "statistic": None, "value": {"subset_A_mean_D": float(np.mean(a)) if a.size else None, "subset_B_mean_D": float(np.mean(b)) if b.size else None}, "settings": {"assignment": "even/odd predeclared order"}, "interpretation_boundary": "Temporal subset sensitivity only."})
        elif name == "bootstrap_mean_CI":
            if not active.size:
                results.append({"name": name, "role": "sensitivity", "method": "iid_test_level_percentile_bootstrap_mean_D", "statistic": None, "CI": None, "settings": {}, "interpretation_boundary": "Unavailable because there are no active units."})
                continue
            repetitions = int(primary_protocol.get("sensitivity_repetitions", 10_000))
            seed = int(primary_protocol.get("sensitivity_seed", 20260830))
            rng = np.random.default_rng(seed)
            indices = rng.integers(0, active.size, size=(repetitions, active.size))
            ci = np.quantile(np.mean(active[indices], axis=1), [0.025, 0.975]).astype(float).tolist()
            results.append({"name": name, "role": "sensitivity", "method": "iid_test_level_percentile_bootstrap_mean_D", "statistic": float(np.mean(active)), "CI": ci, "settings": {"repetitions": repetitions, "seed": seed}, "interpretation_boundary": "Sensitivity only; not the primary p-value."})
        elif name == "trimmed_mean":
            ordered = np.sort(active)
            trim = int(math.floor(0.1 * ordered.size))
            kept = ordered[trim: ordered.size - trim] if trim else ordered
            value = float(np.mean(kept)) if kept.size else None
            results.append({"name": name, "role": "sensitivity", "method": "ten_percent_trimmed_mean_D", "statistic": value, "value": value, "settings": {"trim_each_tail": trim}, "interpretation_boundary": "Descriptive sensitivity only."})
        elif name == "median_ci":
            results.append({"name": name, "role": "sensitivity", "method": "moving_block_bootstrap_median_D", "statistic": float(np.median(active)) if active.size else None, "CI": None, "settings": {"reported_by_primary_diagnostics": True}, "interpretation_boundary": "Sensitivity only; the primary statistic remains mean D."})
        elif name == "non_overlap_subset":
            results.append({"name": name, "role": "sensitivity", "method": "predeclared_non_overlap_subset", "statistic": None, "value": None, "settings": {"subset_source": "frozen_protocol_artifact"}, "interpretation_boundary": "Conservative sensitivity only; values are attached by a frozen-artifact importer when available."})
        elif name == "outlier_sensitivity":
            value = {"drop_min_mean_D": float(np.mean(np.delete(active, np.argmin(active)))) if active.size > 1 else None, "drop_max_mean_D": float(np.mean(np.delete(active, np.argmax(active)))) if active.size > 1 else None}
            results.append({"name": name, "role": "sensitivity", "method": "leave_extreme_out_mean_D", "statistic": None, "value": value, "settings": {}, "interpretation_boundary": "Outlier sensitivity only."})
    return results

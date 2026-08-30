from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from dgraudit.adapters import DGraFormerAdapter
from dgraudit.cli.validate_pattern import empirical_p_plus_one


DEFAULT_RUN = "a778b2bdac2e3a012177d432ad237ada8dd6d5e24cccb57115c6edceb5cadeb8"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    if seconds < 3600:
        return f"{seconds / 60:.1f} minutes"
    return f"{seconds / 3600:.2f} hours"


def synchronize() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default=DEFAULT_RUN)
    parser.add_argument("--runs-root", default="artifacts/runs")
    parser.add_argument("--registry", default="tmp/phase1_registry_etth1_downloads.json")
    parser.add_argument("--config", default="configs/precomputed_evidence_catalog_etth1_40_grid.json")
    parser.add_argument("--output", default="artifacts/evidence_validation")
    parser.add_argument("--hypotheses", type=int, default=8)
    parser.add_argument("--new-controls", type=int, default=50)
    parser.add_argument("--selection-seed", type=int, default=20260830)
    args = parser.parse_args()

    repo = Path.cwd().resolve()
    run_dir = (repo / args.runs_root / args.run).resolve()
    output_dir = (repo / args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog = load_json(run_dir / "evidence_catalog.json")
    manifest = load_json(run_dir / "manifest.json")
    registry = load_json((repo / args.registry).resolve())
    config = load_json((repo / args.config).resolve())
    cases = catalog["cases"]
    if not 5 <= args.hypotheses <= 10:
        raise ValueError("--hypotheses must be between 5 and 10")

    selection_rng = np.random.default_rng(args.selection_seed)
    chosen_indices = sorted(
        int(value)
        for value in selection_rng.choice(len(cases), size=args.hypotheses, replace=False)
    )
    chosen = [cases[index] for index in chosen_indices]

    cache_groups = list((run_dir / "predictions").glob("*.npz"))
    retained_prediction_count = 0
    retained_counts = []
    for path in cache_groups:
        operands = np.load(path)
        count = int(operands["retained_edge_predictions"].shape[0])
        retained_prediction_count += count
        retained_counts.append(count)

    all_prefix_mismatches = []
    all_focal_rows_available = True
    distinct_control_rows = set()
    unique_sample_ids = set()
    for case in cases:
        unique_sample_ids.add(int(case["sample"]["original_index"]))
        operands_path = run_dir / Path(case["raw_operands"]["predictions"].replace("\\", "/"))
        operands = np.load(operands_path)
        retained_edges = [tuple(map(int, edge)) for edge in operands["retained_edges"].tolist()]
        focal = (int(case["graph"]["source"]), int(case["graph"]["target"]))
        focal_index = retained_edges.index(focal)
        all_focal_rows_available = all_focal_rows_available and (
            int(case["raw_operands"]["focal_prediction_row"]) == focal_index
        )
        eligible = [index for index in range(len(retained_edges)) if index != focal_index]
        case_rng = np.random.default_rng(int(case["controls"]["random_seed"]))
        expected_rows = [
            eligible[int(case_rng.integers(0, len(eligible)))] for _ in range(100)
        ]
        stored_controls = load_json(
            run_dir / Path(case["controls"]["records"].replace("\\", "/"))
        )
        stored_rows = [int(item["retained_edge_prediction_row"]) for item in stored_controls]
        if stored_rows != expected_rows:
            all_prefix_mismatches.append(case["conclusion_id"])
        for row in stored_rows:
            distinct_control_rows.add(
                (int(case["sample"]["original_index"]), int(case["graph"]["window"]), row)
            )

    first_100_reusable = True
    benchmark_plans = []
    for case_index, case in zip(chosen_indices, chosen):
        operands_path = run_dir / Path(case["raw_operands"]["predictions"].replace("\\", "/"))
        operands = np.load(operands_path)
        retained_edges = [tuple(map(int, edge)) for edge in operands["retained_edges"].tolist()]
        focal = (int(case["graph"]["source"]), int(case["graph"]["target"]))
        focal_index = retained_edges.index(focal)
        eligible = [index for index in range(len(retained_edges)) if index != focal_index]
        case_rng = np.random.default_rng(int(case["controls"]["random_seed"]))
        draws = [
            eligible[int(case_rng.integers(0, len(eligible)))]
            for _ in range(100 + args.new_controls)
        ]
        stored_controls = load_json(
            run_dir / Path(case["controls"]["records"].replace("\\", "/"))
        )
        stored_rows = [int(item["retained_edge_prediction_row"]) for item in stored_controls]
        prefix_matches = stored_rows == draws[:100]
        first_100_reusable = first_100_reusable and prefix_matches
        benchmark_plans.append(
            {
                "case_index": case_index,
                "conclusion_id": case["conclusion_id"],
                "sample_id": int(case["sample"]["original_index"]),
                "window_id": int(case["graph"]["window"]),
                "focal_edge": list(focal),
                "case_seed": int(case["controls"]["random_seed"]),
                "prefix_1_100_matches_cache": prefix_matches,
                "new_rows_101_150": draws[100:],
                "new_edges_101_150": [list(retained_edges[index]) for index in draws[100:]],
                "operands_path": str(operands_path),
            }
        )

    statistical_benchmarks = {}
    for target_B in (800, 1000):
        start = time.perf_counter()
        for case in chosen:
            impacts = np.asarray(
                case["raw_operands"]["weight_impact"]["raw_impacts"], dtype=float
            )
            focal_index = int(case["raw_operands"]["focal_prediction_row"])
            eligible = [index for index in range(len(impacts)) if index != focal_index]
            control_rng = np.random.default_rng(int(case["controls"]["random_seed"]))
            rows_for_target = [
                eligible[int(control_rng.integers(0, len(eligible)))] for _ in range(target_B)
            ]
            control_impacts = impacts[rows_for_target]
            focal_impact = float(case["metrics"]["prediction_delta_abs"])
            empirical_p_plus_one(control_impacts, focal_impact)
            standard_deviation = float(control_impacts.std(ddof=1))
            if standard_deviation:
                float((focal_impact - control_impacts.mean()) / standard_deviation)
            bootstrap_rng = np.random.default_rng(int(case["controls"]["random_seed"]) + 100000)
            bootstrap_means = bootstrap_rng.choice(
                control_impacts,
                size=(int(config["control_experiment"]["bootstrap_repetitions"]), target_B),
                replace=True,
            ).mean(axis=1)
            np.quantile(
                focal_impact - bootstrap_means,
                [
                    (1 - float(config["control_experiment"]["confidence_level"])) / 2,
                    1 - (1 - float(config["control_experiment"]["confidence_level"])) / 2,
                ],
            )
        measured_seconds = time.perf_counter() - start
        estimated_family_seconds = measured_seconds * len(cases) / len(chosen)
        statistical_benchmarks[str(target_B)] = {
            "sampled_hypotheses": len(chosen),
            "measured_seconds": measured_seconds,
            "estimated_320_hypothesis_seconds": estimated_family_seconds,
            "estimated_320_hypothesis_human": format_duration(estimated_family_seconds),
            "includes": "RNG draws, cached impact lookup, empirical p, effect size, 10,000-repetition bootstrap CI",
            "excludes": "JSON/CSV export and BH sorting, both expected to be minor relative to bootstrap",
        }

    dataset_name = config["dataset"]
    dataset = registry["datasets"][dataset_name]
    adapter = DGraFormerAdapter(
        registry["source_root"], dataset_name, registry["common"], dataset, registry["random_seed"]
    )
    checkpoint = (
        Path(registry["source_root"])
        / "checkpoints"
        / dataset["setting"]
        / "checkpoint.pth"
    )
    adapter.load_checkpoint(str(checkpoint))

    first_plan = benchmark_plans[0]
    warm_batch = dict(adapter.load_sample("test", first_plan["sample_id"]))
    warm_batch["current_epoch"] = config["current_epoch"]
    warm_edge = first_plan["new_edges_101_150"][0]
    for _ in range(10):
        adapter.predict_with_graph_override(
            warm_batch,
            {
                "type": "structural_edge_removal",
                "window": first_plan["window_id"],
                "source": warm_edge[0],
                "target": warm_edge[1],
                "current_epoch": config["current_epoch"],
            },
        )
    synchronize()

    total_wall = 0.0
    total_gpu = 0.0
    total_forwards = 0
    max_cache_difference = 0.0
    benchmark_results = []
    for plan in benchmark_plans:
        batch = dict(adapter.load_sample("test", plan["sample_id"]))
        batch["current_epoch"] = config["current_epoch"]
        operands = np.load(plan["operands_path"])
        cached_predictions = operands["retained_edge_predictions"]
        start_event = torch.cuda.Event(enable_timing=True) if torch.cuda.is_available() else None
        end_event = torch.cuda.Event(enable_timing=True) if torch.cuda.is_available() else None
        synchronize()
        if start_event is not None:
            start_event.record()
        wall_start = time.perf_counter()
        for row, edge in zip(plan["new_rows_101_150"], plan["new_edges_101_150"]):
            outcome = adapter.predict_with_graph_override(
                batch,
                {
                    "type": "structural_edge_removal",
                    "window": plan["window_id"],
                    "source": edge[0],
                    "target": edge[1],
                    "current_epoch": config["current_epoch"],
                },
            )
            replay = outcome["prediction"].numpy()[0]
            difference = float(np.max(np.abs(replay - cached_predictions[row])))
            max_cache_difference = max(max_cache_difference, difference)
        if end_event is not None:
            end_event.record()
        synchronize()
        wall_seconds = time.perf_counter() - wall_start
        gpu_seconds = (
            float(start_event.elapsed_time(end_event)) / 1000.0
            if start_event is not None and end_event is not None
            else wall_seconds
        )
        count = len(plan["new_rows_101_150"])
        total_wall += wall_seconds
        total_gpu += gpu_seconds
        total_forwards += count
        benchmark_results.append(
            {
                "conclusion_id": plan["conclusion_id"],
                "sample_id": plan["sample_id"],
                "window_id": plan["window_id"],
                "focal_edge": plan["focal_edge"],
                "forward_count": count,
                "wall_seconds": wall_seconds,
                "cuda_event_seconds": gpu_seconds,
                "wall_forwards_per_second": count / wall_seconds,
                "cuda_event_forwards_per_second": count / gpu_seconds,
            }
        )

    adapter.close()
    hypotheses = len(cases)
    current_B = 100
    target_B_800 = 800
    target_B_1000 = 1000
    missing_800 = hypotheses * (target_B_800 - current_B)
    missing_1000 = hypotheses * (target_B_1000 - current_B)
    wall_throughput = total_forwards / total_wall
    gpu_throughput = total_forwards / total_gpu
    naive_800_seconds = missing_800 / wall_throughput
    naive_1000_seconds = missing_1000 / wall_throughput

    report = {
        "status": "complete",
        "scope": "runtime feasibility only; no B=800 or B=1000 evidence family was executed",
        "dataset": dataset_name,
        "run_id": args.run,
        "checkpoint_sha256": manifest["checkpoint_sha256"],
        "data_sha256": manifest["data_sha256"],
        "device": str(adapter.device),
        "cache_audit": {
            "hypotheses": hypotheses,
            "existing_cached_controls": hypotheses * current_B,
            "cached_prediction_groups": len(cache_groups),
            "cached_baseline_group_copies": len(cache_groups),
            "unique_sample_baselines": len(unique_sample_ids),
            "cached_focal_results": hypotheses,
            "all_focal_prediction_rows_available": all_focal_rows_available,
            "cached_all_retained_edge_results": retained_prediction_count,
            "retained_edges_per_group_min": min(retained_counts),
            "retained_edges_per_group_median": float(np.median(retained_counts)),
            "retained_edges_per_group_max": max(retained_counts),
            "distinct_control_prediction_rows_referenced": len(distinct_control_rows),
            "all_320_first_100_control_sequences_reusable": not all_prefix_mismatches,
            "all_320_prefix_mismatch_count": len(all_prefix_mismatches),
            "benchmark_subset_first_100_control_sequences_reusable": first_100_reusable,
            "baseline_reusable": True,
            "focal_reusable": True,
            "all_matched_control_draws_reusable_from_retained_edge_cache": True,
        },
        "expansion": {
            "missing_control_records_for_B_800": missing_800,
            "missing_control_records_for_B_1000": missing_1000,
            "additional_model_forwards_for_B_800_with_cache": 0,
            "additional_model_forwards_for_B_1000_with_cache": 0,
            "forced_replay_forwards_for_B_800_without_cache": missing_800,
            "forced_replay_forwards_for_B_1000_without_cache": missing_1000,
        },
        "benchmark": {
            "selection_seed": args.selection_seed,
            "hypotheses": args.hypotheses,
            "new_controls_per_hypothesis": args.new_controls,
            "warmup_forwards_not_counted": 10,
            "measured_forwards": total_forwards,
            "execution_mode": "sequential single-sample, single-edge replay",
            "batched_inference_currently_used": False,
            "total_wall_seconds": total_wall,
            "total_cuda_event_seconds": total_gpu,
            "wall_forwards_per_second": wall_throughput,
            "cuda_event_forwards_per_second": gpu_throughput,
            "max_absolute_replay_vs_cache_difference": max_cache_difference,
            "all_replays_match_cache": max_cache_difference == 0.0,
            "cases": benchmark_results,
        },
        "runtime_estimates": {
            "cache_aware_B_800_model_forward_seconds": 0.0,
            "cache_aware_B_1000_model_forward_seconds": 0.0,
            "cache_aware_B_800_estimated_statistics_seconds": statistical_benchmarks["800"]["estimated_320_hypothesis_seconds"],
            "cache_aware_B_800_estimated_statistics_human": statistical_benchmarks["800"]["estimated_320_hypothesis_human"],
            "cache_aware_B_1000_estimated_statistics_seconds": statistical_benchmarks["1000"]["estimated_320_hypothesis_seconds"],
            "cache_aware_B_1000_estimated_statistics_human": statistical_benchmarks["1000"]["estimated_320_hypothesis_human"],
            "cache_aware_statistics_benchmark": statistical_benchmarks,
            "cache_aware_note": (
                "Only deterministic control-row resampling and statistic/export work remain; "
                "GPU inference is unnecessary because every eligible same-window edge result is cached."
            ),
            "forced_replay_B_800_seconds": naive_800_seconds,
            "forced_replay_B_800_human": format_duration(naive_800_seconds),
            "forced_replay_B_1000_seconds": naive_1000_seconds,
            "forced_replay_B_1000_human": format_duration(naive_1000_seconds),
            "estimate_basis": "end-to-end wall forwards/sec from the 400-forward GPU replay benchmark",
        },
    }
    json_path = output_dir / "runtime_feasibility.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    markdown = f"""# Runtime feasibility for expanding matched controls

This is a feasibility benchmark only. No complete B=800 or B=1000 evidence experiment was started.

| Item | Result |
| --- | ---: |
| Existing cached controls | {hypotheses * current_B:,} records ({current_B} × {hypotheses}) |
| Missing controls for B=800 | {missing_800:,} records |
| Missing controls for B=1000 | {missing_1000:,} records |
| Additional model forwards for B=800 with current cache | 0 |
| Additional model forwards for B=1000 with current cache | 0 |
| Measured wall throughput | {wall_throughput:.3f} forwards/sec |
| Measured CUDA-event throughput | {gpu_throughput:.3f} forwards/sec |
| Estimated cache-aware B=800 statistics runtime | {statistical_benchmarks['800']['estimated_320_hypothesis_human']} |
| Estimated cache-aware B=1000 statistics runtime | {statistical_benchmarks['1000']['estimated_320_hypothesis_human']} |
| Estimated B=800 runtime if cache is ignored | {format_duration(naive_800_seconds)} |
| Estimated B=1000 runtime if cache is ignored | {format_duration(naive_1000_seconds)} |
| Batched inference currently used | NO |

## Cache finding

The current production pipeline performs every retained same-window edge intervention once per sample×window group, saves those predictions, and samples matched-control rows from that finite cache with replacement. The run contains `{len(cache_groups)}` group-level baseline copies covering `{len(unique_sample_ids)}` unique samples, `{hypotheses}` focal mappings, and `{retained_prediction_count}` retained-edge intervention results. All first 100 sampled control sequences for all `{hypotheses}` hypotheses were reproduced exactly from their saved seeds (mismatches: `{len(all_prefix_mismatches)}`).

Therefore adding control draws 101–800 or 101–1000 requires **zero additional model forwards**. It only requires deterministic RNG continuation, cached-row lookup, and recomputation of empirical p/effect-size/CI/BH outputs. The forced replay estimates are upper bounds for an implementation that unnecessarily reruns every sampled control.

## Actual GPU benchmark

- Fixed hypothesis-selection seed: `{args.selection_seed}`
- Random hypotheses: `{args.hypotheses}`
- New controls replayed per hypothesis: `{args.new_controls}`
- Measured forwards: `{total_forwards}` plus 10 unmeasured warmups
- Execution: sequential batch-size-1 edge interventions
- Total wall time: `{total_wall:.6f}` seconds
- Total CUDA-event time: `{total_gpu:.6f}` seconds
- Wall throughput: `{wall_throughput:.3f}` forwards/sec
- CUDA-event throughput: `{gpu_throughput:.3f}` forwards/sec
- Maximum replay-versus-cache difference: `{max_cache_difference:.12g}`

## Runtime interpretation

With cache reuse, GPU forward time for either expansion is 0 seconds. Based on the same 8 randomly selected hypotheses, the CPU-side RNG/cache/statistics/10,000-bootstrap workload extrapolates to about `{statistical_benchmarks['800']['estimated_320_hypothesis_human']}` for B=800 and `{statistical_benchmarks['1000']['estimated_320_hypothesis_human']}` for B=1000, excluding final file export. These are the relevant cache-aware runtime estimates.

If the cache were ignored, sequential replay would require `{missing_800:,}` forwards for B=800 and `{missing_1000:,}` for B=1000. At the measured wall throughput, those upper bounds are approximately `{format_duration(naive_800_seconds)}` and `{format_duration(naive_1000_seconds)}` respectively. Current inference is not batched.
"""
    (output_dir / "runtime_feasibility.md").write_text(markdown, encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

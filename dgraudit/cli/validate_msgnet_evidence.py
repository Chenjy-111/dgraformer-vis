from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, spearmanr

from dgraudit.cli.validate_pattern import benjamini_hochberg


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", required=True)
    parser.add_argument("--output-root", default="artifacts/runs")
    parser.add_argument("--bootstrap", type=int, default=10000)
    args = parser.parse_args()
    scan_path = Path(args.scan).resolve()
    scan = json.loads(scan_path.read_text(encoding="utf-8"))
    run_id = hashlib.sha256("|".join((sha256(scan_path), str(args.bootstrap), "msgnet_evidence_v1")).encode()).hexdigest()
    run_dir = Path(args.output_root).resolve() / run_id
    evidence_dir = run_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    grouped = {}
    for case in scan["cases"]:
        grouped.setdefault((case["sample_index"], case["layer"], case["scale_index"]), []).append(case)
    records = []
    for group_key, cases in sorted(grouped.items()):
        weights = np.asarray([c["adaptive_weight"] for c in cases], dtype=float)
        impacts = np.asarray([c["prediction_delta_abs"] for c in cases], dtype=float)
        corr = spearmanr(weights, impacts)
        weight_ranks = rankdata(-weights, method="average")
        for index, case in enumerate(cases):
            controls = np.delete(impacts, index)
            focal = impacts[index]
            empirical_p = float((1 + np.sum(controls >= focal)) / (len(controls) + 1))
            std = float(controls.std(ddof=1))
            seed = 20260813 + len(records)
            rng = np.random.default_rng(seed)
            boot_means = rng.choice(controls, size=(args.bootstrap, len(controls)), replace=True).mean(1)
            difference = focal - boot_means
            record = {
                **case,
                "conclusion_id": f"msgnet_etth1_s{case['sample_index']}_l{case['layer']}_k{case['scale_index']}_e{case['source']}_{case['target']}",
                "status": "complete", "claim_level": "interventional_model_evidence",
                "graph": {"weight_rank": float(weight_ranks[index]), "weight_impact_spearman_rho": float(corr.statistic),
                          "weight_impact_spearman_p": float(corr.pvalue)},
                "controls": {"count": len(controls), "sampling": "all other directed non-self edges in the same sample, layer, and scale",
                             "prediction_delta_abs": controls.tolist()},
                "statistics": {
                    "control_mean_prediction_delta_abs": float(controls.mean()),
                    "control_median_prediction_delta_abs": float(np.median(controls)),
                    "control_percentile": float(100 * np.mean(controls <= focal)),
                    "empirical_p": empirical_p, "bh_adjusted_p": None,
                    "standardized_effect_size": None if std == 0 else float((focal - controls.mean()) / std),
                    "candidate_minus_control_mean_bootstrap_ci_95": np.quantile(difference, [0.025, 0.975]).tolist(),
                    "bootstrap_repetitions": args.bootstrap, "bootstrap_seed": seed,
                },
                "limitations": ["Checkpoint-internal response only.", "No real-world causal claim.",
                                "Only one locally trained MSGNet checkpoint is available."],
            }
            records.append(record)
    adjusted = benjamini_hochberg([r["statistics"]["empirical_p"] for r in records])
    for record, value in zip(records, adjusted):
        record["statistics"]["bh_adjusted_p"] = value
        (evidence_dir / f"{record['conclusion_id']}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    ranked = sorted(records, key=lambda r: r["prediction_delta_abs"], reverse=True)
    catalog = {
        "run_id": run_id, "status": "complete", "model": "MSGNet", "dataset": "ETTh1",
        "case_count": len(records), "multiple_comparison_family_size": len(records),
        "multiple_comparison_correction": "Benjamini-Hochberg", "bh_supported_count": sum(r["statistics"]["bh_adjusted_p"] < .05 for r in records),
        "scan_run_id": scan["run_id"], "scan_sha256": sha256(scan_path), "cases": records, "top_cases": ranked[:40],
        "cross_run": {"status": "missing", "metrics": None, "reason": "Only one locally trained MSGNet checkpoint is available."},
    }
    catalog_path = run_dir / "evidence_catalog.json"
    catalog_path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    manifest = {key: catalog[key] for key in ("run_id", "status", "model", "dataset", "case_count", "multiple_comparison_family_size", "multiple_comparison_correction", "bh_supported_count", "scan_run_id", "scan_sha256", "cross_run")}
    manifest["evidence_catalog_sha256"] = sha256(catalog_path)
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "command.txt").write_text(f"python -m dgraudit.cli.validate_msgnet_evidence --scan {args.scan} --bootstrap {args.bootstrap}\n", encoding="utf-8")
    (run_dir / "stdout.log").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (run_dir / "stderr.log").write_text("", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

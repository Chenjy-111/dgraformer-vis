from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a lossless summary index for the ETTh1 web workspace.")
    parser.add_argument("--local", default="public/data/evidence/etth1_intervention_catalog.json")
    parser.add_argument("--global-catalog", default="public/data/evidence/etth1_global_intervention_catalog.json")
    parser.add_argument("--output", default="public/data/evidence/etth1_intervention_index.json")
    args = parser.parse_args()

    local = json.loads(Path(args.local).read_text(encoding="utf-8"))
    global_catalog = json.loads(Path(args.global_catalog).read_text(encoding="utf-8"))
    assert local["dataset"] == global_catalog["dataset"] == "ETTh1"
    assert local["samples"] == global_catalog["samples"]
    assert local["schedule"] == global_catalog["schedule"]
    assert local["cross_run"]["status"] == global_catalog["cross_run"]["status"] == "missing"
    assert local["cross_run"]["metrics"] is None and global_catalog["cross_run"]["metrics"] is None

    local_fields = (
        "prediction_delta_abs", "error_delta_mae", "control_mean_prediction_delta_abs",
        "empirical_p", "bh_adjusted_p",
    )
    global_fields = local_fields
    index = {
        "status": "complete",
        "dataset": "ETTh1",
        "source_runs": {
            **local["source_runs"],
            "global": global_catalog["run_id"],
        },
        "schedule": local["schedule"],
        "samples": local["samples"],
        "edges": local["edges"],
        "local_cases": [{
            "conclusion_id": case["conclusion_id"],
            "sample_index": case["sample_index"],
            "window": case["window"],
            "window_active": case["window_active"],
            "edge": case["edge"],
            "structural_metrics": {key: case["structural_metrics"][key] for key in local_fields},
        } for case in local["cases"]],
        "global_cases": [{
            "id": case["id"],
            "sample": case["sample"],
            "edge": case["edge"],
            "affected_exposed_windows": case["affected_exposed_windows"],
            "metrics": {key: case["metrics"][key] for key in global_fields},
        } for case in global_catalog["cases"]],
        "cross_run": local["cross_run"],
        "notice": local["notice"],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "local_cases": len(index["local_cases"]),
        "global_cases": len(index["global_cases"]),
        "source_bytes": Path(args.local).stat().st_size + Path(args.global_catalog).stat().st_size,
        "index_bytes": output.stat().st_size,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

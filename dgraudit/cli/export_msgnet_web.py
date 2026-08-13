from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline-run", required=True)
    p.add_argument("--graph-run", required=True)
    p.add_argument("--evidence-run", required=True)
    p.add_argument("--output", default="public/data/models/msgnet/etth1/catalog.json")
    a = p.parse_args()
    baseline, graphs, evidence = map(lambda x: Path(x).resolve(), (a.baseline_run, a.graph_run, a.evidence_run))
    manifest = json.loads((baseline / "manifest.json").read_text(encoding="utf-8"))
    catalog = json.loads((evidence / "evidence_catalog.json").read_text(encoding="utf-8"))
    pred = np.load(baseline / "predictions" / "baseline.npy")
    truth = np.load(baseline / "predictions" / "ground_truth.npy")
    history = np.load(baseline / "predictions" / "history.npy")
    indices = [s["sample_index"] for s in manifest["samples"]]
    cases_by_sample = {i: [] for i in indices}
    for case in catalog["cases"]:
        cases_by_sample[case["sample_index"]].append(case)
    samples = []
    for row, index in enumerate(indices):
        graph = json.loads((graphs / "graphs" / f"sample_{index}.json").read_text(encoding="utf-8"))
        samples.append({
            "sample_index": index,
            "history": history[row].T.tolist(), "ground_truth": truth[row].T.tolist(),
            "prediction": pred[row].T.tolist(), "metrics": manifest["samples"][row],
            "contexts": [{"layer": c["layer"], "scale_index": c["scale_index"], "period": c["period"],
                          "fft_strength": c["fft_strength"], "scale_contribution": c["scale_contribution"],
                          "adaptive": c["adaptive"], "effective": c["effective"]} for c in graph["contexts"]],
            "edge_impacts": sorted(cases_by_sample[index], key=lambda x: x["prediction_delta_abs"], reverse=True),
        })
    output = {
        "model": "MSGNet", "dataset": "ETTh1", "variables": ["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL", "OT"],
        "lookback": 96, "horizon": 96, "checkpoint_sha256": manifest["checkpoint_sha256"],
        "baseline_run_id": manifest["run_id"], "graph_run_id": json.loads((graphs / "manifest.json").read_text())["run_id"],
        "evidence_run_id": catalog["run_id"], "bh_supported_count": catalog["bh_supported_count"],
        "case_count": catalog["case_count"], "samples": samples,
        "notice": "Scale contribution, graph weight, and measured edge-removal response are distinct quantities. No causal or cross-checkpoint claim is made."
    }
    target = Path(a.output).resolve(); target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"output": str(target), "samples": len(samples), "cases": catalog["case_count"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

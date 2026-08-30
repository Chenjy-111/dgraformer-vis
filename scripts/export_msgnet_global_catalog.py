"""Merge real all-scale MSGNet edge-removal inference into the web catalog."""

import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
WEB_CATALOG = ROOT / "legacy/v1/artifacts/public-data/models/msgnet/etth1/catalog.json"
RUN_DIR = ROOT / "artifacts/runs/4e3e6fd4970fedbf3ddc91e2f43db952d347afec9f82028a96c45cc0e1547bef"
GLOBAL_CATALOG = RUN_DIR / "global_evidence_catalog.json"


def main() -> None:
    catalog = json.loads(WEB_CATALOG.read_text(encoding="utf-8"))
    evidence = json.loads(GLOBAL_CATALOG.read_text(encoding="utf-8"))
    samples = {sample["sample_index"]: sample for sample in catalog["samples"]}

    for sample in catalog["samples"]:
        sample["global_edge_impacts"] = []

    for case in evidence["cases"]:
        prediction = np.load(RUN_DIR / case["intervention_prediction_file"])
        if prediction.shape == (1, catalog["horizon"], len(catalog["variables"])):
            prediction = prediction[0]
        if prediction.shape != (catalog["horizon"], len(catalog["variables"])):
            raise ValueError(f"Unexpected prediction shape {prediction.shape} for {case}")

        exported = {key: value for key, value in case.items() if key != "intervention_prediction_file"}
        # The website consistently stores time series as [variable][forecast step].
        exported["intervention_prediction"] = prediction.T.tolist()
        samples[case["sample_index"]]["global_edge_impacts"].append(exported)

    expected = evidence["case_count"]
    actual = sum(len(sample["global_edge_impacts"]) for sample in catalog["samples"])
    if actual != expected:
        raise ValueError(f"Expected {expected} cases but exported {actual}")

    catalog["global_intervention_run_id"] = evidence["run_id"]
    catalog["global_case_count"] = evidence["case_count"]
    catalog["global_bh_supported_count"] = evidence["bh_supported_count"]
    catalog["global_intervention_notice"] = evidence["notice"]
    WEB_CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Exported {actual} real global interventions to {WEB_CATALOG}")


if __name__ == "__main__":
    main()

"""Refresh the protected current Session v2 graph/model-core hash fixture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests" / "fixtures" / "pipeline_v2_graph_baseline.json"
SOURCES = {
    "DGraFormer": ROOT / "public" / "data" / "evidence" / "dgraformer_etth1_session_v2.json",
    "MSGNet": ROOT / "tests" / "fixtures" / "msgnet_graph_core_baseline.json",
    "MTGNN": ROOT / "tests" / "fixtures" / "mtgnn_quick_session_v2.json",
}


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def freeze(path: Path) -> dict[str, Any]:
    session = json.loads(path.read_text(encoding="utf-8"))
    samples = []
    for sample in session["samples"]:
        core = {
            "sample_id": sample["sample_id"],
            "display_id": sample["display_id"],
            "split": sample["split"],
            "sample_index": sample["sample_index"],
            "history": sample["history"],
            "ground_truth": sample["ground_truth"],
            "baseline_prediction": sample["baseline_prediction"],
            "sample_metrics": sample["sample_metrics"],
            "contexts": sample["contexts"],
        }
        samples.append({
            "sample_id": sample["sample_id"],
            "sample_index": sample["sample_index"],
            "context_count": len(sample["contexts"]),
            "node_counts": [context["node_count"] for context in sample["contexts"]],
            "graph_shapes": [
                {name: graph["shape"] for name, graph in context["graphs"].items()}
                for context in sample["contexts"]
            ],
            "graph_core_sha256": canonical_hash(core),
            "baseline_prediction_sha256": canonical_hash(sample["baseline_prediction"]),
            "contexts_sha256": canonical_hash(sample["contexts"]),
        })
    relation_core = [{
        "relation_id": relation["relation_id"],
        "sample_id": relation["sample_id"],
        "source": relation["source"],
        "target": relation["target"],
        "native_occurrences": relation["native_occurrences"],
    } for relation in session["relations"]]
    return {
        "source": str(path.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "sample_count": len(session["samples"]),
        "relation_count": len(session["relations"]),
        "samples": samples,
        "relation_core_sha256": canonical_hash(relation_core),
    }


def main() -> None:
    result = {
        "fixture_version": "pipeline_v2_graph_baseline.v2",
        "rule": "Current Session v2 graph/model core must remain exactly equivalent after canonical JSON serialization.",
        "models": {model: freeze(path) for model, path in SOURCES.items()},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()

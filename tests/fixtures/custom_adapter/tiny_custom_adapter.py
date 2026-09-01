from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping

import torch

from dgraudit.adapters import AdapterCapabilities, DynamicGraphForecastAdapter, GraphContext


class TinyDeterministicGraphAdapter(DynamicGraphForecastAdapter):
    """Test-only external adapter; not an official research model or benchmark."""

    ADAPTER_ID = "tiny_external_fixture"
    MODEL_NAME = "TinyDeterministicGraph"
    ADAPTER_VERSION = "fixture-v1"
    CAPABILITIES = AdapterCapabilities(
        graph_context_type="global",
        supports_quick_inspection=True,
        supports_graph_override=True,
        supports_multi_context=False,
        supports_broader_context=False,
        audit_graph_key="learned_adjacency",
        local_scope="global_graph",
        dataset_formats=("custom_csv",),
    )

    def __init__(self, config: Mapping[str, Any], resolved_paths: Mapping[str, Path]):
        self.config = config
        self.paths = resolved_paths
        self.variables = list(config["dataset"]["variables"])
        self.graph: torch.Tensor | None = None
        self.output_scale: float | None = None
        self.checkpoint_path: str | None = None

    def load_checkpoint(self, checkpoint_path: str) -> None:
        payload = json.loads(Path(checkpoint_path).read_text(encoding="utf-8"))
        graph = torch.tensor(payload["learned_adjacency"], dtype=torch.float32)
        expected = (len(self.variables), len(self.variables))
        if tuple(graph.shape) != expected or not torch.isfinite(graph).all():
            raise RuntimeError(f"incompatible learned_adjacency; expected {expected}")
        if bool((graph.sum(1) <= 0).any()):
            raise RuntimeError("learned_adjacency has a non-positive row")
        self.graph = graph / graph.sum(1, keepdim=True)
        self.output_scale = float(payload["output_scale"])
        self.checkpoint_path = str(Path(checkpoint_path).resolve())

    def load_sample(self, split: str, sample_index: int) -> Mapping[str, Any]:
        if split != "test":
            raise ValueError("fixture supports only the test split")
        with self.paths["dataset"].open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        seq_len = int(self.config["dataset"]["seq_len"])
        pred_len = int(self.config["dataset"]["pred_len"])
        start = int(sample_index)
        if start < 0 or start + seq_len + pred_len > len(rows):
            raise IndexError(sample_index)
        values = torch.tensor([[float(row[name]) for name in self.variables] for row in rows], dtype=torch.float32)
        return {"x": values[start:start + seq_len], "y": values[start + seq_len:start + seq_len + pred_len], "sample_index": sample_index, "split": split}

    def _forward(self, batch: Mapping[str, Any], graph: torch.Tensor) -> torch.Tensor:
        if self.output_scale is None:
            raise RuntimeError("checkpoint is not loaded")
        x = torch.as_tensor(batch["x"], dtype=torch.float32)
        prediction = torch.matmul(x[-1], graph) * self.output_scale
        return prediction.view(1, 1, -1)

    def predict(self, batch: Mapping[str, Any]) -> torch.Tensor:
        if self.graph is None:
            raise RuntimeError("checkpoint is not loaded")
        return self._forward(batch, self.graph).detach().clone()

    def extract_graph_stages(self, batch: Mapping[str, Any]) -> Mapping[str, Any]:
        del batch
        if self.graph is None:
            raise RuntimeError("checkpoint is not loaded")
        graph = self.graph.detach().clone()
        return {"contexts": [GraphContext(
            context_id="global:0",
            context_type="global",
            index=0,
            audit_graph=graph,
            graphs={"learned_adjacency": graph},
            display_label="Global learned graph",
            metadata={"construction": "fixed fixture parameters loaded from the exact checkpoint"},
        )]}

    def predict_with_graph_override(self, batch, graph_override):
        if self.graph is None:
            raise RuntimeError("checkpoint is not loaded")
        before = torch.as_tensor(graph_override.get("graph", self.graph), dtype=torch.float32).detach().clone()
        after = before.clone()
        kind = graph_override["type"]
        if kind == "structural_edge_removal":
            after[int(graph_override["source"]), int(graph_override["target"])] = 0
            after = after / after.sum(1, keepdim=True)
        elif kind != "identity":
            raise ValueError(f"unsupported fixture intervention: {kind}")
        prediction = self._forward(batch, after)
        protocol = {key: value for key, value in graph_override.items() if key != "graph"}
        return {"prediction": prediction, "graph_before": before, "graph_after": after, "renormalized": kind != "identity", "protocol": protocol}

    def get_metadata(self) -> Mapping[str, Any]:
        return {
            "adapter": type(self).__name__,
            "adapter_version": self.ADAPTER_VERSION,
            "model": self.MODEL_NAME,
            "dataset": self.config["dataset"]["name"],
            "node_labels": list(self.variables),
            "graph_contexts": ["global:0"],
            "device": "cpu",
            "checkpoint_format": "deterministic JSON parameters",
            "checkpoint_loaded": self.checkpoint_path is not None,
        }

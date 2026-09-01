"""External MTGNN integration used to prove the public custom-adapter path.

This module intentionally does not import or subclass dgraudit.adapters.MTGNNAdapter and is not
registered in OFFICIAL_ADAPTER_REGISTRY. It drives the unmodified public MTGNN source directly.
"""

from __future__ import annotations

import random
import sys
import types
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch

from dgraudit.adapters import AdapterCapabilities, DynamicGraphForecastAdapter, GraphContext


class ExternalMTGNNAdapter(DynamicGraphForecastAdapter):
    ADAPTER_ID = "mtgnn_external"
    MODEL_NAME = "MTGNN"
    ADAPTER_VERSION = "dgrainsight-external-integration-v1"
    CAPABILITIES = AdapterCapabilities(
        graph_context_type="global_graph",
        supports_quick_inspection=True,
        supports_graph_override=True,
        supports_multi_context=False,
        supports_broader_context=False,
        audit_graph_key="learned_adjacency",
        local_scope="global_graph",
        dataset_formats=("mtgnn_numeric_matrix",),
    )

    def __init__(self, config: Mapping[str, Any], resolved_paths: Mapping[str, Path]):
        self.config = config
        self.paths = resolved_paths
        adapter_config = config["adapter_config"]
        model_config = adapter_config["model"]
        self.seed = int(adapter_config["random_seed"])
        requested_device = str(adapter_config.get("device", "auto"))
        if requested_device == "auto":
            requested_device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(requested_device)
        model_root_raw = Path(str(adapter_config["model_source_root"]))
        self.model_source_root = (
            model_root_raw if model_root_raw.is_absolute()
            else Path(resolved_paths["source_root"]) / model_root_raw
        ).resolve()
        if not (self.model_source_root / "net.py").is_file() or not (self.model_source_root / "util.py").is_file():
            raise FileNotFoundError("MTGNN model_source_root must contain net.py and util.py")
        source = str(self.model_source_root)
        if source not in sys.path:
            sys.path.insert(0, source)

        random.seed(self.seed)
        np.random.seed(self.seed)
        torch.manual_seed(self.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(self.seed)

        from net import gtnet

        self.model = gtnet(
            bool(model_config["gcn_true"]), bool(model_config["build_a_true"]),
            int(model_config["gcn_depth"]), int(model_config["num_nodes"]), self.device,
            predefined_A=None, static_feat=None, dropout=float(model_config["dropout"]),
            subgraph_size=int(model_config["subgraph_size"]), node_dim=int(model_config["node_dim"]),
            dilation_exponential=int(model_config["dilation_exponential"]),
            conv_channels=int(model_config["conv_channels"]),
            residual_channels=int(model_config["residual_channels"]),
            skip_channels=int(model_config["skip_channels"]), end_channels=int(model_config["end_channels"]),
            seq_length=int(model_config["seq_in_len"]), in_dim=int(model_config["in_dim"]),
            out_dim=int(model_config["seq_out_len"]), layers=int(model_config["layers"]),
            propalpha=float(model_config["propalpha"]), tanhalpha=float(model_config["tanhalpha"]),
            layer_norm_affline=bool(model_config["layer_norm_affline"]),
        ).float().to(self.device)
        self._datasets: dict[str, Any] = {}
        self.checkpoint_path: str | None = None

    @classmethod
    def validate_dataset_file(
        cls, dataset_path: Path, dataset_config: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        try:
            matrix = np.loadtxt(dataset_path, delimiter=",")
        except (OSError, ValueError) as exc:
            raise ValueError(f"MTGNN numeric matrix could not be parsed: {exc}") from exc
        expected_nodes = len(dataset_config["variables"])
        if matrix.ndim != 2 or matrix.shape[1] != expected_nodes:
            raise ValueError(
                f"MTGNN matrix node count mismatch: expected {expected_nodes}, found {list(matrix.shape)}"
            )
        if matrix.shape[0] <= int(dataset_config["seq_len"]) or not np.isfinite(matrix).all():
            raise ValueError("MTGNN matrix is too short or contains non-finite values")
        return {
            "format": dataset_config["format"],
            "row_count": int(matrix.shape[0]),
            "node_count": int(matrix.shape[1]),
            "node_labels": list(dataset_config["variables"]),
        }

    def load_checkpoint(self, checkpoint_path: str) -> None:
        payload = torch.load(checkpoint_path, map_location=self.device)
        state = payload.get("state_dict", payload) if isinstance(payload, Mapping) else payload
        self.model.load_state_dict(state, strict=True)
        self.model.eval()
        self.checkpoint_path = str(Path(checkpoint_path).resolve())

    def _dataset(self, split: str):
        if split != "test":
            raise ValueError("ExternalMTGNNAdapter supports only the original MTGNN test split")
        if split not in self._datasets:
            from util import DataLoaderS

            model_config = self.config["adapter_config"]["model"]
            self._datasets[split] = DataLoaderS(
                str(self.paths["dataset"]),
                float(model_config["train_ratio"]), float(model_config["validation_ratio"]),
                self.device, int(model_config["horizon"]), int(model_config["seq_in_len"]),
                int(model_config["normalize"]),
            )
        return self._datasets[split]

    def load_sample(self, split: str, sample_index: int) -> Mapping[str, Any]:
        dataset = self._dataset(split)
        x_normalized = dataset.test[0][sample_index].clone()
        y_normalized = dataset.test[1][sample_index].clone()
        scale = dataset.scale.detach().cpu()
        return {
            "x": x_normalized.detach().cpu() * scale.view(1, -1),
            "y": (y_normalized.detach().cpu() * scale).view(1, -1),
            "x_normalized": x_normalized,
            "sample_index": int(sample_index),
            "split": split,
        }

    def _model_input(self, batch: Mapping[str, Any]) -> torch.Tensor:
        value = torch.as_tensor(batch["x_normalized"], dtype=torch.float32, device=self.device)
        if value.ndim == 2:
            value = value.unsqueeze(0)
        return value.unsqueeze(1).transpose(2, 3)

    def predict(self, batch: Mapping[str, Any]) -> torch.Tensor:
        with torch.no_grad():
            output = self.model(self._model_input(batch))
        prediction = output.squeeze(-1)
        scale = self._dataset(str(batch.get("split", "test"))).scale.view(1, 1, -1)
        return (prediction * scale).detach().cpu()

    def extract_graph_stages(self, batch: Mapping[str, Any]) -> Mapping[str, Any]:
        del batch
        with torch.no_grad():
            learned = self.model.gc(self.model.idx).detach().cpu()
        return {"contexts": [GraphContext(
            context_id="global_graph:0",
            context_type="global_graph",
            index=0,
            audit_graph=learned,
            graphs={
                "learned_adjacency": learned,
                "transpose_adjacency": learned.transpose(0, 1).contiguous(),
            },
            display_label="Global learned MTGNN graph",
            metadata={
                "edge_count": int((learned > 0).sum()),
                "subgraph_size": int(self.config["adapter_config"]["model"]["subgraph_size"]),
                "gcn_layer_count": int(self.config["adapter_config"]["model"]["layers"]),
                "construction": "public MTGNN graph_constructor output shared across mixprop layers",
            },
        )]}

    def predict_with_graph_override(
        self, batch: Mapping[str, Any], graph_override: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        before = torch.as_tensor(graph_override["graph"], dtype=torch.float32, device=self.device).clone()
        after = before.clone()
        kind = str(graph_override["type"])
        if kind == "structural_edge_removal":
            after[int(graph_override["source"]), int(graph_override["target"])] = 0
        elif kind != "identity":
            raise ValueError(f"Unsupported external MTGNN intervention: {kind}")

        original_forward = self.model.gc.forward

        def overridden_forward(_self, idx):
            return after.index_select(0, idx).index_select(1, idx)

        self.model.gc.forward = types.MethodType(overridden_forward, self.model.gc)
        try:
            prediction = self.predict(batch)
        finally:
            self.model.gc.forward = original_forward
        protocol = {
            key: value for key, value in graph_override.items() if key != "graph"
        }
        protocol.update({
            "applied_to": "shared learned adjacency before every public MTGNN mixprop layer",
            "transpose_branch_updated": True,
            "internal_mixprop_normalization": True,
        })
        return {
            "prediction": prediction,
            "graph_before": before.detach().cpu(),
            "graph_after": after.detach().cpu(),
            "renormalized": False,
            "protocol": protocol,
        }

    def get_metadata(self) -> Mapping[str, Any]:
        return {
            "adapter": type(self).__name__,
            "adapter_version": self.ADAPTER_VERSION,
            "model": self.MODEL_NAME,
            "dataset": self.config["dataset"]["name"],
            "node_labels": list(self.config["dataset"]["variables"]),
            "graph_contexts": ["global_graph:0"],
            "device": str(self.device),
            "checkpoint_format": "PyTorch state_dict",
            "checkpoint_loaded": self.checkpoint_path is not None,
            "model_source_root": str(self.model_source_root),
        }

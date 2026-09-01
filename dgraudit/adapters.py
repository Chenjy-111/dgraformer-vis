from __future__ import annotations

import os
import random
import sys
import types
from abc import ABC, abstractmethod
from argparse import Namespace
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch
import torch.nn.functional as F


@dataclass(frozen=True)
class AdapterCapabilities:
    """Technical execution capabilities; this never declares formal validity."""

    graph_context_type: str
    supports_quick_inspection: bool = True
    supports_graph_override: bool = True
    supports_multi_context: bool = False
    supports_broader_context: bool = False
    audit_graph_key: str = "audit_graph"
    local_scope: str = "single_context"
    broader_scope: str = "all_contexts"
    dataset_formats: tuple[str, ...] = ()


@dataclass(frozen=True)
class GraphContext:
    """Canonical internal context used by custom adapters and the audit core."""

    context_id: str
    context_type: str
    index: int
    audit_graph: Any
    graphs: Mapping[str, Any] = field(default_factory=dict)
    display_label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    identity: Mapping[str, Any] = field(default_factory=dict)

    def as_mapping(self) -> dict[str, Any]:
        graphs = dict(self.graphs)
        graphs.setdefault("audit_graph", self.audit_graph)
        return {
            "context_id": self.context_id,
            "context_type": self.context_type,
            "index": self.index,
            "audit_graph": self.audit_graph,
            "graphs": graphs,
            "display_label": self.display_label,
            "metadata": dict(self.metadata),
            "identity": dict(self.identity),
        }


def apply_graph_intervention(graph: torch.Tensor, protocol: Mapping[str, Any]) -> torch.Tensor:
    """Apply an explicit intervention to one final normalized graph window."""
    kind = protocol["type"]
    result = graph.clone()
    if kind == "identity":
        return result
    if kind == "normalized_channel_mask":
        result[protocol["source"], protocol["target"]] = 0
        return result

    # Structural protocols operate on the pre-normalized self-loop graph.
    # A positive row scaling does not affect its later row normalization, so the
    # normalized graph is a valid set of proportional pre-normalized operands.
    n = result.shape[0]
    if kind == "structural_edge_removal":
        result[protocol["source"], protocol["target"]] = 0
    elif kind == "variable_outgoing_removal":
        variable = protocol["variable"]
        result[variable, :] = 0
        result[variable, variable] = 1
    elif kind == "variable_incoming_removal":
        variable = protocol["variable"]
        result[:, variable] = 0
        result[variable, variable] = 1
    elif kind == "variable_associated_removal":
        variable = protocol["variable"]
        result[variable, :] = 0
        result[:, variable] = 0
        result[variable, variable] = 1
    elif kind == "edge_set_removal":
        for source, target in protocol["edges"]:
            result[source, target] = 0
    elif kind == "edge_set_keep_only":
        keep = {(int(s), int(t)) for s, t in protocol["edges"]}
        for source in range(n):
            for target in range(n):
                if source != target and (source, target) not in keep:
                    result[source, target] = 0
    else:
        raise ValueError(f"Unsupported graph intervention: {kind}")
    row_sums = result.sum(1, keepdim=True)
    if bool((row_sums <= 0).any()):
        raise ValueError("Structural intervention produced a non-positive row sum")
    return result / row_sums


class DynamicGraphForecastAdapter(ABC):
    CAPABILITIES: AdapterCapabilities | None = None
    ADAPTER_ID = ""
    MODEL_NAME = ""
    ADAPTER_VERSION: str | None = None

    @classmethod
    def from_audit_config(
        cls, config: Mapping[str, Any], resolved_paths: Mapping[str, Path]
    ) -> "DynamicGraphForecastAdapter":
        """Stable external construction hook; subclasses may override it."""

        return cls(config, resolved_paths)  # type: ignore[call-arg]

    @classmethod
    def validate_dataset_file(
        cls, dataset_path: Path, dataset_config: Mapping[str, Any]
    ) -> Mapping[str, Any] | None:
        """Optionally validate a native non-CSV dataset before adapter construction.

        Returning ``None`` selects DGraInsight's strict date-column CSV validator.
        Custom formats should return bounded technical measurements or raise a clear error.
        """

        return None

    @abstractmethod
    def load_checkpoint(self, checkpoint_path: str) -> None: ...

    @abstractmethod
    def load_sample(self, split: str, sample_index: int) -> Mapping[str, Any]: ...

    @abstractmethod
    def predict(self, batch: Mapping[str, Any]) -> Any: ...

    @abstractmethod
    def extract_graph_stages(self, batch: Mapping[str, Any]) -> Mapping[str, Any]: ...

    @abstractmethod
    def predict_with_graph_override(
        self, batch: Mapping[str, Any], graph_override: Mapping[str, Any]
    ) -> Any: ...

    @abstractmethod
    def get_metadata(self) -> Mapping[str, Any]: ...

    def close(self) -> None:
        """Release adapter-scoped process state after an offline operation."""


def canonical_graph_contexts(extracted: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Normalize custom-adapter GraphContext objects/mappings without guessing semantics."""

    raw_contexts = extracted.get("contexts")
    if not isinstance(raw_contexts, Sequence) or isinstance(raw_contexts, (str, bytes, bytearray)):
        raise ValueError("extract_graph_stages must return a non-empty 'contexts' sequence.")
    contexts: list[dict[str, Any]] = []
    for raw in raw_contexts:
        if isinstance(raw, GraphContext):
            contexts.append(raw.as_mapping())
        elif isinstance(raw, Mapping):
            contexts.append(dict(raw))
        else:
            raise TypeError("Every graph context must be a GraphContext or mapping.")
    if not contexts:
        raise ValueError("extract_graph_stages returned no learned graph contexts.")
    return contexts


class DGraFormerAdapter(DynamicGraphForecastAdapter):
    """Thin adapter around the supplied, unmodified DGraFormer inference path."""

    ADAPTER_ID = "dgraformer"
    MODEL_NAME = "DGraFormer"
    CAPABILITIES = AdapterCapabilities(
        graph_context_type="window", supports_multi_context=True, supports_broader_context=True,
        audit_graph_key="normalized", local_scope="single_window", broader_scope="all_retained_windows",
        dataset_formats=("ett_hour",),
    )

    def __init__(self, source_root: str, dataset_name: str, common: Mapping[str, Any], dataset: Mapping[str, Any], seed: int):
        self.source_root = Path(source_root).resolve()
        self.dataset_name = dataset_name
        self.config = {**common, **dataset}
        self.seed = seed
        self.current_epoch = 1
        self._old_cwd = Path.cwd()

        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

        source = str(self.source_root)
        if source not in sys.path:
            sys.path.insert(0, source)
        os.chdir(self.source_root)
        try:
            from exp.exp_main import Exp_Main

            args = self._namespace()
            self.exp = Exp_Main(args)
            self.model = self.exp.model
            self.device = self.exp.device
            self._datasets: dict[str, Any] = {}
        except Exception:
            os.chdir(self._old_cwd)
            raise

    def _namespace(self) -> Namespace:
        c = self.config
        return Namespace(
            random_seed=self.seed, is_training=0, model_id=self.dataset_name,
            model="DGraFormer", data=c["data"], root_path=c["root_path"],
            data_path=c["data_path"], freq=c["freq"], checkpoints="./checkpoints/",
            seq_len=c["seq_len"], label_len=c["label_len"], pred_len=c["pred_len"],
            numpoint_win=c["numpoint_win"], w_bias=c["w_bias"], d_graph=c["d_graph"],
            d_gcn=c["d_gcn"], w_ratio=c["w_ratio"], mp_layers=c["mp_layers"],
            predictor_dropout=c["predictor_dropout"], patch_len=c["patch_len"],
            stride=c["stride"], revin=c["revin"], affine=c["affine"],
            subtract_last=c["subtract_last"], n_vars=c["n_vars"], d_model=c["d_model"],
            n_heads=c["n_heads"], e_layers=c["e_layers"], d_ff=c["d_ff"],
            dropout=c["dropout"], embed=c["embed"], activation=c["activation"],
            do_predict=False, num_workers=0, itr=1, train_epochs=200, batch_size=128,
            patience=20, learning_rate=0.0001, des="test", lradj="constant",
            pct_start=0.3, use_amp=False, use_gpu=torch.cuda.is_available(), gpu=0,
            use_multi_gpu=False, devices="0", test_flop=False,
        )

    def load_checkpoint(self, checkpoint_path: str) -> None:
        state = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(state)
        self.model.eval()

    def load_sample(self, split: str, sample_index: int) -> Mapping[str, Any]:
        if split not in self._datasets:
            dataset, _ = self.exp._get_data(flag=split)
            self._datasets[split] = dataset
        x, y, time_index = self._datasets[split][sample_index]
        return {"x": x, "y": y, "time_index": time_index, "sample_index": sample_index, "split": split}

    def predict(self, batch: Mapping[str, Any]) -> torch.Tensor:
        x = torch.as_tensor(batch["x"], dtype=torch.float32, device=self.device).unsqueeze(0)
        time_index = torch.as_tensor(batch["time_index"], device=self.device).unsqueeze(0)
        with torch.no_grad():
            output = self.model(x, time_index, int(batch.get("current_epoch", self.current_epoch)))
        return output[:, -self.config["pred_len"] :, :].detach().cpu()

    def extract_graph_stages(self, batch: Mapping[str, Any]) -> Mapping[str, Any]:
        epoch = int(batch.get("current_epoch", self.current_epoch))
        gc = self.model.model.gc
        windows = []
        with torch.no_grad():
            for index in range(gc.num_adj_matrices):
                nodevec1 = torch.tanh(gc.lin1[index](gc.emb_list1[index]))
                nodevec2 = torch.tanh(gc.lin2[index](gc.emb_list2[index]))
                proportion = min(epoch / 5, gc.alpha)
                raw_score = ((1 - proportion) * gc.init_adj_matrix
                             + proportion * torch.mm(nodevec1, nodevec2.transpose(1, 0)))
                activated = F.relu(torch.tanh(raw_score))
                diagonal_removed = activated - torch.diag(torch.diag(activated))
                edge_slots = int(gc.n_vars * gc.n_vars * gc.w_ratio)
                _, indices = torch.topk(diagonal_removed.reshape(-1), edge_slots, largest=True)
                topk_mask = torch.zeros_like(diagonal_removed.reshape(-1), device=diagonal_removed.device)
                topk_mask[indices] = 1
                topk_mask = topk_mask.view_as(diagonal_removed)
                topk_graph = topk_mask * diagonal_removed
                self_loop_graph = topk_graph + torch.eye(gc.n_vars, device=diagonal_removed.device)
                normalized = self_loop_graph / self_loop_graph.sum(1).view(-1, 1)
                windows.append({
                    "window": index,
                    "static_prior": gc.init_adj_matrix.detach().cpu(),
                    "raw_score": raw_score.detach().cpu(),
                    "activated": activated.detach().cpu(),
                    "diagonal_removed": diagonal_removed.detach().cpu(),
                    "topk_mask": topk_mask.detach().cpu(),
                    "topk_graph": topk_graph.detach().cpu(),
                    "self_loop_graph": self_loop_graph.detach().cpu(),
                    "normalized": normalized.detach().cpu(),
                    "topk_slots": edge_slots,
                    "blend_proportion": proportion,
                })
        return {"current_epoch": epoch, "windows": windows}

    def predict_with_graph_override(self, batch: Mapping[str, Any], graph_override: Mapping[str, Any]) -> Any:
        epoch = int(graph_override.get("current_epoch", batch.get("current_epoch", self.current_epoch)))
        protocol = dict(graph_override)
        protocol.pop("current_epoch", None)
        if protocol["type"] == "input_variable_mask":
            modified_batch = dict(batch)
            x = np.array(batch["x"], copy=True)
            x[:, protocol["variable"]] = 0
            modified_batch["x"] = x
            modified_batch["current_epoch"] = epoch
            return {"prediction": self.predict(modified_batch), "graph_before": None, "graph_after": None,
                    "renormalized": False, "protocol": protocol}

        stages = self.extract_graph_stages({"current_epoch": epoch})
        graphs = torch.stack([window["normalized"] for window in stages["windows"]]).to(self.device)
        if protocol["type"] == "global_structural_edge_removal":
            affected = []
            before = graphs.clone()
            for window in range(graphs.shape[0]):
                if float(graphs[window, protocol["source"], protocol["target"]]) > 0:
                    graphs[window] = apply_graph_intervention(graphs[window], {
                        "type": "structural_edge_removal", "source": protocol["source"],
                        "target": protocol["target"],
                    })
                    affected.append(window)
            after = graphs.clone()
            protocol["affected_windows"] = affected
        else:
            window = int(protocol["window"])
            before = graphs[window].clone()
            after = apply_graph_intervention(before, protocol)
            graphs[window] = after
        gc = self.model.model.gc
        original_forward = gc.forward

        def overridden_forward(_self, time_indices, current_epoch):
            selected = time_indices % _self.num_adj_matrices
            return graphs[selected]

        gc.forward = types.MethodType(overridden_forward, gc)
        try:
            modified_batch = dict(batch)
            modified_batch["current_epoch"] = epoch
            prediction = self.predict(modified_batch)
        finally:
            gc.forward = original_forward
        return {"prediction": prediction, "graph_before": before.cpu(), "graph_after": after.cpu(),
                "renormalized": protocol["type"] not in {"normalized_channel_mask", "identity"}, "protocol": protocol}

    def get_metadata(self) -> Mapping[str, Any]:
        return {"adapter": "DGraFormerAdapter", "dataset": self.dataset_name, "seed": self.seed,
                "current_epoch": self.current_epoch, "device": str(self.device), "source_root": str(self.source_root)}

    def close(self) -> None:
        if Path.cwd() == self.source_root:
            os.chdir(self._old_cwd)


class MSGNetAdapter(DynamicGraphForecastAdapter):
    """Adapter around the supplied MSGNet source without editing upstream files."""

    ADAPTER_ID = "msgnet"
    MODEL_NAME = "MSGNet"
    CAPABILITIES = AdapterCapabilities(
        graph_context_type="scale", supports_multi_context=True, supports_broader_context=True,
        audit_graph_key="adaptive", local_scope="single_scale", broader_scope="all_scales",
        dataset_formats=("ett_hour",),
    )

    def __init__(self, source_root: str, config: Mapping[str, Any]):
        self.source_root = Path(source_root).resolve()
        self.config = dict(config)
        self.seed = int(config.get("random_seed", 2021))
        random.seed(self.seed)
        np.random.seed(self.seed)
        torch.manual_seed(self.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(self.seed)
        source = str(self.source_root)
        if source not in sys.path:
            sys.path.insert(0, source)
        from models.MSGNet import Model
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.args = self._namespace()
        self.model = Model(self.args).float().to(self.device)
        self._datasets: dict[str, Any] = {}

    def _namespace(self) -> Namespace:
        ds, mc = self.config["dataset"], self.config["model_config"]
        return Namespace(
            task_name=mc["task_name"], seq_len=ds["seq_len"], label_len=ds["label_len"],
            pred_len=ds["pred_len"], top_k=mc["top_k"], d_model=mc["d_model"],
            d_ff=mc["d_ff"], n_heads=mc["n_heads"], dropout=mc["dropout"],
            c_out=mc["c_out"], conv_channel=mc["conv_channel"], skip_channel=mc["skip_channel"],
            gcn_depth=mc["gcn_depth"], propalpha=mc["propalpha"], node_dim=mc["node_dim"],
            e_layers=mc["e_layers"], enc_in=mc["enc_in"], embed=mc["embed"],
            freq=ds["frequency"], individual=mc["individual"],
        )

    def load_checkpoint(self, checkpoint_path: str) -> None:
        state = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(state)
        self.model.eval()

    def _dataset(self, split: str):
        if split not in self._datasets:
            from data_provider.data_loader import Dataset_ETT_hour
            ds = self.config["dataset"]
            path = Path(ds["path"])
            self._datasets[split] = Dataset_ETT_hour(
                root_path=str(path.parent), data_path=path.name, flag=split,
                size=[ds["seq_len"], ds["label_len"], ds["pred_len"]],
                features=ds["features"], target=ds["target"], timeenc=1, freq=ds["frequency"],
            )
        return self._datasets[split]

    def load_sample(self, split: str, sample_index: int) -> Mapping[str, Any]:
        x, y, x_mark, y_mark = self._dataset(split)[sample_index]
        return {"x": x, "y": y, "x_mark": x_mark, "y_mark": y_mark,
                "sample_index": sample_index, "split": split}

    def _tensors(self, batch: Mapping[str, Any]):
        def tensor(value):
            result = torch.as_tensor(value, dtype=torch.float32, device=self.device)
            return result.unsqueeze(0) if result.ndim == 2 else result
        x, y = tensor(batch["x"]), tensor(batch["y"])
        x_mark, y_mark = tensor(batch["x_mark"]), tensor(batch["y_mark"])
        dec = torch.cat([y[:, : self.args.label_len], torch.zeros_like(y[:, -self.args.pred_len :])], dim=1)
        return x, y, x_mark, y_mark, dec

    def predict(self, batch: Mapping[str, Any]) -> torch.Tensor:
        x, _, x_mark, y_mark, dec = self._tensors(batch)
        with torch.no_grad():
            return self.model(x, x_mark, dec, y_mark).detach().cpu()

    @staticmethod
    def _graph_stages(graph_block) -> Mapping[str, torch.Tensor]:
        raw = torch.mm(graph_block.nodevec1, graph_block.nodevec2)
        activated = F.relu(raw)
        adaptive = F.softmax(activated, dim=1)
        self_loop = adaptive + torch.eye(adaptive.shape[0], device=adaptive.device)
        effective = self_loop / self_loop.sum(1, keepdim=True)
        return {"raw_affinity": raw, "activated": activated, "adaptive": adaptive,
                "self_loop_graph": self_loop, "effective": effective}

    def extract_graph_stages(self, batch: Mapping[str, Any]) -> Mapping[str, Any]:
        from models.MSGNet import FFT_for_Period
        x, _, x_mark, _, _ = self._tensors(batch)
        contexts = []
        with torch.no_grad():
            means = x.mean(1, keepdim=True)
            normalized = (x - means) / torch.sqrt(torch.var(x, dim=1, keepdim=True, unbiased=False) + 1e-5)
            layer_input = self.model.enc_embedding(normalized, x_mark)
            for layer_index, scale_block in enumerate(self.model.model):
                periods, weights = FFT_for_Period(layer_input, scale_block.k)
                contributions = F.softmax(weights, dim=1)
                for scale_index, graph_block in enumerate(scale_block.gconv):
                    stages = self._graph_stages(graph_block)
                    contexts.append({
                        "layer": layer_index, "scale_index": scale_index,
                        "period": int(periods[scale_index]),
                        "fft_strength": float(weights[0, scale_index]),
                        "scale_contribution": float(contributions[0, scale_index]),
                        **{key: value.detach().cpu() for key, value in stages.items()},
                    })
                layer_input = self.model.layer_norm(scale_block(layer_input))
        return {"contexts": contexts}

    def predict_with_graph_override(self, batch: Mapping[str, Any], graph_override: Mapping[str, Any]) -> Any:
        layer = int(graph_override.get("layer", 0))
        selected = graph_override.get("scale_index")
        targets = range(self.args.top_k) if graph_override.get("scope") == "global" else [int(selected)]
        originals = {}
        before, after = {}, {}
        for scale_index in targets:
            block = self.model.model[layer].gconv[scale_index]
            stages = self._graph_stages(block)
            adaptive = stages["adaptive"].detach().clone()
            modified = adaptive.clone()
            kind = graph_override["type"]
            if kind == "structural_edge_removal":
                modified[int(graph_override["source"]), int(graph_override["target"])] = 0
            elif kind != "identity":
                raise ValueError(f"Unsupported MSGNet intervention: {kind}")
            originals[scale_index] = block.gconv1.forward
            before[scale_index] = adaptive.cpu()
            after[scale_index] = modified.cpu()

            def overridden(_self, x, adj, fixed=modified):
                return originals_local(_self, x, fixed)

            originals_local = block.gconv1.forward.__func__
            block.gconv1.forward = types.MethodType(overridden, block.gconv1)
        try:
            prediction = self.predict(batch)
        finally:
            for scale_index, original in originals.items():
                self.model.model[layer].gconv[scale_index].gconv1.forward = original
        return {"prediction": prediction, "graph_before": before, "graph_after": after,
                "renormalized": True, "protocol": dict(graph_override)}

    def get_metadata(self) -> Mapping[str, Any]:
        return {"adapter": "MSGNetAdapter", "dataset": self.config["dataset"]["name"],
                "seed": self.seed, "device": str(self.device), "source_root": str(self.source_root)}


class MTGNNAdapter(DynamicGraphForecastAdapter):
    """Adapter around the supplied MTGNN source without editing upstream files."""

    ADAPTER_ID = "mtgnn"
    MODEL_NAME = "MTGNN"
    CAPABILITIES = AdapterCapabilities(
        graph_context_type="global_graph", audit_graph_key="learned_adjacency",
        local_scope="global_graph", dataset_formats=("mtgnn_matrix",),
    )

    def __init__(self, source_root: str, config: Mapping[str, Any]):
        self.source_root = Path(source_root).resolve()
        self.config = dict(config)
        self.seed = int(config.get("random_seed", 42))
        random.seed(self.seed)
        np.random.seed(self.seed)
        torch.manual_seed(self.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(self.seed)
        source = str(self.source_root)
        if source not in sys.path:
            sys.path.insert(0, source)
        from net import gtnet

        mc = self.config["model_config"]
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.model = gtnet(
            bool(mc["gcn_true"]), bool(mc["build_a_true"]), int(mc["gcn_depth"]),
            int(mc["num_nodes"]), self.device, predefined_A=None, static_feat=None,
            dropout=float(mc["dropout"]), subgraph_size=int(mc["subgraph_size"]),
            node_dim=int(mc["node_dim"]), dilation_exponential=int(mc["dilation_exponential"]),
            conv_channels=int(mc["conv_channels"]), residual_channels=int(mc["residual_channels"]),
            skip_channels=int(mc["skip_channels"]), end_channels=int(mc["end_channels"]),
            seq_length=int(mc["seq_in_len"]), in_dim=int(mc["in_dim"]),
            out_dim=int(mc["seq_out_len"]), layers=int(mc["layers"]),
            propalpha=float(mc["propalpha"]), tanhalpha=float(mc["tanhalpha"]),
            layer_norm_affline=bool(mc["layer_norm_affline"]),
        ).float().to(self.device)
        self._datasets: dict[str, Any] = {}

    def load_checkpoint(self, checkpoint_path: str) -> None:
        payload = torch.load(checkpoint_path, map_location=self.device)
        state = payload.get("state_dict", payload) if isinstance(payload, Mapping) else payload
        self.model.load_state_dict(state, strict=True)
        self.model.eval()

    def _dataset(self, split: str):
        if split != "test":
            raise ValueError("MTGNNAdapter currently supports only the test split.")
        if split not in self._datasets:
            from util import DataLoaderS

            ds, mc = self.config["dataset"], self.config["model_config"]
            self._datasets[split] = DataLoaderS(
                ds["path"], float(mc["train_ratio"]), float(mc["validation_ratio"]),
                self.device, int(mc["horizon"]), int(mc["seq_in_len"]),
                int(mc["normalize"]),
            )
        return self._datasets[split]

    def load_sample(self, split: str, sample_index: int) -> Mapping[str, Any]:
        dataset = self._dataset(split)
        x_normalized = dataset.test[0][sample_index].clone()
        y_normalized = dataset.test[1][sample_index].clone()
        scale = dataset.scale.detach().cpu()
        return {
            "x": x_normalized * scale.view(1, -1),
            "y": (y_normalized * scale).view(1, -1),
            "x_normalized": x_normalized,
            "sample_index": sample_index,
            "split": split,
        }

    def _model_input(self, batch: Mapping[str, Any]) -> torch.Tensor:
        x = torch.as_tensor(batch["x_normalized"], dtype=torch.float32, device=self.device)
        if x.ndim == 2:
            x = x.unsqueeze(0)
        return x.unsqueeze(1).transpose(2, 3)

    def predict(self, batch: Mapping[str, Any]) -> torch.Tensor:
        with torch.no_grad():
            output = self.model(self._model_input(batch))
        prediction = output.squeeze(-1)
        scale = self._dataset(str(batch.get("split", "test"))).scale.view(1, 1, -1)
        return (prediction * scale).detach().cpu()

    def extract_graph_stages(self, batch: Mapping[str, Any]) -> Mapping[str, Any]:
        with torch.no_grad():
            learned = self.model.gc(self.model.idx).detach().cpu()
        return {"contexts": [{
            "index": 0,
            "learned_adjacency": learned,
            "transpose_adjacency": learned.transpose(0, 1).contiguous(),
            "edge_count": int((learned > 0).sum()),
            "subgraph_size": int(self.config["model_config"]["subgraph_size"]),
            "gcn_layer_count": int(self.config["model_config"]["layers"]),
            "construction": "MTGNN graph_constructor output shared by every gconv1 layer; transpose shared by every gconv2 layer",
        }]}

    def predict_with_graph_override(
        self, batch: Mapping[str, Any], graph_override: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        with torch.no_grad():
            before = self.model.gc(self.model.idx).detach().clone()
        after = before.clone()
        kind = graph_override["type"]
        if kind == "structural_edge_removal":
            after[int(graph_override["source"]), int(graph_override["target"])] = 0
        elif kind != "identity":
            raise ValueError(f"Unsupported MTGNN intervention: {kind}")

        original_forward = self.model.gc.forward

        def overridden_forward(_self, idx):
            return after.index_select(0, idx).index_select(1, idx)

        self.model.gc.forward = types.MethodType(overridden_forward, self.model.gc)
        try:
            prediction = self.predict(batch)
        finally:
            self.model.gc.forward = original_forward
        protocol = {
            **dict(graph_override),
            "applied_to": "shared learned adjacency before every MTGNN mixprop layer",
            "transpose_branch_updated": True,
            "internal_mixprop_normalization": True,
        }
        return {
            "prediction": prediction,
            "graph_before": before.cpu(),
            "graph_after": after.cpu(),
            "renormalized": False,
            "protocol": protocol,
        }

    def get_metadata(self) -> Mapping[str, Any]:
        return {
            "adapter": "MTGNNAdapter",
            "dataset": self.config["dataset"]["name"],
            "seed": self.seed,
            "device": str(self.device),
            "source_root": str(self.source_root),
        }

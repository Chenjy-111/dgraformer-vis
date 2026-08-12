from __future__ import annotations

import os
import random
import sys
import types
from abc import ABC, abstractmethod
from argparse import Namespace
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import torch
import torch.nn.functional as F


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


class DGraFormerAdapter(DynamicGraphForecastAdapter):
    """Thin adapter around the supplied, unmodified DGraFormer inference path."""

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
        from exp.exp_main import Exp_Main

        args = self._namespace()
        self.exp = Exp_Main(args)
        self.model = self.exp.model
        self.device = self.exp.device
        self._datasets: dict[str, Any] = {}

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

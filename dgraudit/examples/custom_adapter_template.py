"""DGraInsight custom adapter template.

Copy this file into your model source tree and replace every NotImplementedError.
Do not return random graphs, cached fake predictions, or placeholder evidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from dgraudit.adapters import AdapterCapabilities, DynamicGraphForecastAdapter, GraphContext


class MyGraphAdapter(DynamicGraphForecastAdapter):
    ADAPTER_ID = "replace_with_stable_adapter_id"
    MODEL_NAME = "ReplaceWithModelName"
    ADAPTER_VERSION = None  # Use a real release/source identity, otherwise leave unavailable.
    CAPABILITIES = AdapterCapabilities(
        graph_context_type="replace_with_context_type",  # e.g. window, scale, global, or a truthful custom type
        supports_quick_inspection=True,
        supports_graph_override=True,
        supports_multi_context=False,
        supports_broader_context=False,
        audit_graph_key="audit_graph",
        local_scope="single_context",
        dataset_formats=("replace_with_dataset_format",),
    )

    def __init__(self, config: Mapping[str, Any], resolved_paths: Mapping[str, Path]):
        # Initialize the real architecture from model source + adapter_config here.
        # Keep the resolved dataset/checkpoint paths; do not load an arbitrary checkpoint yet.
        self.config = config
        self.resolved_paths = resolved_paths
        raise NotImplementedError("Initialize the real model, preprocessing, and device.")

    @classmethod
    def from_audit_config(cls, config, resolved_paths):
        # This is the stable explicit construction hook used by the local loader.
        return cls(config, resolved_paths)

    @classmethod
    def validate_dataset_file(cls, dataset_path: Path, dataset_config: Mapping[str, Any]):
        # Optional: override this only when the native dataset is not the default date-column CSV.
        # Validate the original file/shape/node order without converting it to a misleading format.
        # Return bounded technical measurements; raise on incompatibility. Returning None uses the
        # default strict CSV validator.
        return None

    def load_checkpoint(self, checkpoint_path: str) -> None:
        # Load the exact declared checkpoint, reject incompatible/missing state, move the model
        # to the correct device, and enable evaluation mode. Never retrain or silently ignore state.
        raise NotImplementedError("Load the exact checkpoint and call model.eval().")

    def load_sample(self, split: str, sample_index: int) -> Mapping[str, Any]:
        # Run the model's real preprocessing for this exact sample. Return every input needed by
        # predict(), extract_graph_stages(), and predict_with_graph_override(). Include x and y in
        # [seq_len, node] / [>=pred_len, node] form so the shared case-evidence path can serialize them.
        raise NotImplementedError("Load and preprocess one exact dataset sample.")

    def predict(self, batch: Mapping[str, Any]) -> Any:
        # Execute the real checkpoint-backed baseline forward. Return a finite tensor/array with
        # shape [1, pred_len, node_count]. A cached or synthetic prediction is not conformance.
        raise NotImplementedError("Run the real baseline forward.")

    def extract_graph_stages(self, batch: Mapping[str, Any]) -> Mapping[str, Any]:
        # Return the learned graph that ACTUALLY enters prediction computation, not a visual-only
        # similarity matrix. Each GraphContext needs stable node identity, context identity, and an
        # audit_graph that is exactly the replaceable operand used in forward.
        context = GraphContext(
            context_id="replace_with_stable_context_id",
            context_type=self.CAPABILITIES.graph_context_type,
            index=0,
            audit_graph=None,
            graphs={},
            display_label=None,
            metadata={},
        )
        del context
        raise NotImplementedError("Extract the actual forward graph as one or more GraphContext values.")

    def predict_with_graph_override(
        self, batch: Mapping[str, Any], graph_override: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        # This is the scientific execution boundary. Inject graph_override['graph'] at the actual
        # graph consumption point and re-run the model. For type='identity', inject it unchanged.
        # For type='structural_edge_removal', remove the exact source->target relation according to
        # your declared graph semantics, then inject that graph. Return the real prediction plus
        # graph_before, graph_after, and a bounded protocol mapping. Never edit only a display copy.
        raise NotImplementedError("Inject the graph override into the real forward path and rerun.")

    def get_metadata(self) -> Mapping[str, Any]:
        # Return technical provenance only: adapter/model/dataset identity, node labels, declared
        # graph contexts, device, checkpoint format, and any reliable version. Use None/unavailable
        # when an identity cannot be established; do not invent a hash or scientific interpretation.
        raise NotImplementedError("Return reproducible technical metadata.")

    def close(self) -> None:
        # Release adapter-scoped hooks, files, or process state if necessary.
        pass

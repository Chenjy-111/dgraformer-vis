from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from dgraudit.quick_audit import _context_id, _context_weight, _resolve
from dgraudit.validation import resolve_adapter_spec


def inspect_native_edges(
    config_path: str | Path,
    *,
    sample_index: int | None = None,
    context_index: int | None = None,
    layer: int | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Load a supported checkpoint and list real retained edges by native graph context."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    path = Path(config_path).resolve()
    config: Mapping[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    spec = resolve_adapter_spec(config, path)
    if spec is None:
        raise ValueError(f"Unsupported adapter: {config.get('adapter')}")
    resolved = {
        "source_root": _resolve(path.parent, config["source_root"]),
        "dataset": _resolve(path.parent, config["dataset"]["path"]),
        "checkpoint": _resolve(path.parent, config["checkpoint"]["path"]),
    }
    if sample_index is None:
        sample_index = int(config["audit"]["samples"][0])
    adapter = spec.create_adapter(config, resolved)
    try:
        adapter.load_checkpoint(str(resolved["checkpoint"]))
        raw = adapter.load_sample(config["audit"]["split"], sample_index)
        batch = spec.prepare_batch(raw, config)
        extracted = adapter.extract_graph_stages(batch)
        contexts = spec.contexts(extracted)
        variables = list(config["dataset"]["variables"])
        results = []
        for context in contexts:
            native_index = spec.context_index(context)
            native_layer = int(context["layer"]) if "layer" in context else None
            if context_index is not None and native_index != context_index:
                continue
            if layer is not None and native_layer != layer:
                continue
            matrix = _context_weight(spec, context)
            edges = [
                {
                    "source": source,
                    "target": target,
                    "source_name": variables[source],
                    "target_name": variables[target],
                    "weight": float(matrix[source, target]),
                }
                for source in range(matrix.shape[0])
                for target in range(matrix.shape[1])
                if source != target and float(matrix[source, target]) > 0
            ]
            edges.sort(key=lambda item: (-item["weight"], item["source"], item["target"]))
            results.append({
                "context_id": _context_id(spec, context),
                "type": spec.native_context_type,
                "index": native_index,
                "layer": native_layer,
                "retained_edge_count": len(edges),
                "top_edges": edges[:limit],
            })
        if not results:
            raise ValueError("No native graph context matches the requested context/layer filter.")
        return {
            "model": spec.model_name,
            "adapter": spec.adapter_name,
            "dataset": config["dataset"]["name"],
            "sample_index": sample_index,
            "native_context_type": spec.native_context_type,
            "native_context_count": len(contexts),
            "displayed_context_count": len(results),
            "contexts": results,
        }
    finally:
        adapter.close()


def render_edge_inspection(report: Mapping[str, Any]) -> str:
    lines = [
        "DGraInsight Native Graph Inspector",
        "",
        f"Model: {report['model']} | Dataset: {report['dataset']} | test sample {report['sample_index']}",
        f"Native graphs found: {report['native_context_count']} ({report['native_context_type']})",
    ]
    for context in report["contexts"]:
        lines.extend(["", f"[{context['context_id']}] retained directed edges: {context['retained_edge_count']}"])
        for rank, edge in enumerate(context["top_edges"], start=1):
            lines.append(
                f"  {rank:>2}. {edge['source_name']} -> {edge['target_name']}  "
                f"source={edge['source']} target={edge['target']} weight={edge['weight']:.9f}"
            )
    lines.extend([
        "",
        "Copy source, target, and the shown native context into audit.relations in the config.",
    ])
    return "\n".join(lines)

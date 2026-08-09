from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import torch

from dgraudit.adapters import DGraFormerAdapter


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def edges_for_window(scores: torch.Tensor, mask: torch.Tensor) -> list[dict]:
    n = scores.shape[0]
    ranked = sorted(((float(scores[i, j]), i, j) for i in range(n) for j in range(n) if i != j), reverse=True)
    ranks = {(i, j): rank for rank, (_, i, j) in enumerate(ranked, 1)}
    return [{"source": i, "target": j, "weight": float(scores[i, j]), "rank": ranks[(i, j)],
             "kept": bool(mask[i, j] == 1 and scores[i, j] > 0)}
            for i in range(n) for j in range(n) if i != j]


def attention_record(layer, scale: int, patch_steps: int, n_vars: int) -> dict:
    values = layer.attn.detach().cpu().reshape(n_vars, layer.attn.shape[1], layer.attn.shape[-2], layer.attn.shape[-1])
    averaged = values.mean(0)
    return {"scale": scale, "patchSteps": patch_steps, "nPatches": values.shape[-1],
            "heads": averaged.tolist(), "mean": averaged.mean(0).tolist(),
            "variableHeads": values.tolist(),
            "semantic": {1: "fine-grained local patches", 2: "medium-range combined patches", 3: "coarse combined patches"}[scale]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="configs/phase1_registry.json")
    parser.add_argument("--output-root", default="artifacts/runs")
    parser.add_argument("--web-output", default="public/data/samples")
    args = parser.parse_args()
    workspace_root = Path.cwd().resolve()
    registry_path = Path(args.registry).resolve()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    source = Path(registry["source_root"])
    schedule = registry["schedule"]
    epoch = int(schedule["current_epoch_equivalent"])
    fingerprints = [sha256(registry_path), json.dumps(schedule, sort_keys=True)]
    for name, ds in registry["datasets"].items():
        fingerprints.extend([sha256(source / "checkpoints" / ds["setting"] / "checkpoint.pth"),
                             sha256(source / ds["root_path"] / ds["data_path"])])
    run_id = hashlib.sha256("|".join(fingerprints).encode()).hexdigest()
    run_dir = Path(args.output_root).resolve() / run_id
    prediction_dir = run_dir / "predictions"
    graph_dir = run_dir / "graphs"
    web_dir = Path(args.web_output).resolve()
    variables_by_dataset = json.loads(
        (workspace_root / "public/data/index.json").read_text(encoding="utf-8")
    )["datasets"]
    prediction_dir.mkdir(parents=True, exist_ok=True)
    graph_dir.mkdir(parents=True, exist_ok=True)
    web_dir.mkdir(parents=True, exist_ok=True)
    summaries = []

    for name, ds in registry["datasets"].items():
        adapter = DGraFormerAdapter(str(source), name, registry["common"], ds, registry["random_seed"])
        checkpoint = source / "checkpoints" / ds["setting"] / "checkpoint.pth"
        data_path = source / ds["root_path"] / ds["data_path"]
        adapter.load_checkpoint(str(checkpoint))
        for encoder in [adapter.model.model.mtt.encoder1, adapter.model.model.mtt.encoder2, adapter.model.model.mtt.encoder3]:
            encoder.layers[0].store_attn = True
        stages = adapter.extract_graph_stages({"current_epoch": epoch})
        graph_payload = {"dataset": name, "current_epoch": epoch,
                         "schedule": schedule,
                         "stages": [{k: (v.tolist() if isinstance(v, torch.Tensor) else v) for k, v in w.items()}
                                    for w in stages["windows"]]}
        graph_path = graph_dir / f"{name}.json"
        graph_path.write_text(json.dumps(graph_payload, indent=2), encoding="utf-8")
        predictions = []
        truths = []
        inputs = []
        generated = []
        for web_id, test_index in enumerate(ds["web_sample_indices"]):
            batch = adapter.load_sample("test", test_index)
            prediction = adapter.predict({**batch, "current_epoch": epoch}).squeeze(0)
            truth = torch.as_tensor(batch["y"][-registry["common"]["pred_len"]:, :], dtype=torch.float32)
            history = torch.as_tensor(batch["x"], dtype=torch.float32)
            time_index = np.asarray(batch["time_index"], dtype=int) % len(stages["windows"])
            variables = variables_by_dataset[name]["variables"]
            windows = []
            for w in stages["windows"]:
                scores = w["diagonal_removed"]
                mask = w["topk_mask"]
                edge_list = edges_for_window(scores, mask)
                kept = [edge for edge in edge_list if edge["kept"]]
                filtered = [edge for edge in edge_list if not edge["kept"]]
                active_steps = np.flatnonzero(time_index == w["window"]).tolist()
                windows.append({
                    "window_id": w["window"], "start": min(active_steps) if active_steps else 0,
                    "end": max(active_steps) + 1 if active_steps else 0,
                    "active_input_steps": active_steps,
                    "static_graph": w["static_prior"].tolist(),
                    "dynamic_graph": scores.tolist(),
                    "sparse_graph": w["normalized"].tolist(),
                    "edges": edge_list, "kept_edges": kept, "filtered_edges": filtered,
                    "top_edges": sorted(kept, key=lambda edge: edge["rank"])[:5],
                    "sparsity_ratio": len(filtered) / max(1, len(edge_list)),
                    "mean_error": None, "explanation": "",
                })
            error = (truth - prediction).abs()
            mse = float(((truth - prediction) ** 2).mean())
            mae = float(error.mean())
            sample = {
                "dataset": name, "sample_id": web_id, "horizon": 96, "variables": variables,
                "targetDefault": len(variables) - 1, "history": history.T.tolist(),
                "ground_truth": truth.T.tolist(), "prediction": prediction.T.tolist(), "error": error.T.tolist(),
                "windows": windows, "windowSize": 24, "patchLen": 8,
                "attention": {
                    "scale_1": attention_record(adapter.model.model.mtt.encoder1.layers[0], 1, 8, len(variables)),
                    "scale_2": attention_record(adapter.model.model.mtt.encoder2.layers[0], 2, 16, len(variables)),
                    "scale_3": attention_record(adapter.model.model.mtt.encoder3.layers[0], 3, 32, len(variables)),
                },
                "metrics": {"mse": mse, "mae": mae},
                "narrative": f"DGraFormer final-schedule checkpoint output for {name} test sample {test_index}.",
                "provenance": {"scheduleState": schedule["state"], "currentEpochEquivalent": epoch,
                    "staticWeight": schedule["static_weight"], "learnedWeight": schedule["learned_weight"],
                    "testSampleIndex": test_index, "checkpointSha256": sha256(checkpoint),
                    "dataSha256": sha256(data_path), "runId": run_id},
            }
            web_path = web_dir / f"{name}_{web_id:03d}_h96.json"
            web_path.write_text(json.dumps(sample, indent=2), encoding="utf-8")
            predictions.append(prediction.numpy()); truths.append(truth.numpy()); inputs.append(history.numpy())
            generated.append({"web_sample_id": web_id, "test_sample_index": test_index,
                              "web_path": str(web_path), "web_sha256": sha256(web_path), "mse": mse, "mae": mae})
        np.save(prediction_dir / f"{name}_pred.npy", np.stack(predictions))
        np.save(prediction_dir / f"{name}_true.npy", np.stack(truths))
        np.save(prediction_dir / f"{name}_x.npy", np.stack(inputs))
        summaries.append({"dataset": name, "checkpoint_sha256": sha256(checkpoint), "data_sha256": sha256(data_path),
                          "graph_sha256": sha256(graph_path), "samples": generated})

    manifest = {"run_id": run_id, "status": "complete", "schedule": schedule,
                "registry_path": str(registry_path), "registry_sha256": sha256(registry_path), "datasets": summaries}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "command.txt").write_text(
        f"python -m dgraudit.cli.rebuild_canonical --registry {args.registry} --output-root {args.output_root} --web-output {args.web_output}\n", encoding="utf-8")
    (run_dir / "environment.json").write_text(json.dumps({"python": platform.python_version(), "torch": torch.__version__, "cuda": torch.version.cuda}, indent=2), encoding="utf-8")
    (run_dir / "stdout.log").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (run_dir / "stderr.log").write_text("", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "status": "complete", "schedule": schedule, "sample_count": 25}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

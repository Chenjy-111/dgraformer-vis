from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import torch

from dgraudit.adapters import MSGNetAdapter


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metrics(base: torch.Tensor, changed: torch.Tensor, truth: torch.Tensor) -> dict:
    delta = changed - base
    return {
        "prediction_delta_abs": float(delta.abs().mean()),
        "prediction_delta_max": float(delta.abs().max()),
        "error_delta_mae": float((changed - truth).abs().mean() - (base - truth).abs().mean()),
        "error_delta_mse": float((changed - truth).square().mean() - (base - truth).square().mean()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/msgnet_etth1.json")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output-root", default="artifacts/runs")
    args = parser.parse_args()
    config_path, checkpoint = Path(args.config).resolve(), Path(args.checkpoint).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    adapter = MSGNetAdapter(config["source_root"], config)
    adapter.load_checkpoint(str(checkpoint))
    run_id = hashlib.sha256("|".join((sha256(config_path), sha256(checkpoint), "msgnet_edge_scan_v1")).encode()).hexdigest()
    run_dir = Path(args.output_root).resolve() / run_id
    evidence_dir = run_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    names = ["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL", "OT"]
    cases = []
    for sample_index in config["dataset"]["web_sample_indices"]:
        batch = adapter.load_sample("test", sample_index)
        baseline = adapter.predict(batch)
        truth = torch.as_tensor(batch["y"][-config["dataset"]["pred_len"]:], dtype=torch.float32).unsqueeze(0)
        contexts = adapter.extract_graph_stages(batch)["contexts"]
        for context in contexts:
            for source in range(len(names)):
                for target in range(len(names)):
                    if source == target:
                        continue
                    result = adapter.predict_with_graph_override(batch, {
                        "type": "structural_edge_removal", "scope": "local", "layer": context["layer"],
                        "scale_index": context["scale_index"], "source": source, "target": target,
                    })
                    cases.append({
                        "sample_index": sample_index, "layer": context["layer"],
                        "scale_index": context["scale_index"], "period": context["period"],
                        "scale_contribution": context["scale_contribution"],
                        "source": source, "target": target, "source_name": names[source],
                        "target_name": names[target],
                        "adaptive_weight": float(context["adaptive"][source, target]),
                        **metrics(baseline, result["prediction"], truth),
                    })
    ranked = sorted(cases, key=lambda item: item["prediction_delta_abs"], reverse=True)
    report = {
        "run_id": run_id, "status": "complete", "model": "MSGNet", "dataset": "ETTh1",
        "intervention": "single-scale structural edge removal before MixHop self-loop addition and normalization",
        "config_sha256": sha256(config_path), "checkpoint_sha256": sha256(checkpoint),
        "case_count": len(cases), "cases": cases, "top_cases": ranked[:20],
        "notice": "All effects are checkpoint-internal responses, not real-world causal effects.",
    }
    (evidence_dir / "msgnet_etth1_edge_scan.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps({key: report[key] for key in (
        "run_id", "status", "model", "dataset", "intervention", "config_sha256", "checkpoint_sha256", "case_count", "top_cases", "notice")
    }, indent=2), encoding="utf-8")
    (run_dir / "command.txt").write_text(
        f"python -m dgraudit.cli.scan_msgnet_edge_impacts --config {args.config} --checkpoint {args.checkpoint}\n",
        encoding="utf-8")
    (run_dir / "stdout.log").write_text(json.dumps({"run_id": run_id, "case_count": len(cases), "top_cases": ranked[:5]}, indent=2) + "\n", encoding="utf-8")
    (run_dir / "stderr.log").write_text("", encoding="utf-8")
    print(json.dumps({"run_id": run_id, "case_count": len(cases), "top_cases": ranked[:5]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

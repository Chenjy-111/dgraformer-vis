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


def serializable(context: dict) -> dict:
    return {key: value.tolist() if isinstance(value, torch.Tensor) else value for key, value in context.items()}


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
    fingerprint = "|".join((sha256(config_path), sha256(checkpoint), "msgnet_graph_identity_v1"))
    run_id = hashlib.sha256(fingerprint.encode()).hexdigest()
    run_dir = Path(args.output_root).resolve() / run_id
    graph_dir = run_dir / "graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    samples = []
    for sample_index in config["dataset"]["web_sample_indices"]:
        batch = adapter.load_sample("test", sample_index)
        baseline = adapter.predict(batch)
        extracted = adapter.extract_graph_stages(batch)
        validations = []
        for context in extracted["contexts"]:
            identity = adapter.predict_with_graph_override(batch, {
                "type": "identity", "scope": "local", "layer": context["layer"],
                "scale_index": context["scale_index"],
            })["prediction"]
            difference = torch.abs(baseline - identity)
            torch.testing.assert_close(baseline, identity, atol=config["baseline_atol"], rtol=config["baseline_rtol"])
            validations.append({
                "layer": context["layer"], "scale_index": context["scale_index"],
                "period": context["period"], "scale_contribution": context["scale_contribution"],
                "adaptive_row_sum_max_error": float((context["adaptive"].sum(1) - 1).abs().max()),
                "effective_row_sum_max_error": float((context["effective"].sum(1) - 1).abs().max()),
                "identity_max_absolute_difference": float(difference.max()),
                "finite": bool(torch.isfinite(context["effective"]).all()),
            })
        record = {"sample_index": sample_index, "contexts": [serializable(c) for c in extracted["contexts"]],
                  "validations": validations}
        (graph_dir / f"sample_{sample_index}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        samples.append({"sample_index": sample_index, "validations": validations})
    report = {"run_id": run_id, "status": "complete", "model": "MSGNet", "dataset": "ETTh1",
              "config_sha256": sha256(config_path), "checkpoint_sha256": sha256(checkpoint), "samples": samples}
    (run_dir / "manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (run_dir / "command.txt").write_text(
        f"python -m dgraudit.cli.validate_msgnet_graphs --config {args.config} --checkpoint {args.checkpoint}\n",
        encoding="utf-8")
    (run_dir / "stdout.log").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (run_dir / "stderr.log").write_text("", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

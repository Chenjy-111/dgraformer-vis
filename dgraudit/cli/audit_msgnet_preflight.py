from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path


SOURCE_FILES = (
    "models/MSGNet.py",
    "layers/MSGBlock.py",
    "data_provider/data_loader.py",
    "data_provider/data_factory.py",
    "exp/exp_main.py",
    "run_longExp.py",
    "scripts/ETTh1.sh",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_dates(path: Path) -> tuple[list[str], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        dates = [row["date"] for row in reader]
    return columns, dates


def sample_record(index: int, dates: list[str], seq_len: int, pred_len: int) -> dict:
    # Dataset_ETT_hour test border is 12 months train + 4 months validation,
    # with seq_len history rows prepended to the test slice.
    test_origin = 12 * 30 * 24 + 4 * 30 * 24
    history_start = test_origin - seq_len + index
    history_end = history_start + seq_len - 1
    forecast_start = history_end + 1
    forecast_end = forecast_start + pred_len - 1
    if forecast_end >= len(dates):
        raise IndexError(f"Sample {index} exceeds dataset length")
    return {
        "website_sample_index": index,
        "msgnet_test_index": index,
        "raw_indices": {
            "history_start": history_start,
            "history_end": history_end,
            "forecast_start": forecast_start,
            "forecast_end": forecast_end,
        },
        "timestamps": {
            "history_start": dates[history_start],
            "history_end": dates[history_end],
            "forecast_start": dates[forecast_start],
            "forecast_end": dates[forecast_end],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/msgnet_etth1.json")
    parser.add_argument("--output", default="artifacts/msgnet_preflight")
    args = parser.parse_args()
    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    source = Path(config["source_root"]).resolve()
    dataset = Path(config["dataset"]["path"]).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    source_hashes = {}
    missing_source_files = []
    for relative in SOURCE_FILES:
        path = source / relative
        if path.is_file():
            source_hashes[relative] = sha256(path)
        else:
            missing_source_files.append(relative)

    actual_data_hash = sha256(dataset) if dataset.is_file() else None
    columns, dates = read_dates(dataset) if dataset.is_file() else ([], [])
    ds = config["dataset"]
    samples = [sample_record(i, dates, ds["seq_len"], ds["pred_len"])
               for i in ds["web_sample_indices"]] if dates else []
    checkpoint_value = config["training"].get("checkpoint_path")
    checkpoint = Path(checkpoint_value).resolve() if checkpoint_value else None

    checks = {
        "source_root_exists": source.is_dir(),
        "required_source_files_present": not missing_source_files,
        "dataset_exists": dataset.is_file(),
        "dataset_hash_matches": actual_data_hash == ds["sha256"],
        "dataset_columns_match_etth1": columns == ["date", "HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL", "OT"],
        # The official loader consumes fixed ETT borders through row 17280.
        # Canonical ETTh1 CSVs may contain additional trailing rows.
        "dataset_covers_official_split": len(dates) >= 12 * 30 * 24 + 8 * 30 * 24,
        "checkpoint_available": bool(checkpoint and checkpoint.is_file()),
    }
    status = "ready_for_baseline" if all(checks.values()) else "blocked_before_baseline"
    report = {
        "phase": "MSGNet Phase 1 preflight",
        "status": status,
        "generated_at": datetime.now().astimezone().isoformat(),
        "config_path": str(config_path),
        "config_sha256": sha256(config_path),
        "source_root": str(source),
        "source_repository": config["source_repository"],
        "source_commit": config.get("source_commit"),
        "source_hashes": source_hashes,
        "missing_source_files": missing_source_files,
        "dataset_path": str(dataset),
        "dataset_sha256": actual_data_hash,
        "dataset_columns": columns,
        "dataset_row_count": len(dates),
        "sample_alignment": samples,
        "checkpoint_path": str(checkpoint) if checkpoint else None,
        "checks": checks,
        "blocking_reasons": [name for name, passed in checks.items() if not passed],
        "notes": [
            "MSGNet and DGraFormer use the same Dataset_ETT_hour split formula for ETTh1.",
            "Matching test indices therefore map to matching raw history and forecast timestamps when seq_len and pred_len are equal.",
            "A checkpoint must be trained or supplied before any baseline, graph, or intervention result is claimed.",
        ],
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":")).encode()
    report["run_id"] = hashlib.sha256(canonical).hexdigest()
    (output / "preflight.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output / "command.txt").write_text(
        f"python dgraudit/cli/audit_msgnet_preflight.py --config {args.config} --output {args.output}\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "checks": checks, "run_id": report["run_id"]}, indent=2))
    return 0 if status == "ready_for_baseline" else 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd
import torch

from dgraudit.adapters import MSGNetAdapter


ROOT = Path(__file__).resolve().parents[2]
NAMES = ["HUFL", "HULL", "MUFL", "MULL", "LUFL", "LULL", "OT"]
RELATIONS = [(source, target) for source in range(7) for target in range(7) if source != target]
NUMERIC_CASE_FIELDS = (
    "prediction_delta_abs",
    "prediction_delta_max",
    "error_delta_mae",
    "error_delta_mse",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collection_sha256(paths: Iterable[Path], base: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix()):
        digest.update(path.relative_to(base).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_frozen_json(path: Path, value: Any) -> None:
    if path.exists():
        if read_json(path) != value:
            raise RuntimeError("Refusing to change frozen file: {}".format(path))
        return
    write_json(path, value)


def resolve_config_path(config_path: Path, value: str) -> Path:
    candidate = Path(value)
    return candidate.resolve() if candidate.is_absolute() else (ROOT / candidate).resolve()


def load_config(config_path: Path) -> Dict[str, Any]:
    config = read_json(config_path)
    dataset_path = resolve_config_path(config_path, config["dataset"]["path"])
    checkpoint_path = resolve_config_path(config_path, config["checkpoint"]["path"])
    if not dataset_path.is_file() or sha256(dataset_path) != config["dataset"]["sha256"]:
        raise RuntimeError("Dataset is missing or SHA-256 does not match the frozen config")
    if not checkpoint_path.is_file() or sha256(checkpoint_path) != config["checkpoint"]["sha256"]:
        raise RuntimeError("Checkpoint is missing or SHA-256 does not match the frozen config")
    upstream = Path(config["source_root"]).resolve()
    source_paths = {
        "models/MSGNet.py": upstream / "models/MSGNet.py",
        "layers/MSGBlock.py": upstream / "layers/MSGBlock.py",
        "data_provider/data_loader.py": upstream / "data_provider/data_loader.py",
        "dgraudit/adapters.py": ROOT / "dgraudit/adapters.py",
    }
    for label, path in source_paths.items():
        expected = config["source_file_sha256"][label]
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError("Source provenance mismatch for {}".format(label))
    config["_dataset_path"] = str(dataset_path)
    config["_checkpoint_path"] = str(checkpoint_path)
    config["_config_path"] = str(config_path)
    return config


def dataset_instance(config: Mapping[str, Any]):
    source_root = Path(config["source_root"]).resolve()
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    from data_provider.data_loader import Dataset_ETT_hour

    ds = config["dataset"]
    path = Path(config["_dataset_path"])
    return Dataset_ETT_hour(
        root_path=str(path.parent),
        data_path=path.name,
        flag="test",
        size=[ds["seq_len"], ds["label_len"], ds["pred_len"]],
        features=ds["features"],
        target=ds["target"],
        timeenc=1,
        freq=ds["frequency"],
    )


def prepare(config_path: Path) -> None:
    config = load_config(config_path)
    output = (ROOT / config["output_root"]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    dataset = dataset_instance(config)
    valid_min, valid_max = 0, len(dataset) - 1
    count = int(config["selection"]["test_count"])
    selected = np.rint(np.linspace(valid_min, valid_max, count)).astype(int).tolist()
    if len(set(selected)) != count:
        raise RuntimeError("Deterministic test selection produced duplicate IDs")

    seq_len = int(config["dataset"]["seq_len"])
    pred_len = int(config["dataset"]["pred_len"])
    raw_span = seq_len + pred_len
    gaps = [selected[index + 1] - selected[index] for index in range(count - 1)]
    if min(gaps) < raw_span:
        raise RuntimeError("The frozen linspace rule cannot fit 14 non-overlapping tests")

    dates = pd.read_csv(config["_dataset_path"], usecols=["date"])["date"].tolist()
    test_border1 = 12 * 30 * 24 + 4 * 30 * 24 - seq_len
    tests = []
    for test_id in selected:
        raw_start = test_border1 + test_id
        raw_end = raw_start + raw_span - 1
        tests.append({
            "test_id": test_id,
            "raw_start": raw_start,
            "raw_end": raw_end,
            "input_start": raw_start,
            "input_end": raw_start + seq_len - 1,
            "forecast_start": raw_start + seq_len,
            "forecast_end": raw_end,
            "start_timestamp": dates[raw_start],
            "end_timestamp": dates[raw_end],
        })
    adjacent_overlap = sum(
        tests[index + 1]["raw_start"] <= tests[index]["raw_end"]
        for index in range(count - 1)
    )
    all_overlap = sum(
        not (left["raw_end"] < right["raw_start"] or right["raw_end"] < left["raw_start"])
        for index, left in enumerate(tests)
        for right in tests[index + 1 :]
    )
    if adjacent_overlap or all_overlap:
        raise RuntimeError("Frozen test protocol contains overlapping raw intervals")

    protocol = {
        "protocol_version": config["protocol_version"],
        "created_at": config["created_at"],
        "created_before_intervention": True,
        "selection_rule": config["selection"]["rule"],
        "dataset_path": config["_dataset_path"],
        "dataset_sha256": config["dataset"]["sha256"],
        "loader": "MSGNet data_provider.data_loader.Dataset_ETT_hour(flag='test')",
        "seq_len": seq_len,
        "pred_len": pred_len,
        "raw_span": raw_span,
        "valid_min_index": valid_min,
        "valid_max_index": valid_max,
        "valid_sample_count": len(dataset),
        "selected_test_ids": selected,
        "tests": tests,
        "start_gaps": gaps,
        "minimum_start_gap": min(gaps),
        "median_start_gap": float(np.median(gaps)),
        "overlapping_adjacent_pairs": int(adjacent_overlap),
        "overlapping_all_pairs": int(all_overlap),
    }
    protocol_path = output / "test_protocol.json"
    write_frozen_json(protocol_path, protocol)
    protocol_hash = sha256(protocol_path)
    sidecar = output / "test_protocol.sha256"
    if sidecar.exists() and sidecar.read_text(encoding="ascii").strip() != protocol_hash:
        raise RuntimeError("Frozen protocol hash sidecar disagrees with test_protocol.json")
    if not sidecar.exists():
        sidecar.write_text(protocol_hash + "\n", encoding="ascii")

    single_members = []
    for scale_index in config["hypotheses"]["scale_indices"]:
        for source, target in RELATIONS:
            single_members.append({
                "family_name": "single_scale",
                "hypothesis_id": "single_scale:{}:{}->{}".format(scale_index, source, target),
                "scale_index": scale_index,
                "source": source,
                "target": target,
                "source_name": NAMES[source],
                "target_name": NAMES[target],
            })
    all_members = [{
        "family_name": "all_scales",
        "hypothesis_id": "all_scales:{}->{}".format(source, target),
        "source": source,
        "target": target,
        "source_name": NAMES[source],
        "target_name": NAMES[target],
    } for source, target in RELATIONS]
    family = {
        "protocol_version": config["protocol_version"],
        "created_at": config["created_at"],
        "frozen_before_intervention": True,
        "selection_rule": "complete directed non-self graph; no outcome-based filtering",
        "hypothesis_identity": "scale_index (not observed FFT period) for single-scale; source,target for all-scale",
        "relation_universe_size": len(RELATIONS),
        "families": [
            {"family_name": "single_scale", "family_size": len(single_members), "members": single_members},
            {"family_name": "all_scales", "family_size": len(all_members), "members": all_members},
        ],
        "sanity_probes": {
            "single_scale": {
                "scale_indices": config["hypotheses"]["scale_indices"],
                **config["hypotheses"]["single_scale_sanity_probe"],
            },
            "all_scales": config["hypotheses"]["all_scale_sanity_probe"],
        },
    }
    write_frozen_json(output / "candidate_family.json", family)
    print(json.dumps({
        "status": "protocol_frozen",
        "test_protocol_sha256": protocol_hash,
        "selected_test_ids": selected,
        "single_family_size": len(single_members),
        "all_family_size": len(all_members),
    }, indent=2))


def relative_to_output(path: Path, output: Path) -> str:
    return path.relative_to(output).as_posix()


def tensor_numpy(value: Any) -> np.ndarray:
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().numpy()
    return np.asarray(value)


def save_array(path: Path, value: Any, expected_shape: Tuple[int, ...]) -> np.ndarray:
    array = np.asarray(tensor_numpy(value), dtype=np.float32)
    if array.shape != expected_shape or not np.isfinite(array).all():
        raise RuntimeError("Invalid array {} at {}".format(array.shape, path))
    if path.exists():
        existing = np.load(path)
        if existing.shape != expected_shape or not np.array_equal(existing, array):
            raise RuntimeError("Refusing to overwrite a different trajectory: {}".format(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, array)
    return array


def append_record(handle, record: Mapping[str, Any]) -> None:
    handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    handle.flush()


def load_jsonl(path: Path) -> Dict[str, Dict[str, Any]]:
    records: Dict[str, Dict[str, Any]] = {}
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            key = record["case_id"]
            if key in records:
                raise RuntimeError("Duplicate case_id {} in {} line {}".format(key, path, line_number))
            records[key] = record
    return records


def metric_record(
    *,
    case_id: str,
    test_id: int,
    scope: str,
    scale_index: Any,
    observed_period: Any,
    source: int,
    target: int,
    affected_scales: Sequence[int],
    baseline_file: Path,
    prediction_file: Path,
    output: Path,
    baseline: np.ndarray,
    changed: np.ndarray,
    truth: np.ndarray,
    weights_before: Sequence[float],
    runtime_graph_keys: Sequence[int],
) -> Dict[str, Any]:
    delta = changed - baseline
    values = [
        float(np.mean(np.abs(delta))),
        float(np.max(np.abs(delta))),
        float(np.mean(np.abs(changed - truth)) - np.mean(np.abs(baseline - truth))),
        float(np.mean(np.square(changed - truth)) - np.mean(np.square(baseline - truth))),
    ]
    if not np.isfinite(values).all():
        raise RuntimeError("Non-finite intervention metrics for {}".format(case_id))
    return {
        "case_id": case_id,
        "test_id": test_id,
        "scope": scope,
        "scale_index": scale_index,
        "observed_period": observed_period,
        "source": source,
        "target": target,
        "source_name": NAMES[source],
        "target_name": NAMES[target],
        "affected_scales": list(affected_scales),
        "runtime_graph_keys": list(runtime_graph_keys),
        "baseline_prediction_file": relative_to_output(baseline_file, output),
        "intervention_prediction_file": relative_to_output(prediction_file, output),
        "graph_before_focal_weights": list(weights_before),
        "graph_after_focal_weights": [0.0 for _ in weights_before],
        "prediction_delta_abs": values[0],
        "prediction_delta_max": values[1],
        "error_delta_mae": values[2],
        "error_delta_mse": values[3],
        "trajectory_shape": list(changed.shape),
        "trajectory_finite": True,
    }


def run_inference(config_path: Path) -> None:
    config = load_config(config_path)
    output = (ROOT / config["output_root"]).resolve()
    protocol_path = output / "test_protocol.json"
    family_path = output / "candidate_family.json"
    if not protocol_path.is_file() or not family_path.is_file():
        raise RuntimeError("Run prepare before any inference")
    frozen_hash = (output / "test_protocol.sha256").read_text(encoding="ascii").strip()
    if sha256(protocol_path) != frozen_hash:
        raise RuntimeError("test_protocol.json changed after freezing")
    protocol = read_json(protocol_path)
    family = read_json(family_path)
    if not protocol.get("created_before_intervention") or not family.get("frozen_before_intervention"):
        raise RuntimeError("Protocol/family is not marked frozen before intervention")
    if protocol["overlapping_adjacent_pairs"] or protocol["overlapping_all_pairs"]:
        raise RuntimeError("Overlapping tests are not allowed")

    adapter = MSGNetAdapter(config["source_root"], config)
    if config["device"] == "cuda:0" and adapter.device.type != "cuda":
        raise RuntimeError("Frozen protocol requires CUDA but CUDA is unavailable")
    adapter.load_checkpoint(config["_checkpoint_path"])
    output.joinpath("baseline").mkdir(parents=True, exist_ok=True)
    output.joinpath("single_scale_predictions").mkdir(parents=True, exist_ok=True)
    output.joinpath("all_scale_predictions").mkdir(parents=True, exist_ok=True)
    output.joinpath("validation").mkdir(parents=True, exist_ok=True)

    batches: Dict[int, Mapping[str, Any]] = {}
    baselines: Dict[int, np.ndarray] = {}
    truths: Dict[int, np.ndarray] = {}
    contexts_by_test: Dict[int, List[Dict[str, Any]]] = {}
    baseline_records = []
    noop_records = []
    adjacency_records = []
    try:
        for test_id in protocol["selected_test_ids"]:
            batch = adapter.load_sample("test", int(test_id))
            batches[test_id] = batch
            history = np.asarray(batch["x"], dtype=np.float32)
            truth = np.asarray(batch["y"][-config["dataset"]["pred_len"] :], dtype=np.float32)
            baseline = tensor_numpy(adapter.predict(batch)).squeeze(0).astype(np.float32)
            history_file = output / "baseline" / "history_test_{:04d}.npy".format(test_id)
            truth_file = output / "baseline" / "ground_truth_test_{:04d}.npy".format(test_id)
            baseline_file = output / "baseline" / "baseline_test_{:04d}.npy".format(test_id)
            save_array(history_file, history, (96, 7))
            save_array(truth_file, truth, (96, 7))
            save_array(baseline_file, baseline, (96, 7))
            baselines[test_id], truths[test_id] = baseline, truth

            extracted = adapter.extract_graph_stages(batch)["contexts"]
            contexts = []
            context_arrays = {}
            for context in extracted:
                adaptive = tensor_numpy(context["adaptive"]).astype(np.float32)
                scale_index = int(context["scale_index"])
                if adaptive.shape != (7, 7) or not np.isfinite(adaptive).all():
                    raise RuntimeError("Invalid adaptive adjacency for test {} scale {}".format(test_id, scale_index))
                mask = ~np.eye(7, dtype=bool)
                retained = int(np.count_nonzero(adaptive[mask] > 0))
                adjacency_records.append({
                    "test_id": test_id,
                    "scale_index": scale_index,
                    "retained_directed_non_self_edges": retained,
                    "all_42_retained": retained == 42,
                    "minimum_off_diagonal_weight": float(adaptive[mask].min()),
                })
                if retained != 42:
                    raise RuntimeError("Current graph structure changed: not all 42 relations are retained")
                context_arrays["adaptive_{}".format(scale_index)] = adaptive
                contexts.append({
                    "scale_index": scale_index,
                    "observed_period": int(context["period"]),
                    "fft_strength": float(context["fft_strength"]),
                    "scale_contribution": float(context["scale_contribution"]),
                    "adaptive_shape": [7, 7],
                })
            context_file = output / "baseline" / "contexts_test_{:04d}.npz".format(test_id)
            if context_file.exists():
                with np.load(context_file) as existing:
                    if set(existing.files) != set(context_arrays) or any(
                        not np.array_equal(existing[key], value) for key, value in context_arrays.items()
                    ):
                        raise RuntimeError("Refusing to overwrite different context cache")
            else:
                np.savez(context_file, **context_arrays)
            contexts_by_test[test_id] = [
                {**item, "adaptive": context_arrays["adaptive_{}".format(item["scale_index"])]}
                for item in contexts
            ]
            baseline_records.append({
                "test_id": test_id,
                "history_file": relative_to_output(history_file, output),
                "ground_truth_file": relative_to_output(truth_file, output),
                "baseline_prediction_file": relative_to_output(baseline_file, output),
                "history_shape": [96, 7],
                "ground_truth_shape": [96, 7],
                "baseline_prediction_shape": [96, 7],
                "context_file": relative_to_output(context_file, output),
                "contexts": contexts,
                "value_space": "Dataset_ETT_hour standardized model input/output space",
            })

            identity = tensor_numpy(adapter.predict_with_graph_override(batch, {
                "type": "identity", "layer": 0, "scale_index": 0,
            })["prediction"]).squeeze(0).astype(np.float32)
            max_diff = float(np.max(np.abs(identity - baseline)))
            passed = bool(np.allclose(identity, baseline, atol=1e-6, rtol=1e-5))
            noop_records.append({
                "test_id": test_id,
                "max_abs_diff": max_diff,
                "atol": 1e-6,
                "rtol": 1e-5,
                "status": "PASS" if passed else "FAIL",
            })
            print("baseline/no-op test {}: {} max_diff={:.9g}".format(test_id, "PASS" if passed else "FAIL", max_diff), flush=True)

        write_json(output / "baseline" / "baseline_records.json", baseline_records)
        write_json(output / "validation" / "noop_validation.json", {
            "status": "PASS" if all(item["status"] == "PASS" for item in noop_records) else "FAIL",
            "count": len(noop_records),
            "records": noop_records,
        })
        write_json(output / "validation" / "adjacency_validation.json", {
            "status": "PASS" if all(item["all_42_retained"] for item in adjacency_records) else "FAIL",
            "expected_records": 42,
            "actual_records": len(adjacency_records),
            "records": adjacency_records,
        })
        if any(item["status"] != "PASS" for item in noop_records):
            raise RuntimeError("No-op validation failed; no edge intervention was started")

        raw_path = output / "intervention_records.jsonl"
        completed = load_jsonl(raw_path)
        with raw_path.open("a", encoding="utf-8") as handle:
            for test_id in protocol["selected_test_ids"]:
                baseline = baselines[test_id]
                truth = truths[test_id]
                baseline_file = output / "baseline" / "baseline_test_{:04d}.npy".format(test_id)
                context_map = {item["scale_index"]: item for item in contexts_by_test[test_id]}
                for scale_index in config["hypotheses"]["scale_indices"]:
                    observed_period = int(context_map[scale_index]["observed_period"])
                    adaptive = context_map[scale_index]["adaptive"]
                    for source, target in RELATIONS:
                        case_id = "single:test={}:scale={}:{}->{}".format(test_id, scale_index, source, target)
                        if case_id in completed:
                            continue
                        prediction_file = output / "single_scale_predictions" / (
                            "test_{:04d}_scale_{}_edge_{}_{}.npy".format(test_id, scale_index, source, target)
                        )
                        if prediction_file.exists():
                            changed = np.load(prediction_file).astype(np.float32)
                            graph_keys = [scale_index]
                        else:
                            outcome = adapter.predict_with_graph_override(batches[test_id], {
                                "type": "structural_edge_removal",
                                "layer": 0,
                                "scale_index": scale_index,
                                "source": source,
                                "target": target,
                            })
                            graph_keys = sorted(int(key) for key in outcome["graph_after"].keys())
                            if graph_keys != [scale_index]:
                                raise RuntimeError("Single-scale intervention touched unexpected scales")
                            before = float(tensor_numpy(outcome["graph_before"][scale_index])[source, target])
                            after = float(tensor_numpy(outcome["graph_after"][scale_index])[source, target])
                            if before <= 0 or after != 0:
                                raise RuntimeError("Single-scale graph mutation failed")
                            changed = tensor_numpy(outcome["prediction"]).squeeze(0).astype(np.float32)
                            save_array(prediction_file, changed, (96, 7))
                        record = metric_record(
                            case_id=case_id, test_id=test_id, scope="single_scale",
                            scale_index=scale_index, observed_period=observed_period,
                            source=source, target=target, affected_scales=[scale_index],
                            baseline_file=baseline_file, prediction_file=prediction_file, output=output,
                            baseline=baseline, changed=changed, truth=truth,
                            weights_before=[float(adaptive[source, target])], runtime_graph_keys=graph_keys,
                        )
                        append_record(handle, record)
                        completed[case_id] = record
                    print("single complete test={} scale={}: 42".format(test_id, scale_index), flush=True)

                for source, target in RELATIONS:
                    case_id = "all:test={}:{}->{}".format(test_id, source, target)
                    if case_id in completed:
                        continue
                    prediction_file = output / "all_scale_predictions" / (
                        "test_{:04d}_edge_{}_{}.npy".format(test_id, source, target)
                    )
                    weights = [float(context_map[index]["adaptive"][source, target]) for index in (0, 1, 2)]
                    if prediction_file.exists():
                        changed = np.load(prediction_file).astype(np.float32)
                        graph_keys = [0, 1, 2]
                    else:
                        outcome = adapter.predict_with_graph_override(batches[test_id], {
                            "type": "structural_edge_removal", "scope": "global", "layer": 0,
                            "source": source, "target": target,
                        })
                        graph_keys = sorted(int(key) for key in outcome["graph_after"].keys())
                        if graph_keys != [0, 1, 2]:
                            raise RuntimeError("All-scale intervention did not touch exactly scales 0,1,2")
                        for scale_index in graph_keys:
                            before = float(tensor_numpy(outcome["graph_before"][scale_index])[source, target])
                            after = float(tensor_numpy(outcome["graph_after"][scale_index])[source, target])
                            if before <= 0 or after != 0:
                                raise RuntimeError("All-scale graph mutation failed")
                        changed = tensor_numpy(outcome["prediction"]).squeeze(0).astype(np.float32)
                        save_array(prediction_file, changed, (96, 7))
                    record = metric_record(
                        case_id=case_id, test_id=test_id, scope="all_scales",
                        scale_index=None, observed_period=None,
                        source=source, target=target, affected_scales=[0, 1, 2],
                        baseline_file=baseline_file, prediction_file=prediction_file, output=output,
                        baseline=baseline, changed=changed, truth=truth,
                        weights_before=weights, runtime_graph_keys=graph_keys,
                    )
                    append_record(handle, record)
                    completed[case_id] = record
                print("all-scale complete test={}: 42".format(test_id), flush=True)
    finally:
        adapter.close()

    if len(completed) != 2352:
        raise RuntimeError("Inference incomplete: expected 2352 records, found {}".format(len(completed)))
    analyze(config_path)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise RuntimeError("Cannot write empty CSV: {}".format(path))
    fields: List[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def bh_adjust(values: Sequence[float]) -> List[float]:
    order = np.argsort(np.asarray(values, dtype=float))
    result = np.empty(len(values), dtype=float)
    running = 1.0
    for reverse_position in range(len(values) - 1, -1, -1):
        index = int(order[reverse_position])
        rank = reverse_position + 1
        running = min(running, float(values[index]) * len(values) / rank)
        result[index] = running
    return result.tolist()


def exact_signflip_p(d: np.ndarray, signs: np.ndarray) -> float:
    observed = float(np.mean(d))
    statistics = np.mean(signs * d.reshape(1, -1), axis=1)
    return float(np.count_nonzero(statistics >= observed) / statistics.size)


def exact_sign_test_p(positive: int, negative: int) -> float:
    n = positive + negative
    if n == 0:
        return 1.0
    return float(sum(math.comb(n, value) for value in range(positive, n + 1)) / (2 ** n))


def relation_statistics(
    hypothesis_id: str,
    family: str,
    scale_index: Any,
    source: int,
    target: int,
    rows: Sequence[Mapping[str, Any]],
    signs: np.ndarray,
    rng: np.random.Generator,
    bootstrap_repetitions: int,
) -> Dict[str, Any]:
    ordered = sorted(rows, key=lambda row: int(row["test_id"]))
    d = np.asarray([float(row["D"]) for row in ordered], dtype=float)
    if len(d) != 14 or not np.isfinite(d).all():
        raise RuntimeError("Hypothesis {} does not have 14 finite D values".format(hypothesis_id))
    positive = int(np.count_nonzero(d > 0))
    negative = int(np.count_nonzero(d < 0))
    zero = int(np.count_nonzero(d == 0))
    sorted_d = np.sort(d)
    trimmed = sorted_d[1:-1]
    loo = np.asarray([(float(d.sum()) - float(value)) / 13 for value in d], dtype=float)
    indices = rng.integers(0, 14, size=(bootstrap_repetitions, 14))
    boot = d[indices]
    boot_sorted = np.sort(boot, axis=1)
    mean_ci = np.quantile(np.mean(boot, axis=1), [0.025, 0.975])
    median_ci = np.quantile(np.median(boot, axis=1), [0.025, 0.975])
    trimmed_ci = np.quantile(np.mean(boot_sorted[:, 1:-1], axis=1), [0.025, 0.975])
    periods = sorted(set(
        int(row["observed_period"]) for row in ordered if row.get("observed_period") not in (None, "")
    ))
    return {
        "family": family,
        "hypothesis_id": hypothesis_id,
        "scale_index": scale_index,
        "source": source,
        "target": target,
        "source_name": NAMES[source],
        "target_name": NAMES[target],
        "observed_periods": json.dumps(periods, separators=(",", ":")),
        "N_tests": 14,
        "positive_count": positive,
        "negative_count": negative,
        "zero_count": zero,
        "positive_fraction": positive / 14,
        "mean_D": float(np.mean(d)),
        "median_D": float(np.median(d)),
        "sample_SD": float(np.std(d, ddof=1)),
        "Q1": float(np.quantile(d, 0.25)),
        "Q3": float(np.quantile(d, 0.75)),
        "min_D": float(np.min(d)),
        "max_D": float(np.max(d)),
        "trimmed_mean_10_percent": float(np.mean(trimmed)),
        "trim_count_each_tail": 1,
        "raw_p_exact_signflip": exact_signflip_p(d, signs),
        "sign_test_p": exact_sign_test_p(positive, negative),
        "LOO_minimum_mean_D": float(np.min(loo)),
        "LOO_maximum_mean_D": float(np.max(loo)),
        "LOO_means_gt_zero": int(np.count_nonzero(loo > 0)),
        "all_LOO_positive": bool(np.all(loo > 0)),
        "bootstrap_mean_CI95_low": float(mean_ci[0]),
        "bootstrap_mean_CI95_high": float(mean_ci[1]),
        "bootstrap_median_CI95_low": float(median_ci[0]),
        "bootstrap_median_CI95_high": float(median_ci[1]),
        "bootstrap_trimmed_mean_CI95_low": float(trimmed_ci[0]),
        "bootstrap_trimmed_mean_CI95_high": float(trimmed_ci[1]),
        "bootstrap_repetitions": bootstrap_repetitions,
        "bootstrap_seed": 20260830,
        "bootstrap_role": "SENSITIVITY ONLY",
    }


def markdown_table(rows: Sequence[Mapping[str, Any]], columns: Sequence[Tuple[str, str]]) -> List[str]:
    lines = ["| " + " | ".join(label for _, label in columns) + " |"]
    lines.append("|" + "|".join("---" for _ in columns) + "|")
    for row in rows:
        values = []
        for key, _ in columns:
            value = row.get(key, "")
            values.append("{:.8g}".format(value) if isinstance(value, float) else str(value))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def analyze(config_path: Path) -> None:
    config = load_config(config_path)
    output = (ROOT / config["output_root"]).resolve()
    protocol = read_json(output / "test_protocol.json")
    family = read_json(output / "candidate_family.json")
    records = list(load_jsonl(output / "intervention_records.jsonl").values())
    if len(records) != 2352:
        raise RuntimeError("Expected 2352 intervention records")

    groups: Dict[Tuple[Any, ...], List[Mapping[str, Any]]] = {}
    for record in records:
        if record["scope"] == "single_scale":
            key = ("single_scale", int(record["test_id"]), int(record["scale_index"]))
        else:
            key = ("all_scales", int(record["test_id"]))
        groups.setdefault(key, []).append(record)
    case_rows = []
    control_counts = []
    for key, items in groups.items():
        if len(items) != 42 or len({(item["source"], item["target"]) for item in items}) != 42:
            raise RuntimeError("Control group {} is not the complete 42-relation universe".format(key))
        responses = {(int(item["source"]), int(item["target"])): float(item["prediction_delta_abs"]) for item in items}
        for item in items:
            focal_key = (int(item["source"]), int(item["target"]))
            controls = [(edge, value) for edge, value in responses.items() if edge != focal_key]
            if len(controls) != 41 or len({edge for edge, _ in controls}) != 41:
                raise RuntimeError("A case does not have exactly 41 unique controls")
            values = np.asarray([value for _, value in controls], dtype=float)
            focal = responses[focal_key]
            below = int(np.count_nonzero(values < focal))
            equal_or_above = int(np.count_nonzero(values >= focal))
            equal = int(np.count_nonzero(values == focal))
            rank = 1 + int(np.count_nonzero(values > focal))
            percentile = 100 * (below + 0.5 * (equal + 1)) / 42
            control_counts.append(len(controls))
            hypothesis_id = (
                "single_scale:{}:{}->{}".format(item["scale_index"], item["source"], item["target"])
                if item["scope"] == "single_scale"
                else "all_scales:{}->{}".format(item["source"], item["target"])
            )
            case_rows.append({
                "case_id": item["case_id"],
                "hypothesis_id": hypothesis_id,
                "test_id": item["test_id"],
                "scope": item["scope"],
                "scale_index": "" if item["scale_index"] is None else item["scale_index"],
                "observed_period": "" if item["observed_period"] is None else item["observed_period"],
                "source": item["source"],
                "target": item["target"],
                "source_name": item["source_name"],
                "target_name": item["target_name"],
                "focal_response": focal,
                "unique_control_count": len(controls),
                "control_mean": float(np.mean(values)),
                "control_median": float(np.median(values)),
                "D": float(focal - np.mean(values)),
                "focal_rank_among_42": rank,
                "focal_percentile_midrank": percentile,
                "number_controls_below_focal": below,
                "number_controls_equal_or_above_focal": equal_or_above,
                "control_relation_ids": json.dumps(
                    ["{}->{}".format(edge[0], edge[1]) for edge, _ in controls], separators=(",", ":")
                ),
                "prediction_delta_abs": item["prediction_delta_abs"],
                "prediction_delta_max": item["prediction_delta_max"],
                "error_delta_mae": item["error_delta_mae"],
                "error_delta_mse": item["error_delta_mse"],
                "baseline_prediction_file": item["baseline_prediction_file"],
                "intervention_prediction_file": item["intervention_prediction_file"],
            })
    write_csv(output / "case_evidence.csv", case_rows)

    signs = np.where(
        ((np.arange(2 ** 14, dtype=np.uint16)[:, None] >> np.arange(14, dtype=np.uint16)) & 1) == 1,
        1.0,
        -1.0,
    )
    rng = np.random.default_rng(int(config["bootstrap_seed"]))
    by_hypothesis: Dict[str, List[Mapping[str, Any]]] = {}
    for row in case_rows:
        by_hypothesis.setdefault(str(row["hypothesis_id"]), []).append(row)

    relation_rows: Dict[str, List[Dict[str, Any]]] = {"single_scale": [], "all_scales": []}
    for family_item in family["families"]:
        family_name = family_item["family_name"]
        for member in family_item["members"]:
            hypothesis_id = member["hypothesis_id"]
            relation_rows[family_name].append(relation_statistics(
                hypothesis_id=hypothesis_id,
                family=family_name,
                scale_index=member.get("scale_index", ""),
                source=int(member["source"]),
                target=int(member["target"]),
                rows=by_hypothesis.get(hypothesis_id, []),
                signs=signs,
                rng=rng,
                bootstrap_repetitions=int(config["bootstrap_repetitions"]),
            ))
    for family_name, rows in relation_rows.items():
        q_values = bh_adjust([float(row["raw_p_exact_signflip"]) for row in rows])
        for row, q_value in zip(rows, q_values):
            row["bh_q"] = q_value
            row["bh_supported"] = bool(q_value < 0.05)
        filename = (
            "relation_evidence_single_scale.csv"
            if family_name == "single_scale"
            else "relation_evidence_all_scale.csv"
        )
        write_csv(output / filename, rows)

    counts = np.asarray(control_counts, dtype=int)
    control_validation = {
        "status": "PASS" if len(counts) == 2352 and np.all(counts == 41) else "FAIL",
        "case_count": int(len(counts)),
        "unique_control_count_min": int(counts.min()),
        "unique_control_count_Q1": float(np.quantile(counts, 0.25)),
        "unique_control_count_median": float(np.median(counts)),
        "unique_control_count_Q3": float(np.quantile(counts, 0.75)),
        "unique_control_count_max": int(counts.max()),
        "not_equal_41_count": int(np.count_nonzero(counts != 41)),
        "control_identity_rule": "same test and scope/scale; complete E minus focal; no replacement",
    }
    write_json(output / "validation" / "control_pool_validation.json", control_validation)

    single_probe = config["hypotheses"]["single_scale_sanity_probe"]
    all_probe = config["hypotheses"]["all_scale_sanity_probe"]
    probes = []
    for record in records:
        is_single_probe = (
            record["scope"] == "single_scale"
            and record["source"] == single_probe["source"]
            and record["target"] == single_probe["target"]
        )
        is_all_probe = (
            record["scope"] == "all_scales"
            and record["source"] == all_probe["source"]
            and record["target"] == all_probe["target"]
        )
        if is_single_probe or is_all_probe:
            expected_scales = [int(record["scale_index"])] if is_single_probe else [0, 1, 2]
            passed = (
                record["affected_scales"] == expected_scales
                and record["runtime_graph_keys"] == expected_scales
                and all(value > 0 for value in record["graph_before_focal_weights"])
                and all(value == 0 for value in record["graph_after_focal_weights"])
                and record["trajectory_shape"] == [96, 7]
                and record["trajectory_finite"]
            )
            probes.append({
                "case_id": record["case_id"],
                "expected_affected_scales": expected_scales,
                "actual_affected_scales": record["affected_scales"],
                "runtime_graph_keys": record["runtime_graph_keys"],
                "graph_before_focal_weights": record["graph_before_focal_weights"],
                "graph_after_focal_weights": record["graph_after_focal_weights"],
                "mixprop_normalization": "unchanged upstream add-self-loop then row-normalize",
                "status": "PASS" if passed else "FAIL",
            })
    write_json(output / "validation" / "intervention_validation.json", {
        "status": "PASS" if len(probes) == 56 and all(item["status"] == "PASS" for item in probes) else "FAIL",
        "predeclared_relation": "0->1",
        "expected_probe_count": 56,
        "actual_probe_count": len(probes),
        "records": probes,
    })

    baseline_files = sorted((output / "baseline").glob("baseline_test_*.npy"))
    single_files = sorted((output / "single_scale_predictions").glob("*.npy"))
    all_files = sorted((output / "all_scale_predictions").glob("*.npy"))
    invalid_arrays = []
    for path in baseline_files + single_files + all_files:
        array = np.load(path)
        if array.shape != (96, 7) or not np.isfinite(array).all():
            invalid_arrays.append(relative_to_output(path, output))
    numeric_values = [
        float(record[field]) for record in records for field in NUMERIC_CASE_FIELDS
    ] + [float(row["D"]) for row in case_rows]
    nan_inf_count = int(np.count_nonzero(~np.isfinite(np.asarray(numeric_values))))
    completeness = {
        "status": "PASS",
        "baseline_expected": 14,
        "baseline_actual": len(baseline_files),
        "single_scale_records_expected": 1764,
        "single_scale_records_actual": sum(record["scope"] == "single_scale" for record in records),
        "all_scale_records_expected": 588,
        "all_scale_records_actual": sum(record["scope"] == "all_scales" for record in records),
        "single_scale_trajectories_expected": 1764,
        "single_scale_trajectories_actual": len(single_files),
        "all_scale_trajectories_expected": 588,
        "all_scale_trajectories_actual": len(all_files),
        "single_hypotheses_expected": 126,
        "single_hypotheses_actual": len(relation_rows["single_scale"]),
        "all_hypotheses_expected": 42,
        "all_hypotheses_actual": len(relation_rows["all_scales"]),
        "tests_per_hypothesis": sorted({row["N_tests"] for rows in relation_rows.values() for row in rows}),
        "invalid_trajectory_arrays": invalid_arrays,
        "nan_inf_count": nan_inf_count,
        "missing_intervention_count": 2352 - len(records),
    }
    expected_actual_pairs = [
        (14, len(baseline_files)), (1764, completeness["single_scale_records_actual"]),
        (588, completeness["all_scale_records_actual"]), (1764, len(single_files)),
        (588, len(all_files)), (126, len(relation_rows["single_scale"])),
        (42, len(relation_rows["all_scales"])),
    ]
    if (
        any(expected != actual for expected, actual in expected_actual_pairs)
        or completeness["tests_per_hypothesis"] != [14]
        or invalid_arrays or nan_inf_count or control_validation["status"] != "PASS"
    ):
        completeness["status"] = "FAIL"
    write_json(output / "validation" / "runtime_completeness.json", completeness)

    summaries = {}
    for family_name, rows in relation_rows.items():
        summaries[family_name] = {
            "raw_p_lt_0_05_count": sum(float(row["raw_p_exact_signflip"]) < 0.05 for row in rows),
            "bh_q_lt_0_05_count": sum(float(row["bh_q"]) < 0.05 for row in rows),
            "minimum_raw_p": min(float(row["raw_p_exact_signflip"]) for row in rows),
            "minimum_bh_q": min(float(row["bh_q"]) for row in rows),
        }
    supported = [row for rows in relation_rows.values() for row in rows if row["bh_supported"]]
    report_lines = [
        "# MSGNet / ETTh1 Cross-Test Evidence Validation v1",
        "",
        "> PRELIMINARY / FOR REVIEW ONLY. This run is not production website data.",
        "",
        "## A. Protocol",
        "",
        "- Test IDs: `{}`".format(", ".join(map(str, protocol["selected_test_ids"]))),
        "- Selection: `{}`".format(protocol["selection_rule"]),
        "- Dataset SHA-256: `{}`".format(protocol["dataset_sha256"]),
        "- Raw span: {} rows; start gaps: `{}`".format(protocol["raw_span"], protocol["start_gaps"]),
        "- Minimum/median start gap: {}/{}; adjacent/all-pair overlaps: {}/{}".format(
            protocol["minimum_start_gap"], protocol["median_start_gap"],
            protocol["overlapping_adjacent_pairs"], protocol["overlapping_all_pairs"],
        ),
        "",
    ]
    report_lines += markdown_table(protocol["tests"], [
        ("test_id", "test"), ("raw_start", "raw start"), ("raw_end", "raw end"),
        ("start_timestamp", "start timestamp"), ("end_timestamp", "end timestamp"),
    ])
    report_lines += [
        "", "## B. Runtime completeness", "",
        "| item | expected | actual |", "|---|---:|---:|",
        "| baseline trajectories | 14 | {} |".format(len(baseline_files)),
        "| single-scale records/trajectories | 1764 | {}/{} |".format(completeness["single_scale_records_actual"], len(single_files)),
        "| all-scale records/trajectories | 588 | {}/{} |".format(completeness["all_scale_records_actual"], len(all_files)),
        "", "## C. Controls", "",
        "Unique controls min/Q1/median/Q3/max: `{}/{}/{}/{}/{}`; non-41 cases: `{}`.".format(
            control_validation["unique_control_count_min"], control_validation["unique_control_count_Q1"],
            control_validation["unique_control_count_median"], control_validation["unique_control_count_Q3"],
            control_validation["unique_control_count_max"], control_validation["not_equal_41_count"],
        ),
        "", "## D. Single-scale relation results", "",
        "All 126 rows: [relation_evidence_single_scale.csv](relation_evidence_single_scale.csv).",
        "", "## E. All-scale relation results", "",
        "All 42 rows: [relation_evidence_all_scale.csv](relation_evidence_all_scale.csv).",
        "", "## F. Multiple testing", "",
        "| family | raw p < .05 | BH q < .05 | minimum raw p | minimum BH q |",
        "|---|---:|---:|---:|---:|",
        "| single-scale | {} | {} | {:.9g} | {:.9g} |".format(
            summaries["single_scale"]["raw_p_lt_0_05_count"], summaries["single_scale"]["bh_q_lt_0_05_count"],
            summaries["single_scale"]["minimum_raw_p"], summaries["single_scale"]["minimum_bh_q"],
        ),
        "| all-scale | {} | {} | {:.9g} | {:.9g} |".format(
            summaries["all_scales"]["raw_p_lt_0_05_count"], summaries["all_scales"]["bh_q_lt_0_05_count"],
            summaries["all_scales"]["minimum_raw_p"], summaries["all_scales"]["minimum_bh_q"],
        ),
        "", "Primary p is the complete 16,384-configuration, one-sided exact sign-flip test on mean D. BH is separate for 126 single-scale and 42 all-scale hypotheses.",
        "", "## G. Robustness candidates", "",
    ]
    if supported:
        report_lines += markdown_table(supported, [
            ("hypothesis_id", "hypothesis"), ("mean_D", "mean D"), ("median_D", "median D"),
            ("positive_count", "positive/14"), ("bh_q", "BH q"),
            ("LOO_minimum_mean_D", "LOO min mean"),
            ("trimmed_mean_10_percent", "trimmed mean"),
            ("bootstrap_mean_CI95_low", "bootstrap CI low"),
            ("bootstrap_mean_CI95_high", "bootstrap CI high"),
        ])
    else:
        report_lines.append("BH-supported relations: **0**.")
    report_lines += [
        "", "Bootstrap intervals are SENSITIVITY ONLY; they do not replace the primary exact p.",
        "", "## H. Prediction trajectory availability", "",
        "- Single-scale: {}/1764 `(96,7)` trajectory files.".format(len(single_files)),
        "- All-scale: {}/588 `(96,7)` trajectory files.".format(len(all_files)),
        "- Baseline: {}/14 `(96,7)` trajectory files.".format(len(baseline_files)),
        "", "## I. Problems", "",
        "- UNKNOWN: upstream MSGNet source commit; no Git metadata exists. Critical source file SHA-256 values are frozen in the config/manifest.",
        "- WARNING: observed FFT period is sample-dependent and is not part of hypothesis identity.",
        "- MISSING intervention: {}.".format(completeness["missing_intervention_count"]),
        "- FAILED validation items: {}.".format(0 if completeness["status"] == "PASS" else 1),
        "- NaN/Inf count: {}.".format(nan_inf_count),
        "", "## J. Final status", "",
        "**{}**".format("DATA GENERATION PASS" if completeness["status"] == "PASS" else "DATA GENERATION INCOMPLETE"),
        "",
    ]
    report_path = output / "MSGNET_CROSS_TEST_RESULTS.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    artifact_paths = [
        output / "test_protocol.json", output / "test_protocol.sha256", output / "candidate_family.json",
        output / "baseline/baseline_records.json", output / "intervention_records.jsonl",
        output / "case_evidence.csv",
        output / "relation_evidence_single_scale.csv", output / "relation_evidence_all_scale.csv",
        output / "validation/noop_validation.json", output / "validation/intervention_validation.json",
        output / "validation/adjacency_validation.json", output / "validation/control_pool_validation.json",
        output / "validation/runtime_completeness.json",
        report_path,
    ]
    manifest = {
        "protocol_version": config["protocol_version"],
        "status": "DATA GENERATION PASS" if completeness["status"] == "PASS" else "DATA GENERATION INCOMPLETE",
        "dataset_path": config["_dataset_path"],
        "dataset_sha256": config["dataset"]["sha256"],
        "checkpoint_path": config["_checkpoint_path"],
        "checkpoint_sha256": config["checkpoint"]["sha256"],
        "config_path": str(config_path),
        "config_sha256": sha256(config_path),
        "source_commit": config["source_commit"],
        "source_file_sha256": config["source_file_sha256"],
        "test_protocol_sha256": sha256(output / "test_protocol.json"),
        "candidate_family_sha256": sha256(output / "candidate_family.json"),
        "selected_test_ids": protocol["selected_test_ids"],
        "seq_len": 96,
        "pred_len": 96,
        "number_baseline_forwards": 14,
        "number_noop_forwards": 14,
        "number_single_scale_interventions": completeness["single_scale_records_actual"],
        "expected_single_scale_interventions": 1764,
        "number_all_scale_interventions": completeness["all_scale_records_actual"],
        "expected_all_scale_interventions": 588,
        "total_intervention_forwards": len(records),
        "expected_total_intervention_forwards": 2352,
        "candidate_family_sizes": {"single": 126, "all": 42},
        "primary_inference": "exact one-sided sign flip on mean D; 16384 complete configurations; ties >=; no +1 correction",
        "BH": "separate families",
        "bootstrap_seed": config["bootstrap_seed"],
        "bootstrap_repetitions": config["bootstrap_repetitions"],
        "runtime": config["runtime"],
        "creation_timestamp": datetime.now().astimezone().isoformat(),
        "old_case_level_p_q_used": False,
        "production_catalog_modified": False,
        "trajectory_collection_sha256": {
            "baseline_predictions": collection_sha256(baseline_files, output),
            "single_scale_predictions": collection_sha256(single_files, output),
            "all_scale_predictions": collection_sha256(all_files, output),
        },
        "artifact_sha256": {relative_to_output(path, output): sha256(path) for path in artifact_paths},
    }
    write_json(output / "manifest.json", manifest)
    print(json.dumps({"status": manifest["status"], "summaries": summaries}, indent=2), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "run", "analyze"))
    parser.add_argument("--config", default="configs/msgnet_etth1_cross_test_v1.json")
    args = parser.parse_args()
    config_path = (ROOT / args.config).resolve()
    if args.command == "prepare":
        prepare(config_path)
    elif args.command == "run":
        run_inference(config_path)
    else:
        analyze(config_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import platform
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def quantile(values: list[float], q: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), q)) if values else 0.0


def edge_id(source: int, target: int) -> str:
    return f"{source}->{target}"


def candidate(kind: str, **payload) -> dict:
    return {"label": "Candidate Pattern", "pattern_type": kind, **payload}


def source_names(csv_path: Path) -> list[str]:
    with csv_path.open(encoding="utf-8", errors="replace", newline="") as handle:
        return next(csv.reader(handle))[1:]


def analyze_dataset(graph: dict, names: list[str], q_low: float, q_high: float,
                    persistent_count: int, specific_count: int,
                    minimum_cooccurrence: int, maximum_sets: int) -> dict:
    windows = graph["stages"]
    n = len(names)
    stats: dict[tuple[int, int], dict] = {}
    retained_by_window: list[set[tuple[int, int]]] = []

    for window in windows:
        scores = np.asarray(window["diagonal_removed"], dtype=float)
        mask = np.asarray(window["topk_mask"], dtype=float)
        flat_scores = scores.reshape(-1)
        ranked_slots = np.argsort(-flat_scores, kind="stable")
        slot_rank = np.empty_like(ranked_slots)
        slot_rank[ranked_slots] = np.arange(1, len(ranked_slots) + 1)
        offdiag = sorted((float(scores[i, j]), i, j) for i in range(n) for j in range(n) if i != j)
        offdiag.reverse()
        offdiag_rank = {(i, j): rank for rank, (_, i, j) in enumerate(offdiag, 1)}
        kth_score = float(np.partition(flat_scores, -int(window["topk_slots"]))[-int(window["topk_slots"])])
        retained = set()
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                kept = bool(mask[i, j] == 1 and scores[i, j] > 0)
                if kept:
                    retained.add((i, j))
                record = stats.setdefault((i, j), {"windows": [], "scores": [], "retained_scores": [], "evidence": []})
                record["scores"].append(float(scores[i, j]))
                if kept:
                    record["windows"].append(int(window["window"]))
                    record["retained_scores"].append(float(scores[i, j]))
                record["evidence"].append({
                    "window": int(window["window"]), "score_before_topk": float(scores[i, j]),
                    "retained": kept, "global_slot_rank": int(slot_rank[i * n + j]),
                    "off_diagonal_rank": int(offdiag_rank[(i, j)]),
                    "topk_boundary_score": kth_score,
                    "score_minus_topk_boundary": float(scores[i, j] - kth_score),
                })
        retained_by_window.append(retained)

    retained_stats = []
    for (i, j), record in stats.items():
        count = len(record["windows"])
        if count == 0:
            continue
        retained_stats.append({
            "source": i, "target": j, "source_name": names[i], "target_name": names[j],
            "edge_id": edge_id(i, j), "retained_window_count": count,
            "frequency": count / len(windows), "windows": record["windows"],
            "mean_retained_score": float(np.mean(record["retained_scores"])),
            "mean_all_window_score": float(np.mean(record["scores"])),
            "evidence": record["evidence"],
        })

    frequencies = [item["frequency"] for item in retained_stats]
    mean_scores = [item["mean_retained_score"] for item in retained_stats]
    fq1, fq3 = quantile(frequencies, q_low), quantile(frequencies, q_high)
    sq1, sq3 = quantile(mean_scores, q_low), quantile(mean_scores, q_high)

    persistent = [candidate("persistent_edge", **item) for item in retained_stats
                  if item["retained_window_count"] == persistent_count]
    window_specific = [candidate("window_specific_edge", **item) for item in retained_stats
                       if item["retained_window_count"] == specific_count]
    high_weight_low_frequency = [candidate("high_weight_low_frequency_edge", **item) for item in retained_stats
                                 if item["mean_retained_score"] >= sq3 and item["frequency"] <= fq1]
    high_frequency_low_weight = [candidate("high_frequency_low_weight_edge", **item) for item in retained_stats
                                 if item["frequency"] >= fq3 and item["mean_retained_score"] <= sq1]

    outgoing = Counter()
    incoming = Counter()
    for item in retained_stats:
        outgoing[item["source"]] += item["retained_window_count"]
        incoming[item["target"]] += item["retained_window_count"]
    out_q3 = quantile([float(outgoing[i]) for i in range(n)], q_high)
    in_q3 = quantile([float(incoming[i]) for i in range(n)], q_high)
    sender_roles = [candidate("sender_role", variable=i, variable_name=names[i],
                              retained_outgoing_occurrences=outgoing[i], threshold=out_q3)
                    for i in range(n) if outgoing[i] >= out_q3]
    receiver_roles = [candidate("receiver_role", variable=i, variable_name=names[i],
                                retained_incoming_occurrences=incoming[i], threshold=in_q3)
                      for i in range(n) if incoming[i] >= in_q3]

    pair_counts = Counter()
    pair_windows: dict[tuple, list[int]] = defaultdict(list)
    for window_id, edges in enumerate(retained_by_window):
        for pair in itertools.combinations(sorted(edges), 2):
            pair_counts[pair] += 1
            pair_windows[pair].append(window_id)
    repeated = []
    eligible = [(count, pair) for pair, count in pair_counts.items() if count >= minimum_cooccurrence]
    for count, pair in sorted(eligible, key=lambda item: (-item[0], item[1]))[:maximum_sets]:
        repeated.append(candidate(
            "repeated_local_edge_set",
            edges=[{"source": s, "target": t, "source_name": names[s], "target_name": names[t]}
                   for s, t in pair],
            cooccurrence_count=count, frequency=count / len(windows), windows=pair_windows[pair],
        ))

    categories = {
        "persistent_edges": persistent,
        "window_specific_edges": window_specific,
        "high_weight_low_frequency_edges": high_weight_low_frequency,
        "high_frequency_low_weight_edges": high_frequency_low_weight,
        "sender_roles": sender_roles,
        "receiver_roles": receiver_roles,
        "repeated_local_edge_sets": repeated,
        "cross_run_repeated_patterns": {
            "status": "missing", "reason": "Only one checkpoint is available for this dataset."
        },
    }
    return {
        "dataset": graph["dataset"], "status": "complete", "claim_level": "structural_candidate",
        "window_count": len(windows), "variable_names": names,
        "thresholds": {"frequency_q1": fq1, "frequency_q3": fq3,
                       "mean_retained_score_q1": sq1, "mean_retained_score_q3": sq3,
                       "sender_occurrence_q3": out_q3, "receiver_occurrence_q3": in_q3},
        "definitions": {
            "persistent_edge": f"retained in exactly {persistent_count} windows",
            "window_specific_edge": f"retained in exactly {specific_count} window",
            "high_weight_low_frequency_edge": "mean retained score >= empirical Q3 and frequency <= empirical Q1",
            "high_frequency_low_weight_edge": "frequency >= empirical Q3 and mean retained score <= empirical Q1",
            "sender_receiver_role": "retained outgoing/incoming occurrence count >= empirical Q3",
            "repeated_local_edge_set": f"two-edge set co-occurs in at least {minimum_cooccurrence} windows",
        },
        "all_retained_edge_statistics": retained_stats,
        "candidate_patterns": categories,
        "limitations": [
            "Candidate Pattern is a structural description of this checkpoint only.",
            "It is not an importance, intervention, causal, or real-world relation claim."
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--registry", default="configs/phase1_registry.json")
    parser.add_argument("--output-root", default="artifacts/runs")
    args = parser.parse_args()
    pattern_config_path = Path(args.config).resolve()
    registry_path = Path(args.registry).resolve()
    pattern_config = json.loads(pattern_config_path.read_text(encoding="utf-8"))
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    upstream_dir = Path(args.output_root).resolve() / pattern_config["upstream_run_id"]
    upstream_manifest = upstream_dir / "manifest.json"
    web_index = Path("public/data/index.json").resolve()
    fingerprints = [sha256(pattern_config_path), sha256(registry_path), sha256(upstream_manifest), sha256(web_index)]
    run_id = hashlib.sha256("|".join(fingerprints).encode()).hexdigest()
    run_dir = Path(args.output_root).resolve() / run_id
    pattern_dir = run_dir / "patterns"
    pattern_dir.mkdir(parents=True, exist_ok=True)
    summaries = []

    for dataset, ds in registry["datasets"].items():
        graph_path = upstream_dir / "graphs" / f"{dataset}.json"
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        names = source_names(Path(registry["source_root"]) / ds["root_path"] / ds["data_path"])
        result = analyze_dataset(
            graph, names, pattern_config["quantile_low"], pattern_config["quantile_high"],
            pattern_config["persistent_window_count"], pattern_config["window_specific_count"],
            pattern_config["minimum_cooccurrence"], pattern_config["maximum_reported_cooccurring_sets"],
        )
        result["upstream_graph_path"] = str(graph_path)
        result["upstream_graph_sha256"] = sha256(graph_path)
        (pattern_dir / f"{dataset}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        counts = {key: len(value) for key, value in result["candidate_patterns"].items() if isinstance(value, list)}
        summaries.append({"dataset": dataset, "status": "complete", "counts": counts,
                          "pattern_path": str(pattern_dir / f"{dataset}.json")})

    manifest = {"run_id": run_id, "status": "complete", "claim_label": pattern_config["claim_label"],
                "upstream_run_id": pattern_config["upstream_run_id"], "datasets": summaries}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (run_dir / "command.txt").write_text(
        f"python -m dgraudit.cli.discover_patterns --config {args.config} --registry {args.registry} --output-root {args.output_root}\n",
        encoding="utf-8")
    (run_dir / "environment.json").write_text(json.dumps({"python": platform.python_version(), "numpy": np.__version__}, indent=2), encoding="utf-8")
    (run_dir / "stdout.log").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (run_dir / "stderr.log").write_text("", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

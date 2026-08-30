from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from dgraudit.edge_discovery import inspect_native_edges, render_edge_inspection
from dgraudit.local_audit import LocalAuditError, run_local_audit


Input = Callable[[str], str]
Print = Callable[[str], None]


def _absolute_override(raw: str) -> str:
    return str(Path(raw).expanduser().resolve())


def _resolved_input_path(config_path: Path, raw: str) -> str:
    candidate = Path(raw).expanduser()
    return str((config_path.parent / candidate).resolve() if not candidate.is_absolute() else candidate.resolve())


def _ask_index(prompt: str, maximum: int, input_fn: Input) -> int:
    while True:
        raw = input_fn(prompt).strip()
        try:
            value = int(raw)
        except ValueError:
            value = 0
        if 1 <= value <= maximum:
            return value - 1
        print(f"Please enter a number from 1 to {maximum}.")


def _ask_yes_no(prompt: str, input_fn: Input, *, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        raw = input_fn(f"{prompt} {suffix}: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Please enter y or n.")


def _timestamped_config_path(output: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return output.with_name(f"{output.stem}.audit_config.{stamp}.json")


def run_wizard(
    config_path: str | Path,
    *,
    output_path: str | Path = "dgrainsight_session.json",
    bootstrap_repetitions: int = 2000,
    source_root: str | None = None,
    checkpoint: str | None = None,
    dataset: str | None = None,
    sample_index: int | None = None,
    context_index: int | None = None,
    layer: int | None = None,
    edge_rank: int | None = None,
    limit: int = 10,
    include_broader_context: bool | None = None,
    assume_yes: bool = False,
    input_fn: Input = input,
    print_fn: Print = print,
) -> tuple[Path, Path, dict[str, Any]]:
    """Guide one exact supported-model relation from real graph inspection to a portable session."""
    original_path = Path(config_path).expanduser().resolve()
    config = json.loads(original_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Audit config root must be an object.")

    # Persist absolute operands in the wizard-generated config so moving the
    # selected config beside the output never changes path resolution.
    config["source_root"] = _absolute_override(source_root) if source_root else _resolved_input_path(original_path, config["source_root"])
    if checkpoint:
        config["checkpoint"]["path"] = _absolute_override(checkpoint)
        config["checkpoint"].pop("sha256", None)
    else:
        config["checkpoint"]["path"] = _resolved_input_path(original_path, config["checkpoint"]["path"])
    if dataset:
        config["dataset"]["path"] = _absolute_override(dataset)
        config["dataset"].pop("sha256", None)
    else:
        config["dataset"]["path"] = _resolved_input_path(original_path, config["dataset"]["path"])

    output = Path(output_path).expanduser().resolve()
    selected_config = _timestamped_config_path(output)
    selected_config.parent.mkdir(parents=True, exist_ok=True)
    selected_config.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    selection_persisted = False
    try:
        report = inspect_native_edges(
            selected_config,
            sample_index=sample_index,
            context_index=context_index,
            layer=layer,
            limit=limit,
        )
        print_fn(render_edge_inspection(report))
        contexts = report["contexts"]
        if len(contexts) == 1:
            selected_context = contexts[0]
            print_fn(f"\nSelected native graph: {selected_context['context_id']}")
        else:
            print_fn("\nChoose one native graph context:")
            for index, context in enumerate(contexts, start=1):
                print_fn(
                    f"  {index}. {context['context_id']} "
                    f"({context['retained_edge_count']} retained directed edges)"
                )
            context_choice = _ask_index("Context number: ", len(contexts), input_fn)
            selected_context = contexts[context_choice]

        edges = selected_context["top_edges"]
        if not edges:
            raise ValueError(f"{selected_context['context_id']} has no retained directed non-self edges.")
        if edge_rank is None:
            choice = _ask_index(f"Edge number in {selected_context['context_id']}: ", len(edges), input_fn)
        else:
            if not 1 <= edge_rank <= len(edges):
                raise ValueError(f"edge-rank must be between 1 and {len(edges)} for the selected context.")
            choice = edge_rank - 1
        edge = edges[choice]

        native_type = str(selected_context["type"])
        if native_type == "global_graph":
            broader = False
            print_fn("MTGNN already uses this global learned graph across all GCN layers; no synthetic broader scope is added.")
        elif include_broader_context is not None:
            broader = include_broader_context
        elif assume_yes:
            broader = False
        else:
            broader = _ask_yes_no("Also audit removal across all applicable native graph contexts?", input_fn)

        context: dict[str, Any] = {
            "type": native_type,
            "index": int(selected_context["index"]),
        }
        if selected_context.get("layer") is not None:
            context["layer"] = int(selected_context["layer"])
        sample = int(report["sample_index"])
        config["audit"] = {
            "split": "test",
            "samples": [sample],
            "relations": [{
                "sample": sample,
                "context": context,
                "source": int(edge["source"]),
                "target": int(edge["target"]),
                "include_broader_context": broader,
            }],
        }
        selected_config.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        selection_persisted = True

        print_fn(
            f"\nExact selection: {edge['source_name']} -> {edge['target_name']} | "
            f"{selected_context['context_id']} | source={edge['source']} target={edge['target']}"
        )
        if not assume_yes and not _ask_yes_no("Run the validated local audit now?", input_fn, default=True):
            raise KeyboardInterrupt("Audit cancelled by user.")
        print_fn(f"Selected config saved to: {selected_config}")
        written, session = run_local_audit(
            selected_config,
            output_path=output,
            bootstrap_repetitions=bootstrap_repetitions,
            progress=lambda message: print_fn(f"[DGraInsight] {message}"),
        )
        return written, selected_config, session
    except BaseException:
        # Keep the selected config only after an exact selection was persisted.
        if not selection_persisted and selected_config.exists():
            selected_config.unlink()
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Interactively inspect native graphs, select a real edge, and generate a portable audit session."
    )
    parser.add_argument("--config", required=True, help="Model-specific Audit Config v1 template.")
    parser.add_argument("--output", default="dgrainsight_session.json")
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--source-root", help="Override the model source directory without editing the template.")
    parser.add_argument("--checkpoint", help="Override the checkpoint path without editing the template.")
    parser.add_argument("--dataset", help="Override the dataset path without editing the template.")
    parser.add_argument("--sample", type=int)
    parser.add_argument("--context", type=int)
    parser.add_argument("--layer", type=int)
    parser.add_argument("--edge-rank", type=int, help="Choose a displayed edge non-interactively (1-based).")
    parser.add_argument("--limit", type=int, default=10)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--broader", action="store_true", help="Also audit all applicable native contexts.")
    scope.add_argument("--local-only", action="store_true", help="Audit only the selected exact native context.")
    parser.add_argument("--yes", action="store_true", help="Run without the final confirmation prompt.")
    args = parser.parse_args(argv)
    broader = True if args.broader else False if args.local_only else None
    try:
        output, selected_config, session = run_wizard(
            args.config,
            output_path=args.output,
            bootstrap_repetitions=args.bootstrap,
            source_root=args.source_root,
            checkpoint=args.checkpoint,
            dataset=args.dataset,
            sample_index=args.sample,
            context_index=args.context,
            layer=args.layer,
            edge_rank=args.edge_rank,
            limit=args.limit,
            include_broader_context=broader,
            assume_yes=args.yes,
        )
    except KeyboardInterrupt:
        print("\nDGraInsight wizard cancelled.", file=sys.stderr)
        return 130
    except (LocalAuditError, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"DGraInsight wizard failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": "complete",
        "output": str(output),
        "selected_config": str(selected_config),
        "session_id": session["session"]["session_id"],
        "model": session["model"]["name"],
        "dataset": session["dataset"]["name"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

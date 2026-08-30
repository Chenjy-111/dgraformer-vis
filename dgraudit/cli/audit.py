from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dgraudit.quick_audit import run_quick_audit
from dgraudit.v2.runner import run_audit_v2, terminal_summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a validated DGraFormer, MSGNet, or MTGNN audit and create a portable "
            "DGraInsight Session v2."
        )
    )
    parser.add_argument("--config", required=True, help="Path to a DGraInsight Audit Config v2.")
    parser.add_argument("--output", default="dgrainsight_session_v2.json", help="Destination Session v2 JSON.")
    parser.add_argument(
        "--no-embedded-trajectories",
        action="store_true",
        help="Diagnostic only: omit embedded intervention tensors from frozen formal output.",
    )
    args = parser.parse_args(argv)
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")
    try:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        if config.get("config_version") != 2:
            raise ValueError("DGraInsight audit accepts Audit Config v2 only.")
        if config.get("audit_mode") == "formal_evidence_audit":
            output, session = run_audit_v2(
                args.config,
                output_path=args.output,
                progress=lambda message: print(f"[DGraInsight] {message}", flush=True),
                include_intervention_trajectories=not args.no_embedded_trajectories,
            )
            print(terminal_summary(session, output))
            return 0
        if config.get("audit_mode") != "quick_inspection":
            raise ValueError("audit_mode must be quick_inspection or formal_evidence_audit.")
        output, session = run_quick_audit(
            args.config,
            output_path=args.output,
            progress=lambda message: print(f"[DGraInsight Quick Inspection] {message}", flush=True),
        )
        print("Quick Inspection: Single-case inspection does not constitute cross-sample statistical evidence.")
    except (OSError, ValueError, KeyError, RuntimeError, ModuleNotFoundError, json.JSONDecodeError) as exc:
        print("DGraInsight local audit failed", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({
        "status": session["session"].get("status", "complete"),
        "output": str(output),
        "session_id": session["session"]["session_id"],
        "model": session["model"]["name"],
        "dataset": session["dataset"]["name"],
        "sample_count": len(session["samples"]),
        "relation_count": len(session["relations"]),
        "schema_version": session["schema_version"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

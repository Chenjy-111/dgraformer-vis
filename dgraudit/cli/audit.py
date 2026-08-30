from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from dgraudit.v2.quick import upgrade_quick_session_v1
from dgraudit.v2.runner import run_audit_v2, terminal_summary
from dgraudit.v2.session import write_audit_session_v2


def run_local_audit(*args, **kwargs):
    from dgraudit.local_audit import run_local_audit as legacy_run_local_audit
    return legacy_run_local_audit(*args, **kwargs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a validated DGraFormer, MSGNet, or MTGNN audit on this computer and create one "
            "portable dgrainsight_session.json file for the DGraInsight website."
        )
    )
    parser.add_argument("--config", required=True, help="Path to a DGraInsight Audit Config v2 (or a v1 template for Quick Inspection).")
    parser.add_argument("--output", default="dgrainsight_session.json", help="Destination portable session JSON.")
    parser.add_argument(
        "--bootstrap",
        type=int,
        default=2000,
        help="Bootstrap repetitions for matched-control confidence intervals (default: 2000).",
    )
    parser.add_argument("--session-version", choices=("1", "2"), default="2", help="Output Session v2 by default; v1 requires an explicit legacy request.")
    parser.add_argument("--legacy-v1", action="store_true", help="Explicit alias for --session-version 1.")
    parser.add_argument("--no-embedded-trajectories", action="store_true", help="Diagnostic only: omit embedded intervention tensors from frozen Session v2 output.")
    args = parser.parse_args(argv)
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")
    try:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        legacy = args.legacy_v1 or args.session_version == "1"
        if legacy:
            output, session = run_local_audit(args.config, output_path=args.output, bootstrap_repetitions=args.bootstrap, progress=lambda message: print(f"[DGraInsight legacy v1] {message}", flush=True))
            print("Legacy single-case / legacy inference session (explicit v1 mode).", file=sys.stderr)
        elif config.get("config_version") == 2:
            output, session = run_audit_v2(args.config, output_path=args.output, progress=lambda message: print(f"[DGraInsight] {message}", flush=True), include_intervention_trajectories=not args.no_embedded_trajectories)
            print(terminal_summary(session, output))
            return 0
        else:
            destination = Path(args.output).expanduser().resolve()
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="dgraudit-v1-quick-", dir=destination.parent) as directory:
                legacy_output = Path(directory) / "legacy_session_v1.json"
                _, legacy_session = run_local_audit(args.config, output_path=legacy_output, bootstrap_repetitions=args.bootstrap, progress=lambda message: print(f"[DGraInsight Quick Inspection] {message}", flush=True))
                session = upgrade_quick_session_v1(legacy_session)
                output = write_audit_session_v2(destination, session)
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

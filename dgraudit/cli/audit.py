from __future__ import annotations

import argparse
import json
import sys

from dgraudit.local_audit import LocalAuditError, run_local_audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a validated DGraFormer, MSGNet, or MTGNN audit on this computer and create one "
            "portable dgrainsight_session.json file for the DGraInsight website."
        )
    )
    parser.add_argument("--config", required=True, help="Path to a DGraInsight Audit Config v1 JSON file.")
    parser.add_argument("--output", default="dgrainsight_session.json", help="Destination portable session JSON.")
    parser.add_argument(
        "--bootstrap",
        type=int,
        default=2000,
        help="Bootstrap repetitions for matched-control confidence intervals (default: 2000).",
    )
    args = parser.parse_args(argv)
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")
    try:
        output, session = run_local_audit(
            args.config,
            output_path=args.output,
            bootstrap_repetitions=args.bootstrap,
            progress=lambda message: print(f"[DGraInsight] {message}", flush=True),
        )
    except (LocalAuditError, OSError) as exc:
        print("DGraInsight local audit failed", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({
        "status": "complete",
        "output": str(output),
        "session_id": session["session"]["session_id"],
        "model": session["model"]["name"],
        "dataset": session["dataset"]["name"],
        "sample_count": len(session["samples"]),
        "relation_count": len(session["relations"]),
        "evidence_summary": session["evidence_summary"],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

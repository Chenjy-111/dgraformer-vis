from __future__ import annotations

import argparse
import json
import sys

from dgraudit.session import AuditSessionError, write_audit_session


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Legacy compatibility exporter for immutable Audit Session v1 artifacts; v1 case p/BH is not Pipeline v2 formal evidence."
    )
    parser.add_argument("--config", required=True, help="Path to a DGraInsight Session Export Config v1 JSON file.")
    parser.add_argument("--output", help="Optional output override for dgrainsight_session.json.")
    args = parser.parse_args()

    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")
    try:
        output, session = write_audit_session(args.config, output_path=args.output)
    except AuditSessionError as exc:
        print("DGraInsight Audit Session export failed", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 2

    summary = {
        "status": "exported",
        "output": str(output),
        "schema_version": session["schema_version"],
        "session_id": session["session"]["session_id"],
        "model": session["model"]["name"],
        "dataset": session["dataset"]["name"],
        "sample_count": len(session["samples"]),
        "relation_count": len(session["relations"]),
        "evidence_summary": session["evidence_summary"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

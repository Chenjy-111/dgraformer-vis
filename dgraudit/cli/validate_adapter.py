from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dgraudit.validation import render_validation_report, validate_audit_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate an official or explicitly declared custom adapter for Quick Inspection."
    )
    parser.add_argument("--config", required=True, help="Quick Inspection Audit Config v2.")
    parser.add_argument("--output", help="Optional JSON conformance report destination.")
    parser.add_argument("--debug", action="store_true", help="Include bounded underlying exception details.")
    args = parser.parse_args(argv)
    try:
        report = validate_audit_config(args.config, debug=args.debug)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"DGraInsight adapter conformance failed: {exc}", file=sys.stderr)
        return 2
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")
    print(render_validation_report(report))
    if args.output:
        destination = Path(args.output).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if report.get("status") == "ready_for_audit" else 2


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dgraudit.validation import render_validation_report, validate_audit_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate supported DGraInsight local-audit inputs before audit execution.")
    parser.add_argument("--config", required=True, help="Path to a DGraInsight Audit Config v1 JSON file.")
    parser.add_argument("--output", help="Optional path for the machine-readable validation report.")
    parser.add_argument("--debug", action="store_true", help="Include bounded exception details in the JSON report.")
    args = parser.parse_args(argv)

    report = validate_audit_config(args.config, debug=args.debug)
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")
    print(render_validation_report(report))
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if report["status"] == "ready_for_audit" else 2


if __name__ == "__main__":
    raise SystemExit(main())

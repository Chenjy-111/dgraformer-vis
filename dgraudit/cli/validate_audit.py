from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dgraudit.v2.config import statistical_protocol_checks, validate_audit_config_v2
from dgraudit.validation import render_validation_report, validate_audit_config


def validate_config_file(path: str | Path, *, debug: bool = False) -> tuple[dict, str]:
    config_path = Path(path).expanduser().resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if isinstance(config, dict) and config.get("config_version") == 2:
        errors = validate_audit_config_v2(config)
        report = {
            "schema_version": "dgrainsight.audit_config_validation.v2",
            "config": str(config_path),
            "status": "ready_for_audit" if not errors else "invalid_config",
            "errors": errors,
            "checks": statistical_protocol_checks(config),
        }
        return report, json.dumps(report, indent=2, ensure_ascii=False)
    report = validate_audit_config(config_path, debug=debug)
    return report, render_validation_report(report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate supported DGraInsight local-audit inputs before audit execution.")
    parser.add_argument("--config", required=True, help="Path to a current Audit Config v2 or legacy v1 JSON file.")
    parser.add_argument("--output", help="Optional path for the machine-readable validation report.")
    parser.add_argument("--debug", action="store_true", help="Include bounded exception details in the JSON report.")
    args = parser.parse_args(argv)

    try:
        report, rendered = validate_config_file(args.config, debug=args.debug)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"DGraInsight config validation failed: {exc}", file=sys.stderr)
        return 2
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")
    print(rendered)
    if args.output:
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if report["status"] == "ready_for_audit" else 2


if __name__ == "__main__":
    raise SystemExit(main())

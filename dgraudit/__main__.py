from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m dgraudit",
        description="DGraInsight supported local audit and portable-session tools.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="Run the required V01-V09 adapter preflight.")
    validate.add_argument("--config", required=True)
    validate.add_argument("--output")
    validate.add_argument("--debug", action="store_true")
    audit = subparsers.add_parser("audit", help="Run the offline audit and generate dgrainsight_session.json.")
    audit.add_argument("--config", required=True)
    audit.add_argument("--output", default="dgrainsight_session.json")
    audit.add_argument("--bootstrap", type=int, default=2000)
    args = parser.parse_args()
    if args.command == "validate":
        from dgraudit.cli.validate_audit import main as validate_main

        forwarded = ["--config", args.config]
        if args.output:
            forwarded.extend(["--output", args.output])
        if args.debug:
            forwarded.append("--debug")
        return validate_main(forwarded)
    from dgraudit.cli.audit import main as audit_main

    return audit_main([
        "--config", args.config,
        "--output", args.output,
        "--bootstrap", str(args.bootstrap),
    ])


if __name__ == "__main__":
    raise SystemExit(main())

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
    edges = subparsers.add_parser("edges", help="Show native graph counts and retained edge candidates.")
    edges.add_argument("--config", required=True)
    edges.add_argument("--sample", type=int)
    edges.add_argument("--context", type=int)
    edges.add_argument("--layer", type=int)
    edges.add_argument("--limit", type=int, default=10)
    edges.add_argument("--json", action="store_true", dest="as_json")
    wizard = subparsers.add_parser("wizard", help="Choose a real native edge interactively and generate a session.")
    wizard.add_argument("--config", required=True)
    wizard.add_argument("--output", default="dgrainsight_session.json")
    wizard.add_argument("--bootstrap", type=int, default=2000)
    wizard.add_argument("--source-root")
    wizard.add_argument("--checkpoint")
    wizard.add_argument("--dataset")
    wizard.add_argument("--sample", type=int)
    wizard.add_argument("--context", type=int)
    wizard.add_argument("--layer", type=int)
    wizard.add_argument("--edge-rank", type=int)
    wizard.add_argument("--limit", type=int, default=10)
    wizard_scope = wizard.add_mutually_exclusive_group()
    wizard_scope.add_argument("--broader", action="store_true")
    wizard_scope.add_argument("--local-only", action="store_true")
    wizard.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    if args.command == "validate":
        from dgraudit.cli.validate_audit import main as validate_main

        forwarded = ["--config", args.config]
        if args.output:
            forwarded.extend(["--output", args.output])
        if args.debug:
            forwarded.append("--debug")
        return validate_main(forwarded)
    if args.command == "edges":
        from dgraudit.cli.inspect_edges import main as inspect_main

        forwarded = ["--config", args.config, "--limit", str(args.limit)]
        if args.sample is not None:
            forwarded.extend(["--sample", str(args.sample)])
        if args.context is not None:
            forwarded.extend(["--context", str(args.context)])
        if args.layer is not None:
            forwarded.extend(["--layer", str(args.layer)])
        if args.as_json:
            forwarded.append("--json")
        return inspect_main(forwarded)
    if args.command == "wizard":
        from dgraudit.cli.wizard import main as wizard_main

        forwarded = [
            "--config", args.config,
            "--output", args.output,
            "--bootstrap", str(args.bootstrap),
            "--limit", str(args.limit),
        ]
        for flag, value in (
            ("--source-root", args.source_root), ("--checkpoint", args.checkpoint),
            ("--dataset", args.dataset), ("--sample", args.sample),
            ("--context", args.context), ("--layer", args.layer),
            ("--edge-rank", args.edge_rank),
        ):
            if value is not None:
                forwarded.extend([flag, str(value)])
        if args.broader:
            forwarded.append("--broader")
        if args.local_only:
            forwarded.append("--local-only")
        if args.yes:
            forwarded.append("--yes")
        return wizard_main(forwarded)
    from dgraudit.cli.audit import main as audit_main

    return audit_main([
        "--config", args.config,
        "--output", args.output,
        "--bootstrap", str(args.bootstrap),
    ])


if __name__ == "__main__":
    raise SystemExit(main())

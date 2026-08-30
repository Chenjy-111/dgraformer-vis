from __future__ import annotations

import argparse
import json
import sys

from dgraudit.edge_discovery import inspect_native_edges, render_edge_inspection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show native graph counts and real retained edge candidates.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--sample", type=int)
    parser.add_argument("--context", type=int)
    parser.add_argument("--layer", type=int)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        report = inspect_native_edges(
            args.config,
            sample_index=args.sample,
            context_index=args.context,
            layer=args.layer,
            limit=args.limit,
        )
    except Exception as exc:
        print(f"DGraInsight graph inspection failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.as_json else render_edge_inspection(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dgraudit.v2.session import validate_audit_session_v2


def validate_json_schema(session: object, schema_path: str | Path | None = None) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    path = Path(schema_path) if schema_path else Path(__file__).resolve().parents[2] / "schemas/dgrainsight_audit_session_v2.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    if jsonschema is None:
        from dgraudit.v2.jsonschema_subset import validate
        return validate(session, schema)
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{'.'.join(str(part) for part in error.absolute_path)}: {error.message}" for error in sorted(validator.iter_errors(session), key=lambda item: list(item.absolute_path))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a DGraInsight Portable Audit Session v2 semantically and against JSON Schema.")
    parser.add_argument("session")
    parser.add_argument("--schema")
    args = parser.parse_args(argv)
    try:
        session = json.loads(Path(args.session).read_text(encoding="utf-8"))
        errors = validate_json_schema(session, args.schema) + validate_audit_session_v2(session)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"SESSION V2 INVALID: {exc}", file=sys.stderr)
        return 2
    if errors:
        print("SESSION V2 INVALID", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("SESSION V2 VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

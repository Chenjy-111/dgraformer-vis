"""Dependency-free validator for the JSON Schema keywords used by DGraInsight.

The project prefers ``jsonschema`` when installed. This fallback keeps offline
bundles verifiable without downloading a package; unsupported keywords fail
closed during schema loading rather than being silently ignored.
"""

from __future__ import annotations

import math
from typing import Any, Mapping


SUPPORTED = {"$schema", "$id", "$defs", "title", "description", "$ref", "type", "const", "enum", "required", "properties", "additionalProperties", "items", "minItems", "uniqueItems", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "allOf", "anyOf", "not", "if", "then"}


def validate(instance: Any, schema: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    _check_keywords(schema, "#", errors)
    if errors:
        return errors
    _validate(instance, schema, schema, "$", errors)
    return errors


def _check_keywords(schema: Any, path: str, errors: list[str]) -> None:
    if isinstance(schema, Mapping):
        unknown = set(schema) - SUPPORTED
        if unknown:
            errors.append(f"{path}: unsupported JSON Schema keywords {sorted(unknown)}")
        for key, value in schema.items():
            if key not in {"properties", "$defs"}:
                _check_keywords(value, f"{path}/{key}", errors)
            elif isinstance(value, Mapping):
                for name, child in value.items():
                    _check_keywords(child, f"{path}/{key}/{name}", errors)
    elif isinstance(schema, list):
        for index, child in enumerate(schema):
            _check_keywords(child, f"{path}/{index}", errors)


def _resolve(root: Mapping[str, Any], reference: str) -> Mapping[str, Any]:
    if not reference.startswith("#/"):
        raise ValueError(f"Only local JSON Schema references are supported: {reference}")
    value: Any = root
    for part in reference[2:].split("/"):
        value = value[part.replace("~1", "/").replace("~0", "~")]
    return value


def _is_type(value: Any, expected: str) -> bool:
    return {
        "null": value is None,
        "object": isinstance(value, Mapping),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)),
    }.get(expected, False)


def _subvalid(value: Any, schema: Mapping[str, Any], root: Mapping[str, Any]) -> bool:
    temporary: list[str] = []
    _validate(value, schema, root, "$", temporary)
    return not temporary


def _validate(value: Any, schema: Mapping[str, Any], root: Mapping[str, Any], path: str, errors: list[str]) -> None:
    if "$ref" in schema:
        _validate(value, _resolve(root, str(schema["$ref"])), root, path, errors)
        return
    expected = schema.get("type")
    if expected is not None:
        choices = expected if isinstance(expected, list) else [expected]
        if not any(_is_type(value, str(choice)) for choice in choices):
            errors.append(f"{path}: expected type {choices}")
            return
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value is not in enum")
    if "allOf" in schema:
        for child in schema["allOf"]:
            _validate(value, child, root, path, errors)
    if "anyOf" in schema and not any(_subvalid(value, child, root) for child in schema["anyOf"]):
        errors.append(f"{path}: no anyOf branch matched")
    if "not" in schema and _subvalid(value, schema["not"], root):
        errors.append(f"{path}: forbidden schema matched")
    if "if" in schema and _subvalid(value, schema["if"], root) and "then" in schema:
        _validate(value, schema["then"], root, path, errors)
    if isinstance(value, Mapping):
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}: missing required property {name}")
        properties = schema.get("properties", {})
        for name, child in properties.items():
            if name in value:
                _validate(value[name], child, root, f"{path}.{name}", errors)
        if schema.get("additionalProperties") is False:
            for name in set(value) - set(properties):
                errors.append(f"{path}: additional property {name} is not allowed")
        elif isinstance(schema.get("additionalProperties"), Mapping):
            for name in set(value) - set(properties):
                _validate(value[name], schema["additionalProperties"], root, f"{path}.{name}", errors)
    if isinstance(value, list):
        if len(value) < int(schema.get("minItems", 0)):
            errors.append(f"{path}: array is shorter than minItems")
        if schema.get("uniqueItems"):
            import json
            encoded = [json.dumps(item, sort_keys=True, ensure_ascii=False) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: array items are not unique")
        if isinstance(schema.get("items"), Mapping):
            for index, item in enumerate(value):
                _validate(item, schema["items"], root, f"{path}[{index}]", errors)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: below exclusiveMinimum")
        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            errors.append(f"{path}: above exclusiveMaximum")

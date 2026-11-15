"""A small JSON Schema checker for the subset the phone contract uses.

The schemas in packages/contracts/phone/ are the single source of truth: the service checks
requests and its own answers against them directly. Only the keywords in KNOWN are understood. A
schema using any other keyword is refused when it is loaded, so a schema can't quietly ask for a
check this code doesn't make. Objects never accept unknown fields, whatever the schema says.
"""

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

KNOWN = {
    "$schema", "$id", "title", "description", "type", "properties", "required", "additionalProperties",
    "enum", "const", "minLength", "maxLength", "pattern", "minItems", "maxItems", "items", "minimum",
    "maximum", "format",
}
TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}
FORMATS = {"date-time"}

# RFC 3339 with a required offset; seconds and up to 6 fraction digits optional (Shortcuts' ISO 8601).
DATE_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:?\d{2})$")

CONTRACTS = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "phone"


class SchemaError(ValueError):
    """The schema itself is broken or uses something this checker doesn't do."""


class Invalid(ValueError):
    """A value doesn't match its schema. The message names the place, never the value."""

    def __init__(self, path, message):
        super().__init__(f"{path}: {message}")
        self.path = path


def parse_date_time(text):
    """Return an aware datetime for an RFC 3339 string with an offset, or None."""
    if not isinstance(text, str) or not DATE_TIME.match(text):
        return None
    value = text[:-1] + "+00:00" if text.endswith("Z") else text
    if re.search(r"[+-]\d{4}$", value):
        value = f"{value[:-2]}:{value[-2:]}"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def check_schema(schema, path="$"):
    if not isinstance(schema, dict):
        raise SchemaError(f"{path}: a schema must be an object")
    unknown = set(schema) - KNOWN
    if unknown:
        raise SchemaError(f"{path}: unsupported keyword(s): {', '.join(sorted(unknown))}")
    types = schema.get("type")
    if types is not None:
        for t in types if isinstance(types, list) else [types]:
            if t not in TYPES:
                raise SchemaError(f"{path}: unknown type {t!r}")
    if "additionalProperties" in schema and schema["additionalProperties"] is not False:
        raise SchemaError(f"{path}: only additionalProperties: false is supported")
    if "format" in schema and schema["format"] not in FORMATS:
        raise SchemaError(f"{path}: unsupported format {schema['format']!r}")
    if "pattern" in schema:
        re.compile(schema["pattern"])
    for name, sub in (schema.get("properties") or {}).items():
        check_schema(sub, f"{path}.{name}")
    for name in schema.get("required") or []:
        if name not in (schema.get("properties") or {}):
            raise SchemaError(f"{path}: required field {name!r} has no schema")
    if "items" in schema:
        check_schema(schema["items"], f"{path}[]")
    return schema


def load(name, directory=CONTRACTS):
    """Load and check packages/contracts/phone/<name>.schema.json."""
    with open(Path(directory) / f"{name}.schema.json", encoding="utf-8") as handle:
        return check_schema(json.load(handle))


def _type_of(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def _same(a, b):
    """Equality that keeps true apart from 1 and 1.0 apart from 1."""
    return _type_of(a) == _type_of(b) and a == b


def _type_ok(value, wanted):
    actual = _type_of(value)
    for t in wanted if isinstance(wanted, list) else [wanted]:
        if t == actual:
            return True
        if t == "number" and actual == "integer":
            return True
    return False


def validate(schema, value, path="$"):
    """Raise Invalid at the first problem. Returns the value unchanged."""
    if "const" in schema and not _same(value, schema["const"]):
        raise Invalid(path, "has the wrong value")
    if "enum" in schema and not any(_same(value, option) for option in schema["enum"]):
        raise Invalid(path, "isn't one of the allowed values")
    if "type" in schema and not _type_ok(value, schema["type"]):
        raise Invalid(path, f"must be {schema['type'] if isinstance(schema['type'], str) else ' or '.join(schema['type'])}")
    kind = _type_of(value)
    if kind == "number" and not math.isfinite(value):
        raise Invalid(path, "must be a finite number")
    if kind in ("integer", "number"):
        if "minimum" in schema and value < schema["minimum"]:
            raise Invalid(path, f"is below {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise Invalid(path, f"is above {schema['maximum']}")
    if kind == "string":
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise Invalid(path, f"is shorter than {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise Invalid(path, f"is longer than {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise Invalid(path, "has the wrong form")
        if schema.get("format") == "date-time" and parse_date_time(value) is None:
            raise Invalid(path, "must be an ISO 8601 date and time with an offset")
    if kind == "array":
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise Invalid(path, f"has fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise Invalid(path, f"has more than {schema['maxItems']} items")
        if "items" in schema:
            for index, item in enumerate(value):
                validate(schema["items"], item, f"{path}[{index}]")
    if kind == "object":
        properties = schema.get("properties") or {}
        for name in value:
            if name not in properties:
                raise Invalid(path, f"has an unknown field {name[:40]!r}")
        for name in schema.get("required") or []:
            if name not in value:
                raise Invalid(path, f"is missing {name!r}")
        for name, sub in properties.items():
            if name in value:
                validate(sub, value[name], f"{path}.{name}")
    return value


def utc_now():
    return datetime.now(timezone.utc)

from __future__ import annotations

import codecs
import json
import re
from pathlib import Path
from typing import Any

from reconciliation.errors import ConfigurationError
from reconciliation.models import CsvOptions, DecimalFormat, FieldRule, KeyPart, KeyRule, MappingConfig
from reconciliation.normalize import text_value


def _object(
    value: Any, location: str, allowed: set[str], required: set[str] | None = None
) -> dict:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{location} must be an object")
    extra = set(value) - allowed
    missing = (required or set()) - set(value)
    if extra:
        raise ConfigurationError(f"{location}: unknown option(s): {', '.join(sorted(extra))}")
    if missing:
        raise ConfigurationError(f"{location}: required option(s): {', '.join(sorted(missing))}")
    return value


def _string(value: Any, location: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ConfigurationError(f"{location} must be a non-empty string")
    return value


def _boolean(value: Any, location: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigurationError(f"{location} must be true or false")
    return value


def _csv_options(value: Any, location: str) -> CsvOptions:
    data = _object(value, location, {"delimiter", "encoding"})
    delimiter = _string(data.get("delimiter", ","), f"{location}.delimiter")
    if len(delimiter) != 1 or delimiter in ('"', "\r", "\n", "\x00"):
        raise ConfigurationError(f"{location}.delimiter must be one valid CSV separator")
    encoding = _string(data.get("encoding", "utf-8-sig"), f"{location}.encoding")
    try:
        codecs.lookup(encoding)
    except LookupError as exc:
        raise ConfigurationError(f"{location}.encoding is unsupported: {encoding}") from exc
    return CsvOptions(delimiter=delimiter, encoding=encoding)


def _decimal_format(value: Any, location: str) -> DecimalFormat:
    data = _object(value, location, {"decimal", "thousands"}, {"decimal"})
    decimal = _string(data["decimal"], f"{location}.decimal")
    thousands = _string(data.get("thousands", ""), f"{location}.thousands", allow_empty=True)
    if len(decimal) != 1 or len(thousands) > 1 or decimal == thousands:
        raise ConfigurationError(f"{location} separators must be distinct single characters")
    invalid_decimal = decimal.isdigit() or decimal in "+-\r\n"
    invalid_thousands = bool(thousands) and (thousands.isdigit() or thousands in "+-\r\n")
    if invalid_decimal or invalid_thousands:
        raise ConfigurationError(f"{location} contains an invalid numeric separator")
    return DecimalFormat(decimal=decimal, thousands=thousands)


def _date_format(value: Any, location: str) -> str:
    pattern = _string(value, location)
    if "%Y" not in pattern:
        raise ConfigurationError(f"{location} must include a four-digit year")
    tokens = re.findall(r"%[Ymd]", pattern)
    invalid = re.sub(r"%[Ymd]|[-./ ]", "", pattern)
    if invalid or sorted(tokens) != ["%Y", "%d", "%m"]:
        raise ConfigurationError(f"{location} must use %Y, %m and %d once each")
    return pattern


def _field(value: Any, index: int) -> FieldRule:
    location = f"fields[{index}]"
    data = _object(
        value,
        location,
        {
            "name", "source", "target", "type", "required", "category", "strip",
            "casefold", "collapse_whitespace", "aliases", "source_format", "target_format",
            "absolute_tolerance",
        },
        {"name", "source", "target", "type"},
    )
    name = _string(data["name"], f"{location}.name")
    source = _string(data["source"], f"{location}.source")
    target = _string(data["target"], f"{location}.target")
    data_type = data["type"]
    if data_type not in ("text", "decimal", "date"):
        raise ConfigurationError(f"{location}.type must be text, decimal or date")
    category = data.get("category", "value")
    if category not in ("value", "status") or (category == "status" and data_type != "text"):
        raise ConfigurationError(f"{location}.category must be value or text/status")

    required = _boolean(data.get("required", True), f"{location}.required")
    strip = _boolean(data.get("strip", True), f"{location}.strip")
    casefold = _boolean(data.get("casefold", False), f"{location}.casefold")
    collapse = _boolean(data.get("collapse_whitespace", False), f"{location}.collapse_whitespace")
    aliases = data.get("aliases", {})
    if not isinstance(aliases, dict) or any(
        not isinstance(key, str) or not isinstance(alias, str) or not key or not alias
        for key, alias in aliases.items()
    ):
        raise ConfigurationError(f"{location}.aliases must map non-empty strings to strings")
    if data_type != "text" and (aliases or "casefold" in data or "collapse_whitespace" in data):
        raise ConfigurationError(f"{location}: text normalization applies only to text fields")
    if data_type == "text" and ("source_format" in data or "target_format" in data):
        raise ConfigurationError(f"{location}: text fields do not take formats")
    if data_type in ("decimal", "date") and (
        "source_format" not in data or "target_format" not in data
    ):
        raise ConfigurationError(f"{location}: {data_type} requires both source_format and target_format")

    tolerance = data.get("absolute_tolerance")
    if tolerance is not None:
        if data_type != "decimal" or not isinstance(tolerance, str) or not re.fullmatch(r"(?:0|[0-9]+)(?:\.[0-9]+)?", tolerance):
            raise ConfigurationError(f"{location}.absolute_tolerance must be a non-negative decimal string on decimal fields")
    if data_type == "decimal":
        source_format = _decimal_format(data["source_format"], f"{location}.source_format")
        target_format = _decimal_format(data["target_format"], f"{location}.target_format")
    elif data_type == "date":
        source_format = _date_format(data["source_format"], f"{location}.source_format")
        target_format = _date_format(data["target_format"], f"{location}.target_format")
    else:
        source_format = target_format = None

    # Aliases follow the same normalization as input values.
    normalized_aliases: dict[str, str] = {}
    for alias, canonical in aliases.items():
        normalized = text_value(alias, strip=strip, casefold=casefold, collapse=collapse)
        canonical = text_value(canonical, strip=strip, casefold=casefold, collapse=collapse)
        if normalized in normalized_aliases and normalized_aliases[normalized] != canonical:
            raise ConfigurationError(f"{location}.aliases contains conflicting normalized keys")
        normalized_aliases[normalized] = canonical
    return FieldRule(
        name=name, source=source, target=target, type=data_type, required=required,
        category=category, strip=strip, casefold=casefold, collapse_whitespace=collapse,
        aliases=normalized_aliases, source_format=source_format, target_format=target_format,
        absolute_tolerance=tolerance,
    )


def load_config(path: Path) -> MappingConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"cannot load mapping from {path}: {exc}") from exc

    data = _object(raw, "config", {"version", "source", "target", "key", "fields"},
                   {"version", "source", "target", "key", "fields"})
    if type(data["version"]) is not int or data["version"] != 1:
        raise ConfigurationError("config.version must be 1")
    key_data = _object(data["key"], "key", {"source", "target", "parts", "strip", "casefold"})
    if "parts" in key_data:
        if "source" in key_data or "target" in key_data:
            raise ConfigurationError("key: use either source/target or parts, not both")
        raw_parts = key_data["parts"]
        if not isinstance(raw_parts, list) or not (2 <= len(raw_parts) <= 6):
            raise ConfigurationError("key.parts must contain 2 to 6 components")
        parts = tuple(KeyPart(
            source=_string(_object(part, f"key.parts[{i}]", {"source", "target"}, {"source", "target"})["source"], f"key.parts[{i}].source"),
            target=_string(part["target"], f"key.parts[{i}].target"),
        ) for i, part in enumerate(raw_parts))
        if len({p.source for p in parts}) != len(parts) or len({p.target for p in parts}) != len(parts):
            raise ConfigurationError("key.parts columns must be unique on each side")
        source_name, target_name = "", ""
    else:
        _object(key_data, "key", {"source", "target", "strip", "casefold"}, {"source", "target"})
        source_name = _string(key_data["source"], "key.source")
        target_name = _string(key_data["target"], "key.target")
        parts = ()
    key = KeyRule(
        source=source_name, target=target_name,
        strip=_boolean(key_data.get("strip", True), "key.strip"),
        casefold=_boolean(key_data.get("casefold", False), "key.casefold"), parts=parts,
    )
    values = data["fields"]
    if not isinstance(values, list) or not values:
        raise ConfigurationError("config.fields must be a non-empty list")
    fields = tuple(_field(value, index) for index, value in enumerate(values))
    names = [field.name for field in fields]
    if len(names) != len(set(names)):
        raise ConfigurationError("config.fields has duplicate logical names")
    return MappingConfig(
        source=_csv_options(data["source"], "source"),
        target=_csv_options(data["target"], "target"),
        key=key,
        fields=fields,
    )

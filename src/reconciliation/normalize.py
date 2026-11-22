from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from reconciliation.errors import InvalidValue
from reconciliation.models import DecimalFormat, FieldRule, Side


def text_value(value: str, *, strip: bool, casefold: bool, collapse: bool) -> str:
    if strip:
        value = value.strip()
    if collapse:
        value = " ".join(value.split())
    if casefold:
        value = value.casefold()
    return value


def normalize_key(value: str, *, strip: bool, casefold: bool) -> str:
    return text_value(value, strip=strip, casefold=casefold, collapse=False)


def decimal_value(value: str, fmt: DecimalFormat) -> str:
    integer = (
        rf"(?:[0-9]{{1,3}}(?:{re.escape(fmt.thousands)}[0-9]{{3}})+|[0-9]+)"
        if fmt.thousands
        else r"[0-9]+"
    )
    pattern = rf"[+-]?{integer}(?:{re.escape(fmt.decimal)}[0-9]+)?"
    if not re.fullmatch(pattern, value):
        raise InvalidValue("invalid decimal for the configured separators")
    normalized = value.replace(fmt.thousands, "") if fmt.thousands else value
    normalized = normalized.replace(fmt.decimal, ".")
    try:
        number = Decimal(normalized)
    except InvalidOperation as exc:
        raise InvalidValue("invalid decimal") from exc
    if not number.is_finite():
        raise InvalidValue("non-finite decimal is not allowed")
    if not number:
        return "0"
    fixed = format(number, "f")
    return fixed.rstrip("0").rstrip(".") if "." in fixed else fixed


def date_value(value: str, pattern: str) -> str:
    try:
        parsed = datetime.strptime(value, pattern)
    except ValueError as exc:
        raise InvalidValue("date does not match the configured format") from exc
    if parsed.strftime(pattern) != value:
        raise InvalidValue("date is not in the exact configured format")
    return parsed.date().isoformat()


def normalize_field(value: str, rule: FieldRule, side: Side) -> str | None:
    if rule.strip:
        value = value.strip()
    if not value:
        if rule.required:
            raise InvalidValue("required value is empty")
        return None
    if rule.type == "text":
        canonical = text_value(
            value, strip=rule.strip, casefold=rule.casefold,
            collapse=rule.collapse_whitespace,
        )
        return rule.aliases.get(canonical, canonical)
    fmt = rule.source_format if side == "source" else rule.target_format
    if rule.type == "decimal":
        assert isinstance(fmt, DecimalFormat)
        return decimal_value(value, fmt)
    assert isinstance(fmt, str)
    return date_value(value, fmt)

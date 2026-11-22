from __future__ import annotations

import pytest

from reconciliation.errors import InvalidValue
from reconciliation.models import DecimalFormat, FieldRule
from reconciliation.normalize import date_value, decimal_value, normalize_field, normalize_key, text_value


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1.250,00", "1250"), ("0,01", "0.01"), ("-2,50", "-2.5"),
     ("1000000,00", "1000000"), ("+1,0", "1"), ("0", "0")],
)
def test_br_decimal(raw: str, expected: str) -> None:
    assert decimal_value(raw, DecimalFormat(decimal=",", thousands=".")) == expected


@pytest.mark.parametrize("raw", ["1.25,00", "12,3,4", "1.234.56,00", "1e3", "NaN", "1 234,00"])
def test_reject_ambiguous_or_bad_decimal(raw: str) -> None:
    with pytest.raises(InvalidValue):
        decimal_value(raw, DecimalFormat(decimal=",", thousands="."))


def test_decimal_exactness_beyond_float_precision() -> None:
    assert decimal_value("999999999999999999999.01", DecimalFormat()) == "999999999999999999999.01"


def test_date_normalization() -> None:
    assert date_value("03/11/2026", "%d/%m/%Y") == "2026-11-03"
    with pytest.raises(InvalidValue):
        date_value("31/02/2026", "%d/%m/%Y")


def test_no_implicit_key_conversion() -> None:
    assert normalize_key(" 00045 ", strip=True, casefold=False) == "00045"
    assert normalize_key(" AbC ", strip=True, casefold=True) == "abc"


def test_text_rules_are_explicit() -> None:
    assert text_value("  A   B  ", strip=True, casefold=True, collapse=True) == "a b"
    assert text_value("  A   B  ", strip=False, casefold=False, collapse=False) == "  A   B  "


def test_aliases_resolve_to_canonical_status(config) -> None:
    rule = next(field for field in config.fields if field.name == "status")
    assert normalize_field(" PAGO ", rule, "target") == "paid"
    assert normalize_field("paid", rule, "source") == "paid"


def test_optional_blank_is_not_an_error() -> None:
    rule = FieldRule(name="note", source="note", target="note", type="text", required=False)
    assert normalize_field(" ", rule, "source") is None


def test_required_blank_is_an_error() -> None:
    rule = FieldRule(name="status", source="s", target="t", type="text")
    with pytest.raises(InvalidValue, match="required"):
        normalize_field("", rule, "source")


def test_negative_zero_equals_zero() -> None:
    assert decimal_value("-0.00", DecimalFormat()) == "0"


def test_unicode_digits_are_not_accepted_as_ascii_amounts() -> None:
    with pytest.raises(InvalidValue):
        decimal_value("\u0661\u0662", DecimalFormat())


def test_high_precision_is_not_rounded() -> None:
    raw = "123456789012345678901234567890.0012300"
    assert decimal_value(raw, DecimalFormat()) == "123456789012345678901234567890.00123"


def test_date_format_is_not_lenient() -> None:
    with pytest.raises(InvalidValue, match="exact"):
        date_value("3/11/2026", "%d/%m/%Y")

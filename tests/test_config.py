from __future__ import annotations

import json

import pytest

from reconciliation.config import load_config
from reconciliation.errors import ConfigurationError


@pytest.fixture
def valid_raw():
    return {
        "version": 1,
        "source": {"delimiter": ","},
        "target": {"delimiter": ";"},
        "key": {"source": "id", "target": "id"},
        "fields": [{"name": "status", "source": "s", "target": "t", "type": "text"}],
    }


def load_raw(tmp_path, raw):
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return load_config(path)


def test_valid_mapping(tmp_path, valid_raw) -> None:
    cfg = load_raw(tmp_path, valid_raw)
    assert cfg.key.source == "id"
    assert cfg.target.delimiter == ";"


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        (lambda d: d.update(version=2), "version"),
        (lambda d: d.update(fields=[]), "non-empty"),
        (lambda d: d.update(unknown=True), "unknown option"),
        (lambda d: d.update(source={"delimiter": "::"}), "delimiter"),
        (lambda d: d.update(key={"source": "id"}), "required option"),
        (lambda d: d["fields"][0].update(type="number"), "type"),
        (lambda d: d["fields"].append(d["fields"][0].copy()), "duplicate"),
    ],
)
def test_invalid_config_rejected(tmp_path, valid_raw, mutation, error) -> None:
    mutation(valid_raw)
    with pytest.raises(ConfigurationError, match=error):
        load_raw(tmp_path, valid_raw)


def test_decimal_format_must_be_explicit(tmp_path, valid_raw) -> None:
    valid_raw["fields"][0]["type"] = "decimal"
    with pytest.raises(ConfigurationError, match="requires both"):
        load_raw(tmp_path, valid_raw)


def test_conflicting_aliases_are_rejected(tmp_path, valid_raw) -> None:
    valid_raw["fields"][0].update(casefold=True, aliases={"PAID": "paid", "paid": "unpaid"})
    with pytest.raises(ConfigurationError, match="conflicting"):
        load_raw(tmp_path, valid_raw)


def test_bad_json_is_a_configuration_error(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{ broken", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="cannot load"):
        load_config(path)


@pytest.mark.parametrize("fmt", ["%Q/%m/%Y", "%m/%Y", "%d/%m/%y", "%d/%m/%Y %H"])
def test_unsupported_date_pattern_rejected(tmp_path, valid_raw, fmt) -> None:
    valid_raw["fields"][0].update(type="date", source_format=fmt, target_format="%Y-%m-%d")
    with pytest.raises(ConfigurationError, match="format|year"):
        load_raw(tmp_path, valid_raw)


def test_unknown_field_parameter_rejected(tmp_path, valid_raw) -> None:
    valid_raw["fields"][0]["normalize_automatically"] = True
    with pytest.raises(ConfigurationError, match="unknown option"):
        load_raw(tmp_path, valid_raw)


def test_invalid_decimal_separator_rejected(tmp_path, valid_raw) -> None:
    valid_raw["fields"][0].update(
        type="decimal",
        source_format={"decimal": ".", "thousands": "."},
        target_format={"decimal": ",", "thousands": "."},
    )
    with pytest.raises(ConfigurationError, match="distinct"):
        load_raw(tmp_path, valid_raw)

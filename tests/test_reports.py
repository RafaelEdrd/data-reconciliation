from __future__ import annotations

import csv
import json
import os

import pytest

from reconciliation.errors import OutputError
from reconciliation.matcher import reconcile
from reconciliation.readers import read_dataset
from reconciliation.reports import spreadsheet_cell, write_reports


def build_result(config, example_paths):
    a = read_dataset(
        example_paths[0], "source", config.source,
        {config.key.source, *(rule.source for rule in config.fields)},
    )
    b = read_dataset(
        example_paths[1], "target", config.target,
        {config.key.target, *(rule.target for rule in config.fields)},
    )
    return a, b, reconcile(a, b, config)


def test_reports_and_fingerprints(config, example_paths, tmp_path) -> None:
    a, b, result = build_result(config, example_paths)
    output = tmp_path / "reports"
    write_reports(output, result, a, b, example_paths[0].parent / "mapping.json", include_matched=True)
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["counts"]["MATCHED"] == 3
    assert len(summary["source"]["sha256"]) == 64
    assert len(summary["target"]["sha256"]) == 64
    assert len(summary["mapping_sha256"]) == 64
    assert summary["blocked_keys"] == 1
    assert (output / "matched.csv").exists()
    with (output / "invalid_records.csv").open(encoding="utf-8-sig", newline="") as stream:
        issues = list(csv.DictReader(stream))
    assert len(issues) == 1
    assert issues[0]["field"] == "amount"


def test_refuse_existing_destination(config, example_paths, tmp_path) -> None:
    a, b, result = build_result(config, example_paths)
    output = tmp_path / "already-there"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("never overwrite", encoding="utf-8")
    with pytest.raises(OutputError, match="already exists"):
        write_reports(output, result, a, b, example_paths[0].parent / "mapping.json")
    assert sentinel.read_text(encoding="utf-8") == "never overwrite"


@pytest.mark.parametrize("cell", ["=2+2", "+cmd", "-cmd", "@SUM(1)", "  =2+2", "\t=1+1"])
def test_formula_prefix_is_neutralized(cell: str) -> None:
    assert spreadsheet_cell(cell).startswith("'")


def test_regular_cells_are_unchanged() -> None:
    assert spreadsheet_cell("00001") == "00001"
    assert spreadsheet_cell("paid") == "paid"
    assert spreadsheet_cell(12) == "12"


def test_reports_create_missing_parent_directories(config, example_paths, tmp_path) -> None:
    a, b, result = build_result(config, example_paths)
    output = tmp_path / "deep" / "reports" / "first-run"
    write_reports(output, result, a, b, example_paths[0].parent / "mapping.json")
    assert (output / "summary.json").is_file()
    assert not (output / "matched.csv").exists()


def test_formulas_are_escaped_in_written_report(config, tmp_path) -> None:
    from reconciliation.reports import DIFFERENCE_COLUMNS, _write_csv

    out = tmp_path / "differences.csv"
    _write_csv(out, DIFFERENCE_COLUMNS, [{"status": "VALUE_MISMATCH", "key": "=1+1"}])
    with out.open(encoding="utf-8-sig", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["key"] == "'=1+1"


def test_symlink_output_is_rejected(config, example_paths, tmp_path) -> None:
    a, b, result = build_result(config, example_paths)
    output = tmp_path / "report-link"
    try:
        output.symlink_to(tmp_path / "nonexistent", target_is_directory=True)
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
            pytest.skip("Windows symlink privilege unavailable")
        raise
    with pytest.raises(OutputError, match="symlink"):
        write_reports(output, result, a, b, example_paths[0].parent / "mapping.json")
    assert output.is_symlink()

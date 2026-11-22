from __future__ import annotations

import pytest

from reconciliation.errors import InputFileError
from reconciliation.models import CsvOptions
from reconciliation.readers import read_dataset


def test_blank_input_rejected(tmp_path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(InputFileError, match="empty"):
        read_dataset(path, "source", CsvOptions(), {"id"})


def test_duplicate_columns_rejected(tmp_path) -> None:
    path = tmp_path / "duplicate.csv"
    path.write_text("id,id\n1,2\n", encoding="utf-8")
    with pytest.raises(InputFileError, match="duplicate"):
        read_dataset(path, "source", CsvOptions(), {"id"})


def test_missing_mapping_column_rejected(tmp_path) -> None:
    path = tmp_path / "missing.csv"
    path.write_text("id,value\n1,2\n", encoding="utf-8")
    with pytest.raises(InputFileError, match="mapped columns"):
        read_dataset(path, "source", CsvOptions(), {"status"})


def test_bad_row_shape_is_preserved_as_issue(tmp_path) -> None:
    path = tmp_path / "wrong.csv"
    path.write_text("id,value\n1,10,extra\n2,20\n", encoding="utf-8")
    data = read_dataset(path, "source", CsvOptions(), {"id", "value"})
    assert data.row_count == 2
    assert data.rows[0].shape_error == "expected 2 columns, got 3"
    assert data.rows[1].shape_error is None


def test_multiline_quoted_value_tracks_csv_end_line(tmp_path) -> None:
    path = tmp_path / "quote.csv"
    path.write_bytes(b'id,value\n1,"line\nline"\n')
    data = read_dataset(path, "source", CsvOptions(), {"id", "value"})
    assert data.rows[0].line == 3
    assert data.rows[0].values["value"] == "line\nline"


def test_bom_and_blank_lines(tmp_path) -> None:
    path = tmp_path / "bom.csv"
    path.write_text("\ufeffid,value\n\n1,yes\n", encoding="utf-8")
    data = read_dataset(path, "source", CsvOptions(), {"id", "value"})
    assert data.row_count == 1
    assert data.rows[0].values["id"] == "1"

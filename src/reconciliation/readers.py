from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from reconciliation.errors import InputFileError
from reconciliation.models import CsvOptions, Dataset, InputRow, Side


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_dataset(path: Path, side: Side, options: CsvOptions, columns: set[str]) -> Dataset:
    if not path.is_file():
        raise InputFileError(f"{side} input does not exist or is not a file: {path}")
    rows: list[InputRow] = []
    try:
        digest = _file_digest(path)
        with path.open("r", encoding=options.encoding, newline="") as stream:
            reader = csv.reader(stream, delimiter=options.delimiter, strict=True)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise InputFileError(f"{side} input is empty: {path}") from exc
            if not header or any(not name.strip() for name in header):
                raise InputFileError(f"{side} input has an empty column name")
            if len(set(header)) != len(header):
                raise InputFileError(f"{side} input contains duplicate column names")
            missing = columns - set(header)
            if missing:
                raise InputFileError(
                    f"{side} input is missing mapped columns: {', '.join(sorted(missing))}"
                )
            for fields in reader:
                if not fields:
                    continue
                if len(fields) != len(header):
                    error = f"expected {len(header)} columns, got {len(fields)}"
                else:
                    error = None
                values = dict(zip(header, fields, strict=False))
                rows.append(InputRow(line=reader.line_num, values=values, shape_error=error))
    except InputFileError:
        raise
    except (OSError, UnicodeError, csv.Error) as exc:
        raise InputFileError(f"cannot read {side} input: {exc}") from exc
    return Dataset(side=side, path=path, digest=digest, row_count=len(rows), rows=tuple(rows))

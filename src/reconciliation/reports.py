from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from reconciliation.errors import OutputError
from reconciliation.models import Dataset, ReconciliationResult

DIFFERENCE_COLUMNS = (
    "status", "key", "source_line", "target_line", "field", "source_value", "target_value",
    "source_normalized", "target_normalized", "detail",
)
ISSUE_COLUMNS = ("side", "line", "key", "field", "raw_value", "reason")
MATCH_COLUMNS = ("key", "source_line", "target_line")


def spreadsheet_cell(value: object) -> str:
    """Neutralize leading spreadsheet formula operators in human-facing CSV reports."""
    result = "" if value is None else str(value)
    if result.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + result
    return result


def _write_csv(path: Path, columns: tuple[str, ...], records: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for item in records:
            writer.writerow({column: spreadsheet_cell(item.get(column)) for column in columns})


def _difference_rows(result: ReconciliationResult) -> list[dict[str, object]]:
    return [
        {column: getattr(item, column) for column in DIFFERENCE_COLUMNS}
        for item in result.differences
    ]


def _issue_rows(result: ReconciliationResult) -> list[dict[str, object]]:
    return [
        {column: getattr(item, column) for column in ISSUE_COLUMNS}
        for item in result.issues
    ]


def _match_rows(result: ReconciliationResult) -> list[dict[str, object]]:
    return [
        {column: getattr(item, column) for column in MATCH_COLUMNS}
        for item in result.matches
    ]


def _metadata(dataset: Dataset) -> dict[str, str | int]:
    return {
        "filename": dataset.path.name,
        "sha256": dataset.digest,
        "rows": dataset.row_count,
    }


def write_reports(
    output: Path,
    result: ReconciliationResult,
    source: Dataset,
    target: Dataset,
    config_path: Path,
    *,
    include_matched: bool = False,
) -> None:
    """Stage output in a private directory; publish only on successful completion."""
    if output.is_symlink():
        raise OutputError(f"output cannot be a symlink: {output}")
    output = output.resolve()
    if output.exists():
        raise OutputError(f"output already exists; choose a new directory: {output}")
    parent = output.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputError(f"cannot create output parent directory: {exc}") from exc

    try:
        config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise OutputError(f"cannot read mapping for report fingerprint: {exc}") from exc

    staging: Path | None = None
    try:
        staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=parent))
        _write_csv(staging / "differences.csv", DIFFERENCE_COLUMNS, _difference_rows(result))
        _write_csv(staging / "invalid_records.csv", ISSUE_COLUMNS, _issue_rows(result))
        if include_matched:
            _write_csv(staging / "matched.csv", MATCH_COLUMNS, _match_rows(result))

        summary = {
            "schema_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": _metadata(source),
            "target": _metadata(target),
            "mapping_sha256": config_hash,
            "counts": result.counts,
            "mismatched_fields": result.mismatched_fields,
            "tolerated_fields": result.tolerated_fields,
            "blocked_keys": len(result.blocked_keys),
            "invalid_issues": len(result.issues),
            "difference_rows": len(result.differences),
            "has_findings": result.has_findings,
        }
        (staging / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        # Refuse to clobber output, including when another process created it meanwhile.
        if output.exists():
            raise OutputError(f"output directory was created concurrently: {output}")
        staging.rename(output)
        staging = None
    except (OSError, UnicodeError, csv.Error) as exc:
        raise OutputError(f"failed writing reports: {exc}") from exc
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging)

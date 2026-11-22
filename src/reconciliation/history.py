"""Summarize previous report manifests without opening source datasets."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from reconciliation.errors import OutputError
from reconciliation.reports import spreadsheet_cell

COLUMNS = ("run", "generated_at", "source_sha256", "target_sha256", "mapping_sha256",
           "source_rows", "target_rows", "matched", "mismatched", "missing_source",
           "missing_target", "blocked_keys", "invalid_records", "duplicate_keys")


def collect(root: Path) -> list[dict[str, str | int]]:
    if not root.is_dir():
        raise OutputError(f"history directory does not exist: {root}")
    records: list[dict[str, str | int]] = []
    for file in sorted(root.rglob("summary.json")):
        try:
            manifest = json.loads(file.read_text(encoding="utf-8"))
            if manifest["schema_version"] != 1:
                raise ValueError("unsupported report schema")
            counts = manifest["counts"]
            records.append({
                "run": file.parent.relative_to(root).as_posix(),
                "generated_at": manifest["generated_at"],
                "source_sha256": manifest["source"]["sha256"],
                "target_sha256": manifest["target"]["sha256"],
                "mapping_sha256": manifest["mapping_sha256"],
                "source_rows": manifest["source"]["rows"],
                "target_rows": manifest["target"]["rows"],
                "matched": counts["MATCHED"],
                "mismatched": counts["MISMATCHED"],
                "missing_source": counts["MISSING_SOURCE"],
                "missing_target": counts["MISSING_TARGET"],
                "blocked_keys": counts["BLOCKED_KEY"],
                "invalid_records": counts["INVALID_RECORD"],
                "duplicate_keys": counts["DUPLICATE_KEY"],
            })
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise OutputError(f"invalid report manifest {file}: {exc}") from exc
    return sorted(records, key=lambda row: (str(row["generated_at"]), str(row["run"])))


def export_history(root: Path, output: Path) -> int:
    records = collect(root)
    if output.exists() or output.is_symlink():
        raise OutputError(f"history output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Open with x so concurrent invocations cannot silently overwrite one another.
    try:
        with output.open("x", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows({key: spreadsheet_cell(value) for key, value in record.items()}
                             for record in records)
    except OSError as exc:
        raise OutputError(f"cannot write history: {exc}") from exc
    return len(records)

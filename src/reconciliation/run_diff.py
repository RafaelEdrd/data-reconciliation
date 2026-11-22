"""Compare report manifests without guessing whether changed populations imply improvement."""
from __future__ import annotations

import json
import re
from pathlib import Path

from reconciliation.errors import OutputError

METRICS = (
    "MATCHED", "MISMATCHED", "MISSING_SOURCE", "MISSING_TARGET", "DUPLICATE_KEY",
    "BLOCKED_KEY", "INVALID_RECORD",
)


def _manifest(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise ValueError("expected a v1 reconciliation manifest")
        for field in ("source", "target"):
            info = raw[field]
            if not isinstance(info["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", info["sha256"]):
                raise ValueError(f"invalid {field} fingerprint")
            if type(info["rows"]) is not int or info["rows"] < 0:
                raise ValueError(f"invalid {field} row count")
        if not isinstance(raw["mapping_sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", raw["mapping_sha256"]):
            raise ValueError("invalid mapping fingerprint")
        counts = raw["counts"]
        if not isinstance(counts, dict) or any(
            type(counts.get(metric)) is not int or counts[metric] < 0 for metric in METRICS
        ):
            raise ValueError("invalid reconciliation counts")
        if not isinstance(raw["generated_at"], str):
            raise ValueError("missing generation timestamp")
        return raw
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        raise OutputError(f"invalid manifest {path}: {exc}") from exc


def compare_runs(before: Path, after: Path, *, allow_mapping_change: bool = False) -> dict:
    left = _manifest(before)
    right = _manifest(after)
    same_mapping = left["mapping_sha256"] == right["mapping_sha256"]
    if not same_mapping and not allow_mapping_change:
        raise OutputError("mapping changed: comparisons require --allow-mapping-change")
    return {
        "schema_version": 1,
        "baseline": {"manifest": str(before), "generated_at": left["generated_at"]},
        "candidate": {"manifest": str(after), "generated_at": right["generated_at"]},
        "comparable_mapping": same_mapping,
        "inputs_changed": {
            side: left[side]["sha256"] != right[side]["sha256"]
            for side in ("source", "target")
        },
        "rows": {
            side: {"before": left[side]["rows"], "after": right[side]["rows"],
                   "delta": right[side]["rows"] - left[side]["rows"]}
            for side in ("source", "target")
        },
        "counts": {
            metric: {"before": left["counts"][metric], "after": right["counts"][metric],
                     "delta": right["counts"][metric] - left["counts"][metric]}
            for metric in METRICS
        },
        "interpretation": "Deltas describe changes, not causal improvement. Review population and mapping.",
    }


def write_comparison(before: Path, after: Path, output: Path, *, allow_mapping_change: bool = False) -> dict:
    report = compare_runs(before, after, allow_mapping_change=allow_mapping_change)
    if output.is_symlink():
        raise OutputError("comparison output must not be a symlink")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except FileExistsError as exc:
        raise OutputError(f"comparison output already exists: {output}") from exc
    except OSError as exc:
        raise OutputError(f"cannot write comparison: {exc}") from exc
    return report

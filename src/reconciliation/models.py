from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

DataType = Literal["text", "decimal", "date"]
Side = Literal["source", "target"]


@dataclass(frozen=True)
class CsvOptions:
    delimiter: str = ","
    encoding: str = "utf-8-sig"


@dataclass(frozen=True)
class KeyPart:
    source: str
    target: str


@dataclass(frozen=True)
class KeyRule:
    source: str
    target: str
    strip: bool = True
    casefold: bool = False
    parts: tuple[KeyPart, ...] = ()

    def columns(self, side: Side) -> tuple[str, ...]:
        if self.parts:
            return tuple(getattr(part, side) for part in self.parts)
        return (getattr(self, side),)


@dataclass(frozen=True)
class DecimalFormat:
    decimal: str = "."
    thousands: str = ""


@dataclass(frozen=True)
class FieldRule:
    name: str
    source: str
    target: str
    type: DataType
    required: bool = True
    category: Literal["value", "status"] = "value"
    strip: bool = True
    casefold: bool = False
    collapse_whitespace: bool = False
    aliases: dict[str, str] = field(default_factory=dict)
    source_format: DecimalFormat | str | None = None
    target_format: DecimalFormat | str | None = None
    absolute_tolerance: str | None = None


@dataclass(frozen=True)
class MappingConfig:
    source: CsvOptions
    target: CsvOptions
    key: KeyRule
    fields: tuple[FieldRule, ...]


@dataclass(frozen=True)
class InputRow:
    line: int
    values: dict[str, str]
    shape_error: str | None = None


@dataclass(frozen=True)
class Dataset:
    side: Side
    path: Path
    digest: str
    row_count: int
    rows: tuple[InputRow, ...]


@dataclass(frozen=True)
class Record:
    key: str
    raw_key: str
    line: int
    values: dict[str, str | None]
    raw_values: dict[str, str]


@dataclass(frozen=True)
class QualityIssue:
    side: Side
    line: int
    key: str
    field: str
    raw_value: str
    reason: str


@dataclass(frozen=True)
class Difference:
    status: str
    key: str
    source_line: int | None = None
    target_line: int | None = None
    field: str = ""
    source_value: str = ""
    target_value: str = ""
    source_normalized: str = ""
    target_normalized: str = ""
    detail: str = ""


@dataclass(frozen=True)
class Match:
    key: str
    source_line: int
    target_line: int


@dataclass
class ReconciliationResult:
    counts: dict[str, int]
    differences: list[Difference]
    issues: list[QualityIssue]
    matches: list[Match]
    blocked_keys: set[str]
    mismatched_fields: dict[str, int]
    tolerated_fields: dict[str, int] = field(default_factory=dict)

    @property
    def has_findings(self) -> bool:
        return bool(self.differences or self.issues or self.blocked_keys)

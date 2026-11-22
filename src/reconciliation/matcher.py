from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
import json

from reconciliation.errors import InvalidValue
from reconciliation.models import (
    Dataset, Difference, MappingConfig, Match, QualityIssue, ReconciliationResult, Record, Side,
)
from reconciliation.normalize import normalize_field, normalize_key


def _index(
    dataset: Dataset, config: MappingConfig
) -> tuple[dict[str, list[Record]], list[QualityIssue], set[str]]:
    side: Side = dataset.side
    key_columns = config.key.columns(side)
    index: dict[str, list[Record]] = defaultdict(list)
    issues: list[QualityIssue] = []
    blocked: set[str] = set()

    for row in dataset.rows:
        raw_parts = tuple(row.values.get(column, "") for column in key_columns)
        normalized_parts = tuple(normalize_key(value, strip=config.key.strip, casefold=config.key.casefold)
                                 for value in raw_parts)
        key = (normalized_parts[0] if len(normalized_parts) == 1 else
               json.dumps(normalized_parts, ensure_ascii=False, separators=(",", ":")))
        raw_key = raw_parts[0] if len(raw_parts) == 1 else json.dumps(raw_parts, ensure_ascii=False)
        errors: list[QualityIssue] = []
        for column, raw, value in zip(key_columns, raw_parts, normalized_parts, strict=True):
            if not value:
                errors.append(QualityIssue(side, row.line, key, column, raw, "empty key component"))
        if row.shape_error:
            errors.append(QualityIssue(side, row.line, key, "__row__", "", row.shape_error))

        normalized: dict[str, str | None] = {}
        raw_values: dict[str, str] = {}
        for rule in config.fields:
            column = rule.source if side == "source" else rule.target
            raw = row.values.get(column, "")
            raw_values[rule.name] = raw
            if row.shape_error:
                continue
            try:
                normalized[rule.name] = normalize_field(raw, rule, side)
            except InvalidValue as exc:
                errors.append(QualityIssue(side, row.line, key, rule.name, raw, str(exc)))

        if errors:
            issues.extend(errors)
            if key:
                blocked.add(key)
            continue
        index[key].append(Record(key, raw_key, row.line, normalized, raw_values))

    return index, issues, blocked


def reconcile(source: Dataset, target: Dataset, config: MappingConfig) -> ReconciliationResult:
    left, left_issues, left_blocked = _index(source, config)
    right, right_issues, right_blocked = _index(target, config)
    blocked_keys = left_blocked | right_blocked
    issues = sorted(left_issues + right_issues, key=lambda item: (item.side, item.line, item.field))
    counts: dict[str, int] = {
        "MATCHED": 0,
        "MISMATCHED": 0,
        "MISSING_SOURCE": 0,
        "MISSING_TARGET": 0,
        "DUPLICATE_KEY": 0,
        "BLOCKED_KEY": len(blocked_keys),
        "INVALID_RECORD": len({(issue.side, issue.line) for issue in issues}),
    }
    differences: list[Difference] = []
    matches: list[Match] = []
    mismatched_fields: Counter[str] = Counter()
    tolerated_fields: Counter[str] = Counter()

    for key in sorted(left.keys() | right.keys()):
        if key in blocked_keys:
            continue
        source_records = left.get(key, [])
        target_records = right.get(key, [])
        if len(source_records) > 1 or len(target_records) > 1:
            counts["DUPLICATE_KEY"] += 1
            for record in source_records:
                differences.append(Difference(
                    "DUPLICATE_KEY", key, source_line=record.line,
                    detail=f"source has {len(source_records)} records for this key",
                ))
            for record in target_records:
                differences.append(Difference(
                    "DUPLICATE_KEY", key, target_line=record.line,
                    detail=f"target has {len(target_records)} records for this key",
                ))
            continue
        if not source_records:
            counts["MISSING_SOURCE"] += 1
            differences.append(Difference(
                "MISSING_SOURCE", key, target_line=target_records[0].line,
                detail="key only exists in target",
            ))
            continue
        if not target_records:
            counts["MISSING_TARGET"] += 1
            differences.append(Difference(
                "MISSING_TARGET", key, source_line=source_records[0].line,
                detail="key only exists in source",
            ))
            continue

        source_record = source_records[0]
        target_record = target_records[0]
        unequal = False
        for rule in config.fields:
            a = source_record.values[rule.name]
            b = target_record.values[rule.name]
            if a == b:
                continue
            if rule.type == "decimal" and a is not None and b is not None and rule.absolute_tolerance is not None:
                if abs(Decimal(a) - Decimal(b)) <= Decimal(rule.absolute_tolerance):
                    tolerated_fields[rule.name] += 1
                    continue
            unequal = True
            mismatched_fields[rule.name] += 1
            differences.append(Difference(
                status="STATUS_MISMATCH" if rule.category == "status" else "VALUE_MISMATCH",
                key=key, source_line=source_record.line, target_line=target_record.line,
                field=rule.name, source_value=source_record.raw_values[rule.name],
                target_value=target_record.raw_values[rule.name],
                source_normalized=a or "", target_normalized=b or "",
            ))
        if unequal:
            counts["MISMATCHED"] += 1
        else:
            counts["MATCHED"] += 1
            matches.append(Match(key, source_record.line, target_record.line))

    return ReconciliationResult(
        counts=counts,
        differences=differences,
        issues=issues,
        matches=matches,
        blocked_keys=blocked_keys,
        mismatched_fields=dict(sorted(mismatched_fields.items())),
        tolerated_fields=dict(sorted(tolerated_fields.items())),
    )

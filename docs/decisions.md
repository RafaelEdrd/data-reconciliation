# Engineering decisions

## v0.1 scope

The application compares two flat CSV exports using a single configured key. It does not implement fuzzy matching, database connections, heuristics for customer names or a web UI.

## Runtime dependencies

Only the Python standard library is used at runtime. `argparse`, `csv`, `Decimal`, `json` and `hashlib` cover the current problem. A dataframe dependency would add installation cost without improving this workload.

## Deterministic matching

Keys are compared exactly after explicitly configured whitespace and case normalization. Leading zeros are preserved. A key seen more than once on either side is not matched arbitrarily.

Invalid records with a valid key block that key on both sides. Otherwise one malformed amount might incorrectly become a missing order. A key without a usable identifier is listed only as a data-quality issue.

## Numeric and date values

Numbers are parsed according to a configured decimal and thousands separator, with strict grouping. `Decimal` avoids binary floating-point artefacts, and the tool does not round money to hide mismatches. Dates are parsed with explicit source and target formats.

## Audit and error handling

Reports contain a summary, detailed differences and invalid records. Each summary includes SHA-256 digests of the input exports and mapping. Physical CSV line numbers refer to the ending line of each record when multiline quoted fields are present.

An output directory must not exist. Files are prepared in a temporary sibling directory and only published when complete, reducing partial reports after errors. A failed validation returns exit code 2; findings can produce exit code 1 when requested.

## Scaling boundary

For the current version, records are indexed in memory for linear expected matching cost, plus sorting of keys for stable reporting. Large-file streaming, composite identifiers and database-backed reconciliation should only be introduced when real constraints justify them.

## Public repository boundary

All examples are fictional. This repository contains no employer data, rules, code, credentials or screenshots. Lack of a distribution license is intentional until an explicit license is selected.

## v1: composite identity and tolerated monetary differences

Composite identifiers use a JSON tuple instead of string concatenation. This avoids ambiguity for values containing separators. Exact comparisons remain the default; a configured absolute tolerance is opt-in per decimal field and evaluated with `Decimal`. Tolerated fields are counted separately so apparent agreement is not concealed. Historical indexes read only the manifest metadata; data files are not required.

**Known trade-off:** in-memory indexes favor a simple auditable implementation over premature infrastructure. A disk-backed external sort or SQLite index is the next option once dataset size/benchmark warrants it.

## v1.1 RC1: boundaries

Run comparison is manifest-only, so changes in aggregates cannot be assumed causal. Input digests and mapping fingerprints are first-class audit evidence. Disk-backed indexing remains deferred until benchmark evidence justifies a second engine.

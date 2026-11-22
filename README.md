# Data Reconciliation

A deterministic CSV reconciliation tool built with Python.

Data Reconciliation compares exports from independent systems using explicit field mappings, data-quality rules and reproducible reports. It is designed for operational reconciliation, where differences must be explainable rather than silently normalized away.

> Status: 1.1.0 RC1. This project is a technical demonstration and has not been certified for production use.

## Why this project exists

Comparing exports from different systems involves more than checking whether rows match.

Identifiers may have different column names, dates and monetary values may use different formats, and duplicated or malformed records can produce misleading results.

This project separates configuration, validation, normalization, matching and reporting so that reconciliation decisions remain explicit and inspectable.

## Technology

- Python 3.11 or newer
- Python standard library for runtime operations
- pytest for automated tests
- Ruff for static linting
- GitHub Actions for continuous integration

No pandas dependency or database server is required.

## Architecture

The application separates responsibilities across modules:

| Module | Responsibility |
| --- | --- |
| `cli.py` | Command-line interface |
| `config.py` | Mapping configuration |
| `readers.py` | CSV ingestion and input fingerprints |
| `normalize.py` | Field and identifier normalization |
| `matcher.py` | Deterministic reconciliation |
| `models.py` | Domain data structures |
| `reports.py` | Report generation and output protection |
| `history.py` | Historical report indexing |
| `run_diff.py` | Comparison of report manifests |
| `errors.py` | Domain-specific error types |

## Capabilities

### Explicit field mapping

Source and target exports can have different column names, delimiters, encodings and value formats.

The mapping is defined in JSON rather than embedded in the reconciliation logic.

### Deterministic matching

Records are matched by configured identifiers, including composite keys.

Leading zeros are preserved. Composite identifiers use structured tuple serialization to avoid ambiguous string concatenation.

The application does not perform fuzzy matching or infer that similar names represent the same entity.

### Data-quality controls

Invalid values, missing identifiers, malformed rows and duplicate keys are reported explicitly.

Records associated with blocked identifiers are not arbitrarily matched.

### Numeric comparison

Monetary values are parsed using `Decimal`, with configurable decimal and thousands separators.

Absolute tolerance is opt-in. Differences accepted within tolerance remain separately measurable.

### Date normalization

Date fields are interpreted through explicit formats configured for each source.

### Auditable output

Reconciliation reports include differences, invalid records and a summary manifest.

The manifest contains SHA-256 fingerprints of the input files and mapping configuration.

Report generation uses a temporary staging directory before publishing the completed output.

### Historical analysis

The CLI provides commands for building an index of previous report manifests and comparing reconciliation runs.

These operations support historical inspection. Differences between runs do not, by themselves, establish causality.

## Installation

Clone the repository:

```bash
git clone https://github.com/RafaelEdrd/data-reconciliation.git
cd data-reconciliation
```

Create and activate a Python virtual environment:

```bash
python -m venv .venv
```

Install the project:

```bash
python -m pip install -e .
```

For development and testing:

```bash
python -m pip install -e ".[dev]"
```

The editable installation exposes the `reconcile` command.

## Quick Start

Validate the example mapping:

```bash
reconcile validate --config examples/mapping.json
```

Compare the synthetic example exports:

```bash
reconcile compare \
  --source examples/source_a.csv \
  --target examples/source_b.csv \
  --config examples/mapping.json \
  --output reports/example
```

The output directory must not already exist.

Include matched records in the reports:

```bash
reconcile compare \
  --source examples/source_a.csv \
  --target examples/source_b.csv \
  --config examples/mapping.json \
  --output reports/with-matches \
  --include-matched
```

To return a nonzero status when findings exist, add:

```text
--fail-on-findings
```

## CLI Commands

| Command | Purpose |
| --- | --- |
| `reconcile validate` | Validate mapping configuration |
| `reconcile compare` | Compare two exports and generate reports |
| `reconcile history` | Index previous report manifests |
| `reconcile compare-runs` | Compare two reconciliation manifests |

For the current command-line options, use:

```bash
reconcile --help
reconcile history --help
reconcile compare-runs --help
```

## Reconciliation Results

The matcher tracks categories including:

- `MATCHED`
- `MISMATCHED`
- `MISSING_SOURCE`
- `MISSING_TARGET`
- `DUPLICATE_KEY`
- `BLOCKED_KEY`
- `INVALID_RECORD`

Difference records preserve the relevant identifiers, source and target line numbers, field names and original values.

## Configuration

See `examples/mapping.json` for a complete example.

The configuration supports source/target column mapping, normalization rules, field types, status aliases, date formats and decimal formatting.

Examples use synthetic information. They are not exports of real customers or business operations.

## Testing

Run static lint checks:

```bash
python -m ruff check .
```

Run the automated suite:

```bash
python -m pytest -q -ra
```

The GitHub Actions workflow runs tests on Python 3.11 and 3.13.

Local Windows validation on Python 3.14.3 returned 77 passing tests and one skipped test because the operating system did not permit symlink creation.

The Linux CI result must be checked separately.

## Security and Data Handling

The application is intended for authorized datasets.

Reconciliation outputs can contain original input values and must be protected according to the sensitivity of the source information.

The implementation includes:

- Detection of invalid and duplicate identifiers
- Input and configuration SHA-256 fingerprints
- Spreadsheet formula neutralization in exported CSVs
- Refusal to overwrite an existing output directory
- Rejection of symbolic-link output destinations
- Staged report generation

Generated reports are excluded from version control by the provided `.gitignore`.

See [SECURITY.md](SECURITY.md) for additional security guidance.

## Design Boundaries

The current matcher uses in-memory indexes.

This keeps reconciliation logic straightforward and auditable for appropriately sized datasets, but memory consumption grows with input volume.

Database-backed processing, external sorting and distributed execution are outside the present scope.

The project does not implement fuzzy matching, a graphical interface or direct database integrations.

## Documentation

- [Engineering decisions](docs/decisions.md)
- [Security](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [Example mapping](examples/mapping.json)

## License

No open-source license has been assigned. All rights are reserved unless a license is added.

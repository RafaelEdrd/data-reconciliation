# Security notes

This tool operates on local CSV files. It does not send data over the network.

- Input files are considered untrusted; column shapes, headers, numbers and dates are validated.
- Reports may contain source data. Keep report directories private and do not commit them.
- CSV report cells that look like spreadsheet formulas are prefixed with an apostrophe. This is a risk reduction, not a guarantee across all spreadsheet applications or save/reopen workflows.
- The tool does not execute content from input data or mapping files.
- No overwrite flag is provided. An existing output directory causes the run to fail.
- Source hashes allow operators to identify exactly which exports were processed.

Do not use production customer exports in public issues, demonstrations or test fixtures.

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from reconciliation import __version__
from reconciliation.config import load_config
from reconciliation.history import export_history
from reconciliation.run_diff import write_comparison
from reconciliation.errors import ReconciliationError
from reconciliation.matcher import reconcile
from reconciliation.models import MappingConfig
from reconciliation.readers import read_dataset
from reconciliation.reports import write_reports


def _columns(config: MappingConfig, side: str) -> set[str]:
    if side == "source":
        return {*config.key.columns("source"), *(field.source for field in config.fields)}
    return {*config.key.columns("target"), *(field.target for field in config.fields)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reconcile",
        description="Compare two CSV exports using an explicit field mapping.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    actions = parser.add_subparsers(dest="action", required=True)

    compare = actions.add_parser("compare", help="produce reconciliation and data-quality reports")
    compare.add_argument("--source", type=Path, required=True, help="source CSV file")
    compare.add_argument("--target", type=Path, required=True, help="target CSV file")
    compare.add_argument("--config", type=Path, required=True, help="JSON comparison mapping")
    compare.add_argument("--output", type=Path, required=True, help="new report directory")
    compare.add_argument("--include-matched", action="store_true", help="export matched keys too")
    compare.add_argument(
        "--fail-on-findings", action="store_true",
        help="return exit status 1 when differences or quality issues are found",
    )

    validate = actions.add_parser("validate", help="validate a JSON comparison mapping")
    validate.add_argument("--config", type=Path, required=True, help="JSON comparison mapping")
    history = actions.add_parser("history", help="build an audit index from previous report manifests")
    history.add_argument("--root", type=Path, required=True, help="directory containing report runs")
    history.add_argument("--output", type=Path, required=True, help="new CSV index path")
    diff = actions.add_parser("compare-runs", help="compare two existing report manifests")
    diff.add_argument("--before", type=Path, required=True, help="baseline summary.json")
    diff.add_argument("--after", type=Path, required=True, help="candidate summary.json")
    diff.add_argument("--output", type=Path, required=True, help="new comparison JSON path")
    diff.add_argument("--allow-mapping-change", action="store_true",
                      help="report deltas even if the comparison definitions differ")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.action == "history":
            runs = export_history(args.root, args.output)
            print(f"Indexed {runs} report run(s): {args.output}")
            return 0
        if args.action == "compare-runs":
            report = write_comparison(args.before, args.after, args.output,
                                      allow_mapping_change=args.allow_mapping_change)
            print(f"Report comparison: {args.output} (mapping comparable: {report['comparable_mapping']})")
            return 0
        config = load_config(args.config)
        if args.action == "validate":
            print(f"Mapping valid: {len(config.fields)} field(s)")
            return 0
        source = read_dataset(args.source, "source", config.source, _columns(config, "source"))
        target = read_dataset(args.target, "target", config.target, _columns(config, "target"))
        result = reconcile(source, target, config)
        write_reports(
            args.output, result, source, target, args.config,
            include_matched=args.include_matched,
        )
    except ReconciliationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"Source rows: {source.row_count} | Target rows: {target.row_count}")
    for status, value in result.counts.items():
        print(f"{status:17} {value}")
    print(f"Reports: {args.output.resolve()}")
    return 1 if args.fail_on_findings and result.has_findings else 0

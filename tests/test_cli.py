from __future__ import annotations

import json

from reconciliation.cli import main


def test_validate_mapping(config, example_paths, capsys) -> None:
    assert main(["validate", "--config", str(example_paths[0].parent / "mapping.json")]) == 0
    assert "Mapping valid" in capsys.readouterr().out


def test_compare_exit_status_and_output(example_paths, tmp_path) -> None:
    config_path = example_paths[0].parent / "mapping.json"
    output = tmp_path / "reports"
    argv = [
        "compare", "--source", str(example_paths[0]), "--target", str(example_paths[1]),
        "--config", str(config_path), "--output", str(output), "--fail-on-findings",
    ]
    assert main(argv) == 1
    assert json.loads((output / "summary.json").read_text())["has_findings"] is True
    assert main(argv) == 2  # an existing report directory is never overwritten


def test_missing_input_fails_without_report(example_paths, tmp_path, capsys) -> None:
    output = tmp_path / "missing-report"
    assert main([
        "compare", "--source", str(tmp_path / "not-found.csv"),
        "--target", str(example_paths[1]),
        "--config", str(example_paths[0].parent / "mapping.json"),
        "--output", str(output),
    ]) == 2
    assert not output.exists()
    assert "error:" in capsys.readouterr().err


def test_compare_without_findings_returns_zero(example_paths, tmp_path) -> None:
    # Same logical data in different locale formats; source and target are still different files.
    source = tmp_path / "source.csv"
    target = tmp_path / "target.csv"
    source.write_text("order_id,amount,status,created_at\n0001,1.00,paid,2026-11-01\n", encoding="utf-8")
    target.write_text("pedido;valor;situacao;data\n0001;1,00;pago;01/11/2026\n", encoding="utf-8")
    mapping = example_paths[0].parent / "mapping.json"
    assert main([
        "compare", "--source", str(source), "--target", str(target),
        "--config", str(mapping), "--output", str(tmp_path / "reports"), "--fail-on-findings",
    ]) == 0


def test_compare_runs_command_creates_new_audit_delta(example_paths, tmp_path):
    mapping = example_paths[0].parent / 'mapping.json'
    before = tmp_path / 'first'
    after = tmp_path / 'second'
    for output in (before, after):
        assert main(['compare', '--source', str(example_paths[0]), '--target',
                     str(example_paths[1]), '--config', str(mapping),
                     '--output', str(output)]) == 0
    delta = tmp_path / 'comparison.json'
    assert main(['compare-runs', '--before', str(before / 'summary.json'), '--after',
                 str(after / 'summary.json'), '--output', str(delta)]) == 0
    assert json.loads(delta.read_text())['counts']['MISMATCHED']['delta'] == 0
    assert main(['compare-runs', '--before', str(before / 'summary.json'), '--after',
                 str(after / 'summary.json'), '--output', str(delta)]) == 2

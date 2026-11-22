from __future__ import annotations

from pathlib import Path

from reconciliation.matcher import reconcile
from reconciliation.readers import read_dataset


def load(source_path: Path, target_path: Path, cfg):
    a = read_dataset(
        source_path, "source", cfg.source,
        {cfg.key.source, *(field.source for field in cfg.fields)},
    )
    b = read_dataset(
        target_path, "target", cfg.target,
        {cfg.key.target, *(field.target for field in cfg.fields)},
    )
    return reconcile(a, b, cfg)


def test_example_counts(config, example_paths) -> None:
    result = load(*example_paths, config)
    assert result.counts == {
        "MATCHED": 3, "MISMATCHED": 2, "MISSING_SOURCE": 1, "MISSING_TARGET": 1,
        "DUPLICATE_KEY": 1, "BLOCKED_KEY": 1, "INVALID_RECORD": 1,
    }
    assert result.blocked_keys == {"0007"}
    assert result.mismatched_fields == {"amount": 1, "status": 1}
    assert [item.key for item in result.matches] == ["0001", "0004", "0005"]


def test_invalid_source_does_not_create_false_missing(config, tmp_path) -> None:
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("order_id,amount,status,created_at\n001,bad,paid,2026-11-01\n", encoding="utf-8")
    b.write_text("pedido;valor;situacao;data\n001;10,00;pago;01/11/2026\n", encoding="utf-8")
    result = load(a, b, config)
    assert result.counts["BLOCKED_KEY"] == 1
    assert result.counts["MISSING_SOURCE"] == 0
    assert result.counts["MISSING_TARGET"] == 0
    assert result.counts["INVALID_RECORD"] == 1


def test_duplicate_source_does_not_choose_arbitrary_record(config, example_paths) -> None:
    result = load(*example_paths, config)
    rows = [item for item in result.differences if item.status == "DUPLICATE_KEY"]
    assert len(rows) == 3
    assert [item.source_line for item in rows if item.source_line] == [7, 8]


def test_invalid_key_cannot_create_a_match(config, tmp_path) -> None:
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("order_id,amount,status,created_at\n,10,paid,2026-11-01\n", encoding="utf-8")
    b.write_text("pedido;valor;situacao;data\n;10,00;pago;01/11/2026\n", encoding="utf-8")
    result = load(a, b, config)
    assert result.counts["MATCHED"] == 0
    assert result.counts["INVALID_RECORD"] == 2
    assert result.counts["BLOCKED_KEY"] == 0


def test_empty_data_files_are_valid(config, tmp_path) -> None:
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("order_id,amount,status,created_at\n", encoding="utf-8")
    b.write_text("pedido;valor;situacao;data\n", encoding="utf-8")
    result = load(a, b, config)
    assert result.has_findings is False
    assert result.counts["MATCHED"] == 0


def test_mismatch_has_both_original_and_normalized_values(config, example_paths) -> None:
    result = load(*example_paths, config)
    amount = next(item for item in result.differences if item.field == "amount")
    assert amount.key == "0003"
    assert amount.source_value == "875.25"
    assert amount.target_value == "875,75"
    assert amount.source_normalized == "875.25"
    assert amount.target_normalized == "875.75"


def test_malformed_target_blocks_source_key(config, tmp_path) -> None:
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("order_id,amount,status,created_at\n001,10.00,paid,2026-11-01\n", encoding="utf-8")
    b.write_text("pedido;valor;situacao;data\n001;10,00;pago;31/02/2026\n", encoding="utf-8")
    result = load(a, b, config)
    assert result.counts["BLOCKED_KEY"] == 1
    assert result.counts["MISSING_TARGET"] == 0
    assert result.counts["MATCHED"] == 0
    assert result.issues[0].field == "date"


def test_shape_error_blocks_key_and_is_not_silent(config, tmp_path) -> None:
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("order_id,amount,status,created_at\n001,10.00,paid,2026-11-01,EXTRA\n", encoding="utf-8")
    b.write_text("pedido;valor;situacao;data\n001;10,00;pago;01/11/2026\n", encoding="utf-8")
    result = load(a, b, config)
    assert result.counts["BLOCKED_KEY"] == 1
    assert result.issues[0].field == "__row__"


def test_duplicate_on_both_sides_is_still_one_ambiguous_key(config, tmp_path) -> None:
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("order_id,amount,status,created_at\n001,10.00,paid,2026-11-01\n001,10.00,paid,2026-11-01\n", encoding="utf-8")
    b.write_text("pedido;valor;situacao;data\n001;10,00;pago;01/11/2026\n001;10,00;pago;01/11/2026\n", encoding="utf-8")
    result = load(a, b, config)
    assert result.counts["DUPLICATE_KEY"] == 1
    assert len(result.differences) == 4
    assert result.counts["MATCHED"] == 0

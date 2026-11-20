"""Testes unitários de `synth.load` e da CLI (Req. 2.9, 2.10)."""
from __future__ import annotations

from datetime import date

from platform_lib import synth
from platform_lib.synth import (
    DEST_OBJECT,
    DEST_SQL,
    GenParams,
    InMemoryObjectSink,
    InMemorySqlSink,
    NoiseParams,
    generate,
    load,
)

PARAMS = GenParams(
    seed=7, n_customers=20, n_products=5, n_stores=3,
    start=date(2024, 1, 1), end=date(2024, 3, 1),
    noise=NoiseParams(dup_pct=0.1, null_pct=0.1, bad_date_pct=0.1),
)


def test_load_success_counts_and_rerun_is_idempotent():
    ds = generate(PARAMS)
    sql, obj = InMemorySqlSink(), InMemoryObjectSink()
    first = load(ds, sql, obj)
    snapshot = ({e: dict(t) for e, t in sql.tables.items()}, dict(obj.files))
    second = load(ds, sql, obj)
    assert first.success and second.success and first.counts == second.counts
    assert snapshot == ({e: dict(t) for e, t in sql.tables.items()}, dict(obj.files))
    assert set(sql.tables) == set(synth.SQL_ENTITIES)
    assert len(obj.files) == 1
    for entity in synth.SQL_ENTITIES:
        assert first.counts[entity] == len(sql.tables[entity])


def test_validation_failure_writes_nothing_and_names_destination():
    ds = generate(PARAMS)
    sql, obj = InMemorySqlSink(), InMemoryObjectSink(fail_validate=True)
    report = load(ds, sql, obj)
    assert not report.success and report.failed_destination == DEST_OBJECT
    assert sql.tables == {} and obj.files == {}
    report = load(ds, InMemorySqlSink(fail_validate=True), InMemoryObjectSink())
    assert report.failed_destination == DEST_SQL


def test_write_failure_is_total_failure():
    ds = generate(PARAMS)
    report = load(ds, InMemorySqlSink(fail_entity="vendas"), InMemoryObjectSink())
    assert not report.success and report.failed_destination == DEST_SQL
    report = load(ds, InMemorySqlSink(), InMemoryObjectSink(fail_put=True))
    assert not report.success and report.failed_destination == DEST_OBJECT


def test_cli_invalid_param_exit_code(tmp_path, capsys):
    env = tmp_path / ".env"
    env.write_text("SYNTH_SEED=1\n", encoding="utf-8")
    code = synth.main(["--env-file", str(env), "--n-customers", "0", "--n-products", "1",
                       "--n-stores", "1", "--start", "2024-01-01", "--end", "2024-01-02"])
    assert code == 2
    assert "n_customers" in capsys.readouterr().err


def test_generate_unchanged_by_load():
    assert generate(PARAMS).tables == generate(PARAMS).tables

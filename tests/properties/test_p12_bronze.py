# Feature: fabric-data-ai-platform, Property 12: Bronze preserva dados, anexa metadados e é idempotente
"""**Validates: Requirements 3.1, 3.3, 3.7, 4.1**"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from src.platform_lib.ingestion import (
    META_RUN,
    META_SRC,
    META_TS,
    ingest_entity,
    merge_bronze,
)
from tests.strategies_ingest_bronze import now_values, run_ids, source_rows, source_systems

META = {META_TS, META_RUN, META_SRC}


def _canon(rows):
    return sorted(rows, key=lambda r: r["id"])


@settings(max_examples=100)
@given(rows=source_rows(), run_id=run_ids, source=source_systems, now=now_values)
def test_bronze_preserva_dados_e_anexa_metadados(rows, run_id, source, now):
    out = ingest_entity(
        [],
        rows,
        key="id",
        watermark_col="id",
        previous_watermark=None,
        run_id=run_id,
        source=source,
        now_utc=now,
    )
    assert out.ok
    assert out.written == len(rows)  # lidos == gravados
    assert len(out.bronze) == len(rows)
    by_id = {r["id"]: r for r in out.bronze}
    for src in rows:
        b = by_id[src["id"]]
        assert {k: v for k, v in b.items() if k not in META} == src
        assert b[META_TS] is not None
        assert b[META_RUN] == run_id
        assert b[META_SRC] == source


@settings(max_examples=100)
@given(rows=source_rows(), run_id=run_ids, source=source_systems, now=now_values)
def test_merge_do_mesmo_intervalo_duas_vezes_e_idempotente(rows, run_id, source, now):
    kwargs = dict(
        key="id",
        watermark_col="id",
        previous_watermark=None,
        run_id=run_id,
        source=source,
        now_utc=now,
    )
    first = ingest_entity([], rows, **kwargs)
    second = ingest_entity(first.bronze, rows, **kwargs)
    assert _canon(second.bronze) == _canon(first.bronze)
    keys = [r["id"] for r in second.bronze]
    assert len(keys) == len(set(keys))

    # merge_bronze direto também é idempotente
    m1 = merge_bronze([], first.bronze, "id")
    m2 = merge_bronze(m1, first.bronze, "id")
    assert _canon(m2) == _canon(m1)
    assert len({r["id"] for r in m2}) == len(m2)


@settings(max_examples=100)
@given(rows=source_rows(), data=st.data())
def test_merge_com_duplicados_no_lote_nao_gera_duplicata(rows, data):
    dup = rows + data.draw(st.permutations(rows))
    merged = merge_bronze([], dup, "id")
    assert len({r["id"] for r in merged}) == len(merged) == len(rows)

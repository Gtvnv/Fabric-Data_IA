"""Property 11: Marca d'água só avança em sucesso.

**Validates: Requirements 3.5, 3.6**
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from platform_lib.ingestion import ingest_entity, next_watermark, select_incremental
from tests.strategies_ingest_mark import (
    WM_COL,
    bronze_tables,
    failure_kinds,
    optional_watermarks,
    source_rows,
)

NOW = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)


def _ingest(bronze, rows, prev, *, run_id="run-1", source="erp", now=NOW):
    return ingest_entity(
        bronze,
        rows,
        key="id",
        watermark_col=WM_COL,
        previous_watermark=prev,
        run_id=run_id,
        source=source,
        now_utc=now,
    )


# Feature: fabric-data-ai-platform, Property 11: Marca d'água só avança em sucesso
@settings(max_examples=100)
@given(rows=source_rows(), prev=optional_watermarks)
def test_next_watermark_is_max_or_previous(rows, prev):
    written = select_incremental(rows, WM_COL, prev)
    result = next_watermark(written, WM_COL, prev)
    values = [r[WM_COL] for r in written if r[WM_COL] is not None]
    if values:
        assert result == max(values)
    else:
        assert result == prev


# Feature: fabric-data-ai-platform, Property 11: Marca d'água só avança em sucesso
@settings(max_examples=100)
@given(bronze=bronze_tables(), rows=source_rows(), prev=optional_watermarks)
def test_success_advances_watermark_to_max_written(bronze, rows, prev):
    out = _ingest(bronze, rows, prev)
    assert out.ok
    written = select_incremental(rows, WM_COL, prev)
    values = [r[WM_COL] for r in written if r[WM_COL] is not None]
    assert out.watermark == (max(values) if values else prev)
    if prev is not None:
        assert out.watermark >= prev


# Feature: fabric-data-ai-platform, Property 11: Marca d'água só avança em sucesso
@settings(max_examples=100)
@given(
    bronze=bronze_tables(),
    rows=source_rows(),
    prev=optional_watermarks,
    kind=failure_kinds,
)
def test_failure_keeps_watermark_and_bronze(bronze, rows, prev, kind):
    # Garante ao menos uma linha para que a falha ocorra no enriquecimento.
    rows = rows + [{"id": "ZZ-EXTRA", WM_COL: (prev or 0) + 1, "valor": 0}]
    snapshot = copy.deepcopy(bronze)
    kwargs = {}
    if kind == "run_id_vazio":
        kwargs["run_id"] = ""
    elif kind == "source_vazio":
        kwargs["source"] = ""
    else:
        kwargs["now"] = datetime(2024, 1, 1, 12, 0)  # sem fuso
    out = _ingest(bronze, rows, prev, **kwargs)
    assert not out.ok
    assert out.error is not None
    assert out.watermark == prev
    assert out.bronze == snapshot
    assert bronze == snapshot
    assert out.written == 0


# Feature: fabric-data-ai-platform, Property 11: Marca d'água só avança em sucesso
@settings(max_examples=100)
@given(bronze=bronze_tables(), prev=st.integers(min_value=0, max_value=1_000_000))
def test_nothing_written_keeps_previous_watermark(bronze, prev):
    rows = [{"id": "A", WM_COL: prev, "valor": 1}, {"id": "B", WM_COL: None, "valor": 2}]
    out = _ingest(bronze, rows, prev)
    assert out.ok and out.written == 0
    assert out.watermark == prev

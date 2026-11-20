"""Property 10: Seleção incremental por marca d'água.

**Validates: Requirements 3.4**
"""

from __future__ import annotations

from hypothesis import given, settings

from platform_lib.ingestion import select_incremental
from tests.strategies_ingest_wm import incremental_cases


# Feature: fabric-data-ai-platform, Property 10: Seleção incremental por marca d'água
@settings(max_examples=100, deadline=None)
@given(case=incremental_cases())
def test_select_incremental(case):
    rows, col, last_wm = case
    snapshot = [dict(r) for r in rows]

    result = select_incremental(rows, col, last_wm)

    if last_wm is None:
        assert result == snapshot
    else:
        expected = [r for r in snapshot if r.get(col) is not None and r[col] > last_wm]
        assert result == expected
        assert all(r[col] > last_wm for r in result)
    # entrada não é alterada
    assert rows == snapshot

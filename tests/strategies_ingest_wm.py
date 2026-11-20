"""Estratégias para a seleção incremental por marca d'água (Property 10)."""

from __future__ import annotations

from datetime import date, datetime

from hypothesis import strategies as st

from tests.strategies import dates

_wm_values = st.one_of(
    st.integers(min_value=-1_000, max_value=1_000),
    dates,
    st.datetimes(min_value=datetime(2000, 1, 1), max_value=datetime(2100, 12, 31)),
)

_col_names = st.sampled_from(["updated_at", "dt_alteracao", "id_seq", "wm"])


@st.composite
def incremental_cases(draw):
    """(rows, watermark_col, last_wm) com valores de marca de um único tipo.

    Linhas podem ter a marca nula ou ausente; ``last_wm`` pode ser None.
    """
    col = draw(_col_names)
    kind = draw(st.sampled_from(["int", "date", "datetime"]))
    value = {
        "int": st.integers(min_value=-50, max_value=50),
        "date": st.dates(min_value=date(2020, 1, 1), max_value=date(2020, 3, 1)),
        "datetime": st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2020, 1, 5)),
    }[kind]
    wm_or_missing = st.one_of(value, st.none(), st.just(_MISSING))

    n = draw(st.integers(min_value=0, max_value=40))
    rows = []
    for i in range(n):
        wm = draw(wm_or_missing)
        row = {"id": i, "payload": draw(st.text(max_size=5))}
        if wm is not _MISSING:
            row[col] = wm
        rows.append(row)
    last_wm = draw(st.one_of(st.none(), value))
    return rows, col, last_wm


_MISSING = object()

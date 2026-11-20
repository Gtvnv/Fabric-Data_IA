"""Estratégias Hypothesis para Bronze (Property 12)."""

from __future__ import annotations

from datetime import UTC, datetime

from hypothesis import strategies as st

from tests.strategies import money

_text = st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", max_size=12)
_ident = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_", min_size=1, max_size=12)

run_ids = _ident
source_systems = _ident
now_values = st.datetimes(
    min_value=datetime(2020, 1, 1), max_value=datetime(2100, 1, 1), timezones=st.just(UTC)
)


@st.composite
def source_rows(draw, max_size: int = 30) -> list[dict]:
    """Linhas de origem com chave ``id`` única; colunas de dados variadas (inclui None)."""
    ids = draw(st.lists(st.integers(1, 10_000), unique=True, max_size=max_size))
    rows = []
    for i in ids:
        rows.append(
            {
                "id": i,
                "nome": draw(st.one_of(st.none(), _text)),
                "valor": draw(st.one_of(st.none(), money())),
                "qtd": draw(st.integers(-1000, 1000)),
                "ativo": draw(st.booleans()),
            }
        )
    return rows

"""Estratégias para os invariantes de SCD tipo 2 de dim_cliente (Property 18)."""

from __future__ import annotations

from datetime import date, timedelta

from hypothesis import strategies as st

_KEYS = st.integers(min_value=1, max_value=5)
_CIDADES = st.sampled_from(["Curitiba", "Sao Paulo", "Recife", "Manaus"])
_UFS = st.sampled_from(["PR", "SP", "PE", "AM"])
_NOMES = st.sampled_from(["m1", "m2", "m3"])


@st.composite
def cliente_batches(draw):
    """Lote de clientes de entrada (chaves de negócio podem repetir)."""
    return draw(
        st.lists(
            st.fixed_dictionaries(
                {
                    "cliente_id": _KEYS,
                    "nome_mascarado": _NOMES,
                    "cidade": _CIDADES,
                    "uf": _UFS,
                }
            ),
            max_size=8,
        )
    )


@st.composite
def scd2_sequences(draw):
    """Sequência de (as_of, lote) com as_of estritamente crescente."""
    start = draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2024, 12, 31)))
    steps = draw(st.lists(st.integers(min_value=1, max_value=120), min_size=1, max_size=8))
    out = []
    current = start
    for i, delta in enumerate(steps):
        if i:
            current = current + timedelta(days=delta)
        out.append((current, draw(cliente_batches())))
    return out

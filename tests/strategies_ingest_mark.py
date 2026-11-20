"""Estratégias para a Property 11 (marca d'água)."""

from __future__ import annotations

from hypothesis import strategies as st

from tests.strategies import business_keys

WM_COL = "atualizado_em"

watermarks = st.integers(min_value=0, max_value=1_000_000)


@st.composite
def source_rows(draw, max_size: int = 20) -> list[dict]:
    """Linhas de origem com chave, coluna de marca (pode ser nula) e valor."""
    n = draw(st.integers(min_value=0, max_value=max_size))
    keys = draw(st.lists(business_keys, min_size=n, max_size=n, unique=True))
    return [
        {
            "id": k,
            WM_COL: draw(st.one_of(st.none(), watermarks)),
            "valor": draw(st.integers(min_value=-1000, max_value=1000)),
        }
        for k in keys
    ]


@st.composite
def bronze_tables(draw, max_size: int = 10) -> list[dict]:
    """Conteúdo Bronze pré-existente com chaves próprias."""
    n = draw(st.integers(min_value=0, max_value=max_size))
    keys = draw(st.lists(business_keys, min_size=n, max_size=n, unique=True))
    return [
        {"id": k, WM_COL: draw(watermarks), "valor": draw(st.integers(0, 100))} for k in keys
    ]


optional_watermarks = st.one_of(st.none(), watermarks)

failure_kinds = st.sampled_from(["run_id_vazio", "source_vazio", "now_ingenuo"])

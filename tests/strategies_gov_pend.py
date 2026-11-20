"""Estratégias para pendências de governança (Gold + catálogo)."""

from __future__ import annotations

from hypothesis import strategies as st

_TEXT = st.text(alphabet=st.characters(min_codepoint=33, max_codepoint=126), min_size=1, max_size=20)

table_names = st.lists(
    st.text(alphabet="abcdefghij_", min_size=1, max_size=8).map(lambda s: f"gold.{s}"),
    min_size=0,
    max_size=10,
    unique=True,
)

owners = st.one_of(st.none(), st.just(""), st.just("   "), _TEXT)

descriptions = st.one_of(
    st.none(),
    st.just(""),
    st.just("  \t"),
    _TEXT,
    st.integers(min_value=499, max_value=502).map(lambda n: "d" * n),
    st.integers(min_value=501, max_value=800).map(lambda n: "x" * n),
)


@st.composite
def gold_and_catalog(draw):
    """(tabelas Gold, catálogo como dict ou lista); parte das tabelas fica fora do catálogo."""
    tables = draw(table_names)
    catalog: dict[str, dict] = {}
    for t in tables:
        if draw(st.booleans()) or draw(st.booleans()):
            catalog[t] = {"responsavel": draw(owners), "descricao": draw(descriptions)}
    # entradas extras no catálogo que não são Gold
    catalog["extra.nao_gold"] = {"responsavel": None, "descricao": ""}
    as_list = draw(st.booleans())
    if as_list:
        return tables, [{"tabela": k, **v} for k, v in catalog.items()]
    return tables, catalog

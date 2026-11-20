"""Estratégias para a quarentena Silver (Property 16)."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import strategies as st

from platform_lib.silver import (
    META_TS,
    REASON_BAD_DATE,
    REASON_BAD_TYPE,
    REASON_NEGATIVE_SALE,
    REASON_NULL_KEY,
    EntitySpec,
)

SPEC = EntitySpec(
    name="vendas",
    key=("id",),
    columns={"id": "int", "nome": "str", "data": "date", "valor_venda": "decimal"},
    non_negative=("valor_venda",),
)

VALID = "valido"
KINDS = {
    REASON_NULL_KEY: "chave_nula",
    REASON_BAD_TYPE: "tipo",
    REASON_BAD_DATE: "data",
    REASON_NEGATIVE_SALE: "venda_negativa",
}

_names = st.text(alphabet="abcdefghij ", min_size=1, max_size=8).filter(lambda s: s.strip())
_good_dates = st.dates().map(lambda d: d.isoformat())
_good_values = st.decimals(
    min_value=Decimal("0.00"), max_value=Decimal("100000.00"), places=2
).map(str)
_bad_values = st.sampled_from(["abc", "12x", "--", "NaN", "Infinity"])
_bad_dates = st.sampled_from(["2023-02-30", "2021-13-01", "2023-04-31", "2022-00-10", "31/02/2020"])
_neg_values = st.decimals(
    min_value=Decimal("-100000.00"), max_value=Decimal("-0.01"), places=2
).map(str)
_null_keys = st.sampled_from([None, "", "   "])


@st.composite
def bronze_batches(draw):
    """Lote Bronze misto. Retorna (rows, expected) com expected[id_ou_idx] = (código|None)."""
    kinds = draw(
        st.lists(
            st.sampled_from([VALID, *KINDS.values()]),
            min_size=0,
            max_size=25,
        )
    )
    rows, expected = [], []
    for i, kind in enumerate(kinds):
        row = {
            "id": str(i + 1),
            "nome": draw(_names),
            "data": draw(_good_dates),
            "valor_venda": draw(_good_values),
            META_TS: "2024-01-01T00:00:00+00:00",
            "_idx": i,
        }
        code = None
        if kind == "chave_nula":
            row["id"] = draw(_null_keys)
            code = REASON_NULL_KEY
        elif kind == "tipo":
            row["valor_venda"] = draw(_bad_values)
            code = REASON_BAD_TYPE
        elif kind == "data":
            row["data"] = draw(_bad_dates)
            code = REASON_BAD_DATE
        elif kind == "venda_negativa":
            row["valor_venda"] = draw(_neg_values)
            code = REASON_NEGATIVE_SALE
        rows.append(row)
        expected.append(code)
    return rows, expected

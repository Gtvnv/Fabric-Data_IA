"""Estratégias para resolução de chaves substitutas (Property 17)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from hypothesis import strategies as st

from platform_lib.gold import OPEN_END_DATE, build_dim_calendario

CAL_START = date(2024, 1, 1)
CAL_END = date(2024, 3, 31)
CALENDARIO = build_dim_calendario(CAL_START, CAL_END)

# Chaves de negócio existentes: 1..50; inexistentes: 1001..1050 ou None.
_known_keys = st.sets(st.integers(1, 50), max_size=8)
_unknown_key = st.one_of(st.none(), st.integers(1001, 1050))
_dates_in = st.dates(CAL_START, CAL_END)
_dates_out = st.one_of(st.none(), st.dates(date(2020, 1, 1), date(2023, 12, 31)))


@st.composite
def _dim(draw: st.DrawFn, keys: set[int], key_col: str, sk_col: str, scd: bool) -> list[dict[str, Any]]:
    sks = draw(st.lists(st.integers(1, 10_000), min_size=len(keys), max_size=len(keys), unique=True))
    rows: list[dict[str, Any]] = [{sk_col: -1, key_col: None}]
    for k, sk in zip(sorted(keys), sks):
        row: dict[str, Any] = {sk_col: sk, key_col: k}
        if scd:
            row.update(data_inicio=date(1900, 1, 1), data_fim=OPEN_END_DATE, vigente=True)
        rows.append(row)
    return rows


@st.composite
def sales_and_dims(draw: st.DrawFn) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    cli = draw(_known_keys)
    prod = draw(_known_keys)
    loja = draw(_known_keys)
    dims = {
        "dim_cliente": draw(_dim(cli, "cliente_id", "sk_cliente", True)),
        "dim_produto": draw(_dim(prod, "produto_id", "sk_produto", False)),
        "dim_loja": draw(_dim(loja, "loja_id", "sk_loja", False)),
        "dim_calendario": CALENDARIO,
    }

    def pick(known: set[int]) -> st.SearchStrategy[Any]:
        if known:
            return st.one_of(st.sampled_from(sorted(known)), _unknown_key)
        return _unknown_key

    venda = st.fixed_dictionaries(
        {
            "cliente_id": pick(cli),
            "produto_id": pick(prod),
            "loja_id": pick(loja),
            "data_venda": st.one_of(_dates_in, _dates_in, _dates_out),
            "quantidade": st.integers(1, 20),
            "valor_venda": st.decimals(Decimal("0.01"), Decimal("999.99"), places=2),
            "custo_total": st.decimals(Decimal("0.00"), Decimal("500.00"), places=2),
        }
    )
    vendas = draw(st.lists(venda, max_size=30))
    for i, v in enumerate(vendas, start=1):
        v["venda_id"] = i
    return vendas, dims

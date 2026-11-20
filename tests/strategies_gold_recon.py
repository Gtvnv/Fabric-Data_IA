"""Estratégias para a reconciliação Silver x Gold (Property 19)."""
from __future__ import annotations

from datetime import date, timedelta

from hypothesis import strategies as st

from platform_lib.gold import (
    add_unknown_cliente,
    build_dim_calendario,
    build_dim_cliente_scd2,
    build_dim_loja,
    build_dim_produto,
)
from tests.strategies import money

CAL_START = date(2024, 1, 1)
CAL_DAYS = 30
CAL_END = CAL_START + timedelta(days=CAL_DAYS - 1)

# Ids pequenos para provocar colisões de (dia, produto, loja) e chaves sem dimensão.
_ids = st.integers(min_value=1, max_value=6)


@st.composite
def silver_and_dims(draw):
    """Vendas Silver (valor_venda Decimal) + dimensões construídas pelo gold.py.

    As vendas podem referenciar produtos, lojas ou clientes ausentes nas
    dimensões e datas fora do calendário (viram 'Desconhecido').
    """
    prod_ids = draw(st.sets(_ids, max_size=5))
    loja_ids = draw(st.sets(_ids, max_size=5))
    cli_ids = draw(st.sets(_ids, max_size=5))

    dim_produto = build_dim_produto(
        [{"produto_id": p, "nome": f"P{p}", "categoria": "c", "subcategoria": "s",
          "preco_lista": None} for p in sorted(prod_ids)]
    )
    dim_loja = build_dim_loja(
        [{"loja_id": l, "nome": f"L{l}", "regiao": "r", "cidade": "c", "uf": "SP"}
         for l in sorted(loja_ids)]
    )
    dim_cliente = add_unknown_cliente(
        build_dim_cliente_scd2(
            [],
            [{"cliente_id": c, "nome_mascarado": f"C{c}", "cidade": "c", "uf": "SP"}
             for c in sorted(cli_ids)],
            CAL_START,
        )
    )
    dim_calendario = build_dim_calendario(CAL_START, CAL_END)

    n = draw(st.integers(min_value=0, max_value=40))
    day_offsets = st.integers(min_value=-3, max_value=CAL_DAYS + 3)
    vendas = [
        {
            "venda_id": i,
            "cliente_id": draw(_ids),
            "produto_id": draw(_ids),
            "loja_id": draw(_ids),
            "data_venda": CAL_START + timedelta(days=draw(day_offsets)),
            "quantidade": draw(st.integers(min_value=0, max_value=20)),
            "valor_venda": draw(money()),
            "custo_total": draw(money()),
        }
        for i in range(1, n + 1)
    ]
    dims = {
        "dim_cliente": dim_cliente,
        "dim_produto": dim_produto,
        "dim_loja": dim_loja,
        "dim_calendario": dim_calendario,
    }
    return vendas, dims


@st.composite
def periods(draw):
    """Intervalo (inicio, fim) dentro do calendário."""
    a = draw(st.integers(min_value=0, max_value=CAL_DAYS - 1))
    b = draw(st.integers(min_value=a, max_value=CAL_DAYS - 1))
    return CAL_START + timedelta(days=a), CAL_START + timedelta(days=b)

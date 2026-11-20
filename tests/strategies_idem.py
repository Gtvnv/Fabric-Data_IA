"""Estratégias para a Property 20 (transformações Silver/Gold idempotentes).

Autocontido: gera lotes Bronze sujos (inclusive inválidos e duplicados), dimensões
Silver, vendas e uma dimensão cliente SCD2 com entrada e ``as_of`` compatíveis.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from hypothesis import strategies as st

from platform_lib.gold import build_dim_cliente_scd2
from platform_lib.silver import META_TS, T_DATE, T_DECIMAL, T_INT, T_STR, EntitySpec

SPEC_VENDA = EntitySpec(
    name="venda",
    key=("venda_id",),
    columns={
        "venda_id": T_STR,
        "cliente_id": T_STR,
        "produto_id": T_STR,
        "loja_id": T_STR,
        "data_venda": T_DATE,
        "quantidade": T_INT,
        "valor_venda": T_DECIMAL,
        "custo_total": T_DECIMAL,
    },
    non_negative=("valor_venda",),
)

_BASE_TS = datetime(2024, 1, 1, tzinfo=timezone.utc)
_ids = st.sampled_from(["A", "B", "C", "D", "E"])
_pad = st.sampled_from(["", " ", "  "])
_dates = st.dates(min_value=date(2023, 1, 1), max_value=date(2024, 12, 31))
_money = st.decimals(min_value=Decimal("0"), max_value=Decimal("9999.99"), places=2)


def _fmt_date(d: date, fmt: str) -> Any:
    return {
        "iso": d.isoformat(),
        "br": d.strftime("%d/%m/%Y"),
        "compact": d.strftime("%Y%m%d"),
        "date": d,
        "bad": "2023-02-30",
    }[fmt]


@st.composite
def _bronze_venda(draw, idx: int) -> dict[str, Any]:
    d = draw(_dates)
    valor = draw(st.one_of(_money, _money.map(lambda x: -x - Decimal("0.01"))))
    valor_raw = draw(
        st.sampled_from(
            [str(valor), str(valor).replace(".", ","), valor, "abc", None]
        )
    )
    return {
        "venda_id": draw(_pad) + draw(st.sampled_from(["v1", "v2", "v3", "v4", "V5", ""])) + draw(_pad),
        "cliente_id": draw(_ids),
        "produto_id": draw(_ids),
        "loja_id": draw(_ids),
        "data_venda": _fmt_date(d, draw(st.sampled_from(["iso", "br", "compact", "date", "bad"]))),
        "quantidade": draw(st.sampled_from([1, "2", " 3 ", 4.0, "x", None])),
        "valor_venda": valor_raw,
        "custo_total": draw(st.sampled_from([str(draw(_money)), None])),
        META_TS: (_BASE_TS + timedelta(seconds=draw(st.integers(0, 5)))).isoformat(),
    }


@st.composite
def bronze_vendas(draw) -> list[dict[str, Any]]:
    n = draw(st.integers(0, 15))
    return [draw(_bronze_venda(i)) for i in range(n)]


@st.composite
def _cliente_attrs(draw) -> dict[str, Any]:
    return {
        "nome_mascarado": draw(st.sampled_from(["N1", "N2", "N3"])),
        "cidade": draw(st.sampled_from(["X", "Y"])),
        "uf": draw(st.sampled_from(["SP", "RJ", None])),
    }


@st.composite
def scd2_case(draw) -> tuple[list[dict], list[dict], date]:
    """(dim atual, entrada, as_of) com ``as_of`` >= início de toda versão vigente."""
    start = draw(_dates)
    keys = draw(st.lists(_ids, unique=True, max_size=4))
    seed_inc = [{"cliente_id": k, **draw(_cliente_attrs())} for k in keys]
    dim = build_dim_cliente_scd2([], seed_inc, start)
    as_of = start + timedelta(days=draw(st.integers(0, 30)))
    inc_keys = draw(st.lists(_ids, max_size=6))  # pode repetir chaves
    incoming = [{"cliente_id": k, **draw(_cliente_attrs())} for k in inc_keys]
    return dim, incoming, as_of


@st.composite
def silver_dims(draw) -> tuple[list[dict], list[dict], list[dict]]:
    """Linhas Silver de cliente, produto e loja (chaves repetidas permitidas)."""
    clientes = [
        {"cliente_id": draw(_ids), **draw(_cliente_attrs())}
        for _ in range(draw(st.integers(0, 6)))
    ]
    produtos = [
        {
            "produto_id": draw(_ids),
            "nome": draw(st.sampled_from(["P1", "P2"])),
            "categoria": draw(st.sampled_from(["C1", "C2"])),
            "subcategoria": draw(st.sampled_from(["S1", "S2"])),
            "preco_lista": draw(_money),
        }
        for _ in range(draw(st.integers(0, 6)))
    ]
    lojas = [
        {
            "loja_id": draw(_ids),
            "nome": draw(st.sampled_from(["L1", "L2"])),
            "regiao": draw(st.sampled_from(["N", "S"])),
            "cidade": draw(st.sampled_from(["X", "Y"])),
            "uf": draw(st.sampled_from(["SP", "RJ"])),
        }
        for _ in range(draw(st.integers(0, 6)))
    ]
    return clientes, produtos, lojas

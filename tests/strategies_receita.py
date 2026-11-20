"""Estratégias Hypothesis (autossuficientes) para a Property 34 (Receita Total)."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from hypothesis import strategies as st

BASE = date(2024, 1, 1)
SPAN = 60
CATEGORIAS = ["Alimentos", "Bebidas", "Limpeza", "Higiene"]
_money = st.decimals(min_value=Decimal("0.00"), max_value=Decimal("9999.99"), places=2)


@st.composite
def receita_scenarios(draw):
    """Dims (produto/loja/calendário), vendas Silver (com chaves órfãs) e filtro."""
    n_prod = draw(st.integers(1, 6))
    n_loja = draw(st.integers(1, 4))
    produtos = [
        {"produto_id": f"P{i}", "nome": f"p{i}", "categoria": draw(st.sampled_from(CATEGORIAS)),
         "subcategoria": "s", "preco_lista": Decimal("1.00")}
        for i in range(n_prod)
    ]
    lojas = [
        {"loja_id": f"L{i}", "nome": f"l{i}", "regiao": "R", "cidade": "C", "uf": "SP"}
        for i in range(n_loja)
    ]
    clientes = [{"cliente_id": "C0"}]
    n_vendas = draw(st.integers(0, 25))
    vendas = []
    for i in range(n_vendas):
        vendas.append(
            {
                "venda_id": i + 1,
                "cliente_id": "C0",
                # ids até n+1 => alguns órfãos (viram Desconhecido)
                "produto_id": f"P{draw(st.integers(0, n_prod))}",
                "loja_id": f"L{draw(st.integers(0, n_loja))}",
                "data_venda": (BASE + timedelta(days=draw(st.integers(0, SPAN + 5)))).isoformat(),
                "quantidade": draw(st.integers(1, 5)),
                "valor_venda": draw(_money),
                "custo_total": Decimal("0.00"),
            }
        )
    d0 = draw(st.integers(-5, SPAN + 10))
    d1 = draw(st.integers(d0, SPAN + 15))
    filtro = {
        "periodo": draw(st.one_of(
            st.none(), st.just((BASE + timedelta(days=d0), BASE + timedelta(days=d1))))),
        "lojas": draw(st.one_of(
            st.none(), st.sets(st.sampled_from([l["loja_id"] for l in lojas] + ["INEXISTENTE"])))),
        "categorias": draw(st.one_of(
            st.none(), st.sets(st.sampled_from(CATEGORIAS + ["Inexistente"])))),
    }
    return {"produtos": produtos, "lojas": lojas, "clientes": clientes,
            "vendas": vendas, "filtro": filtro}


@st.composite
def empty_match_scenarios(draw):
    """Cenário cujo filtro de categoria nunca casa com nada."""
    sc = draw(receita_scenarios())
    sc["filtro"] = {"periodo": None, "lojas": None, "categorias": {"__nenhuma__"}}
    return sc

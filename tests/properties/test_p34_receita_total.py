"""Property 34: Receita total igual à soma da Gold.
**Validates: Requirements 8.8**
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from hypothesis import given, settings

from platform_lib import gold
from tests.strategies_receita import BASE, SPAN, empty_match_scenarios, receita_scenarios

TOL = Decimal("0.01")
TMDL = (Path(__file__).resolve().parents[2] / "powerbi" / "fdai.SemanticModel"
        / "definition" / "tables" / "fato_vendas.tmdl")


def _build(sc):
    from datetime import timedelta
    dims = {
        "dim_cliente": gold.add_unknown_cliente(gold.build_dim_cliente_scd2(
            [], sc["clientes"], BASE)),
        "dim_produto": gold.build_dim_produto(sc["produtos"]),
        "dim_loja": gold.build_dim_loja(sc["lojas"]),
        "dim_calendario": gold.build_dim_calendario(BASE, BASE + timedelta(days=SPAN)),
    }
    return dims, gold.resolve_fact(sc["vendas"], dims).rows


def dax_receita_total(fact_rows, dims, filtro) -> Decimal:
    """Modelo de referência de SUM(fato_vendas[valor_venda]) sob contexto de filtro
    propagado das dimensões para o fato via chaves substitutas."""
    sk_data = sk_loja = sk_prod = None
    if filtro["periodo"] is not None:
        a, b = filtro["periodo"]
        sk_data = {r["sk_data"] for r in dims["dim_calendario"]
                   if r["data"] is not None and a <= r["data"] <= b}
    if filtro["lojas"] is not None:
        sk_loja = {r["sk_loja"] for r in dims["dim_loja"] if r["loja_id"] in filtro["lojas"]}
    if filtro["categorias"] is not None:
        sk_prod = {r["sk_produto"] for r in dims["dim_produto"]
                   if r["produto_id"] is not None and r["categoria"] in filtro["categorias"]}
    total = Decimal("0")
    for f in fact_rows:
        if sk_data is not None and f["sk_data"] not in sk_data:
            continue
        if sk_loja is not None and f["sk_loja"] not in sk_loja:
            continue
        if sk_prod is not None and f["sk_produto"] not in sk_prod:
            continue
        total += f["valor_venda"]
    return total


def independent_sum(sc) -> Decimal:
    """Soma independente via chaves de negócio das linhas Silver (sem passar por sk)."""
    f = sc["filtro"]
    cat = {p["produto_id"]: p["categoria"] for p in sc["produtos"]}
    lojas = {l["loja_id"] for l in sc["lojas"]}
    total = Decimal("0")
    for v in sc["vendas"]:
        if f["periodo"] is not None:
            d = date.fromisoformat(v["data_venda"])
            a, b = f["periodo"]
            if not (a <= d <= b and (d - BASE).days <= SPAN):
                continue
        if f["lojas"] is not None and not (v["loja_id"] in lojas and v["loja_id"] in f["lojas"]):
            continue
        if f["categorias"] is not None and cat.get(v["produto_id"]) not in f["categorias"]:
            continue
        total += gold.to_decimal(v["valor_venda"])
    return total


# Feature: fabric-data-ai-platform, Property 34: Receita total igual à soma da Gold
@settings(max_examples=100, deadline=None)
@given(receita_scenarios())
def test_receita_total_igual_soma_gold(sc):
    dims, fact = _build(sc)
    assert abs(dax_receita_total(fact, dims, sc["filtro"]) - independent_sum(sc)) <= TOL


# Feature: fabric-data-ai-platform, Property 34: Receita total igual à soma da Gold
@settings(max_examples=100, deadline=None)
@given(empty_match_scenarios())
def test_filtro_sem_correspondencia_resulta_zero(sc):
    dims, fact = _build(sc)
    assert dax_receita_total(fact, dims, sc["filtro"]) == Decimal("0")
    assert independent_sum(sc) == Decimal("0")


def test_medida_tmdl_e_soma_valor_venda():
    text = TMDL.read_text(encoding="utf-8")
    m = re.search(r"^\s*measure 'Receita Total' = (.+)$", text, re.MULTILINE)
    assert m is not None
    assert m.group(1).strip() == "SUM(fato_vendas[valor_venda])"

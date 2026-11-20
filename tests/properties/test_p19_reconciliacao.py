"""Property 19: Reconciliação entre Silver e Gold.

**Validates: Requirements 4.9, 4.11**
"""
from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings

from platform_lib.gold import ZERO, aggregate_daily, reconcile_sales, resolve_fact, sk_data_of
from tests.strategies_gold_recon import periods, silver_and_dims


def _sum(rows) -> Decimal:
    return sum((r["valor_venda"] for r in rows), ZERO)


# Feature: fabric-data-ai-platform, Property 19: Reconciliação entre Silver e Gold
@settings(max_examples=100, deadline=None)
@given(data=silver_and_dims())
def test_p19_soma_silver_igual_fato_e_agregacao(data):
    vendas, dims = data
    fact = resolve_fact(vendas, dims).rows
    agg = aggregate_daily(fact)

    silver_total = _sum(vendas)
    assert _sum(fact) == silver_total
    assert _sum(agg) == silver_total
    assert reconcile_sales(vendas, fact) == Decimal("0.00")
    assert reconcile_sales(vendas, agg) == Decimal("0.00")


# Feature: fabric-data-ai-platform, Property 19: Reconciliação entre Silver e Gold
@settings(max_examples=100, deadline=None)
@given(data=silver_and_dims())
def test_p19_agregacao_uma_linha_por_dia_produto_loja(data):
    vendas, dims = data
    fact = resolve_fact(vendas, dims).rows
    agg = aggregate_daily(fact)

    keys = [(r["sk_data"], r["sk_produto"], r["sk_loja"]) for r in agg]
    assert len(keys) == len(set(keys))
    assert set(keys) == {(f["sk_data"], f["sk_produto"], f["sk_loja"]) for f in fact}
    assert sum(r["quantidade"] for r in agg) == sum(f["quantidade"] for f in fact)


# Feature: fabric-data-ai-platform, Property 19: Reconciliação entre Silver e Gold
@settings(max_examples=100, deadline=None)
@given(data=silver_and_dims(), period=periods())
def test_p19_reconciliacao_no_mesmo_periodo(data, period):
    vendas, dims = data
    start, end = period
    fact = resolve_fact(vendas, dims).rows
    agg = aggregate_daily(fact)

    lo, hi = sk_data_of(start), sk_data_of(end)
    silver_p = [v for v in vendas if start <= v["data_venda"] <= end]
    fact_p = [f for f in fact if lo <= f["sk_data"] <= hi]
    agg_p = [a for a in agg if lo <= a["sk_data"] <= hi]

    assert reconcile_sales(silver_p, fact_p) == Decimal("0.00")
    assert reconcile_sales(silver_p, agg_p) == Decimal("0.00")

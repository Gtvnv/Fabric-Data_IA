# Feature: fabric-data-ai-platform, Property 20: Transformações idempotentes
"""Valida: Requisito 4.10.

**Validates: Requirements 4.10**
"""

from __future__ import annotations

import copy
from datetime import date

from hypothesis import given, settings

from platform_lib.gold import (
    aggregate_daily,
    build_dim_calendario,
    build_dim_cliente_scd2,
    build_dim_loja,
    build_dim_produto,
    resolve_fact,
)
from platform_lib.silver import to_silver
from tests.strategies_idem import SPEC_VENDA, bronze_vendas, scd2_case, silver_dims


def _business(rows):
    """Remove colunas de metadados de execução (prefixo ``_``)."""
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]


def _no_dup_keys(rows, key):
    keys = [tuple(r[k] for k in key) for r in rows]
    return len(keys) == len(set(keys))


@settings(max_examples=100, deadline=None)
@given(batch=bronze_vendas())
def test_silver_idempotente(batch):
    original = copy.deepcopy(batch)
    r1 = to_silver(batch, SPEC_VENDA)
    r2 = to_silver(batch, SPEC_VENDA)

    assert batch == original  # entrada não é mutada
    assert _business(r1.silver_rows) == _business(r2.silver_rows)
    assert _business(r1.quarantine_rows) == _business(r2.quarantine_rows)
    assert _no_dup_keys(r1.silver_rows, ("venda_id",))


@settings(max_examples=100, deadline=None)
@given(batch=bronze_vendas(), dims_in=silver_dims(), scd=scd2_case())
def test_gold_idempotente(batch, dims_in, scd):
    clientes, produtos, lojas = dims_in
    dim_cli, incoming, as_of = scd

    def run():
        cli = build_dim_cliente_scd2(dim_cli, incoming, as_of)
        dims = {
            "dim_cliente": cli,
            "dim_produto": build_dim_produto(produtos),
            "dim_loja": build_dim_loja(lojas),
            "dim_calendario": build_dim_calendario(date(2023, 1, 1), date(2024, 12, 31)),
        }
        silver = to_silver(batch, SPEC_VENDA).silver_rows
        fact = resolve_fact(silver, dims)
        return cli, dims, fact, aggregate_daily(fact.rows)

    a = run()
    b = run()

    assert a[0] == b[0]
    assert a[1] == b[1]
    assert a[2] == b[2]
    assert a[3] == b[3]

    # Sem duplicatas
    assert _no_dup_keys(a[2].rows, ("venda_id",))
    assert _no_dup_keys(a[3], ("sk_data", "sk_produto", "sk_loja"))
    for name, key in (("dim_produto", "sk_produto"), ("dim_loja", "sk_loja")):
        assert _no_dup_keys(a[1][name], (key,))


@settings(max_examples=100, deadline=None)
@given(scd=scd2_case())
def test_scd2_reaplicado_nao_duplica(scd):
    dim, incoming, as_of = scd
    once = build_dim_cliente_scd2(dim, incoming, as_of)
    twice = build_dim_cliente_scd2(once, incoming, as_of)

    assert twice == once
    vigentes = [r["cliente_id"] for r in once if r.get("vigente") and r["cliente_id"] is not None]
    assert len(vigentes) == len(set(vigentes))

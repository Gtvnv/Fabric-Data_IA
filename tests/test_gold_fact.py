from datetime import date
from decimal import Decimal

from platform_lib.gold import (
    UNKNOWN_SK,
    aggregate_daily,
    build_dim_calendario,
    build_dim_cliente_scd2,
    build_dim_loja,
    build_dim_produto,
    build_fato_estoque,
    reconcile_sales,
    resolve_fact,
)


def _dims():
    cli = build_dim_cliente_scd2([], [{"cliente_id": "C1", "cidade": "SP"}], date(2024, 1, 1))
    cli = build_dim_cliente_scd2(cli, [{"cliente_id": "C1", "cidade": "RJ"}], date(2024, 3, 1))
    return {
        "dim_cliente": cli,
        "dim_produto": build_dim_produto([{"produto_id": "P1", "nome": "x"}]),
        "dim_loja": build_dim_loja([{"loja_id": "L1", "nome": "y"}]),
        "dim_calendario": build_dim_calendario("2024-01-01", "2024-12-31"),
    }


def _venda(vid, cli="C1", prod="P1", loja="L1", dt="2024-02-10", v="10.10"):
    return {"venda_id": vid, "cliente_id": cli, "produto_id": prod, "loja_id": loja,
            "data_venda": dt, "quantidade": 2, "valor_venda": v, "custo_total": "5.05"}


def test_resolve_unknown_and_count():
    res = resolve_fact([_venda(1), _venda(2, prod="PX"), _venda(3, dt="2030-01-01")], _dims())
    assert res.unknown_count == 2
    assert res.rows[1]["sk_produto"] == UNKNOWN_SK
    assert res.rows[2]["sk_data"] == UNKNOWN_SK
    assert res.rows[0]["sk_data"] == 20240210


def test_scd2_version_by_sale_date():
    dims = _dims()
    old = resolve_fact([_venda(1, dt="2024-02-10")], dims).rows[0]["sk_cliente"]
    new = resolve_fact([_venda(2, dt="2024-04-10")], dims).rows[0]["sk_cliente"]
    assert old != new and UNKNOWN_SK not in (old, new)


def test_aggregate_and_reconcile_exact_decimal():
    vendas = [_venda(i, v="0.10") for i in range(1, 4)] + [_venda(9, dt="2024-02-11", v="0.20")]
    fact = resolve_fact(vendas, _dims()).rows
    agg = aggregate_daily(fact)
    assert len(agg) == 2
    assert agg[0]["valor_venda"] == Decimal("0.30") and agg[0]["quantidade"] == 6
    assert reconcile_sales(vendas, fact) == Decimal("0")
    assert reconcile_sales(vendas, agg) == Decimal("0")


def test_fato_estoque():
    res = build_fato_estoque(
        [{"produto_id": "P1", "loja_id": "L1", "data_posicao": "2024-02-10",
          "quantidade_estoque": 7},
         {"produto_id": "P?", "loja_id": "L1", "data_posicao": "2024-02-10",
          "quantidade_estoque": 1}],
        _dims(),
    )
    assert res.unknown_count == 1
    assert res.rows[0]["quantidade_estoque"] == 7
    assert res.rows[1]["sk_produto"] == UNKNOWN_SK

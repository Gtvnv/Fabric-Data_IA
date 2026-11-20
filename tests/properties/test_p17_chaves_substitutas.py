"""Property 17: Resolução de chaves substitutas e membro "Desconhecido"."""
from __future__ import annotations

from typing import Any

from hypothesis import given, settings

from platform_lib.gold import UNKNOWN_SK, resolve_fact, sk_data_of
from tests.strategies_gold_keys import sales_and_dims


def _lookup(dim: list[dict[str, Any]], key_col: str, sk_col: str) -> dict[Any, int]:
    return {r[key_col]: r[sk_col] for r in dim if r[key_col] is not None}


# Feature: fabric-data-ai-platform, Property 17: Resolução de chaves substitutas e membro "Desconhecido"
# **Validates: Requirements 4.6, 4.7**
@settings(max_examples=100, deadline=None)
@given(data=sales_and_dims())
def test_chaves_substitutas_e_desconhecido(data) -> None:
    vendas, dims = data
    cli = _lookup(dims["dim_cliente"], "cliente_id", "sk_cliente")
    prod = _lookup(dims["dim_produto"], "produto_id", "sk_produto")
    loja = _lookup(dims["dim_loja"], "loja_id", "sk_loja")
    cal = {r["sk_data"] for r in dims["dim_calendario"]}

    result = resolve_fact(vendas, dims)

    assert len(result.rows) == len(vendas)
    esperado_desconhecidos = 0
    for venda, row in zip(vendas, result.rows):
        sk_data = sk_data_of(venda["data_venda"])
        esperado = {
            "sk_cliente": cli.get(venda["cliente_id"], UNKNOWN_SK),
            "sk_produto": prod.get(venda["produto_id"], UNKNOWN_SK),
            "sk_loja": loja.get(venda["loja_id"], UNKNOWN_SK),
            "sk_data": sk_data if sk_data in cal else UNKNOWN_SK,
        }
        assert row["venda_id"] == venda["venda_id"]
        for col, sk in esperado.items():
            assert row[col] == sk
        if UNKNOWN_SK in esperado.values():
            esperado_desconhecidos += 1

    assert result.unknown_count == esperado_desconhecidos

"""Property 6: Integridade referencial e de datas das vendas.

**Validates: Requirements 2.5**
"""
from __future__ import annotations

from datetime import date

from hypothesis import given, settings

from platform_lib import synth
from tests.strategies_synth_ref import small_clean_params


# Feature: fabric-data-ai-platform, Property 6: Integridade referencial e de datas das vendas
@settings(max_examples=100, deadline=None)
@given(small_clean_params())
def test_vendas_referenciam_entidades_existentes_e_datas_no_intervalo(params):
    data = synth.generate(params)
    clientes = {r["cliente_id"] for r in data.tables["clientes"]}
    produtos = {r["produto_id"] for r in data.tables["produtos"]}
    lojas = {r["loja_id"] for r in data.tables["lojas"]}

    assert data.tables["vendas"]
    for venda in data.tables["vendas"]:
        assert venda["cliente_id"] in clientes
        assert venda["produto_id"] in produtos
        assert venda["loja_id"] in lojas
        assert params.start <= date.fromisoformat(venda["data_venda"]) <= params.end

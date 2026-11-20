"""Property 26: Filtro de segurança em nível de linha."""
from __future__ import annotations

from hypothesis import given, settings

from platform_lib.governance import rls_filter
from tests.strategies_gov_rls import assignments, sales_rows, user_names


# Feature: fabric-data-ai-platform, Property 26: Filtro de segurança em nível de linha
# **Validates: Requirements 6.5**
@settings(max_examples=100)
@given(sales=sales_rows, user=user_names, user_stores=assignments)
def test_rls_retorna_apenas_vendas_das_lojas_do_usuario(sales, user, user_stores) -> None:
    allowed = {m["loja_id"] for m in user_stores if m["usuario"] == user}
    result = rls_filter(sales, user, user_stores)
    assert result == [r for r in sales if r["loja_id"] in allowed]
    assert all(r["loja_id"] in allowed for r in result)
    if not allowed:
        assert result == []

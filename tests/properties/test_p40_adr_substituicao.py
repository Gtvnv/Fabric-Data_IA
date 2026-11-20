"""Property 40: Substituição de ADR."""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from platform_lib.docs_tools import supersede_adr
from tests.strategies_adr_supersede import adr_numbers, adr_texts, distinct_adr_pairs

# Feature: fabric-data-ai-platform, Property 40: Substituição de ADR
# **Validates: Requirements 11.7**


@settings(max_examples=100)
@given(pair=distinct_adr_pairs())
def test_substituicao_atualiza_a_e_referencia_em_b(pair) -> None:
    (na, ta), (nb, tb) = pair
    new_a, new_b = supersede_adr((na, ta), (nb, tb))

    assert f"Status: substituído por {nb}" in new_a.splitlines()
    assert "Status: aceito" not in new_a and "Status: proposto" not in new_a
    # Restante de A preservado (tudo exceto a linha de status)
    rest_old = [ln for ln in ta.splitlines() if not ln.startswith("Status:")]
    rest_new = [ln for ln in new_a.splitlines() if not ln.startswith("Status:")]
    assert rest_new == rest_old

    assert f"Substitui: {na}" in new_b.splitlines()
    # B preservado, exceto a linha adicionada
    assert [ln for ln in new_b.splitlines() if not ln.startswith("Substitui:")] == tb.splitlines()


@settings(max_examples=100)
@given(pair=distinct_adr_pairs(with_status=False))
def test_substituicao_sem_status_previo_preserva_conteudo(pair) -> None:
    (na, ta), (nb, tb) = pair
    new_a, _ = supersede_adr((na, ta), (nb, tb))
    assert f"Status: substituído por {nb}" in new_a.splitlines()
    assert ta in new_a


@settings(max_examples=100)
@given(n=adr_numbers, data=st.data())
def test_mesmo_numero_levanta_value_error(n: str, data) -> None:
    ta = data.draw(adr_texts(n))
    tb = data.draw(adr_texts(n))
    with pytest.raises(ValueError):
        supersede_adr((n, ta), (n, tb))

"""Property 39: Validação do formato de ADR."""
from __future__ import annotations

from hypothesis import given, settings

from platform_lib.docs_tools import is_valid_adr, validate_adr
from tests.strategies_adr import mutated_adrs, valid_adrs

# Feature: fabric-data-ai-platform, Property 39: Validação do formato de ADR
# **Validates: Requirements 11.3**


@settings(max_examples=100)
@given(adr=valid_adrs)
def test_adr_valido_e_aceito(adr: tuple[str, str, tuple[str, ...]]) -> None:
    number, text, existing = adr
    assert validate_adr(number, text, existing) == []
    assert is_valid_adr(number, text, existing)


@settings(max_examples=100)
@given(adr=mutated_adrs())
def test_adr_mutado_e_rejeitado(adr: tuple[str, str, tuple[str, ...], str]) -> None:
    number, text, existing, _kind = adr
    assert not is_valid_adr(number, text, existing)
    assert validate_adr(number, text, existing)

"""Property 8: Dados exclusivamente fictícios.

**Validates: Requirements 2.8**
"""
from __future__ import annotations

from hypothesis import given, settings

from platform_lib import synth
from tests.strategies_synth_fake import small_fake_params


# Feature: fabric-data-ai-platform, Property 8: Dados exclusivamente fictícios
@settings(max_examples=100, deadline=None)
@given(small_fake_params())
def test_emails_documentos_e_telefones_sao_ficticios(params):
    data = synth.generate(params)
    clientes = data.tables["clientes"]
    assert clientes

    for row in clientes:
        if row["email"] is not None:
            assert synth.is_fictitious_email(row["email"])
        if row["documento"] is not None:
            assert not synth.cpf_check_digits_valid(row["documento"])
        if row["telefone"] is not None:
            assert synth.is_fictitious_phone(row["telefone"])

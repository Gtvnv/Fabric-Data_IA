"""Property 4: Geração determinística e completa.

**Validates: Requirements 2.1, 2.2**
"""
from __future__ import annotations

from hypothesis import given, settings

from platform_lib import synth
from tests.strategies_synth_gen import small_gen_params


# Feature: fabric-data-ai-platform, Property 4: Geração determinística e completa
@settings(max_examples=100, deadline=None)
@given(small_gen_params())
def test_geracao_deterministica_e_completa(params):
    first = synth.generate(params)
    second = synth.generate(params)

    # Cinco entidades, cada uma com pelo menos 1 registro.
    assert set(first.tables) == set(synth.ENTITIES)
    for entity in synth.ENTITIES:
        assert len(first.tables[entity]) >= 1

    # Mesmo parâmetros e semente: conteúdo idêntico registro a registro (inclui ruído).
    assert first.tables.keys() == second.tables.keys()
    for entity in synth.ENTITIES:
        assert first.tables[entity] == second.tables[entity]
    assert first.noise_manifest == second.noise_manifest

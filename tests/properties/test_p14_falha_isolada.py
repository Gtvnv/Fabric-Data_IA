# Feature: fabric-data-ai-platform, Property 14: Falha de uma entidade não interrompe as demais
"""**Validates: Requirements 3.12**"""

from __future__ import annotations

from hypothesis import given, settings

from src.platform_lib.ingestion import STATUS_FAILURE, STATUS_SUCCESS, run_entities
from tests.strategies_ingest_entities import entities_with_failures


@settings(max_examples=100, deadline=None)
@given(data=entities_with_failures())
def test_falha_de_uma_entidade_nao_interrompe_as_demais(data):
    names, failing = data
    processed: list[str] = []

    def runner(ent: str) -> None:
        processed.append(ent)
        if ent in failing:
            raise RuntimeError(f"falha em {ent}")

    result = run_entities(names, runner)

    assert processed == names  # todas processadas, na ordem
    assert set(result.failed) == failing
    assert set(result.succeeded) == set(names) - failing
    assert result.status == (STATUS_FAILURE if failing else STATUS_SUCCESS)

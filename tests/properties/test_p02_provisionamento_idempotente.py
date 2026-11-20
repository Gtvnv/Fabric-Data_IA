"""Property 2: Provisionamento idempotente e incremental.

**Validates: Requirements 1.6, 1.8**
"""

from __future__ import annotations

from collections import Counter

from hypothesis import given, settings
from infra.provision import FakeFabricClient, apply, plan

from tests.strategies_prov_idem import desired_and_existing


# Feature: fabric-data-ai-platform, Property 2: Provisionamento idempotente e incremental
@settings(max_examples=100)
@given(desired_and_existing())
def test_provisionamento_idempotente_e_incremental(case):
    desired, existing = case
    existing_before = list(existing)
    client = FakeFabricClient(existing=existing)

    # O plano contém exatamente os itens ausentes.
    missing = plan(desired, client.list_items())
    assert set(missing) == set(desired) - set(existing)
    assert len(missing) == len(set(missing))

    result = apply(missing, client)
    assert result.failures == []

    # Estado final = desejado (mais itens alheios), sem nomes duplicados.
    final = client.list_items()
    assert set(desired) <= set(final)
    assert set(final) == set(desired) | set(existing)
    assert max(Counter(final).values(), default=1) == 1
    assert max(Counter((i.workspace, i.name) for i in final).values(), default=1) == 1

    # Nenhum item existente foi alterado ou excluído.
    assert final[: len(existing_before)] == existing_before
    assert [c for c in client.create_calls] == missing

    # Segunda aplicação não cria nada.
    calls_before = len(client.create_calls)
    second = plan(desired, client.list_items())
    assert second == []
    assert apply(second, client).created == []
    assert len(client.create_calls) == calls_before
    assert client.list_items() == final

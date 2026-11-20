"""Property 3: Falha de provisionamento preserva o que foi criado.

**Validates: Requirements 1.7**
"""
from __future__ import annotations

from hypothesis import given, settings
from infra.provision import WORKSPACE, FakeFabricClient, apply

from tests.strategies_prov_fail import plan_existing_and_failures


# Feature: fabric-data-ai-platform, Property 3: Falha de provisionamento preserva o que foi criado
@settings(max_examples=100)
@given(plan_existing_and_failures())
def test_falha_de_provisionamento_preserva_o_que_foi_criado(case):
    plan, existing, fail_on = case
    existing_before = list(existing)
    client = FakeFabricClient(existing=existing, fail_on=fail_on)

    result = apply(plan, client)

    # Código de saída != 0 se e somente se houve falha injetada.
    assert (result.exit_code != 0) == bool(fail_on)

    # Nome e causa de cada item que falhou são registrados.
    # Itens de workspace que falhou não são tentados: registram a causa do workspace.
    failed_ws = {i.name for i in plan if i.kind == WORKSPACE and i.name in fail_on}
    recorded = {f.name: f.cause for f in result.failures}
    for item in plan:
        if item.name not in fail_on:
            continue
        assert item.name in recorded
        if item.kind == WORKSPACE or item.workspace not in failed_ws:
            assert fail_on[item.name] in recorded[item.name]
        else:
            assert item.workspace in recorded[item.name]

    # Itens preexistentes permanecem, na mesma ordem e sem alteração.
    final = client.list_items()
    assert final[: len(existing_before)] == existing_before

    # Todos os itens criados com sucesso estão presentes; itens com falha não.
    for item in result.created:
        assert item in final
    for item in plan:
        if item.name in fail_on:
            assert item not in final
            assert item not in result.created

    # Itens do plano sem falha própria e sem workspace falho foram criados.
    for item in plan:
        if item.name not in fail_on and item.workspace not in failed_ws:
            assert item in result.created
            assert item in final
    assert set(final) == set(existing_before) | set(result.created)

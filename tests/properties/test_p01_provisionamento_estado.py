"""Property 1: Estado desejado de provisionamento."""

from __future__ import annotations

from hypothesis import given, settings
from infra.provision import LAKEHOUSE, LAYERS, WAREHOUSE, WORKSPACE, desired_state

from tests.strategies_provisioning import distinct_env_lists


# Feature: fabric-data-ai-platform, Property 1: Estado desejado de provisionamento
# **Validates: Requirements 1.1, 1.2, 1.3**
@settings(max_examples=100)
@given(envs=distinct_env_lists)
def test_estado_desejado_por_ambiente(envs: list[str]) -> None:
    items = desired_state(envs)

    # Nenhum item duplicado e total exato: 1 + 3 + 1 por ambiente
    assert len(items) == len(set(items)) == 5 * len(envs)

    for env in envs:
        ws_items = [i for i in items if i.workspace == f"fdai-{env}"]

        workspaces = [i for i in ws_items if i.kind == WORKSPACE]
        lakehouses = [i for i in ws_items if i.kind == LAKEHOUSE]
        warehouses = [i for i in ws_items if i.kind == WAREHOUSE]

        assert len(workspaces) == 1
        assert env in workspaces[0].name

        assert len(lakehouses) == 3
        for layer in LAYERS:
            matching = [i for i in lakehouses if i.name.startswith(f"lh_{layer}_")]
            assert len(matching) == 1
        assert {i.name for i in lakehouses} == {f"lh_{layer}_{env}" for layer in LAYERS}

        assert len(warehouses) == 1
        assert env in warehouses[0].name

"""Propriedade 27: pendências de governança.

**Validates: Requirements 6.8, 6.9**
"""

from __future__ import annotations

from hypothesis import given, settings

from platform_lib.governance import pending_governance
from tests.strategies_gov_pend import gold_and_catalog


def _expected(tables, catalog):
    index = catalog if isinstance(catalog, dict) else {e["tabela"]: e for e in catalog}
    out = []
    for t in tables:
        e = index.get(t)
        if e is None:
            out.append(t)
            continue
        owner, desc = e["responsavel"], e["descricao"]
        if (
            owner is None
            or owner.strip() == ""
            or desc is None
            or desc.strip() == ""
            or len(desc) > 500
        ):
            out.append(t)
    return out


# Feature: fabric-data-ai-platform, Property 27: Pendências de governança
@settings(max_examples=100)
@given(data=gold_and_catalog())
def test_p27_pendencias_governanca(data):
    tables, catalog = data
    result = pending_governance(tables, catalog)
    assert sorted(result) == sorted(_expected(tables, catalog))
    assert set(result) <= set(tables)

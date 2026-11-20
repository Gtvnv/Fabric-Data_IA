# Feature: fabric-data-ai-platform, Property 16: Quarentena de registros inválidos
"""Property 16: registros inválidos vão para quarentena com motivo, ficam fora da
Silver e nunca interrompem o processamento.

**Validates: Requirements 4.3**
"""

from __future__ import annotations

from hypothesis import given, settings

from platform_lib.silver import to_silver
from tests.strategies_silver_quar import SPEC, bronze_batches


@settings(max_examples=100)
@given(batch=bronze_batches())
def test_p16_quarentena_de_registros_invalidos(batch):
    rows, expected = batch

    result = to_silver(rows, SPEC)  # nunca levanta

    invalid_idx = {i for i, c in enumerate(expected) if c is not None}
    valid_idx = set(range(len(rows))) - invalid_idx

    # quarentena contém exatamente os inválidos, cada um com motivo esperado
    assert len(result.quarantine_rows) == len(invalid_idx)
    assert {q["_idx"] for q in result.quarantine_rows} == invalid_idx
    for q in result.quarantine_rows:
        assert q["_motivo"]
        assert q["_motivos"]
        assert any(m.startswith(expected[q["_idx"]]) for m in q["_motivos"])

    # Silver contém exatamente os válidos (ids únicos => sem dedup)
    assert {s["_idx"] for s in result.silver_rows} == valid_idx
    assert not ({s["_idx"] for s in result.silver_rows} & invalid_idx)

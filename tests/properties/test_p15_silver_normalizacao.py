# Feature: fabric-data-ai-platform, Property 15: Normalização Silver e unicidade por chave
"""Valida: Requisitos 4.2, 4.4.

**Validates: Requirements 4.2, 4.4**
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal

from hypothesis import given, settings

from platform_lib.silver import META_TS, to_silver

from tests.strategies_silver_norm import SPEC_LOWER, SPEC_UPPER, bronze_batches

import hypothesis.strategies as st

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _norm(s: str, case: str) -> str:
    s = s.strip()
    return s.lower() if case == "lower" else s.upper()


@settings(max_examples=100, deadline=None)
@given(batch=bronze_batches(), spec=st.sampled_from([SPEC_UPPER, SPEC_LOWER]))
def test_silver_normaliza_e_unico_por_chave(batch, spec):
    result = to_silver([c.raw for c in batch], spec)

    # Todas as linhas são válidas: nada vai para quarentena.
    assert result.quarantine_rows == []

    # Exatamente uma linha vigente por chave de negócio.
    keys = [r["id"] for r in result.silver_rows]
    assert len(keys) == len(set(keys))

    # Esperado: a linha de maior _ingestion_ts_utc por chave normalizada.
    expected = {}
    for c in batch:
        k = _norm(c.key_raw, spec.text_case)
        ts = datetime.fromisoformat(c.raw[META_TS])
        if k not in expected or ts > expected[k][0]:
            expected[k] = (ts, c)
    assert set(keys) == set(expected)

    for row in result.silver_rows:
        _, c = expected[row["id"]]
        # Texto: trim + caixa uniforme.
        assert row["id"] == row["id"].strip()
        assert row["nome"] == _norm(c.nome_raw, spec.text_case)
        # Tipos.
        assert isinstance(row["valor"], Decimal) and row["valor"] == c.valor
        assert isinstance(row["qtd"], int) and not isinstance(row["qtd"], bool)
        assert row["qtd"] == c.qtd
        # Data em ISO 8601.
        assert isinstance(row["data"], str) and _ISO.match(row["data"])
        assert date.fromisoformat(row["data"]) == c.data
        # Timestamp vigente é o máximo.
        assert row[META_TS] == expected[row["id"]][0]

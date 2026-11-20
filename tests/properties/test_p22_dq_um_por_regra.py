"""Property 22: Um resultado por regra avaliada. Validates: Requirements 5.4"""

from __future__ import annotations

from datetime import UTC, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from platform_lib.dq import evaluate_all, persist_results
from tests.strategies_dq_rules import rules_and_tables


class _Sink:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def write(self, rows: list[dict]) -> None:
        self.rows.extend(rows)


# Feature: fabric-data-ai-platform, Property 22: Um resultado por regra avaliada
@settings(max_examples=100)
@given(data=rules_and_tables(), now=st.datetimes(timezones=st.just(UTC)))
def test_p22_um_resultado_por_regra(data, now):
    """**Validates: Requirements 5.4**"""
    rules, tables = data
    results = evaluate_all(rules, tables, now)
    sink = _Sink()
    persist_results(results, sink)

    assert len(sink.rows) == len(rules)
    by_name = {r["regra"]: r for r in sink.rows}
    assert len(by_name) == len(rules)
    for rule, res in zip(rules, results, strict=True):
        row = by_name[rule.name]
        assert row["tabela"] == rule.table
        assert row["severidade"] == rule.severity
        assert row["avaliados"] == len(tables[rule.table])
        assert row["violacoes"] == res.violations >= 0
        assert row["executado_em_utc"].utcoffset() == timedelta(0)
        assert row["executado_em_utc"] == now

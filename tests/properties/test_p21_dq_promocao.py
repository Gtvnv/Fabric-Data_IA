# Feature: fabric-data-ai-platform, Property 21: Decisão de promoção da qualidade
"""**Validates: Requirements 5.2, 5.3**"""

from __future__ import annotations

from hypothesis import given, settings

from platform_lib.dq import decide_promotion
from tests.strategies_dq_promo import rule_result_lists


@settings(max_examples=100)
@given(results=rule_result_lists)
def test_p21_decisao_promocao(results):
    decision = decide_promotion(results)
    expected_failed = tuple(
        (r.rule, r.table) for r in results if r.severity == "blocking" and r.violations >= 1
    )
    blocked = any(r.severity == "blocking" and r.violations >= 1 for r in results)
    assert decision.promote is (not blocked)
    assert decision.failed_rules == expected_failed
    # Alertas nunca bloqueiam: sem regras blocking com violação, promove.
    only_warnings = [r for r in results if r.severity == "warning"]
    assert decide_promotion(only_warnings).promote is True

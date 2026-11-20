"""Estratégias para a Property 21 (decisão de promoção da qualidade)."""

from __future__ import annotations

from datetime import UTC, datetime

from hypothesis import strategies as st

from platform_lib.dq import SEVERITIES, RuleResult

_names = st.text(alphabet="abcdefghij_", min_size=1, max_size=8)


@st.composite
def rule_results(draw) -> RuleResult:
    evaluated = draw(st.integers(min_value=0, max_value=1000))
    violations = draw(st.integers(min_value=0, max_value=evaluated))
    return RuleResult(
        rule=draw(_names),
        table=draw(_names),
        severity=draw(st.sampled_from(SEVERITIES)),
        evaluated=evaluated,
        violations=violations,
        ts_utc=datetime(2024, 1, 1, tzinfo=UTC),
    )


rule_result_lists = st.lists(rule_results(), min_size=0, max_size=20)

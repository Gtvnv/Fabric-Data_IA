# Feature: fabric-data-ai-platform, Property 36: Exclusão mútua de execuções
"""Valida Req. 9.4."""
from __future__ import annotations

from hypothesis import given, settings

from platform_lib.orchestration import can_start
from tests.strategies_orch_lock import active_runs, non_empty_active_runs


@settings(max_examples=100)
@given(runs=active_runs)
def test_can_start_false_iff_active_run_exists(runs):
    """**Validates: Requirements 9.4**"""
    assert can_start(runs) is (len(runs) == 0)


@settings(max_examples=100)
@given(runs=non_empty_active_runs)
def test_can_start_false_with_any_active_run(runs):
    """**Validates: Requirements 9.4**"""
    assert can_start(iter(runs)) is False


def test_can_start_true_without_active_runs():
    assert can_start([]) is True

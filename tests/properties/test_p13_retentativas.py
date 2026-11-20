# Feature: fabric-data-ai-platform, Property 13: Retentativas com limite
"""**Validates: Requirements 3.8, 10.3**"""
from __future__ import annotations

from hypothesis import given, settings

from src.platform_lib.ingestion import run_with_retry
from src.platform_lib.orchestration import StepRecord, notify_failure
from tests.strategies_retry import error_messages, failures_before_success


class _Flaky:
    def __init__(self, k: int, msg: str):
        self.k, self.msg, self.calls = k, msg, 0

    def __call__(self):
        self.calls += 1
        if self.calls <= self.k:
            raise RuntimeError(f"{self.msg}#{self.calls}")
        return "ok"


@settings(max_examples=100)
@given(k=failures_before_success, msg=error_messages)
def test_run_with_retry_limite(k, msg):
    waits: list[float] = []
    op = _Flaky(k, msg)
    res = run_with_retry(op, retries=3, wait_s=60, sleep=waits.append)
    assert op.calls == min(k + 1, 4)
    if k <= 3:
        assert res.ok and res.value == "ok" and res.error is None
        assert res.attempts == k + 1
        assert waits == [60] * k
    else:
        assert not res.ok and res.attempts == 4
        assert isinstance(res.error, RuntimeError) and str(res.error) == f"{msg}#4"
        assert waits == [60] * 3


@settings(max_examples=100)
@given(k=failures_before_success, msg=error_messages)
def test_notify_failure_retentativas(k, msg):
    waits: list[float] = []
    logs: list[dict] = []
    calls = {"n": 0}

    def notifier(_m):
        calls["n"] += 1
        if calls["n"] <= k:
            raise RuntimeError(msg)

    rec = StepRecord(etapa="bronze", status="falha", erro="x")
    ok = notify_failure(notifier, rec, sleep=waits.append, logger=logs.append)
    assert calls["n"] == min(k + 1, 4)
    assert ok == (k <= 3)
    assert waits == [60] * min(k, 3)
    assert bool(logs) == (not ok)

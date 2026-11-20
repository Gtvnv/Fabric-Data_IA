# Feature: fabric-data-ai-platform, Property 35: Execução ordenada e interrupção na falha
"""**Validates: Requirements 9.1, 9.2, 9.3, 9.5**"""
from __future__ import annotations

from hypothesis import given, settings

from src.platform_lib.orchestration import (
    STATUS_FAILED,
    STATUS_NOT_RUN,
    STATUS_SUCCESS,
    STEPS,
    run_pipeline,
)
from tests.strategies_orch_order import step_outcomes


@settings(max_examples=100)
@given(outcomes=step_outcomes)
def test_execucao_ordenada_e_interrupcao(outcomes):
    calls: list[str] = []
    active = 0
    max_active = 0

    def make(step, outcome):
        def runner():
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            calls.append(step)
            try:
                if outcome == "fail":
                    raise RuntimeError(f"falha em {step}")
                return outcome
            finally:
                active -= 1

        return runner

    runners = {s: make(s, o) for s, o in zip(STEPS, outcomes)}
    audited = []
    records = run_pipeline(runners, audit=audited.append)

    first_fail = next((i for i, o in enumerate(outcomes) if o == "fail"), None)
    expected_n = len(STEPS) if first_fail is None else first_fail + 1

    # 9.1: ordem de STEPS, uma por vez, sem executar após a falha (9.2)
    assert calls == STEPS[:expected_n]
    assert max_active == 1

    # 9.5: um registro de auditoria por etapa, na ordem
    assert [r.etapa for r in records] == STEPS
    assert audited == records

    for i, rec in enumerate(records):
        if first_fail is not None and i > first_fail:
            assert rec.status == STATUS_NOT_RUN
            assert rec.inicio is None and rec.termino is None
        elif i == first_fail:
            assert rec.status == STATUS_FAILED
            assert rec.erro
            assert rec.inicio is not None and rec.termino is not None
        else:
            assert rec.status == STATUS_SUCCESS
            assert rec.registros == outcomes[i]
            assert rec.inicio is not None and rec.termino is not None
            assert rec.inicio <= rec.termino

# Feature: fabric-data-ai-platform, Property 37: Reexecução a partir da etapa que falhou
"""**Validates: Requirements 9.10**"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from src.platform_lib.orchestration import (
    STATUS_FAILED,
    STATUS_NOT_RUN,
    STATUS_SUCCESS,
    STEPS,
    StepRecord,
    resume_point,
    run_pipeline,
)
from tests.strategies_orch_resume import (
    failed_index,
    non_success_status,
    rerun_outcomes,
    run_ids,
)


def _prior(k: int, status_k: str, later: list[str]) -> list[StepRecord]:
    recs = []
    for i, step in enumerate(STEPS):
        if i < k:
            st_ = STATUS_SUCCESS
        elif i == k:
            st_ = status_k
        else:
            st_ = later[i - k - 1]
        recs.append(StepRecord(etapa=step, status=st_))
    return recs


@settings(max_examples=100)
@given(
    k=failed_index,
    status_k=non_success_status,
    later=st.lists(non_success_status, min_size=len(STEPS), max_size=len(STEPS)),
    outcomes=rerun_outcomes,
    original=run_ids,
    use_start_from=st.booleans(),
)
def test_reexecucao_a_partir_da_etapa_que_falhou(
    k, status_k, later, outcomes, original, use_start_from
):
    prior = _prior(k, status_k, later)

    # resume_point retorna a primeira etapa com status != sucesso.
    assert resume_point(prior) == STEPS[k]

    calls: list[str] = []

    def make(step, outcome):
        def runner():
            calls.append(step)
            if outcome == "fail":
                raise RuntimeError("falha")
            return outcome

        return runner

    runners = {s: make(s, o) for s, o in zip(STEPS, outcomes)}
    if use_start_from:
        recs = run_pipeline(runners, start_from=resume_point(prior), run_id="novo",
                            original_run_id=original)
    else:
        recs = run_pipeline(runners, prior_statuses=prior, run_id="novo",
                            original_run_id=original)

    # Etapas anteriores não são reexecutadas.
    assert not set(calls) & set(STEPS[:k])
    assert [r.etapa for r in recs] == STEPS
    for r in recs[:k]:
        assert r.status == STATUS_SUCCESS and r.reutilizada

    # A execução recomeça em k e segue a regra de parada na primeira falha.
    expected_calls = []
    for step, outcome in list(zip(STEPS, outcomes))[k:]:
        expected_calls.append(step)
        if outcome == "fail":
            break
    assert calls == expected_calls

    # Todo registro referencia a execução original.
    assert all(r.execucao_original == original for r in recs)
    for r in recs[k + len(expected_calls):]:
        assert r.status == STATUS_NOT_RUN
    if outcomes[k:] and "fail" in outcomes[k:]:
        assert any(r.status == STATUS_FAILED for r in recs)


@settings(max_examples=100)
@given(original=run_ids)
def test_tudo_sucesso_nada_reexecutado(original):
    prior = [StepRecord(etapa=s, status=STATUS_SUCCESS) for s in STEPS]
    assert resume_point(prior) is None
    calls: list[str] = []
    runners = {s: (lambda s=s: calls.append(s) or 1) for s in STEPS}
    recs = run_pipeline(runners, prior_statuses=prior, original_run_id=original)
    assert calls == []
    assert all(r.execucao_original == original for r in recs)

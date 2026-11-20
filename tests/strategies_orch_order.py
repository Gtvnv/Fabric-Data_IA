"""Estratégias para a Property 35 (execução ordenada e interrupção na falha)."""
from __future__ import annotations

from hypothesis import strategies as st
from src.platform_lib.orchestration import STEPS

# Por etapa: inteiro 0..1000 = sucesso com esse número de registros; "fail" = falha.
step_outcomes = st.lists(
    st.one_of(st.integers(min_value=0, max_value=1000), st.just("fail")),
    min_size=len(STEPS),
    max_size=len(STEPS),
)

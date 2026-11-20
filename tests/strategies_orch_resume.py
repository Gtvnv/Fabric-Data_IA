"""Estratégias para a Property 37 (reexecução a partir da etapa que falhou)."""
from __future__ import annotations

from hypothesis import strategies as st

from src.platform_lib.orchestration import STEPS

failed_index = st.integers(min_value=0, max_value=len(STEPS) - 1)
run_ids = st.text(alphabet="abcdef0123456789-", min_size=1, max_size=12)
# Por etapa da reexecução: inteiro = sucesso com esse nº de registros; "fail" = falha.
rerun_outcomes = st.lists(
    st.one_of(st.integers(min_value=0, max_value=1000), st.just("fail")),
    min_size=len(STEPS),
    max_size=len(STEPS),
)
# Status da etapa falha na execução original (qualquer status != sucesso) e das posteriores.
non_success_status = st.sampled_from(["falha", "não executada"])

"""Estratégias para a exclusão mútua de execuções (Property 36)."""
from __future__ import annotations

from hypothesis import strategies as st

run_ids = st.text(alphabet="abcdef0123456789", min_size=1, max_size=12)

# Qualquer conjunto (possivelmente vazio) de execuções ativas.
active_runs = st.lists(run_ids, max_size=10)

# Conjuntos não vazios de execuções ativas.
non_empty_active_runs = st.lists(run_ids, min_size=1, max_size=10)

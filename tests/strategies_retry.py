"""Estratégias para a Property 13 (retentativas com limite)."""
from __future__ import annotations

from hypothesis import strategies as st

# k = número de falhas iniciais; 0..6 cobre sucesso (k<=3) e falha final (k>=4).
failures_before_success = st.integers(min_value=0, max_value=6)
error_messages = st.text(min_size=1, max_size=20)
wait_values = st.sampled_from([60, 60.0])

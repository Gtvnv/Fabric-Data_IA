"""Estratégias para a pontuação em lote (Property 32)."""

from __future__ import annotations

from datetime import UTC, datetime

from hypothesis import strategies as st

feature_rows = st.lists(
    st.fixed_dictionaries(
        {
            "id": st.integers(min_value=1, max_value=10**6),
            "x": st.integers(min_value=-1000, max_value=1000),
            "y": st.floats(min_value=-1000, max_value=1000, allow_nan=False),
        }
    ),
    max_size=50,
)

model_names = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=20
)
versions = st.integers(min_value=1, max_value=1000)
utc_times = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2100, 1, 1),
    timezones=st.just(UTC),
)
run_ids = st.text(alphabet="abcdef0123456789", min_size=1, max_size=12)

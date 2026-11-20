"""Estratégias para RLS (Property 26)."""

from __future__ import annotations

from hypothesis import strategies as st

from tests.strategies import money

store_ids = st.integers(min_value=1, max_value=8)
user_names = st.sampled_from(["ana", "bruno", "carla", "diego"])

sales_rows = st.lists(
    st.fixed_dictionaries(
        {
            "venda_id": st.integers(min_value=1, max_value=10_000),
            "loja_id": store_ids,
            "valor": money(),
        }
    ),
    max_size=30,
)

assignments = st.lists(
    st.fixed_dictionaries({"usuario": user_names, "loja_id": store_ids}),
    max_size=20,
)

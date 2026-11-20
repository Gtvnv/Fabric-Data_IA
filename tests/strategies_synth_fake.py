"""Estratégias Hypothesis para datasets pequenos, com ou sem ruído (Property 8)."""

from __future__ import annotations

from datetime import date, timedelta

from hypothesis import strategies as st

from platform_lib.synth import GenParams, NoiseParams


@st.composite
def small_fake_params(draw) -> GenParams:
    start = draw(st.dates(min_value=date(2000, 1, 1), max_value=date(2090, 12, 31)))
    end = start + timedelta(days=draw(st.integers(0, 400)))
    pct = st.floats(min_value=0.0, max_value=0.20, allow_nan=False)
    noise = draw(
        st.one_of(
            st.none(),
            st.builds(NoiseParams, dup_pct=pct, null_pct=pct, bad_date_pct=pct),
        )
    )
    return GenParams(
        seed=draw(st.integers(0, 2_147_483_647)),
        n_customers=draw(st.integers(1, 30)),
        n_products=draw(st.integers(1, 10)),
        n_stores=draw(st.integers(1, 5)),
        start=start,
        end=end,
        noise=noise,
    )

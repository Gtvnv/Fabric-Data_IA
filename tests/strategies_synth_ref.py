"""Estratégias Hypothesis para a integridade referencial (Property 6): sem ruído, tamanhos pequenos."""

from __future__ import annotations

from datetime import date

from hypothesis import strategies as st

from platform_lib import synth


@st.composite
def small_clean_params(draw) -> synth.GenParams:
    start = draw(st.dates(min_value=date(2000, 1, 1), max_value=date(2090, 12, 31)))
    span = draw(st.integers(0, 400))
    end = date.fromordinal(start.toordinal() + span)
    return synth.validate(
        {
            "seed": draw(st.integers(synth.SEED_MIN, synth.SEED_MAX)),
            "n_customers": draw(st.integers(1, 15)),
            "n_products": draw(st.integers(1, 10)),
            "n_stores": draw(st.integers(1, 5)),
            "start": start,
            "end": end,
            "noise": None,
        }
    )

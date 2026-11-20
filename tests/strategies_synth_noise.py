"""Estratégias Hypothesis para as contagens de ruído (Property 7): tamanhos pequenos."""
from __future__ import annotations

from datetime import date

from hypothesis import strategies as st

from platform_lib import synth

_pct = st.floats(0.0, synth.NOISE_MAX)


@st.composite
def small_noisy_params(draw, with_noise: bool | None = None) -> synth.GenParams:
    """Parâmetros pequenos; `with_noise` None sorteia, True/False força."""
    start = draw(st.dates(min_value=date(2000, 1, 1), max_value=date(2090, 12, 31)))
    end = date.fromordinal(start.toordinal() + draw(st.integers(0, 400)))
    enabled = draw(st.booleans()) if with_noise is None else with_noise
    noise = (
        draw(st.builds(synth.NoiseParams, dup_pct=_pct, null_pct=_pct, bad_date_pct=_pct))
        if enabled
        else None
    )
    return synth.validate(
        {
            "seed": draw(st.integers(synth.SEED_MIN, synth.SEED_MAX)),
            "n_customers": draw(st.integers(1, 40)),
            "n_products": draw(st.integers(1, 20)),
            "n_stores": draw(st.integers(1, 8)),
            "start": start,
            "end": end,
            "noise": noise,
        }
    )

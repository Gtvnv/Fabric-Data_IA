"""Estratégias para a regra de promoção do modelo candidato (Property 31)."""

from __future__ import annotations

from hypothesis import strategies as st

_metric = st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False)
_unit = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

demand_metrics = st.fixed_dictionaries({"MAE": _metric, "RMSE": _metric})
churn_metrics = st.fixed_dictionaries({"AUC": _unit, "F1": _unit})

kinds = st.sampled_from(["demanda", "churn"])


@st.composite
def promo_cases(draw):
    """Retorna (kind, candidato, produção)."""
    kind = draw(kinds)
    strat = demand_metrics if kind == "demanda" else churn_metrics
    return kind, draw(strat), draw(strat)

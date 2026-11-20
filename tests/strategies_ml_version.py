"""Estratégias para a Property 30 (versionamento e falha de registro de modelo)."""
from __future__ import annotations

from hypothesis import strategies as st
from platform_lib.ml.registry import CHURN, DEMAND, REQUIRED_METRICS

# Versões existentes: lista possivelmente vazia, com repetições e fora de ordem.
existing_versions = st.lists(st.integers(min_value=1, max_value=10_000), max_size=30)

model_kinds = st.sampled_from([DEMAND, CHURN])

# Valores de métrica não calculáveis.
bad_metric_values = st.sampled_from([float("nan"), float("inf"), float("-inf"), None])


@st.composite
def valid_metrics(draw, kind: str) -> dict[str, float]:
    return {
        m: draw(st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False))
        for m in REQUIRED_METRICS[kind]
    }


@st.composite
def uncomputable_metrics(draw, kind: str) -> dict[str, float | None]:
    """Métricas com ao menos uma exigida ausente, nula ou não finita."""
    metrics = draw(valid_metrics(kind))
    required = REQUIRED_METRICS[kind]
    broken = draw(st.lists(st.sampled_from(required), min_size=1, unique=True))
    for name in broken:
        if draw(st.booleans()):
            del metrics[name]
        else:
            metrics[name] = draw(bad_metric_values)
    return metrics


training_errors = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")), min_size=1, max_size=20
)

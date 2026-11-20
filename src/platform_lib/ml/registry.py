"""Divisão treino/teste, versionamento e promoção de modelos (Req. 7.2, 7.4, 7.5, 7.6).

Python puro, sem dependência de MLflow ou Spark. O registro real de modelos
fica nos notebooks; aqui está a lógica de decisão testável.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

SEED = 42
TRAIN_FRAC = 0.8

DEMAND = "demanda"
CHURN = "churn"

# Métricas exigidas por tipo de modelo (Req. 7.3, 7.4).
REQUIRED_METRICS: dict[str, tuple[str, ...]] = {
    DEMAND: ("MAE", "RMSE"),
    CHURN: ("AUC", "F1"),
}
# Métrica principal por tipo: (nome, menor_é_melhor) (Req. 7.6).
PRIMARY_METRIC: dict[str, tuple[str, bool]] = {
    DEMAND: ("RMSE", True),
    CHURN: ("AUC", False),
}

Metrics = Mapping[str, float]


def split_train_test(
    ids: Sequence[Any], seed: int = SEED, train_frac: float = TRAIN_FRAC
) -> tuple[list[Any], list[Any]]:
    """Divide ``ids`` em (treino, teste), disjuntos e determinísticos.

    O resultado não depende da ordem de entrada: os ids são ordenados antes do
    embaralhamento com ``random.Random(seed)``. Treino tem ``round(n*frac)``
    elementos (80% por padrão).
    """
    if not 0.0 <= train_frac <= 1.0:
        raise ValueError("train_frac deve estar em [0, 1]")
    try:
        ordered = sorted(ids)
    except TypeError:
        ordered = sorted(ids, key=lambda v: (type(v).__name__, repr(v)))
    random.Random(seed).shuffle(ordered)
    n_train = int(round(len(ordered) * train_frac))
    return ordered[:n_train], ordered[n_train:]


def next_model_version(existing_versions: Sequence[int]) -> int:
    """Próxima versão: ``max + 1``, ou 1 se não há versões (Req. 7.5)."""
    return (max(existing_versions) + 1) if existing_versions else 1


@dataclass(frozen=True)
class PromotionDecision:
    promote: bool
    reason: str
    metric: str
    candidate_value: float | None
    production_value: float | None


def _is_valid(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def should_promote(
    candidate: Metrics, production: Metrics | None, kind: str
) -> PromotionDecision:
    """Decide a promoção pela métrica principal (RMSE demanda; AUC churn).

    Sem produção, promove. Empate promove (RMSE_cand <= RMSE_prod; AUC_cand >=
    AUC_prod). Se o candidato é pior na métrica principal, mantém produção,
    mesmo que melhor nas demais, e o motivo traz os valores comparados.
    """
    if kind not in PRIMARY_METRIC:
        raise ValueError(f"tipo de modelo desconhecido: {kind!r}")
    name, lower_is_better = PRIMARY_METRIC[kind]
    cand = candidate.get(name)
    if not _is_valid(cand):
        raise ValueError(f"métrica {name} do candidato não calculada")
    if production is None:
        return PromotionDecision(
            True, f"sem versão em produção; candidato promovido ({name}={cand})", name, cand, None
        )
    prod = production.get(name)
    if not _is_valid(prod):
        raise ValueError(f"métrica {name} da produção indisponível")
    better = cand <= prod if lower_is_better else cand >= prod
    if better:
        reason = f"candidato promovido: {name} candidato={cand} vs produção={prod}"
    else:
        reason = (
            f"candidato não promovido: {name} candidato={cand} é pior que "
            f"produção={prod}; versão em produção mantida"
        )
    return PromotionDecision(better, reason, name, cand, prod)


@dataclass
class TrainingResult:
    status: str  # "sucesso" | "falha"
    registered_version: int | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    error: str | None = None


def register_if_valid(
    train_fn: Callable[[], Metrics],
    register_fn: Callable[[int], None],
    existing_versions: Sequence[int],
    kind: str,
) -> TrainingResult:
    """Treina e registra o modelo somente se todas as métricas são calculáveis.

    Falha no treino ou métrica ausente/não finita: ``register_fn`` NÃO é
    chamada e o resultado é ``falha`` com a causa (Req. 7.4). Falha ao registrar
    também resulta em ``falha``. Sucesso registra a versão ``max + 1`` (Req. 7.5).
    """
    if kind not in REQUIRED_METRICS:
        raise ValueError(f"tipo de modelo desconhecido: {kind!r}")
    try:
        metrics = dict(train_fn())
    except Exception as exc:  # noqa: BLE001 - qualquer falha de treino marca a execução
        return TrainingResult("falha", error=f"falha no treinamento: {exc}")
    missing = [m for m in REQUIRED_METRICS[kind] if not _is_valid(metrics.get(m))]
    if missing:
        return TrainingResult(
            "falha", error=f"métricas não calculadas: {', '.join(missing)}"
        )
    version = next_model_version(existing_versions)
    try:
        register_fn(version)
    except Exception as exc:  # noqa: BLE001
        return TrainingResult("falha", error=f"falha ao registrar modelo: {exc}")
    return TrainingResult("sucesso", registered_version=version, metrics=metrics)

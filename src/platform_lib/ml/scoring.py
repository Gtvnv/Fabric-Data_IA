"""Pontuação em lote (Req. 7.7, 7.8, 7.9).

`score_batch` gera exatamente uma previsão por registro de entrada, com
`model_name`, `version` e `scored_at_utc`. As previsões são determinísticas: duas
pontuações sobre os mesmos dados e versão diferem apenas em `scored_at_utc`.

`write_predictions` grava em staging e promove de forma atômica; qualquer falha
descarta o staging e preserva as previsões anteriores.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Protocol

Row = dict[str, Any]
Predictions = list[Row]


class ScoringError(Exception):
    """Falha na pontuação ou na gravação das previsões."""


class Model(Protocol):
    def predict(self, rows: Sequence[Mapping[str, Any]]) -> Sequence[Any]:
        """Retorna uma previsão por linha, na mesma ordem."""


class PredictionStore(Protocol):
    def write_staging(self, run_id: str, predictions: Predictions) -> None: ...

    def promote(self, run_id: str) -> None:
        """Substitui atomicamente as previsões vigentes pelas do staging."""

    def discard_staging(self, run_id: str) -> None: ...


def score_batch(
    model: Model,
    features: Sequence[Mapping[str, Any]],
    model_name: str,
    version: int,
    now_utc: datetime,
) -> Predictions:
    """Uma previsão por registro de entrada, na ordem da entrada (Req. 7.7, 7.9)."""
    if now_utc.tzinfo is None or now_utc.utcoffset() is None:
        raise ValueError("now_utc deve ter fuso horário (UTC)")
    scored_at = now_utc.astimezone(UTC)
    rows = [dict(r) for r in features]
    if not rows:
        return []
    values = list(model.predict(rows))
    if len(values) != len(rows):
        raise ScoringError(
            f"modelo retornou {len(values)} previsões para {len(rows)} registros"
        )
    return [
        {
            **row,
            "prediction": value,
            "model_name": model_name,
            "version": version,
            "scored_at_utc": scored_at,
        }
        for row, value in zip(rows, values, strict=True)
    ]


def write_predictions(
    store: PredictionStore, run_id: str, predictions: Predictions
) -> None:
    """Grava em staging e promove atomicamente; em falha, preserva as anteriores (Req. 7.8)."""
    try:
        store.write_staging(run_id, predictions)
        store.promote(run_id)
    except Exception as exc:
        try:
            store.discard_staging(run_id)
        finally:
            raise ScoringError(f"falha ao gravar previsões: {exc}") from exc


class InMemoryPredictionStore:
    """Implementação de referência: `current` só muda na promoção."""

    def __init__(self, current: Predictions | None = None) -> None:
        self.current: Predictions = list(current or [])
        self._staging: dict[str, Predictions] = {}

    def write_staging(self, run_id: str, predictions: Predictions) -> None:
        self._staging[run_id] = [dict(p) for p in predictions]

    def promote(self, run_id: str) -> None:
        self.current = self._staging.pop(run_id)

    def discard_staging(self, run_id: str) -> None:
        self._staging.pop(run_id, None)

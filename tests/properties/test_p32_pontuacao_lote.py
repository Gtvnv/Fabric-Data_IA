# Feature: fabric-data-ai-platform, Property 32: Pontuação em lote completa e determinística
"""Valida Req. 7.7, 7.8, 7.9."""

from __future__ import annotations

import pytest
from hypothesis import given, settings

from platform_lib.ml.scoring import (
    InMemoryPredictionStore,
    ScoringError,
    score_batch,
    write_predictions,
)
from tests.strategies_ml_score import (
    feature_rows,
    model_names,
    run_ids,
    utc_times,
    versions,
)


class DeterministicModel:
    def predict(self, rows):
        return [r["x"] * 2 + r["y"] for r in rows]


class FailingStore(InMemoryPredictionStore):
    def promote(self, run_id):
        raise RuntimeError("falha simulada")


@settings(max_examples=100)
@given(feature_rows, model_names, versions, utc_times, utc_times)
def test_score_batch_completa_e_deterministica(rows, name, version, t1, t2):
    """**Validates: Requirements 7.7, 7.9**"""
    model = DeterministicModel()
    a = score_batch(model, rows, name, version, t1)
    b = score_batch(model, rows, name, version, t2)

    assert len(a) == len(rows) == len(b)
    for p in a:
        assert p["model_name"] == name
        assert p["version"] == version
        assert p["scored_at_utc"] == t1

    strip = lambda ps: [{k: v for k, v in p.items() if k != "scored_at_utc"} for p in ps]
    assert strip(a) == strip(b)


@settings(max_examples=100)
@given(feature_rows, feature_rows, run_ids, utc_times)
def test_falha_na_gravacao_preserva_previsoes_anteriores(prev, new, run_id, now):
    """**Validates: Requirements 7.8**"""
    model = DeterministicModel()
    previous = score_batch(model, prev, "m", 1, now)
    store = FailingStore(previous)
    with pytest.raises(ScoringError):
        write_predictions(store, run_id, score_batch(model, new, "m", 2, now))
    assert store.current == previous

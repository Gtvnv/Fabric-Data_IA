# Feature: fabric-data-ai-platform, Property 31: Regra de promoção do modelo candidato
"""Valida: Requisitos 7.6."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from platform_lib.ml.registry import should_promote
from tests.strategies_ml_promo import churn_metrics, demand_metrics, promo_cases


@settings(max_examples=100)
@given(case=promo_cases())
def test_promocao_pela_metrica_principal(case):
    """**Validates: Requirements 7.6**"""
    kind, cand, prod = case
    d = should_promote(cand, prod, kind)
    if kind == "demanda":
        assert d.promote == (cand["RMSE"] <= prod["RMSE"])
        c, p = cand["RMSE"], prod["RMSE"]
    else:
        assert d.promote == (cand["AUC"] >= prod["AUC"])
        c, p = cand["AUC"], prod["AUC"]
    assert str(c) in d.reason and str(p) in d.reason


@settings(max_examples=100)
@given(cand=demand_metrics, prod=demand_metrics)
def test_pior_na_principal_mantem_producao_mesmo_melhor_nas_outras(cand, prod):
    """**Validates: Requirements 7.6**"""
    # Força MAE melhor e RMSE pior no candidato.
    cand = {"MAE": min(cand["MAE"], prod["MAE"]), "RMSE": cand["RMSE"]}
    if cand["RMSE"] <= prod["RMSE"]:
        return
    assert should_promote(cand, prod, "demanda").promote is False
    c2 = {"AUC": 0.5, "F1": 0.99}
    p2 = {"AUC": 0.9, "F1": 0.1}
    assert should_promote(c2, p2, "churn").promote is False


@settings(max_examples=100)
@given(kind=st.sampled_from(["demanda", "churn"]), data=st.data())
def test_sem_producao_promove(kind, data):
    """**Validates: Requirements 7.6**"""
    cand = data.draw(demand_metrics if kind == "demanda" else churn_metrics)
    d = should_promote(cand, None, kind)
    assert d.promote is True
    assert d.production_value is None

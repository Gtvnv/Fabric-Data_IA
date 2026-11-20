"""Property 28: Granularidade e ausência de dados pessoais nas features."""
from __future__ import annotations

from datetime import date

from hypothesis import given, settings

from platform_lib.ml.features import (
    PII_COLUMNS,
    build_churn_features,
    build_demand_features,
    drop_direct_pii,
)
from tests.strategies_ml_features import gold_data, ref_dates, rows_with_pii

DIRECT_PII = {"nome", "cpf", "email", "telefone", "endereco"}


def _no_pii(rows: list[dict]) -> bool:
    return all(k.lower() not in PII_COLUMNS and k.lower() not in DIRECT_PII for r in rows for k in r)


# Feature: fabric-data-ai-platform, Property 28: Granularidade e ausência de dados pessoais nas features
# **Validates: Requirements 7.1, 7.10**
@settings(max_examples=100)
@given(gold=gold_data)
def test_demand_features_granularidade_e_sem_pii(gold: dict) -> None:
    feats = build_demand_features(gold)
    keys = [(r["sk_produto"], r["sk_loja"], r["data"]) for r in feats]
    assert len(keys) == len(set(keys))
    expected = {
        (r["sk_produto"], r["sk_loja"], date(int(str(r["sk_data"])[:4]), int(str(r["sk_data"])[4:6]), int(str(r["sk_data"])[6:])))
        for r in gold["fato_vendas"]
    }
    assert set(keys) == expected
    assert _no_pii(feats)


# Feature: fabric-data-ai-platform, Property 28: Granularidade e ausência de dados pessoais nas features
# **Validates: Requirements 7.1, 7.10**
@settings(max_examples=100)
@given(gold=gold_data, ref=ref_dates)
def test_churn_features_granularidade_e_sem_pii(gold: dict, ref: date) -> None:
    feats = build_churn_features(gold, ref)
    keys = [(r["sk_cliente"], r["data_ref"]) for r in feats]
    assert len(keys) == len(set(keys))
    assert all(r["data_ref"] == ref for r in feats)
    assert _no_pii(feats)


# Feature: fabric-data-ai-platform, Property 28: Granularidade e ausência de dados pessoais nas features
# **Validates: Requirements 7.1, 7.10**
@settings(max_examples=100)
@given(rows=rows_with_pii())
def test_drop_direct_pii_remove_colunas_pessoais(rows: list[dict]) -> None:
    out = drop_direct_pii(rows)
    assert len(out) == len(rows)
    assert _no_pii(out)
    for before, after in zip(rows, out):
        assert set(after) == {k for k in before if k.lower() not in PII_COLUMNS}

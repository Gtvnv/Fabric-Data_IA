"""Property 29: Divisão treino/teste determinística (Req. 7.2)."""

from __future__ import annotations

from hypothesis import given, settings

from platform_lib.ml.registry import SEED, split_train_test
from tests.strategies_ml_split import id_lists, ids_with_permutation


# Feature: fabric-data-ai-platform, Property 29: Divisão treino/teste determinística
@settings(max_examples=100)
@given(ids=id_lists)
def test_split_disjoint_complete_and_sized(ids):
    """**Validates: Requirements 7.2**"""
    train, test = split_train_test(ids, seed=SEED)
    assert set(train).isdisjoint(test)
    assert sorted(train + test, key=repr) == sorted(ids, key=repr)
    assert len(train) == round(len(ids) * 0.8)
    assert len(test) == len(ids) - len(train)
    assert split_train_test(ids, seed=SEED) == (train, test)


# Feature: fabric-data-ai-platform, Property 29: Divisão treino/teste determinística
@settings(max_examples=100)
@given(data=ids_with_permutation())
def test_split_independent_of_input_order(data):
    """**Validates: Requirements 7.2**"""
    ids, shuffled = data
    assert split_train_test(ids, seed=42) == split_train_test(shuffled, seed=42)

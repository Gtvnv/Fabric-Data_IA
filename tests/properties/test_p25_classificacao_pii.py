# Feature: fabric-data-ai-platform, Property 25: Classificação de dados pessoais
"""Property 25: colunas com dados pessoais (nome, e-mail, documento, telefone) recebem
``dado_pessoal``; as demais ``nao_classificado``.

**Validates: Requirements 6.3**
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from platform_lib.governance import (
    LABEL_NONE,
    LABEL_PERSONAL,
    classify_column,
    classify_columns,
)
from tests.strategies_gov_class import (
    non_pii_column_names,
    pii_column_names,
    pii_content_column,
    plain_samples,
)


@settings(max_examples=100)
@given(name=pii_column_names, values=st.one_of(st.none(), plain_samples))
def test_pii_name_is_personal(name, values):
    assert classify_column(name, values)["sensitivity_label"] == LABEL_PERSONAL


@settings(max_examples=100)
@given(name=non_pii_column_names, values=st.one_of(st.none(), plain_samples))
def test_non_pii_is_not_classified(name, values):
    result = classify_column(name, values)
    assert result["sensitivity_label"] == LABEL_NONE
    assert result["category"] is None


@settings(max_examples=100)
@given(name=non_pii_column_names, values=pii_content_column())
def test_pii_content_is_personal(name, values):
    assert classify_column(name, values)["sensitivity_label"] == LABEL_PERSONAL


@settings(max_examples=100)
@given(
    pii=st.lists(pii_column_names, min_size=1, max_size=4, unique=True),
    other=st.lists(non_pii_column_names, max_size=4, unique=True),
)
def test_classify_columns_labels_each_column(pii, other):
    other = [c for c in other if c not in pii]
    result = classify_columns([*pii, *other])
    assert set(result) == set(pii) | set(other)
    assert all(result[c]["sensitivity_label"] == LABEL_PERSONAL for c in pii)
    assert all(result[c]["sensitivity_label"] == LABEL_NONE for c in other)

"""Property 30: Versionamento e falha de registro de modelo.

**Validates: Requirements 7.4, 7.5**
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from platform_lib.ml.registry import next_model_version, register_if_valid
from tests.strategies_ml_version import (
    existing_versions,
    model_kinds,
    training_errors,
    uncomputable_metrics,
    valid_metrics,
)


# Feature: fabric-data-ai-platform, Property 30: Versionamento e falha de registro de modelo
@settings(max_examples=100)
@given(existing_versions)
def test_next_version_is_max_plus_one(versions):
    expected = max(versions) + 1 if versions else 1
    assert next_model_version(versions) == expected
    assert next_model_version(versions) not in versions


# Feature: fabric-data-ai-platform, Property 30: Versionamento e falha de registro de modelo
@settings(max_examples=100)
@given(existing_versions, st.integers(min_value=1, max_value=10))
def test_versions_strictly_increasing_without_overwrite(versions, n):
    history = list(versions)
    seen = set(history)
    previous = max(history) if history else 0
    for _ in range(n):
        v = next_model_version(history)
        assert v > previous
        assert v not in seen
        history.append(v)
        seen.add(v)
        previous = v


# Feature: fabric-data-ai-platform, Property 30: Versionamento e falha de registro de modelo
@settings(max_examples=100)
@given(st.data(), existing_versions, model_kinds)
def test_success_registers_next_version(data, versions, kind):
    metrics = data.draw(valid_metrics(kind))
    calls: list[int] = []
    result = register_if_valid(lambda: metrics, calls.append, versions, kind)
    assert result.status == "sucesso"
    assert calls == [next_model_version(versions)]
    assert result.registered_version == calls[0]


# Feature: fabric-data-ai-platform, Property 30: Versionamento e falha de registro de modelo
@settings(max_examples=100)
@given(st.data(), existing_versions, model_kinds)
def test_uncomputable_metric_does_not_register(data, versions, kind):
    metrics = data.draw(uncomputable_metrics(kind))
    calls: list[int] = []
    result = register_if_valid(lambda: metrics, calls.append, versions, kind)
    assert result.status == "falha"
    assert calls == []
    assert result.registered_version is None
    assert result.error


# Feature: fabric-data-ai-platform, Property 30: Versionamento e falha de registro de modelo
@settings(max_examples=100)
@given(existing_versions, model_kinds, training_errors)
def test_training_failure_does_not_register(versions, kind, message):
    calls: list[int] = []

    def train():
        raise RuntimeError(message)

    result = register_if_valid(train, calls.append, versions, kind)
    assert result.status == "falha"
    assert calls == []
    assert result.registered_version is None
    assert message in result.error

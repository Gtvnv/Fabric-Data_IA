# Feature: fabric-data-ai-platform, Property 24: Round trip e rejeição de configuração de regras
"""**Validates: Requirements 5.7, 5.8**"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml
from hypothesis import given, settings

from src.platform_lib.dq import Rule, RulesConfigError, load_rules
from tests.strategies_dq_cfg import invalid_rule_sets, valid_rule_sets


def _expected(d: dict) -> Rule:
    return Rule(
        d["name"],
        d["table"],
        d["type"],
        tuple(d["columns"]),
        d["severity"],
        d.get("ref_table"),
        tuple(d.get("ref_columns", ())),
    )


@settings(max_examples=100)
@given(rules=valid_rule_sets())
def test_roundtrip(rules):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "rules.yaml"
        p.write_text(yaml.safe_dump({"rules": rules}), encoding="utf-8")
        assert load_rules(p) == [_expected(d) for d in rules]


@settings(max_examples=100)
@given(case=invalid_rule_sets())
def test_invalid_rule_rejected(case):
    rules, name, _field = case
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "rules.yaml"
        p.write_text(yaml.safe_dump({"rules": rules}), encoding="utf-8")
        with pytest.raises(RulesConfigError) as ei:
            load_rules(p)
        assert name in str(ei.value)


@settings(max_examples=100)
@given(rules=valid_rule_sets())
def test_missing_or_unreadable_file(rules):
    with tempfile.TemporaryDirectory() as tmp:
        missing = Path(tmp) / "nao_existe.yaml"
        with pytest.raises(RulesConfigError) as ei:
            load_rules(missing)
        assert str(missing) in str(ei.value)
        # ilegível: diretório no lugar do arquivo
        with pytest.raises(RulesConfigError):
            load_rules(Path(tmp))

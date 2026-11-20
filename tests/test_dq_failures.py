"""Testes unitários de falha de gravação e de configuração (Req. 5.5, 5.8)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from platform_lib.dq import (
    RuleResult,
    RulesConfigError,
    WriteError,
    load_rules,
    persist_results,
)


class FailingSink:
    def write(self, rows):
        raise OSError("sink indisponível")


def _result() -> RuleResult:
    return RuleResult("r1", "t", "blocking", 3, 1, datetime(2024, 1, 1, tzinfo=UTC))


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "rules.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def _rule(**overrides: str) -> str:
    fields = {
        "name": "r1",
        "table": "t",
        "type": "not_null",
        "severity": "blocking",
    }
    fields.update(overrides)
    lines = [f"  - {k}: {v}" if i == 0 else f"    {k}: {v}" for i, (k, v) in enumerate(fields.items())]
    return "rules:\n" + "\n".join(lines) + "\n    columns: [a]\n"


def test_persist_results_sink_failure_raises_write_error():
    with pytest.raises(WriteError):
        persist_results([_result()], FailingSink())


def test_load_rules_missing_file_raises(tmp_path):
    with pytest.raises(RulesConfigError):
        load_rules(tmp_path / "nao_existe.yaml")


def test_load_rules_valid_rule_ok(tmp_path):
    assert len(load_rules(_write(tmp_path, _rule()))) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"type": "bogus"},
        {"table": "''"},
        {"severity": "critical"},
    ],
)
def test_load_rules_invalid_rule_raises(tmp_path, overrides):
    with pytest.raises(RulesConfigError):
        load_rules(_write(tmp_path, _rule(**overrides)))

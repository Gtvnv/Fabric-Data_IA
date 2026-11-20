"""Verificacao_Qualidade: motor de regras declarativas (YAML) em Python puro.

Linhas são ``dict``; tabelas são ``Mapping[str, Sequence[Row]]``.
Requisitos: 5.1-5.5, 5.7, 5.8.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import yaml

Row = dict[str, Any]

RULE_TYPES = ("unique", "not_null", "referential")
SEVERITIES = ("blocking", "warning")


class RulesConfigError(ValueError):
    """Arquivo de regras ausente, ilegível ou com regra inválida (Req. 5.8)."""


class WriteError(RuntimeError):
    """Falha ao gravar a tabela de resultados (Req. 5.5)."""


class ResultSink(Protocol):
    def write(self, rows: list[Row]) -> None: ...


@dataclass(frozen=True)
class Rule:
    name: str
    table: str
    type: str
    columns: tuple[str, ...]
    severity: str
    ref_table: str | None = None
    ref_columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuleResult:
    rule: str
    table: str
    severity: str
    evaluated: int
    violations: int
    ts_utc: datetime


@dataclass(frozen=True)
class Decision:
    promote: bool
    failed_rules: tuple[tuple[str, str], ...] = field(default_factory=tuple)  # (regra, tabela)


def _as_columns(value: Any, label: str, rule_name: str) -> tuple[str, ...]:
    if isinstance(value, str):
        value = [value]
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(c, str) and c for c in value)
    ):
        raise RulesConfigError(f"regra '{rule_name}': '{label}' inválido")
    return tuple(value)


def _parse_rule(raw: Any, index: int) -> Rule:
    if not isinstance(raw, dict):
        raise RulesConfigError(f"regra #{index}: entrada inválida")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise RulesConfigError(f"regra #{index}: nome inválido")
    table = raw.get("table")
    if not isinstance(table, str) or not table.strip():
        raise RulesConfigError(f"regra '{name}': tabela inválida")
    rtype = raw.get("type")
    if rtype not in RULE_TYPES:
        raise RulesConfigError(f"regra '{name}': tipo inválido ({rtype!r})")
    severity = raw.get("severity")
    if severity not in SEVERITIES:
        raise RulesConfigError(f"regra '{name}': severidade inválida ({severity!r})")
    columns = _as_columns(raw.get("columns"), "columns", name)
    ref_table: str | None = None
    ref_columns: tuple[str, ...] = ()
    if rtype == "referential":
        ref_table = raw.get("ref_table")
        if not isinstance(ref_table, str) or not ref_table.strip():
            raise RulesConfigError(f"regra '{name}': ref_table inválida")
        ref_columns = _as_columns(raw.get("ref_columns"), "ref_columns", name)
        if len(ref_columns) != len(columns):
            raise RulesConfigError(f"regra '{name}': columns e ref_columns de tamanhos diferentes")
    return Rule(name, table, rtype, columns, severity, ref_table, ref_columns)


def load_rules(path: str | Path) -> list[Rule]:
    """Carrega regras do YAML; qualquer problema levanta RulesConfigError (Req. 5.7, 5.8)."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RulesConfigError(f"arquivo de regras ausente ou ilegível: {p} ({exc})") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RulesConfigError(f"arquivo de regras ilegível: {p} ({exc})") from exc
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
        raise RulesConfigError(f"arquivo de regras inválido (chave 'rules' ausente): {p}")
    rules = [_parse_rule(raw, i) for i, raw in enumerate(data["rules"], start=1)]
    names = [r.name for r in rules]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        raise RulesConfigError(f"nomes de regra duplicados: {sorted(dup)}")
    return rules


def _tuple_of(row: Mapping[str, Any], cols: Sequence[str]) -> tuple:
    return tuple(row.get(c) for c in cols)


def _table(tables: Mapping[str, Sequence[Row]], name: str) -> Sequence[Row]:
    if name not in tables:
        raise KeyError(f"tabela não encontrada: {name}")
    return tables[name]


def evaluate(
    rule: Rule, tables: Mapping[str, Sequence[Row]], now_utc: datetime | None = None
) -> RuleResult:
    """Avalia uma regra. Violações: unique = linhas excedentes por chave repetida;
    not_null = linhas com algum nulo; referential = linhas com FK não nula sem pai."""
    rows = _table(tables, rule.table)
    if rule.type == "unique":
        seen: set[tuple] = set()
        violations = 0
        for r in rows:
            k = _tuple_of(r, rule.columns)
            if k in seen:
                violations += 1
            else:
                seen.add(k)
    elif rule.type == "not_null":
        violations = sum(1 for r in rows if any(r.get(c) is None for c in rule.columns))
    else:
        parents = {
            _tuple_of(r, rule.ref_columns) for r in _table(tables, rule.ref_table or "")
        }
        violations = 0
        for r in rows:
            k = _tuple_of(r, rule.columns)
            if any(v is None for v in k):
                continue
            if k not in parents:
                violations += 1
    return RuleResult(
        rule=rule.name,
        table=rule.table,
        severity=rule.severity,
        evaluated=len(rows),
        violations=violations,
        ts_utc=(now_utc or datetime.now(UTC)).astimezone(UTC),
    )


def evaluate_all(
    rules: Iterable[Rule], tables: Mapping[str, Sequence[Row]], now_utc: datetime | None = None
) -> list[RuleResult]:
    return [evaluate(r, tables, now_utc) for r in rules]


def decide_promotion(results: Iterable[RuleResult]) -> Decision:
    """Bloqueia se alguma regra blocking tem violações >= 1; alertas só registram (Req. 5.2, 5.3)."""
    failed = tuple(
        (r.rule, r.table) for r in results if r.severity == "blocking" and r.violations >= 1
    )
    return Decision(promote=not failed, failed_rules=failed)


def persist_results(results: Iterable[RuleResult], sink: ResultSink, run_id: str | None = None) -> None:
    """Grava 1 linha por regra avaliada, inclusive com 0 violações (Req. 5.4, 5.5)."""
    rows: list[Row] = [
        {
            "regra": r.rule,
            "tabela": r.table,
            "severidade": r.severity,
            "avaliados": r.evaluated,
            "violacoes": r.violations,
            "executado_em_utc": r.ts_utc,
            "run_id": run_id,
        }
        for r in results
    ]
    try:
        sink.write(rows)
    except Exception as exc:
        raise WriteError(f"falha ao gravar resultados de qualidade: {exc}") from exc

"""Lógica pura da Camada_Silver: tipos, ISO 8601, trim/caixa, validação, dedup e quarentena.

Linhas são ``dict``. Requisitos: 4.2, 4.3, 4.4.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

Row = dict[str, Any]

META_TS = "_ingestion_ts_utc"

# Motivos de rejeição
REASON_NULL_KEY = "chave_nula"
REASON_BAD_TYPE = "tipo_nao_convertivel"
REASON_BAD_DATE = "data_inexistente"
REASON_NEGATIVE_SALE = "valor_venda_negativo"

# Tipos suportados em EntitySpec.columns
T_STR = "str"
T_INT = "int"
T_DECIMAL = "decimal"
T_DATE = "date"
T_TIMESTAMP = "timestamp"

_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_BR_DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_COMPACT_DATE = re.compile(r"^(\d{4})(\d{2})(\d{2})$")


@dataclass(frozen=True)
class EntitySpec:
    """Descrição de uma entidade Silver.

    columns: nome -> tipo (str, int, decimal, date, timestamp). Colunas fora daqui
    (ex.: metadados ``_*``) passam sem conversão.
    key: colunas da chave de negócio.
    non_negative: colunas que não podem ser negativas (ex.: ``valor_venda``).
    text_case: "upper" ou "lower", aplicado a todas as colunas ``str`` não chave técnica.
    """

    name: str
    key: tuple[str, ...]
    columns: Mapping[str, str]
    non_negative: tuple[str, ...] = ()
    text_case: str = "upper"
    ts_col: str = META_TS


@dataclass(frozen=True)
class RejectReason:
    code: str
    column: str | None = None

    def __str__(self) -> str:
        return f"{self.code}:{self.column}" if self.column else self.code


@dataclass
class SilverResult:
    silver_rows: list[Row] = field(default_factory=list)
    quarantine_rows: list[Row] = field(default_factory=list)


class _BadDate(ValueError):
    pass


def _is_blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _parse_date(v: Any) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        s = v.strip()
        for pat, order in (
            (_ISO_DATE, (1, 2, 3)),
            (_BR_DATE, (3, 2, 1)),
            (_COMPACT_DATE, (1, 2, 3)),
        ):
            m = pat.match(s)
            if m:
                y, mo, d = (int(m.group(i)) for i in order)
                try:
                    return date(y, mo, d)
                except ValueError as exc:
                    raise _BadDate(s) from exc
    raise ValueError(f"data não convertível: {v!r}")


def _parse_timestamp(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    if isinstance(v, str):
        s = v.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            pass
        # ISO bem formado só na forma, mas data inexistente
        if re.match(r"^\d{4}-\d{2}-\d{2}", s):
            raise _BadDate(s)
    raise ValueError(f"timestamp não convertível: {v!r}")


def _parse_int(v: Any) -> int:
    if isinstance(v, bool):
        raise ValueError("bool não é int")
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if v.is_integer():
            return int(v)
        raise ValueError("float não inteiro")
    if isinstance(v, Decimal):
        if v == v.to_integral_value():
            return int(v)
        raise ValueError("decimal não inteiro")
    if isinstance(v, str):
        return int(v.strip())
    raise ValueError(f"int não convertível: {v!r}")


def _parse_decimal(v: Any) -> Decimal:
    if isinstance(v, bool):
        raise ValueError("bool não é decimal")
    try:
        if isinstance(v, str):
            d = Decimal(v.strip().replace(",", "."))
        else:
            d = Decimal(str(v)) if isinstance(v, float) else Decimal(v)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"decimal não convertível: {v!r}") from exc
    if not d.is_finite():
        raise ValueError("decimal não finito")
    return d


def _normalize_text(v: Any, case: str) -> str:
    s = str(v).strip()
    return s.lower() if case == "lower" else s.upper()


def _convert(value: Any, col_type: str, case: str) -> Any:
    """Converte um valor não nulo; levanta ValueError/_BadDate."""
    if col_type == T_STR:
        return _normalize_text(value, case)
    if col_type == T_INT:
        return _parse_int(value)
    if col_type == T_DECIMAL:
        return _parse_decimal(value)
    if col_type == T_DATE:
        return _parse_date(value).isoformat()
    if col_type == T_TIMESTAMP:
        return _parse_timestamp(value)
    raise ValueError(f"tipo desconhecido: {col_type}")


def _convert_row(row: Mapping[str, Any], spec: EntitySpec) -> tuple[Row, list[RejectReason]]:
    out: Row = dict(row)
    reasons: list[RejectReason] = []
    for col, col_type in spec.columns.items():
        v = row.get(col)
        if _is_blank(v):
            out[col] = None
            continue
        try:
            out[col] = _convert(v, col_type, spec.text_case)
        except _BadDate:
            reasons.append(RejectReason(REASON_BAD_DATE, col))
        except (ValueError, TypeError, OverflowError):
            reasons.append(RejectReason(REASON_BAD_TYPE, col))
    return out, reasons


def validate_row(row: Mapping[str, Any], entity_spec: EntitySpec) -> list[RejectReason]:
    """Lista os motivos de rejeição (vazia = válido): chave nula, tipo não
    convertível, data inexistente, valor de venda negativo (Req. 4.3)."""
    converted, reasons = _convert_row(row, entity_spec)
    for k in entity_spec.key:
        if _is_blank(converted.get(k)):
            reasons.append(RejectReason(REASON_NULL_KEY, k))
    for col in entity_spec.non_negative:
        v = converted.get(col)
        if isinstance(v, (Decimal, int)) and not isinstance(v, bool) and v < 0:
            reasons.append(RejectReason(REASON_NEGATIVE_SALE, col))
    return reasons


def _key_of(row: Mapping[str, Any], key: str | Sequence[str]) -> tuple:
    cols = (key,) if isinstance(key, str) else tuple(key)
    return tuple(row.get(c) for c in cols)


def dedup_latest(rows: Iterable[Row], key: str | Sequence[str], ts_col: str) -> list[Row]:
    """Uma linha por chave: a de maior ``ts_col``; empate -> a última do lote.

    Ordem de saída: primeira aparição de cada chave.
    """
    best: dict[tuple, Row] = {}
    for r in rows:
        k = _key_of(r, key)
        cur = best.get(k)
        if cur is None or r[ts_col] >= cur[ts_col]:
            best[k] = r
    return [dict(r) for r in best.values()]


def _jsonable(v: Any) -> Any:
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    return v


def to_silver(bronze_rows: Iterable[Mapping[str, Any]], entity_spec: EntitySpec) -> SilverResult:
    """Converte, normaliza, valida e deduplica. Nunca levanta por registro inválido.

    Quarentena: linhas originais (Bronze) + ``_motivo`` (códigos separados por ``;``)
    e ``_motivos`` (lista). Duplicados são removidos só entre os válidos (Req. 4.2-4.4).
    """
    valid: list[Row] = []
    quarantine: list[Row] = []
    for raw in bronze_rows:
        converted, reasons = _convert_row(raw, entity_spec)
        for k in entity_spec.key:
            if _is_blank(converted.get(k)):
                reasons.append(RejectReason(REASON_NULL_KEY, k))
        for col in entity_spec.non_negative:
            v = converted.get(col)
            if isinstance(v, (Decimal, int)) and not isinstance(v, bool) and v < 0:
                reasons.append(RejectReason(REASON_NEGATIVE_SALE, col))
        try:
            # sem data de ingestão válida não há como escolher o vigente
            converted[entity_spec.ts_col] = _parse_timestamp(converted.get(entity_spec.ts_col))
        except (ValueError, TypeError):
            reasons.append(RejectReason(REASON_BAD_TYPE, entity_spec.ts_col))
        if reasons:
            q = {k: _jsonable(v) for k, v in raw.items()}
            q["_motivos"] = [str(r) for r in reasons]
            q["_motivo"] = ";".join(q["_motivos"])
            quarantine.append(q)
        else:
            valid.append(converted)
    silver = dedup_latest(valid, entity_spec.key, entity_spec.ts_col)
    return SilverResult(silver_rows=silver, quarantine_rows=quarantine)

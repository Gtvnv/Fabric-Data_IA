"""Gerador de dados sintéticos: parâmetros e validação (Req. 2.3, 2.4)."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

SEED_MIN, SEED_MAX = 0, 2_147_483_647
CUSTOMERS_MIN, CUSTOMERS_MAX = 1, 1_000_000
PRODUCTS_MIN, PRODUCTS_MAX = 1, 100_000
STORES_MIN, STORES_MAX = 1, 1_000
NOISE_MIN, NOISE_MAX = 0.0, 0.20
MAX_RANGE_YEARS = 5

_INT_LIMITS: dict[str, tuple[int, int]] = {
    "seed": (SEED_MIN, SEED_MAX),
    "n_customers": (CUSTOMERS_MIN, CUSTOMERS_MAX),
    "n_products": (PRODUCTS_MIN, PRODUCTS_MAX),
    "n_stores": (STORES_MIN, STORES_MAX),
}
_NOISE_FIELDS = ("dup_pct", "null_pct", "bad_date_pct")


class ParamError(ValueError):
    """Parâmetro inválido; `param` carrega o nome do parâmetro."""

    param: str

    def __init__(self, param: str, message: str | None = None) -> None:
        self.param = param
        super().__init__(message or f"Parâmetro inválido: {param}")


@dataclass(frozen=True)
class NoiseParams:
    dup_pct: float = 0.0
    null_pct: float = 0.0
    bad_date_pct: float = 0.0


@dataclass(frozen=True)
class GenParams:
    seed: int
    n_customers: int
    n_products: int
    n_stores: int
    start: date
    end: date
    noise: NoiseParams | None = None


def _get_int(raw: Mapping[str, Any], name: str) -> int:
    if name not in raw or raw[name] is None:
        raise ParamError(name, f"Parâmetro ausente: {name}")
    value = raw[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ParamError(name, f"Parâmetro {name} deve ser inteiro")
    low, high = _INT_LIMITS[name]
    if not low <= value <= high:
        raise ParamError(name, f"Parâmetro {name} fora do limite [{low}, {high}]")
    return value


def _get_date(raw: Mapping[str, Any], name: str) -> date:
    if name not in raw or raw[name] is None:
        raise ParamError(name, f"Parâmetro ausente: {name}")
    value = raw[name]
    if isinstance(value, datetime):
        raise ParamError(name, f"Parâmetro {name} deve ser uma data")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ParamError(name, f"Parâmetro {name} deve ser uma data válida")


def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29/02 em ano não bissexto
        return d.replace(year=d.year + years, day=28)


def _get_noise(raw: Mapping[str, Any]) -> NoiseParams | None:
    value = raw.get("noise")
    if value is None:
        return None
    if isinstance(value, NoiseParams):
        data: Mapping[str, Any] = {f: getattr(value, f) for f in _NOISE_FIELDS}
    elif isinstance(value, Mapping):
        data = value
    else:
        raise ParamError("noise", "Parâmetro noise deve ser um mapeamento")
    parsed: dict[str, float] = {}
    for field in _NOISE_FIELDS:
        v = data.get(field, 0.0)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ParamError(field, f"Parâmetro {field} deve ser numérico")
        if math.isnan(v) or not NOISE_MIN <= v <= NOISE_MAX:
            raise ParamError(field, f"Parâmetro {field} fora do limite [0, 0.20]")
        parsed[field] = float(v)
    return NoiseParams(**parsed)


def validate(raw: Mapping[str, Any]) -> GenParams:
    """Valida presença, tipo e limites; levanta `ParamError` com o nome do parâmetro."""
    if not isinstance(raw, Mapping):
        raise ParamError("params", "Parâmetros devem ser um mapeamento")
    ints = {name: _get_int(raw, name) for name in _INT_LIMITS}
    start = _get_date(raw, "start")
    end = _get_date(raw, "end")
    if start > end:
        raise ParamError("start", "Data inicial deve ser menor ou igual à final")
    if end > _add_years(start, MAX_RANGE_YEARS):
        raise ParamError("end", f"Intervalo máximo de {MAX_RANGE_YEARS} anos excedido")
    noise = _get_noise(raw)
    return GenParams(start=start, end=end, noise=noise, **ints)

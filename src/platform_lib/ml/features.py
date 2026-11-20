"""Engenharia de features de demanda e churn (Req. 7.1, 7.10).

Python puro. ``gold`` é um mapeamento de nome de tabela para lista de dicts
(linhas). Apenas chaves substitutas são usadas; nenhum atributo pessoal direto
(nome, CPF, e-mail, telefone, endereço) é propagado.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta
from typing import Any

Row = dict[str, Any]

# Colunas (e prefixos/fragmentos) tratadas como dado pessoal direto.
PII_COLUMNS: frozenset[str] = frozenset(
    {
        "nome",
        "nome_mascarado",
        "nome_cliente",
        "cpf",
        "email",
        "e_mail",
        "telefone",
        "celular",
        "endereco",
        "endereco_completo",
        "logradouro",
        "cep",
    }
)

CHURN_HORIZON_DAYS = 90
_LAGS = (1, 7, 14)
_MA_WINDOWS = (7, 28)


def drop_direct_pii(df: Iterable[Row]) -> list[Row]:
    """Remove colunas de dado pessoal direto de cada linha (Req. 7.10)."""
    return [{k: v for k, v in row.items() if k.lower() not in PII_COLUMNS} for row in df]


def _sk_data_to_date(sk_data: int | str) -> date:
    s = str(int(sk_data))
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def _to_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return _sk_data_to_date(value)


def _row_date(row: Row) -> date:
    if row.get("sk_data") is not None:
        return _sk_data_to_date(row["sk_data"])
    return _to_date(row["data_venda"])


def build_demand_features(gold: Mapping[str, list[Row]]) -> list[Row]:
    """1 linha por (sk_produto, sk_loja, data) com lags, médias móveis e calendário.

    Lags e médias usam apenas dias anteriores (sem vazamento do alvo); dias sem
    venda contam como quantidade 0. ``qtd_alvo`` é a quantidade do próprio dia.
    """
    daily: dict[tuple[Any, Any], dict[date, float]] = defaultdict(lambda: defaultdict(float))
    for r in gold.get("fato_vendas", []):
        daily[(r["sk_produto"], r["sk_loja"])][_row_date(r)] += float(r["quantidade"])

    out: list[Row] = []
    for (sk_produto, sk_loja), series in sorted(daily.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        for day in sorted(series):
            row: Row = {
                "sk_produto": sk_produto,
                "sk_loja": sk_loja,
                "data": day,
                "ano": day.year,
                "mes": day.month,
                "dia": day.day,
                "dia_semana": day.weekday(),
                "fim_de_semana": day.weekday() >= 5,
            }
            for lag in _LAGS:
                row[f"lag_{lag}"] = series.get(day - timedelta(days=lag), 0.0)
            for w in _MA_WINDOWS:
                row[f"media_movel_{w}"] = (
                    sum(series.get(day - timedelta(days=i), 0.0) for i in range(1, w + 1)) / w
                )
            row["qtd_alvo"] = series[day]
            out.append(row)
    return out


def build_churn_features(
    gold: Mapping[str, list[Row]],
    ref_date: date,
    horizon_days: int = CHURN_HORIZON_DAYS,
) -> list[Row]:
    """1 linha por (sk_cliente, data_ref): recência, frequência, valor e alvo.

    Considera compras até ``ref_date`` (inclusive). ``churn_alvo`` = 1 quando o
    cliente não compra em (ref_date, ref_date + horizon_days].
    """
    ref_date = _to_date(ref_date)
    limit = ref_date + timedelta(days=horizon_days)
    past: dict[Any, list[tuple[date, float]]] = defaultdict(list)
    future: set[Any] = set()
    for r in gold.get("fato_vendas", []):
        d = _row_date(r)
        sk = r["sk_cliente"]
        if d <= ref_date:
            past[sk].append((d, float(r["valor_venda"])))
        elif d <= limit:
            future.add(sk)

    out: list[Row] = []
    for sk in sorted(past, key=str):
        purchases = past[sk]
        last = max(d for d, _ in purchases)
        out.append(
            {
                "sk_cliente": sk,
                "data_ref": ref_date,
                "recencia_dias": (ref_date - last).days,
                "frequencia": len(purchases),
                "valor_total": round(sum(v for _, v in purchases), 2),
                "churn_alvo": 0 if sk in future else 1,
            }
        )
    return out

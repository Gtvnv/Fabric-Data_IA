"""Lógica pura da camada Gold (dimensões, SCD2, chaves substitutas).

Linhas são ``dict``; testável sem Spark. Fato e agregação (tarefa 7.2) entram
neste mesmo módulo, reutilizando ``UNKNOWN_SK`` e ``build_surrogate_keys``.
Requisitos: 4.5, 4.6, 4.8.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Any

Row = dict[str, Any]
BusinessKey = Any

UNKNOWN_SK = -1
UNKNOWN_LABEL = "Desconhecido"
OPEN_END_DATE = date(9999, 12, 31)

CLIENTE_KEY = "cliente_id"
CLIENTE_SK = "sk_cliente"
_SCD_META = {CLIENTE_SK, "data_inicio", "data_fim", "vigente"}


def _to_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _attrs(row: Mapping[str, Any], key: str) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k != key and k not in _SCD_META}


def unknown_member(sk_col: str, key_col: str, **defaults: Any) -> Row:
    """Membro padrão 'Desconhecido' com ``sk = -1`` (Req. 4.6)."""
    return {sk_col: UNKNOWN_SK, key_col: None, **defaults}


def build_dim_cliente_scd2(
    current_dim: Iterable[Mapping[str, Any]],
    incoming_clientes: Iterable[Mapping[str, Any]],
    as_of: date | datetime | str,
    *,
    key: str = CLIENTE_KEY,
) -> list[Row]:
    """Aplica SCD2 a ``dim_cliente`` (Req. 4.8).

    Alteração de atributos fecha a versão vigente (``data_fim = as_of - 1 dia``,
    ``vigente = False``) e abre outra (``data_inicio = as_of``,
    ``data_fim = 9999-12-31``, ``vigente = True``). Chaves novas abrem a primeira
    versão. Chaves ausentes em ``incoming_clientes`` permanecem inalteradas.
    O membro 'Desconhecido' (sk = -1) é preservado e não é versionado.
    Se a versão vigente já começa em ``as_of``, ela é atualizada no lugar, para
    evitar intervalo invertido; ``as_of`` anterior ao início vigente é erro.
    """
    as_of_d = _to_date(as_of)
    dim: list[Row] = [dict(r) for r in current_dim]
    for r in dim:
        for col in ("data_inicio", "data_fim"):
            if r.get(col) is not None:
                r[col] = _to_date(r[col])

    current_by_key: dict[BusinessKey, Row] = {
        r[key]: r for r in dim if r.get("vigente") and r.get(key) is not None
    }
    next_sk = max((r[CLIENTE_SK] for r in dim if r.get(CLIENTE_SK) is not None), default=0) + 1
    next_sk = max(next_sk, 1)

    # Último registro por chave de negócio na entrada (entrada duplicada não gera 2 versões).
    latest: dict[BusinessKey, Mapping[str, Any]] = {}
    for inc in incoming_clientes:
        if inc.get(key) is not None:
            latest[inc[key]] = inc

    new_rows: list[Row] = []
    for bk, inc in latest.items():
        new_attrs = _attrs(inc, key)
        cur = current_by_key.get(bk)
        if cur is None:
            new_rows.append(_open_version(next_sk, bk, key, new_attrs, as_of_d))
            next_sk += 1
            continue
        if _attrs(cur, key) == new_attrs:
            continue
        start = cur["data_inicio"]
        if as_of_d < start:
            raise ValueError(f"as_of {as_of_d} anterior ao início da versão vigente {start}")
        if as_of_d == start:
            for col in [c for c in cur if c not in _SCD_META and c != key]:
                del cur[col]
            cur.update(new_attrs)
            continue
        cur["data_fim"] = as_of_d - timedelta(days=1)
        cur["vigente"] = False
        new_rows.append(_open_version(next_sk, bk, key, new_attrs, as_of_d))
        next_sk += 1

    return dim + new_rows


def _open_version(sk: int, bk: BusinessKey, key: str, attrs: dict[str, Any], start: date) -> Row:
    return {
        CLIENTE_SK: sk,
        key: bk,
        **attrs,
        "data_inicio": start,
        "data_fim": OPEN_END_DATE,
        "vigente": True,
    }


def build_surrogate_keys(
    dim_rows: Iterable[Mapping[str, Any]],
    key_col: str = CLIENTE_KEY,
    sk_col: str = CLIENTE_SK,
) -> dict[BusinessKey, int]:
    """Mapa chave de negócio -> chave substituta (Req. 4.6).

    Em dimensões SCD2 (linhas com ``vigente``), considera só a versão vigente.
    Ignora o membro 'Desconhecido' (chave de negócio nula / sk = -1).
    """
    out: dict[BusinessKey, int] = {}
    for r in dim_rows:
        bk = r.get(key_col)
        sk = r.get(sk_col)
        if bk is None or sk is None or sk == UNKNOWN_SK:
            continue
        if "vigente" in r and not r["vigente"]:
            continue
        out[bk] = sk
    return out


def _build_simple_dim(
    silver_rows: Iterable[Mapping[str, Any]],
    key_col: str,
    sk_col: str,
    columns: Sequence[str],
    unknown_defaults: Mapping[str, Any],
) -> list[Row]:
    """Dimensão tipo 1: uma linha por chave, sk estável por ordem de chave, + 'Desconhecido'."""
    by_key: dict[BusinessKey, Row] = {}
    for r in silver_rows:
        if r.get(key_col) is not None:
            by_key[r[key_col]] = {c: r.get(c) for c in columns}
    rows = [
        {sk_col: i, **by_key[k]}
        for i, k in enumerate(sorted(by_key, key=lambda x: str(x)), start=1)
    ]
    return [unknown_member(sk_col, key_col, **unknown_defaults), *rows]


def build_dim_produto(silver_produtos: Iterable[Mapping[str, Any]]) -> list[Row]:
    return _build_simple_dim(
        silver_produtos,
        "produto_id",
        "sk_produto",
        ["produto_id", "nome", "categoria", "subcategoria", "preco_lista"],
        {"nome": UNKNOWN_LABEL, "categoria": UNKNOWN_LABEL, "subcategoria": UNKNOWN_LABEL,
         "preco_lista": None},
    )


def build_dim_loja(silver_lojas: Iterable[Mapping[str, Any]]) -> list[Row]:
    return _build_simple_dim(
        silver_lojas,
        "loja_id",
        "sk_loja",
        ["loja_id", "nome", "regiao", "cidade", "uf"],
        {"nome": UNKNOWN_LABEL, "regiao": UNKNOWN_LABEL, "cidade": UNKNOWN_LABEL, "uf": None},
    )


def build_dim_calendario(start: date | str, end: date | str) -> list[Row]:
    """Calendário contínuo de ``start`` a ``end`` (inclusive) + 'Desconhecido'.

    ``sk_data`` = yyyymmdd.
    """
    d0, d1 = _to_date(start), _to_date(end)
    if d1 < d0:
        raise ValueError("end anterior a start")
    rows: list[Row] = [
        {"sk_data": UNKNOWN_SK, "data": None, "ano": None, "trimestre": None, "mes": None,
         "dia": None, "dia_semana": None}
    ]
    d = d0
    while d <= d1:
        rows.append(
            {
                "sk_data": d.year * 10000 + d.month * 100 + d.day,
                "data": d,
                "ano": d.year,
                "trimestre": (d.month - 1) // 3 + 1,
                "mes": d.month,
                "dia": d.day,
                "dia_semana": d.isoweekday(),
            }
        )
        d += timedelta(days=1)
    return rows


def add_unknown_cliente(dim: Iterable[Mapping[str, Any]]) -> list[Row]:
    """Garante o membro 'Desconhecido' (sk = -1) em ``dim_cliente`` (uma única vez)."""
    rows = [dict(r) for r in dim]
    if any(r.get(CLIENTE_SK) == UNKNOWN_SK for r in rows):
        return rows
    unknown = unknown_member(
        CLIENTE_SK, CLIENTE_KEY, nome_mascarado=UNKNOWN_LABEL, cidade=UNKNOWN_LABEL, uf=None,
        data_inicio=date(1900, 1, 1), data_fim=OPEN_END_DATE, vigente=True,
    )
    return [unknown, *rows]

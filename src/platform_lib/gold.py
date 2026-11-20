"""Lógica pura da camada Gold (dimensões, SCD2, chaves substitutas).

Linhas são ``dict``; testável sem Spark. Inclui fato, agregação e estoque.
Requisitos: 4.5, 4.6, 4.7, 4.8, 4.9, 4.11.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
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


# ---------------------------------------------------------------------------
# Fato, agregação e estoque (Req. 4.5, 4.6, 4.7, 4.9, 4.11)
# ---------------------------------------------------------------------------

ZERO = Decimal("0.00")


@dataclass(frozen=True)
class FactResult:
    """Resultado de ``resolve_fact``: linhas do fato e nº de chaves 'Desconhecido'.

    ``unknown_count`` conta registros com ao menos uma chave substituta
    resolvida para ``UNKNOWN_SK`` (cliente, produto, loja ou data).
    """

    rows: list[Row]
    unknown_count: int


def to_decimal(value: Any) -> Decimal:
    """Converte para ``Decimal`` sem passar por float; ``None`` vira 0.00."""
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(str(value).strip().replace(",", "."))


def sk_data_of(value: date | datetime | str | None) -> int:
    """``sk_data`` (yyyymmdd) de uma data; ``UNKNOWN_SK`` se nula/inválida."""
    if value is None:
        return UNKNOWN_SK
    try:
        d = _to_date(value)
    except (ValueError, TypeError):
        return UNKNOWN_SK
    return d.year * 10000 + d.month * 100 + d.day


def _cliente_versions(dim_cliente: Iterable[Mapping[str, Any]]) -> dict[BusinessKey, list[Row]]:
    out: dict[BusinessKey, list[Row]] = {}
    for r in dim_cliente:
        bk, sk = r.get(CLIENTE_KEY), r.get(CLIENTE_SK)
        if bk is None or sk is None or sk == UNKNOWN_SK:
            continue
        out.setdefault(bk, []).append(dict(r))
    return out


def _resolve_cliente_sk(versions: list[Row] | None, sale_date: date | None) -> int:
    """Versão SCD2 que cobre a data da venda; senão a vigente; senão 'Desconhecido'."""
    if not versions:
        return UNKNOWN_SK
    if sale_date is not None:
        for v in versions:
            start, end = v.get("data_inicio"), v.get("data_fim")
            if start is None or end is None:
                continue
            if _to_date(start) <= sale_date <= _to_date(end):
                return v[CLIENTE_SK]
    for v in versions:
        if v.get("vigente"):
            return v[CLIENTE_SK]
    return UNKNOWN_SK


def resolve_fact(
    silver_vendas: Iterable[Mapping[str, Any]],
    dims: Mapping[str, Iterable[Mapping[str, Any]]],
) -> FactResult:
    """Resolve chaves substitutas do fato de vendas (Req. 4.6, 4.7).

    ``dims`` usa as chaves ``dim_cliente``, ``dim_produto``, ``dim_loja`` e,
    opcionalmente, ``dim_calendario`` (se informado, datas fora dele viram
    'Desconhecido'). Sem correspondência -> ``sk = -1``. Valores monetários
    saem como ``Decimal``. Uma linha de fato por venda Silver (a Silver
    já é deduplicada por ``venda_id``), preservando a reconciliação.
    """
    cli = _cliente_versions(dims.get("dim_cliente", ()))
    prod = build_surrogate_keys(dims.get("dim_produto", ()), "produto_id", "sk_produto")
    loja = build_surrogate_keys(dims.get("dim_loja", ()), "loja_id", "sk_loja")
    cal_rows = dims.get("dim_calendario")
    cal = None if cal_rows is None else {r["sk_data"] for r in cal_rows}

    rows: list[Row] = []
    unknown = 0
    for v in silver_vendas:
        try:
            d: date | None = _to_date(v["data_venda"]) if v.get("data_venda") is not None else None
        except (ValueError, TypeError):
            d = None
        sk_data = sk_data_of(d)
        if cal is not None and sk_data not in cal:
            sk_data = UNKNOWN_SK
        sks = {
            "sk_cliente": _resolve_cliente_sk(cli.get(v.get(CLIENTE_KEY)), d),
            "sk_produto": prod.get(v.get("produto_id"), UNKNOWN_SK),
            "sk_loja": loja.get(v.get("loja_id"), UNKNOWN_SK),
            "sk_data": sk_data,
        }
        if UNKNOWN_SK in sks.values():
            unknown += 1
        rows.append(
            {
                "venda_id": v.get("venda_id"),
                **sks,
                "quantidade": int(v["quantidade"]) if v.get("quantidade") is not None else 0,
                "valor_venda": to_decimal(v.get("valor_venda")),
                "custo_total": to_decimal(v.get("custo_total")),
            }
        )
    return FactResult(rows=rows, unknown_count=unknown)


def aggregate_daily(fact_rows: Iterable[Mapping[str, Any]]) -> list[Row]:
    """Agrega o fato por dia, produto e loja (Req. 4.9, 4.11).

    Soma em ``Decimal`` (sem perda), logo ``sum(valor_venda)`` do resultado é
    igual ao do fato e da Silver (diferença 0,00). Saída ordenada pela chave.
    """
    acc: dict[tuple[int, int, int], Row] = {}
    for f in fact_rows:
        k = (f["sk_data"], f["sk_produto"], f["sk_loja"])
        a = acc.get(k)
        if a is None:
            a = acc[k] = {
                "sk_data": k[0], "sk_produto": k[1], "sk_loja": k[2],
                "quantidade": 0, "valor_venda": ZERO, "custo_total": ZERO,
            }
        a["quantidade"] += int(f.get("quantidade") or 0)
        a["valor_venda"] += to_decimal(f.get("valor_venda"))
        a["custo_total"] += to_decimal(f.get("custo_total"))
    return [acc[k] for k in sorted(acc)]


def reconcile_sales(
    silver_vendas: Iterable[Mapping[str, Any]], gold_rows: Iterable[Mapping[str, Any]]
) -> Decimal:
    """Diferença absoluta entre somas de ``valor_venda`` (Silver x Gold); 0.00 = ok."""
    s = sum((to_decimal(r.get("valor_venda")) for r in silver_vendas), ZERO)
    g = sum((to_decimal(r.get("valor_venda")) for r in gold_rows), ZERO)
    return abs(s - g)


def build_fato_estoque(
    silver_estoque: Iterable[Mapping[str, Any]],
    dims: Mapping[str, Iterable[Mapping[str, Any]]],
) -> FactResult:
    """Fato de posição de estoque (``sk_data``, ``sk_produto``, ``sk_loja``, quantidade).

    Chaves sem correspondência viram 'Desconhecido' (sk = -1) e são contadas.
    """
    prod = build_surrogate_keys(dims.get("dim_produto", ()), "produto_id", "sk_produto")
    loja = build_surrogate_keys(dims.get("dim_loja", ()), "loja_id", "sk_loja")
    cal_rows = dims.get("dim_calendario")
    cal = None if cal_rows is None else {r["sk_data"] for r in cal_rows}

    rows: list[Row] = []
    unknown = 0
    for e in silver_estoque:
        sk_data = sk_data_of(e.get("data_posicao"))
        if cal is not None and sk_data not in cal:
            sk_data = UNKNOWN_SK
        sks = {
            "sk_data": sk_data,
            "sk_produto": prod.get(e.get("produto_id"), UNKNOWN_SK),
            "sk_loja": loja.get(e.get("loja_id"), UNKNOWN_SK),
        }
        if UNKNOWN_SK in sks.values():
            unknown += 1
        qtd = e.get("quantidade_estoque")
        rows.append({**sks, "quantidade_estoque": int(qtd) if qtd is not None else 0})
    return FactResult(rows=rows, unknown_count=unknown)

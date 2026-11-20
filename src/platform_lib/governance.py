"""Governança: classificação de dados pessoais, pendências do catálogo Gold e filtro RLS.

Lógica pura (sem Spark/Purview), espelhando as regras aplicadas na plataforma.
Requisitos: 6.3, 6.5, 6.8, 6.9.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

Row = dict[str, Any]

LABEL_PERSONAL = "dado_pessoal"
LABEL_NONE = "nao_classificado"
LABEL_CONFIDENTIAL = "confidencial"

PII_NAME = "nome"
PII_EMAIL = "email"
PII_DOCUMENT = "documento"
PII_PHONE = "telefone"

MAX_DESCRIPTION_LEN = 500

# Padrões por nome de coluna (tokens normalizados, separados por "_").
_NAME_PATTERNS: dict[str, re.Pattern[str]] = {
    PII_EMAIL: re.compile(r"(^|_)(e_?mail|email)(_|$)"),
    PII_DOCUMENT: re.compile(r"(^|_)(cpf|cnpj|rg|documento|doc)(_|$)"),
    PII_PHONE: re.compile(r"(^|_)(telefone|fone|celular|phone|tel)(_|$)"),
    PII_NAME: re.compile(r"(^|_)(nome|name)(_|$)"),
}

# Padrões por conteúdo (valor inteiro).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CPF_RE = re.compile(r"^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$")
_CNPJ_RE = re.compile(r"^\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}$")
_PHONE_RE = re.compile(r"^(\+?55\s?)?(\(?\d{2}\)?\s?)?9?\d{4}-?\d{4}$")

_CONTENT_MATCHERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (PII_EMAIL, _EMAIL_RE),
    (PII_DOCUMENT, _CPF_RE),
    (PII_DOCUMENT, _CNPJ_RE),
    (PII_PHONE, _PHONE_RE),
)

# Fração mínima de valores não vazios que deve casar para classificar por conteúdo.
CONTENT_MATCH_THRESHOLD = 0.8


def _normalize(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = re.sub(r"[^0-9a-zA-Z]+", "_", text).strip("_").lower()
    return text


def classify_by_name(column_name: str) -> str | None:
    """Categoria de dado pessoal pelo nome da coluna, ou ``None``."""
    norm = _normalize(column_name)
    for category, pattern in _NAME_PATTERNS.items():
        if pattern.search(norm):
            return category
    return None


def classify_by_content(values: Iterable[Any]) -> str | None:
    """Categoria de dado pessoal pelo padrão dos valores, ou ``None``."""
    samples = [str(v).strip() for v in values if v is not None and str(v).strip()]
    if not samples:
        return None
    for category, pattern in _CONTENT_MATCHERS:
        hits = sum(1 for s in samples if pattern.match(s))
        if hits / len(samples) >= CONTENT_MATCH_THRESHOLD:
            return category
    return None


def classify_column(column_name: str, values: Iterable[Any] | None = None) -> dict[str, Any]:
    """Classifica uma coluna por nome e/ou conteúdo (Req. 6.3).

    Retorna ``{"column", "category", "sensitivity_label"}``; ``sensitivity_label`` é
    ``dado_pessoal`` se nome ou conteúdo casar, senão ``nao_classificado``.
    """
    category = classify_by_name(column_name)
    if category is None and values is not None:
        category = classify_by_content(values)
    return {
        "column": column_name,
        "category": category,
        "sensitivity_label": LABEL_PERSONAL if category else LABEL_NONE,
    }


def classify_columns(
    columns: Sequence[str], rows: Iterable[Row] | None = None
) -> dict[str, dict[str, Any]]:
    """Classifica todas as colunas; ``rows`` (opcional) fornece amostra de conteúdo."""
    sample = list(rows) if rows is not None else None
    result: dict[str, dict[str, Any]] = {}
    for col in columns:
        values = [r.get(col) for r in sample] if sample is not None else None
        result[col] = classify_column(col, values)
    return result


def _catalog_index(catalog: Mapping[str, Any] | Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    if isinstance(catalog, Mapping):
        return dict(catalog)
    return {entry.get("tabela"): entry for entry in catalog}


def pending_governance(
    gold_tables: Iterable[str],
    catalog: Mapping[str, Any] | Iterable[Mapping[str, Any]],
) -> list[str]:
    """Tabelas Gold sem responsável, com descrição vazia ou com mais de 500 caracteres.

    ``catalog`` é um mapa ``tabela -> {responsavel, descricao}`` ou uma lista de linhas de
    ``governanca.catalogo_gold``. Tabela ausente do catálogo é pendente (Req. 6.8, 6.9).
    """
    index = _catalog_index(catalog)
    pending: list[str] = []
    for table in gold_tables:
        entry = index.get(table) or {}
        owner = entry.get("responsavel")
        desc = entry.get("descricao")
        no_owner = owner is None or not str(owner).strip()
        bad_desc = desc is None or not str(desc).strip() or len(str(desc)) > MAX_DESCRIPTION_LEN
        if no_owner or bad_desc:
            pending.append(table)
    return pending


def rls_filter(
    sales: Iterable[Row],
    user: str,
    user_stores: Iterable[Mapping[str, Any]],
    store_col: str = "loja_id",
) -> list[Row]:
    """Filtro RLS de referência: só vendas das lojas do usuário em ``usuario_loja``.

    Usuário sem lojas atribuídas recebe zero linhas (Req. 6.5).
    """
    allowed = {m.get("loja_id") for m in user_stores if m.get("usuario") == user}
    allowed.discard(None)
    if not allowed:
        return []
    return [dict(r) for r in sales if r.get(store_col) in allowed]

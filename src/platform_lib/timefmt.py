"""Formatação de data/hora para exibição (America/Sao_Paulo).
Requisito: 8.5.
"""
from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

SAO_PAULO_TZ = "America/Sao_Paulo"
ULTIMA_ATUALIZACAO_TABLE = "config.ultima_atualizacao"
_FORMAT = "%d/%m/%Y %H:%M"


def format_ultima_atualizacao(ts_utc: datetime) -> str:
    """Converte ``ts_utc`` para America/Sao_Paulo e formata ``dd/MM/yyyy HH:mm``.

    Datetime sem fuso é tratado como UTC.
    """
    if ts_utc.tzinfo is None:
        ts_utc = ts_utc.replace(tzinfo=UTC)
    return ts_utc.astimezone(ZoneInfo(SAO_PAULO_TZ)).strftime(_FORMAT)


def build_ultima_atualizacao_row(ts_utc: datetime) -> dict[str, object]:
    """Linha de ``config.ultima_atualizacao`` (``ts_utc``, ``ts_sao_paulo_texto``)."""
    if ts_utc.tzinfo is None:
        ts_utc = ts_utc.replace(tzinfo=UTC)
    return {"ts_utc": ts_utc, "ts_sao_paulo_texto": format_ultima_atualizacao(ts_utc)}

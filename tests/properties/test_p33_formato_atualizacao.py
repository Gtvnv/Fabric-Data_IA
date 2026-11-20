"""Property 33: Formato da data de atualização. Valida: Requisito 8.5."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from hypothesis import given, settings

from platform_lib.timefmt import format_ultima_atualizacao
from tests.strategies_timefmt import any_utc_instant

_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}$")


# Feature: fabric-data-ai-platform, Property 33: Formato da data de atualização
@settings(max_examples=100)
@given(ts=any_utc_instant)
def test_p33_formato_atualizacao(ts: datetime) -> None:
    """**Validates: Requirements 8.5**"""
    texto = format_ultima_atualizacao(ts)
    assert _PATTERN.match(texto)

    # Cálculo independente: via timestamp epoch -> zoneinfo.
    local = datetime.fromtimestamp(ts.timestamp(), tz=ZoneInfo("America/Sao_Paulo"))
    esperado = (
        f"{local.day:02d}/{local.month:02d}/{local.year:04d} "
        f"{local.hour:02d}:{local.minute:02d}"
    )
    assert texto == esperado

    # Consistência: voltar para UTC usando o offset reproduz o instante (minuto).
    dia, resto = texto.split(" ")
    d, m, y = (int(x) for x in dia.split("/"))
    hh, mm = (int(x) for x in resto.split(":"))
    back = datetime(y, m, d, hh, mm, tzinfo=ZoneInfo("America/Sao_Paulo")).astimezone(UTC)
    assert abs((back - ts).total_seconds()) < 3600 + 60

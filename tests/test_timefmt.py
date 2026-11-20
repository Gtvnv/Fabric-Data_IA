import re
from datetime import UTC, datetime

from platform_lib.timefmt import build_ultima_atualizacao_row, format_ultima_atualizacao


def test_converte_utc_para_sao_paulo():
    assert format_ultima_atualizacao(datetime(2024, 6, 1, 15, 30, tzinfo=UTC)) == "01/06/2024 12:30"


def test_virada_de_dia():
    assert format_ultima_atualizacao(datetime(2024, 1, 1, 1, 5, tzinfo=UTC)) == "31/12/2023 22:05"


def test_row_tem_colunas_do_contrato():
    row = build_ultima_atualizacao_row(datetime(2024, 6, 1, 15, 30))
    assert set(row) == {"ts_utc", "ts_sao_paulo_texto"}
    assert re.fullmatch(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", row["ts_sao_paulo_texto"])

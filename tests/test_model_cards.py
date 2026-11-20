"""Verifica as seções obrigatórias dos model cards (Req. 7.11)."""

from pathlib import Path

import pytest

CARDS_DIR = Path(__file__).resolve().parents[1] / "docs" / "model_cards"
SECOES = ["finalidade", "dados de treino", "métricas", "limitações", "riscos de viés"]


@pytest.mark.parametrize("nome", ["previsao_demanda.md", "previsao_churn.md"])
def test_model_card_tem_secoes_obrigatorias(nome: str) -> None:
    texto = (CARDS_DIR / nome).read_text(encoding="utf-8")
    titulos = {
        linha.lstrip("#").strip().lower()
        for linha in texto.splitlines()
        if linha.startswith("## ")
    }
    for secao in SECOES:
        assert secao in titulos, f"{nome}: seção ausente: {secao}"

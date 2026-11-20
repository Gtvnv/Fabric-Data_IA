"""Valida os ADRs reais de ``docs/adr`` com ``docs_tools.validate_adr``.
Requisitos: 3.9, 4.12, 6.10, 7.12, 11.3, 11.4.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from platform_lib.docs_tools import adr_number, validate_adr

ADR_DIR = Path(__file__).resolve().parent.parent / "docs" / "adr"
FILES = sorted(ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md"))

# Temas obrigatórios (Req. 11.4) e palavra-chave esperada no nome do arquivo.
TEMAS = ("fabric", "lakehouse", "medalhao", "ingestao", "governanca", "ml", "ambientes", "seguranca")


def test_adrs_exist_and_sequential():
    nums = [int(adr_number(f.name)) for f in FILES]
    assert nums == list(range(1, len(nums) + 1))
    assert len(nums) >= 8


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_adr_is_valid(path: Path):
    number = adr_number(path.name)
    existing = [str(int(adr_number(f.name))).zfill(4) for f in FILES if f != path]
    # Número esperado = maior existente + 1; para validar cada ADR isoladamente,
    # usamos como "existentes" apenas os de número menor.
    anteriores = [n for n in existing if int(n) < int(number)]
    text = path.read_text(encoding="utf-8")
    assert validate_adr(number, text, anteriores) == []
    assert text.startswith(f"# {number}.")


def test_all_themes_covered():
    names = " ".join(f.name for f in FILES)
    for tema in TEMAS:
        assert tema in names, f"tema sem ADR: {tema}"


def test_governance_adr_has_retention_in_days():
    text = next(f for f in FILES if "governanca" in f.name).read_text(encoding="utf-8")
    assert "Retenção" in text and "(dias)" in text

"""Smoke tests do projeto PBIP (powerbi/fdai.*).

Valida: Requirements 8.1, 8.2, 8.3, 8.5, 8.7.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

POWERBI = Path(__file__).resolve().parents[1] / "powerbi"
MODEL_DIR = POWERBI / "fdai.SemanticModel" / "definition"
REPORT_DIR = POWERBI / "fdai.Report" / "definition"


def _tables() -> dict[str, str]:
    return {p.stem: p.read_text(encoding="utf-8") for p in (MODEL_DIR / "tables").glob("*.tmdl")}


def test_all_partitions_are_direct_lake() -> None:
    """8.1: nenhuma partição Import/DirectQuery."""
    total = 0
    for name, text in _tables().items():
        partitions = re.findall(r"^\tpartition\s+.+$", text, re.M)
        modes = re.findall(r"^\t\tmode:\s*(\S+)\s*$", text, re.M)
        assert partitions, f"{name}: sem partição"
        assert len(modes) == len(partitions), f"{name}: partição sem mode"
        assert all(m == "directLake" for m in modes), f"{name}: modo {modes}"
        total += len(partitions)
    assert total >= 1
    for forbidden in ("mode: import", "mode: directQuery", "= m\n"):
        assert not any(forbidden.lower() in t.lower() for t in _tables().values())


def test_direct_lake_only_behavior() -> None:
    """8.1: sem fallback para DirectQuery."""
    model = (MODEL_DIR / "model.tmdl").read_text(encoding="utf-8")
    assert re.search(r"^\tdirectLakeBehavior:\s*directLakeOnly\s*$", model, re.M)


def test_exactly_five_report_pages() -> None:
    """8.2: o relatório tem exatamente cinco páginas."""
    pages = json.loads((REPORT_DIR / "pages" / "pages.json").read_text(encoding="utf-8"))
    order = pages["pageOrder"]
    assert len(order) == 5 and len(set(order)) == 5
    page_dirs = {p.parent.name for p in (REPORT_DIR / "pages").glob("*/page.json")}
    assert page_dirs == set(order)


def test_required_measures_present() -> None:
    """8.3: medidas Receita Total, Quantidade, Margem, Ticket Medio, Variacao YoY."""
    text = "\n".join(_tables().values())
    names = {(m[0] or m[1]) for m in re.findall(r"^\tmeasure\s+(?:'([^']+)'|(\w+))\s*=", text, re.M)}
    for expected in ("Receita Total", "Quantidade", "Margem", "Ticket Medio", "Variacao YoY"):
        assert expected in names, f"medida ausente: {expected}"


def test_three_hierarchies_present() -> None:
    """8.3: hierarquias Calendario, Produto e Loja."""
    text = "\n".join(_tables().values())
    names = set(re.findall(r"^\thierarchy\s+(?:'([^']+)'|(\w+))\s*$", text, re.M))
    flat = {a or b for a, b in names}
    assert {"Calendario", "Produto", "Loja"} <= flat
    assert len(flat) == 3


def test_rls_role_present() -> None:
    """8.5: papel RLS definido e referenciado no modelo."""
    role = (MODEL_DIR / "roles" / "rls_loja.tmdl").read_text(encoding="utf-8")
    assert re.search(r"^role\s+rls_loja\s*$", role, re.M)
    assert "tablePermission" in role and "USERPRINCIPALNAME()" in role
    assert "ref role rls_loja" in (MODEL_DIR / "model.tmdl").read_text(encoding="utf-8")


def test_no_convert_tz_under_powerbi() -> None:
    """8.7: nenhum arquivo em powerbi/ usa CONVERT_TZ."""
    offenders = []
    for p in POWERBI.rglob("*"):
        if p.is_file():
            try:
                content = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if "convert_tz" in content.lower():
                offenders.append(str(p.relative_to(POWERBI)))
    assert not offenders, offenders

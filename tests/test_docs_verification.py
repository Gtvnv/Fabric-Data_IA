"""Verificação da documentação (Req. 10.4, 10.5, 11.1, 11.2, 11.6, 7.11).

Checagem estrutural pragmática: não depende do mermaid-cli.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.test_model_cards import CARDS_DIR, SECOES

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

MERMAID_TYPES = (
    "flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram",
    "erDiagram", "gantt", "journey", "pie", "C4Context",
)
PARES = {")": "(", "]": "[", "}": "{"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _mermaid_blocks(texto: str) -> list[str]:
    return re.findall(r"```mermaid\n(.*?)```", texto, flags=re.DOTALL)


def _check_mermaid(bloco: str) -> list[str]:
    erros: list[str] = []
    linhas = [ln for ln in bloco.splitlines() if ln.strip() and not ln.strip().startswith("%%")]
    if not linhas:
        return ["diagrama vazio"]
    if not linhas[0].strip().startswith(MERMAID_TYPES):
        erros.append(f"declaração de tipo ausente: {linhas[0]!r}")
    if bloco.count('"') % 2:
        erros.append("aspas desbalanceadas")
    sem_aspas = re.sub(r'"[^"\n]*"', '""', bloco)
    pilha: list[str] = []
    for ch in sem_aspas:
        if ch in "([{":
            pilha.append(ch)
        elif ch in PARES:
            if not pilha or pilha.pop() != PARES[ch]:
                erros.append(f"delimitador desbalanceado: {ch!r}")
                break
    if pilha:
        erros.append(f"delimitadores não fechados: {pilha}")
    subgraphs = sum(1 for ln in linhas if ln.strip().startswith("subgraph"))
    ends = sum(1 for ln in linhas if ln.strip() == "end")
    if subgraphs != ends:
        erros.append(f"subgraph ({subgraphs}) != end ({ends})")
    return erros


def test_diagramas_tres_blocos_mermaid_validos() -> None:
    blocos = _mermaid_blocks(_read(DOCS / "diagramas.md"))
    assert len(blocos) == 3
    for i, bloco in enumerate(blocos, 1):
        assert _check_mermaid(bloco) == [], f"diagrama {i} inválido"


def test_verificador_mermaid_detecta_defeitos() -> None:
    assert _check_mermaid("flowchart LR\n A[x --> B") != []
    assert _check_mermaid('flowchart LR\n A["x] --> B') != []
    assert _check_mermaid("flowchart LR\n subgraph S\n A --> B") != []
    assert _check_mermaid("A --> B") != []


def _secoes_h2(texto: str) -> dict[str, str]:
    partes = re.split(r"^## (.+)$", texto, flags=re.MULTILINE)
    return {partes[i].strip(): partes[i + 1] for i in range(1, len(partes) - 1, 2)}


def test_readme_secoes_obrigatorias() -> None:
    secoes = {t.lower() for t in _secoes_h2(_read(ROOT / "README.md"))}
    for esperado in ("cenário", "pré-requisitos", "estrutura do repositório"):
        assert any(s.startswith(esperado) for s in secoes), esperado
    assert any(s.startswith("passos de execução") for s in secoes)


def test_readme_passos_numerados_ate_validacao_gold() -> None:
    secoes = _secoes_h2(_read(ROOT / "README.md"))
    chave = next(k for k in secoes if k.lower().startswith("passos de execução"))
    numeros = [int(n) for n in re.findall(r"^(\d+)\. ", secoes[chave], flags=re.MULTILINE)]
    assert numeros == list(range(1, len(numeros) + 1)) and len(numeros) >= 2
    assert "Validar as tabelas Gold" in secoes[chave]


def test_readme_lista_cada_diretorio_de_primeiro_nivel() -> None:
    ignorados = {".git", ".hypothesis", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__"}
    secoes = _secoes_h2(_read(ROOT / "README.md"))
    chave = next(k for k in secoes if k.lower().startswith("estrutura do repositório"))
    corpo = secoes[chave]
    diretorios = [
        p.name for p in ROOT.iterdir()
        if p.is_dir() and p.name not in ignorados and not p.name.endswith(".egg-info")
    ]
    assert diretorios
    for nome in diretorios:
        assert f"`{nome}/`" in corpo, f"diretório sem item no README: {nome}"


def test_runbook_procedimentos_completos() -> None:
    procedimentos = {
        t: c for t, c in _secoes_h2(_read(DOCS / "runbook.md")).items() if re.match(r"\d+\. ", t)
    }
    assert len(procedimentos) >= 3
    for titulo, corpo in procedimentos.items():
        for rotulo in (r"Sintoma", r"Passos", r"Resultado esperado", r"Critério de sucesso"):
            assert re.search(rf"\*\*{rotulo}[^*]*\*\*", corpo), f"{titulo}: falta {rotulo}"


@pytest.mark.parametrize("nome", ["previsao_demanda.md", "previsao_churn.md"])
def test_model_cards_existem_com_secoes(nome: str) -> None:
    # Regra detalhada em tests/test_model_cards.py; aqui só reutiliza as constantes.
    texto = _read(CARDS_DIR / nome).lower()
    for secao in SECOES:
        assert f"## {secao}" in texto, f"{nome}: {secao}"


def test_capacidade_e_custos() -> None:
    texto = _read(DOCS / "capacidade-e-custos.md")
    assert re.search(r"\bSKU\b", texto) and re.search(r"\bF\d+\b", texto)
    assert "R$" in texto and "BRL" in texto
    titulos = " ".join(_secoes_h2(texto)).lower()
    assert "pausa" in titulos and "retomada" in titulos
    assert re.search(r"\d{2}:\d{2}", texto)

"""Ferramentas de documentação: validação de ADR, substituição de ADR e cobertura do dicionário.
Requisitos: 11.3, 11.5, 11.7, 11.8.

Formato do ADR (``docs/adr/NNNN-titulo.md``)::

    # NNNN. Título
    Status: aceito            (ou ``Status: substituído por NNNN``)
    Substitui: NNNN           (opcional; presente no ADR substituto)
    Data: AAAA-MM-DD

    ## Contexto
    ## Decisão
    ## Alternativas consideradas
    - alternativa 1
    - alternativa 2
    ## Consequências

Formato esperado do esquema Gold (``config/gold_schema.yaml``, criado na tarefa 7.3).
Este módulo recebe o esquema já carregado como argumento (``Mapping``)::

    tables:
      dim_produto:
        columns:
          produto_id: {tipo: bigint, descricao: "Chave natural", sensibilidade: interna}

Também é aceita a forma sem a chave ``tables`` (``{tabela: {columns: {...}}}``) e
``columns`` como lista de ``{nome, tipo, descricao, sensibilidade}``.

O dicionário é uma sequência de linhas (``Mapping``) com as chaves
``tabela``, ``coluna``, ``tipo``, ``descricao`` e ``sensibilidade``.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

SENSIBILIDADES = ("pública", "interna", "confidencial", "restrita")
REQUIRED_SECTIONS = ("contexto", "decisão", "consequências")
MIN_ALTERNATIVES = 2
DICT_FIELDS = ("tipo", "descricao", "sensibilidade")

_NUMBER_RE = re.compile(r"^\d{4}$")
_FILENAME_RE = re.compile(r"^(\d{4})(?:-.*)?(?:\.md)?$")
_STATUS_RE = re.compile(r"^(status)\s*:\s*(.*)$", re.IGNORECASE | re.MULTILINE)
_DATE_RE = re.compile(r"^data\s*:\s*(\S.*)$", re.IGNORECASE | re.MULTILINE)
_HEADING_RE = re.compile(r"^#{1,6}\s*(.+?)\s*$", re.MULTILINE)
_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S", re.MULTILINE)


def adr_number(name: str) -> str | None:
    """Extrai o número de 4 dígitos do nome (``0001-titulo.md``); ``None`` se inválido."""
    m = _FILENAME_RE.match(name)
    return m.group(1) if m else None


def _sections(text: str) -> dict[str, str]:
    heads = list(_HEADING_RE.finditer(text))
    out: dict[str, str] = {}
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        key = h.group(1).strip().rstrip(":").lower()
        out.setdefault(key, text[h.end():end])
    return out


def validate_adr(number: str, text: str, existing_numbers: Iterable[str] = ()) -> list[str]:
    """Valida um ADR; devolve a lista de problemas (vazia = válido).

    ``existing_numbers`` são os números dos demais ADRs do diretório; o número deve
    ser o seguinte ao maior existente (``1`` se não houver nenhum).
    """
    problems: list[str] = []
    if not _NUMBER_RE.match(number):
        problems.append("numeração deve ter 4 dígitos")
    else:
        nums = [int(n) for n in existing_numbers if _NUMBER_RE.match(n)]
        expected = (max(nums) + 1) if nums else 1
        if int(number) != expected:
            problems.append(f"numeração não sequencial: esperado {expected:04d}, obtido {number}")
    status = _STATUS_RE.search(text)
    if not status or not status.group(2).strip():
        problems.append("status ausente")
    if not _DATE_RE.search(text):
        problems.append("data ausente")
    secs = _sections(text)
    for name in REQUIRED_SECTIONS:
        if not secs.get(name, "").strip():
            problems.append(f"seção ausente ou vazia: {name}")
    alt_body = next((v for k, v in secs.items() if k.startswith("alternativas")), "")
    if len(_ITEM_RE.findall(alt_body)) < MIN_ALTERNATIVES:
        problems.append(f"alternativas consideradas: mínimo de {MIN_ALTERNATIVES}")
    return problems


def is_valid_adr(number: str, text: str, existing_numbers: Iterable[str] = ()) -> bool:
    return not validate_adr(number, text, existing_numbers)


def supersede_adr(
    adr_a: tuple[str, str], adr_b: tuple[str, str]
) -> tuple[str, str]:
    """Substitui o ADR A pelo B. Cada ADR é ``(numero, texto)``.

    Devolve ``(texto_a, texto_b)``: A recebe ``Status: substituído por B`` e B recebe
    ``Substitui: A``. O restante do conteúdo de A é preservado.
    """
    num_a, text_a = adr_a
    num_b, text_b = adr_b
    if num_a == num_b:
        raise ValueError("um ADR não pode substituir a si mesmo")

    new_status = f"Status: substituído por {num_b}"
    if _STATUS_RE.search(text_a):
        new_a = _STATUS_RE.sub(new_status, text_a, count=1)
    else:
        new_a = f"{new_status}\n{text_a}"

    ref = f"Substitui: {num_a}"
    ref_re = re.compile(r"^substitui\s*:.*$", re.IGNORECASE | re.MULTILINE)
    if ref_re.search(text_b):
        new_b = ref_re.sub(ref, text_b, count=1)
    else:
        m = _STATUS_RE.search(text_b)
        if m:
            new_b = text_b[: m.end()] + f"\n{ref}" + text_b[m.end():]
        else:
            new_b = f"{ref}\n{text_b}"
    return new_a, new_b


def _columns(table: Any) -> list[str]:
    cols = table.get("columns", {}) if isinstance(table, Mapping) else {}
    if isinstance(cols, Mapping):
        return [str(c) for c in cols]
    return [str(c["nome"]) for c in cols if isinstance(c, Mapping) and "nome" in c]


def validate_data_dictionary(
    schema: Mapping[str, Any], entries: Iterable[Mapping[str, Any]]
) -> list[str]:
    """Valida a cobertura do dicionário contra o esquema Gold; devolve problemas (vazia = válido).

    Toda coluna de toda tabela deve ter entrada com ``tipo``, ``descricao`` e
    ``sensibilidade`` preenchidos, e ``sensibilidade`` em ``SENSIBILIDADES``.
    """
    tables = schema.get("tables", schema)
    index: dict[tuple[str, str], Mapping[str, Any]] = {}
    for e in entries:
        index[(str(e.get("tabela", "")), str(e.get("coluna", "")))] = e
    problems: list[str] = []
    for table, spec in tables.items():
        for col in _columns(spec):
            entry = index.get((str(table), col))
            if entry is None:
                problems.append(f"{table}.{col}: sem entrada no dicionário")
                continue
            for f in DICT_FIELDS:
                v = entry.get(f)
                if v is None or not str(v).strip():
                    problems.append(f"{table}.{col}: campo ausente ou vazio: {f}")
            sens = entry.get("sensibilidade")
            if sens is not None and str(sens).strip() and sens not in SENSIBILIDADES:
                problems.append(f"{table}.{col}: sensibilidade inválida: {sens}")
    return problems


def is_dictionary_covered(
    schema: Mapping[str, Any], entries: Iterable[Mapping[str, Any]]
) -> bool:
    return not validate_data_dictionary(schema, list(entries))

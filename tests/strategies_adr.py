"""Estratégias para o formato de ADR (Property 39). Reutilizável por outras propriedades de ADR."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from hypothesis import strategies as st

# Palavras simples, sem ':', '#', '-' ou quebras de linha (não criam seções/itens/status falsos).
_word = st.text(alphabet="abcdefghijklmnopqrstuvwxyzáéíóúçãõ", min_size=3, max_size=10)
_sentence = st.lists(_word, min_size=1, max_size=6).map(" ".join)
_title = _sentence

STATUS_VALUES = ("proposto", "aceito", "rejeitado", "obsoleto")
SECTION_DROPS = ("status", "data", "contexto", "decisão", "consequências")


@dataclass(frozen=True)
class AdrParts:
    number: str  # 4 dígitos
    existing: tuple[str, ...]  # números dos demais ADRs
    title: str
    status: str
    data: str
    contexto: str
    decisao: str
    alternativas: tuple[str, ...]
    consequencias: str

    def render(self) -> str:
        lines = [f"# {self.number}. {self.title}"]
        if self.status:
            lines.append(f"Status: {self.status}")
        if self.data:
            lines.append(f"Data: {self.data}")
        lines.append("")
        if self.contexto is not None:
            lines += ["## Contexto", self.contexto, ""]
        if self.decisao is not None:
            lines += ["## Decisão", self.decisao, ""]
        lines.append("## Alternativas consideradas")
        lines += [f"- {a}" for a in self.alternativas]
        lines.append("")
        if self.consequencias is not None:
            lines += ["## Consequências", self.consequencias, ""]
        return "\n".join(lines)


@st.composite
def valid_adr_parts(draw) -> AdrParts:
    """ADR válido: número sequencial de 4 dígitos, todas as seções e >= 2 alternativas."""
    existing = draw(st.lists(st.integers(1, 9000), max_size=8, unique=True))
    number = (max(existing) + 1) if existing else 1
    return AdrParts(
        number=f"{number:04d}",
        existing=tuple(f"{n:04d}" for n in existing),
        title=draw(_title),
        status=draw(st.sampled_from(STATUS_VALUES)),
        data=draw(st.dates(date(2000, 1, 1), date(2100, 12, 31)).map(date.isoformat)),
        contexto=draw(_sentence),
        decisao=draw(_sentence),
        alternativas=tuple(draw(st.lists(_sentence, min_size=2, max_size=6))),
        consequencias=draw(_sentence),
    )


valid_adrs = valid_adr_parts().map(lambda p: (p.number, p.render(), p.existing))


def drop_section(parts: AdrParts, name: str) -> tuple[str, str, tuple[str, ...]]:
    """Remove uma seção/campo obrigatório e renderiza."""
    if name in ("status", "data"):
        p = replace(parts, **{name: ""})
    else:
        field = {"contexto": "contexto", "decisão": "decisao", "consequências": "consequencias"}[name]
        p = replace(parts, **{field: None})
    return p.number, p.render(), p.existing


@st.composite
def mutated_adrs(draw) -> tuple[str, str, tuple[str, ...], str]:
    """ADR inválido: (numero, texto, existentes, tipo_da_mutação)."""
    parts = draw(valid_adr_parts())
    kind = draw(st.sampled_from(("drop", "few_alternatives", "wrong_number")))
    if kind == "drop":
        n, t, e = drop_section(parts, draw(st.sampled_from(SECTION_DROPS)))
        return n, t, e, kind
    if kind == "few_alternatives":
        k = draw(st.integers(0, 1))
        p = replace(parts, alternativas=parts.alternativas[:k])
        return p.number, p.render(), p.existing, kind
    expected = int(parts.number)
    bad = draw(
        st.one_of(
            st.integers(0, 9999).filter(lambda n: n != expected).map(lambda n: f"{n:04d}"),  # não sequencial
            st.integers(1, 99999).map(str).filter(lambda s: len(s) != 4),  # não tem 4 dígitos
        )
    )
    p = replace(parts, number=bad)
    return p.number, p.render(), p.existing, kind

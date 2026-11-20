"""Estratégias Hypothesis para a substituição de ADR (autocontidas)."""
from __future__ import annotations

from hypothesis import strategies as st

adr_numbers = st.integers(min_value=1, max_value=9999).map(lambda n: f"{n:04d}")

_word = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=10)
_phrase = st.lists(_word, min_size=1, max_size=5).map(" ".join)


@st.composite
def adr_texts(draw, number: str, with_status: bool = True) -> str:
    """ADR válido no formato de docs_tools."""
    titulo = draw(_phrase)
    status = draw(st.sampled_from(["aceito", "proposto"]))
    lines = [f"# {number}. {titulo}"]
    if with_status:
        lines.append(f"Status: {status}")
    lines += [
        "Data: 2025-01-15",
        "",
        "## Contexto",
        draw(_phrase),
        "## Decisão",
        draw(_phrase),
        "## Alternativas consideradas",
        f"- {draw(_phrase)}",
        f"- {draw(_phrase)}",
        "## Consequências",
        draw(_phrase),
    ]
    return "\n".join(lines) + "\n"


@st.composite
def distinct_adr_pairs(draw, with_status: bool = True):
    """Dois ADRs ``(numero, texto)`` com números distintos."""
    na, nb = draw(st.lists(adr_numbers, min_size=2, max_size=2, unique=True))
    return (na, draw(adr_texts(na, with_status))), (nb, draw(adr_texts(nb)))

"""Estratégias para a Property 41 (cobertura do dicionário de dados)."""
from __future__ import annotations

from hypothesis import strategies as st

SENS_VALIDAS = ["pública", "interna", "confidencial", "restrita"]

_names = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=8)
_text = st.text(alphabet="abcdefghij klmnop", min_size=1, max_size=15).filter(lambda s: s.strip())

# Valor de campo: preenchido, vazio, em branco ou ausente (None).
_field_value = st.one_of(_text, st.just(""), st.just("   "), st.none())
_sens_value = st.one_of(
    st.sampled_from(SENS_VALIDAS),
    st.sampled_from(SENS_VALIDAS),
    st.sampled_from(["secreta", "publica", "PÚBLICA", "x"]),
    st.just(""),
    st.none(),
)

gold_schemas = st.dictionaries(
    _names, st.lists(_names, min_size=1, max_size=5, unique=True), min_size=1, max_size=4
)


@st.composite
def schema_and_entries(draw, mostly_complete: bool = True):
    """Devolve (schema no formato ``tables``, entradas do dicionário)."""
    raw = draw(gold_schemas)
    schema = {"tables": {t: {"columns": {c: {} for c in cols}} for t, cols in raw.items()}}
    p_ok = 0.7 if mostly_complete else 0.3
    entries = []
    for t, cols in raw.items():
        for c in cols:
            if draw(st.floats(0, 1)) > 0.9:  # coluna sem entrada
                continue
            perfect = draw(st.floats(0, 1)) < p_ok
            if perfect:
                entry = {
                    "tabela": t, "coluna": c,
                    "tipo": draw(_text), "descricao": draw(_text),
                    "sensibilidade": draw(st.sampled_from(SENS_VALIDAS)),
                }
            else:
                entry = {
                    "tabela": t, "coluna": c,
                    "tipo": draw(_field_value), "descricao": draw(_field_value),
                    "sensibilidade": draw(_sens_value),
                }
            entries.append(entry)
    extra = draw(st.booleans())
    if extra:  # entrada órfã não deve afetar a cobertura
        entries.append({"tabela": "zz_orfa", "coluna": "zz", "tipo": "int",
                        "descricao": "d", "sensibilidade": "interna"})
    return schema, entries

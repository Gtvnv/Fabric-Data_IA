"""Estratégias para configuração de regras de qualidade (Property 24)."""

from __future__ import annotations

from hypothesis import strategies as st
from src.platform_lib.dq import RULE_TYPES, SEVERITIES

_ident = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=10)
_cols = st.lists(_ident, min_size=1, max_size=3, unique=True)


@st.composite
def rule_dicts(draw, name: str) -> dict:
    rtype = draw(st.sampled_from(RULE_TYPES))
    cols = draw(_cols)
    d = {
        "name": name,
        "table": draw(_ident),
        "type": rtype,
        "severity": draw(st.sampled_from(SEVERITIES)),
        "columns": cols,
    }
    if rtype == "referential":
        d["ref_table"] = draw(_ident)
        d["ref_columns"] = draw(
            st.lists(_ident, min_size=len(cols), max_size=len(cols), unique=True)
        )
    return d


@st.composite
def valid_rule_sets(draw) -> list[dict]:
    names = draw(st.lists(_ident, min_size=0, max_size=5, unique=True))
    return [draw(rule_dicts(n)) for n in names]


@st.composite
def invalid_rule_sets(draw) -> tuple[list[dict], str, str]:
    """(regras, nome da regra inválida, campo corrompido)."""
    rules = draw(valid_rule_sets())
    name = "bad_rule"
    bad = draw(rule_dicts(name))
    field = draw(st.sampled_from(["type", "table", "severity"]))
    bad[field] = draw(
        st.sampled_from(["", "   ", None, 123, "nope"])
        if field != "table"
        else st.sampled_from(["", "   ", None, 123])
    )
    pos = draw(st.integers(min_value=0, max_value=len(rules)))
    rules.insert(pos, bad)
    return rules, name, field

"""Estratégias para regras de qualidade e suas tabelas (Property 22)."""

from __future__ import annotations

from hypothesis import strategies as st

from platform_lib.dq import SEVERITIES, Rule

_names = st.text(alphabet="abcdefghij", min_size=1, max_size=6)


@st.composite
def rules_and_tables(draw):
    """Regras com nomes únicos (unique/not_null/referential) e tabelas que as satisfazem ou não."""
    table_names = ["t1", "t2", "t3"]
    tables = {
        t: draw(
            st.lists(
                st.fixed_dictionaries(
                    {"a": st.one_of(st.none(), st.integers(0, 4)), "b": st.integers(0, 4)}
                ),
                max_size=8,
            )
        )
        for t in table_names
    }
    names = draw(st.lists(_names, min_size=0, max_size=8, unique=True))
    rules = []
    for n in names:
        rtype = draw(st.sampled_from(["unique", "not_null", "referential"]))
        rules.append(
            Rule(
                name=n,
                table=draw(st.sampled_from(table_names)),
                type=rtype,
                columns=(draw(st.sampled_from(["a", "b"])),),
                severity=draw(st.sampled_from(SEVERITIES)),
                ref_table=draw(st.sampled_from(table_names)) if rtype == "referential" else None,
                ref_columns=("b",) if rtype == "referential" else (),
            )
        )
    return rules, tables

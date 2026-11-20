"""Estratégias para a engenharia de features de ML (Property 28)."""
from __future__ import annotations

from datetime import date

from hypothesis import strategies as st

from platform_lib.ml.features import PII_COLUMNS

_days = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))

pii_values = st.text(min_size=1, max_size=15)


@st.composite
def fato_vendas_rows(draw) -> dict:
    """Linha de fato_vendas; pode carregar colunas PII extras (que não devem vazar)."""
    day = draw(_days)
    row = {
        "sk_produto": draw(st.integers(1, 4)),
        "sk_loja": draw(st.integers(1, 3)),
        "sk_cliente": draw(st.integers(1, 6)),
        "sk_data": int(day.strftime("%Y%m%d")),
        "quantidade": draw(st.integers(1, 20)),
        "valor_venda": draw(st.integers(1, 100_000)) / 100,
    }
    for col in draw(st.sets(st.sampled_from(sorted(PII_COLUMNS)), max_size=4)):
        row[col] = draw(pii_values)
    return row


gold_data = st.fixed_dictionaries(
    {"fato_vendas": st.lists(fato_vendas_rows(), min_size=0, max_size=40)}
)

ref_dates = _days


@st.composite
def rows_with_pii(draw) -> list[dict]:
    """Linhas arbitrárias com colunas permitidas e colunas PII (variando caixa)."""
    safe = st.sampled_from(["sk_cliente", "sk_produto", "valor", "qtd", "data"])
    rows = []
    for _ in range(draw(st.integers(0, 8))):
        row = {c: draw(st.integers(0, 100)) for c in draw(st.sets(safe, max_size=5))}
        for col in draw(st.sets(st.sampled_from(sorted(PII_COLUMNS)), max_size=6)):
            row[draw(st.sampled_from([col, col.upper()]))] = draw(pii_values)
        rows.append(row)
    return rows

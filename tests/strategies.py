"""Estratégias Hypothesis compartilhadas (base).

Valores monetários usam ``decimal.Decimal``, nunca ``float``.
Tarefas que precisem de estratégias específicas criam ``tests/strategies_<area>.py``.
"""

from __future__ import annotations

import string
from datetime import date
from decimal import Decimal

from hypothesis import strategies as st

MIN_DATE = date(2000, 1, 1)
MAX_DATE = date(2100, 12, 31)

# --- Datas -----------------------------------------------------------------

dates = st.dates(min_value=MIN_DATE, max_value=MAX_DATE)


@st.composite
def date_ranges(draw, max_days: int = 5 * 365) -> tuple[date, date]:
    """Intervalo (inicio, fim) com inicio <= fim e duração limitada."""
    start = draw(st.dates(min_value=MIN_DATE, max_value=date(2095, 12, 31)))
    span = draw(st.integers(min_value=0, max_value=max_days))
    end = date.fromordinal(min(start.toordinal() + span, MAX_DATE.toordinal()))
    return start, end


# --- Decimais monetários ---------------------------------------------------


def money(
    min_value: str | Decimal = "0.00",
    max_value: str | Decimal = "1000000.00",
    places: int = 2,
) -> st.SearchStrategy[Decimal]:
    """Valores monetários Decimal com ``places`` casas decimais."""
    return st.decimals(
        min_value=Decimal(min_value),
        max_value=Decimal(max_value),
        places=places,
        allow_nan=False,
        allow_infinity=False,
    )


monetary = money()
positive_monetary = money(min_value="0.01")

# --- Identificadores -------------------------------------------------------

_ID_ALPHABET = string.ascii_uppercase + string.digits

positive_ids = st.integers(min_value=1, max_value=2_147_483_647)

business_keys = st.text(alphabet=_ID_ALPHABET, min_size=1, max_size=20)

prefixed_ids = st.builds(
    lambda prefix, n: f"{prefix}{n:08d}",
    st.sampled_from(["CLI", "PRD", "LOJ", "VND"]),
    st.integers(min_value=1, max_value=99_999_999),
)

env_names = st.sampled_from(["dev", "test", "prod"])

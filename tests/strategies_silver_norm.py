"""Estratégias para a Property 15 (normalização Silver e unicidade por chave).

Gera linhas Bronze válidas porém "sujas" (espaços, caixa mista, formatos de data e
número variados) junto com os valores esperados após a normalização.
"""

from __future__ import annotations

import string
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from hypothesis import strategies as st

from platform_lib.silver import META_TS, T_DATE, T_DECIMAL, T_INT, T_STR, EntitySpec
from tests.strategies import dates, money

SPEC_UPPER = EntitySpec(
    name="produto",
    key=("id",),
    columns={"id": T_STR, "nome": T_STR, "valor": T_DECIMAL, "data": T_DATE, "qtd": T_INT},
    text_case="upper",
)
SPEC_LOWER = EntitySpec(
    name="produto",
    key=("id",),
    columns=SPEC_UPPER.columns,
    text_case="lower",
)

_BASE_TS = datetime(2024, 1, 1, tzinfo=UTC)

_alnum = string.ascii_letters + string.digits
_ws = st.text(alphabet=" \t", max_size=3)

# Poucas chaves distintas para provocar duplicidade.
_keys = st.text(alphabet=_alnum[:6] + "12", min_size=1, max_size=3)
_names = st.text(alphabet=_alnum + " ", min_size=1, max_size=12).filter(lambda s: s.strip())


@dataclass(frozen=True)
class Case:
    raw: dict[str, Any]
    key_raw: str
    nome_raw: str
    valor: Decimal
    data: date
    qtd: int


@st.composite
def _case(draw) -> Case:
    key = draw(_keys)
    nome = draw(_names)
    valor = draw(money())
    d = draw(dates)
    qtd = draw(st.integers(min_value=-1000, max_value=1000))

    key_raw = draw(_ws) + key + draw(_ws)
    nome_raw = draw(_ws) + nome + draw(_ws)

    valor_fmt = draw(st.sampled_from(["dot", "comma", "decimal"]))
    valor_raw: Any = {
        "dot": str(valor),
        "comma": str(valor).replace(".", ","),
        "decimal": valor,
    }[valor_fmt]

    data_fmt = draw(st.sampled_from(["iso", "br", "compact", "date"]))
    data_raw: Any = {
        "iso": d.isoformat(),
        "br": d.strftime("%d/%m/%Y"),
        "compact": d.strftime("%Y%m%d"),
        "date": d,
    }[data_fmt]

    qtd_raw: Any = draw(st.sampled_from([qtd, str(qtd), f" {qtd} ", float(qtd)]))

    raw = {"id": key_raw, "nome": nome_raw, "valor": valor_raw, "data": data_raw, "qtd": qtd_raw}
    return Case(raw, key_raw, nome_raw, valor, d, qtd)


@st.composite
def bronze_batches(draw, max_size: int = 25) -> list[Case]:
    """Lote de casos; cada linha recebe um ``_ingestion_ts_utc`` único (sem empates)."""
    cases = draw(st.lists(_case(), min_size=1, max_size=max_size))
    order = draw(st.permutations(range(len(cases))))
    out = []
    for c, offset in zip(cases, order):
        raw = dict(c.raw)
        raw[META_TS] = (_BASE_TS + timedelta(seconds=offset)).isoformat()
        out.append(Case(raw, c.key_raw, c.nome_raw, c.valor, c.data, c.qtd))
    return out

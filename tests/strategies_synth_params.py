"""Estratégias Hypothesis para parâmetros do gerador sintético (Property 5).

``synth_param_cases`` produz ``(mapeamento, parametro_invalido_esperado)``;
o segundo item é ``None`` quando o mapeamento é válido.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from hypothesis import strategies as st

from platform_lib import synth

_INT_LIMITS = {
    "seed": (synth.SEED_MIN, synth.SEED_MAX),
    "n_customers": (synth.CUSTOMERS_MIN, synth.CUSTOMERS_MAX),
    "n_products": (synth.PRODUCTS_MIN, synth.PRODUCTS_MAX),
    "n_stores": (synth.STORES_MIN, synth.STORES_MAX),
}
_REQUIRED = [*_INT_LIMITS, "start", "end"]
_MAX_VALID_SPAN = 5 * 365  # sempre dentro de 5 anos
_MIN_INVALID_SPAN = 5 * 366 + 2  # sempre acima de 5 anos


def _int_in_limits(name: str) -> st.SearchStrategy[int]:
    low, high = _INT_LIMITS[name]
    return st.one_of(
        st.integers(min_value=low, max_value=high),
        st.sampled_from([low, high]),
    )


@st.composite
def valid_params(draw) -> dict[str, Any]:
    params: dict[str, Any] = {n: draw(_int_in_limits(n)) for n in _INT_LIMITS}
    start = draw(st.dates(min_value=date(2000, 1, 1), max_value=date(2090, 12, 31)))
    span = draw(st.one_of(st.integers(0, _MAX_VALID_SPAN), st.sampled_from([0, _MAX_VALID_SPAN])))
    end = date.fromordinal(start.toordinal() + span)
    if draw(st.booleans()):  # datas ISO em texto também são aceitas
        params["start"], params["end"] = start.isoformat(), end.isoformat()
    else:
        params["start"], params["end"] = start, end
    return params


_BAD_INT_TYPES = st.one_of(
    st.text(max_size=5),
    st.floats(allow_nan=True, allow_infinity=True),
    st.booleans(),
    st.lists(st.integers(), max_size=2),
)
_BAD_DATE_TYPES = st.one_of(
    st.integers(),
    st.booleans(),
    st.text(max_size=8).filter(lambda s: _not_iso(s)),
    st.datetimes().map(lambda d: d),
    st.lists(st.integers(), max_size=2),
)


def _not_iso(s: str) -> bool:
    try:
        date.fromisoformat(s)
    except ValueError:
        return True
    return False


@st.composite
def synth_param_cases(draw) -> tuple[dict[str, Any], str | None]:
    params = draw(valid_params())
    kind = draw(
        st.sampled_from(
            ["valid", "missing", "none", "bad_type", "out_of_limit", "start_after_end", "range_too_long"]
        )
    )
    if kind == "valid":
        return params, None
    if kind in ("missing", "none", "bad_type"):
        name = draw(st.sampled_from(_REQUIRED))
        if kind == "missing":
            del params[name]
        elif kind == "none":
            params[name] = None
        elif name in _INT_LIMITS:
            params[name] = draw(_BAD_INT_TYPES)
        else:
            params[name] = draw(_BAD_DATE_TYPES)
        return params, name
    if kind == "out_of_limit":
        name = draw(st.sampled_from(list(_INT_LIMITS)))
        low, high = _INT_LIMITS[name]
        params[name] = draw(
            st.one_of(
                st.integers(max_value=low - 1),
                st.integers(min_value=high + 1),
                st.sampled_from([low - 1, high + 1]),
            )
        )
        return params, name
    start = draw(st.dates(min_value=date(2000, 1, 1), max_value=date(2090, 12, 31)))
    if kind == "start_after_end":
        gap = draw(st.integers(1, 3000))
        end = date.fromordinal(start.toordinal() - gap) if start.toordinal() - gap > 1 else date.min
        params["start"], params["end"] = start, end
        return params, "start"
    span = draw(st.integers(_MIN_INVALID_SPAN, _MIN_INVALID_SPAN + 2000))
    params["start"], params["end"] = start, date.fromordinal(start.toordinal() + span)
    return params, "end"

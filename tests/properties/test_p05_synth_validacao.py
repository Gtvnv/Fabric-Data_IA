"""Property 5: Validação de parâmetros do gerador.

**Validates: Requirements 2.3, 2.4**
"""

from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given, settings

from platform_lib import synth
from platform_lib.synth import ParamError
from tests.strategies_synth_params import synth_param_cases


# Feature: fabric-data-ai-platform, Property 5: Validação de parâmetros do gerador
@settings(max_examples=200, deadline=None)
@given(case=synth_param_cases())
def test_validate_aceita_sse_valido_senao_param_error(case):
    params, expected_invalid = case
    if expected_invalid is None:
        result = synth.validate(params)
        assert result.seed == params["seed"]
        assert result.n_customers == params["n_customers"]
        assert result.n_products == params["n_products"]
        assert result.n_stores == params["n_stores"]
        assert result.start <= result.end
    else:
        with pytest.raises(ParamError) as exc:
            synth.validate(params)
        assert exc.value.param == expected_invalid


def _base(start: date, end: date) -> dict:
    return {"seed": 0, "n_customers": 1, "n_products": 1, "n_stores": 1, "start": start, "end": end}


def test_limite_de_cinco_anos_com_ano_bissexto():
    synth.validate(_base(date(2020, 2, 29), date(2025, 2, 28)))
    with pytest.raises(ParamError) as exc:
        synth.validate(_base(date(2020, 2, 29), date(2025, 3, 1)))
    assert exc.value.param == "end"


def test_limites_inclusivos_dos_inteiros():
    p = _base(date(2024, 1, 1), date(2024, 1, 1))
    p.update(seed=2_147_483_647, n_customers=1_000_000, n_products=100_000, n_stores=1_000)
    synth.validate(p)

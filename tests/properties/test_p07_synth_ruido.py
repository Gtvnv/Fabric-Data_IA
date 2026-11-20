"""Property 7: Contagens de ruído.
**Validates: Requirements 2.6, 2.7**
"""
from __future__ import annotations

from datetime import date

from hypothesis import given, settings

from platform_lib import synth
from tests.strategies_synth_noise import small_noisy_params


def _clean_sizes(p: synth.GenParams) -> dict[str, int]:
    return {
        "clientes": p.n_customers,
        "produtos": p.n_products,
        "lojas": p.n_stores,
        "vendas": p.n_customers * synth.SALES_PER_CUSTOMER,
        "estoque": min(
            p.n_products * p.n_stores,
            synth.STOCK_ROWS_PER_ENTITY * max(p.n_products, p.n_stores),
        ),
    }


def _unparseable(value) -> bool:
    try:
        date.fromisoformat(str(value)[:10])
    except ValueError:
        return True
    return False


def _scan(entity: str, rows: list[dict]) -> tuple[int, int, int]:
    key_cols = synth.KEY_COLUMNS[entity]
    if entity == "estoque":
        # data_posicao pode ser corrompida pelo ruído; (produto, loja) já é único no dado limpo.
        key_cols = ("produto_id", "loja_id")
    keys = [tuple(r[c] for c in key_cols) for r in rows]
    dups = len(keys) - len(set(keys))
    nulls = sum(r[synth.NULL_NOISE_COLUMN[entity]] is None for r in rows)
    bads = sum(_unparseable(r[synth.DATE_NOISE_COLUMN[entity]]) for r in rows)
    return dups, nulls, bads


# Feature: fabric-data-ai-platform, Property 7: Contagens de ruído
@settings(max_examples=100, deadline=None)
@given(small_noisy_params(with_noise=True))
def test_contagens_de_ruido_conferem_com_proporcao(params):
    data = synth.generate(params)
    noise = params.noise
    for entity, n in _clean_sizes(params).items():
        exp_dup = round(noise.dup_pct * n)
        exp_null = round(noise.null_pct * n)
        exp_bad = round(noise.bad_date_pct * n)
        entry = data.noise_manifest[entity]
        assert (len(entry.duplicates), len(entry.nulls), len(entry.bad_dates)) == (
            exp_dup,
            exp_null,
            exp_bad,
        )
        assert _scan(entity, data.tables[entity]) == (exp_dup, exp_null, exp_bad)
        assert len(data.tables[entity]) == n + exp_dup


# Feature: fabric-data-ai-platform, Property 7: Contagens de ruído
@settings(max_examples=100, deadline=None)
@given(small_noisy_params(with_noise=False))
def test_sem_ruido_todas_as_contagens_sao_zero(params):
    data = synth.generate(params)
    for entity, n in _clean_sizes(params).items():
        entry = data.noise_manifest[entity]
        assert (len(entry.duplicates), len(entry.nulls), len(entry.bad_dates)) == (0, 0, 0)
        assert _scan(entity, data.tables[entity]) == (0, 0, 0)
        assert len(data.tables[entity]) == n

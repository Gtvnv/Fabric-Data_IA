"""Property 18: Invariantes de SCD tipo 2 (Req. 4.8)."""

from __future__ import annotations

from datetime import date, timedelta

from hypothesis import given, settings

from platform_lib.gold import OPEN_END_DATE, build_dim_cliente_scd2
from tests.strategies_gold_scd2 import scd2_sequences


# Feature: fabric-data-ai-platform, Property 18: Invariantes de SCD tipo 2
@settings(max_examples=100, deadline=None)
@given(seq=scd2_sequences())
def test_scd2_invariants(seq):
    """**Validates: Requirements 4.8**"""
    dim: list = []
    for as_of, batch in seq:
        dim = build_dim_cliente_scd2(dim, batch, as_of)

        by_key: dict = {}
        for r in dim:
            by_key.setdefault(r["cliente_id"], []).append(r)

        for versions in by_key.values():
            # no máximo uma versão vigente
            vigentes = [v for v in versions if v["vigente"]]
            assert len(vigentes) == 1
            cur = vigentes[0]
            assert cur["data_fim"] == OPEN_END_DATE

            ordered = sorted(versions, key=lambda v: v["data_inicio"])
            for prev, nxt in zip(ordered, ordered[1:]):
                # sem sobreposição e fechamento = próximo início - 1 dia
                assert not prev["vigente"]
                assert prev["data_inicio"] <= prev["data_fim"]
                assert prev["data_fim"] == nxt["data_inicio"] - timedelta(days=1)
            assert ordered[-1] is cur or ordered[-1]["vigente"]
            assert all(isinstance(v["data_inicio"], date) for v in versions)

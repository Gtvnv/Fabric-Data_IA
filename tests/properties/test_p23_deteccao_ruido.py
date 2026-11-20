# Feature: fabric-data-ai-platform, Property 23: Detecção completa de ruído
"""Property 23: o pipeline detecta 100% do ruído inserido (duplicados, nulos em coluna
obrigatória e datas inválidas), por tipo, conforme `Dataset.noise_manifest`.

**Validates: Requirements 5.6**
"""
from __future__ import annotations

from hypothesis import given, settings

from platform_lib.dq import evaluate
from platform_lib.silver import REASON_BAD_DATE, to_silver
from platform_lib.synth import ENTITIES, generate
from tests.strategies_noise_detect import INGESTION_TS, RULES, SPECS, TS_COLUMN, noisy_params


@settings(max_examples=100, deadline=None)
@given(params=noisy_params())
def test_p23_deteccao_completa_de_ruido(params):
    dataset = generate(params)
    for entity in ENTITIES:
        manifest = dataset.noise_manifest[entity]
        rows = dataset.tables[entity]

        unique_rule, not_null_rule = RULES[entity]
        tables = {entity: rows}
        assert evaluate(unique_rule, tables).violations == len(manifest.duplicates), entity
        assert evaluate(not_null_rule, tables).violations == len(manifest.nulls), entity

        bronze = [{**r, TS_COLUMN: INGESTION_TS} for r in rows]
        result = to_silver(bronze, SPECS[entity])
        bad_dates = [
            q
            for q in result.quarantine_rows
            if f"{REASON_BAD_DATE}:{manifest.date_column}" in q["_motivos"]
        ]
        assert len(bad_dates) == len(manifest.bad_dates), entity
        # nenhuma outra causa de quarentena: o ruído de nulo não vira rejeição
        assert len(result.quarantine_rows) == len(manifest.bad_dates), entity

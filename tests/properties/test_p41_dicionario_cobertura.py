"""Property 41: Cobertura do dicionário de dados."""
from __future__ import annotations

from hypothesis import given, settings

from platform_lib.docs_tools import is_dictionary_covered, validate_data_dictionary
from tests.strategies_dict import SENS_VALIDAS, schema_and_entries


def _filled(v) -> bool:
    return v is not None and bool(str(v).strip())


def _expected_covered(schema, entries) -> bool:
    index = {(e["tabela"], e["coluna"]): e for e in entries}
    for table, spec in schema["tables"].items():
        for col in spec["columns"]:
            e = index.get((table, col))
            if e is None:
                return False
            if not (_filled(e.get("tipo")) and _filled(e.get("descricao"))):
                return False
            if e.get("sensibilidade") not in SENS_VALIDAS:
                return False
    return True


# Feature: fabric-data-ai-platform, Property 41: Cobertura do dicionário de dados
# **Validates: Requirements 11.5, 11.8**
@settings(max_examples=100)
@given(data=schema_and_entries())
def test_dicionario_coberto_sse_toda_coluna_tem_entrada_completa(data) -> None:
    schema, entries = data
    expected = _expected_covered(schema, entries)
    assert is_dictionary_covered(schema, entries) is expected
    assert (validate_data_dictionary(schema, entries) == []) is expected


# Feature: fabric-data-ai-platform, Property 41: Cobertura do dicionário de dados
# **Validates: Requirements 11.5, 11.8**
@settings(max_examples=100)
@given(data=schema_and_entries(mostly_complete=True))
def test_remover_entrada_de_coluna_quebra_cobertura(data) -> None:
    schema, entries = data
    if not _expected_covered(schema, entries):
        return
    assert is_dictionary_covered(schema, entries)
    for i, e in enumerate(entries):
        if e["tabela"] == "zz_orfa":
            continue
        assert not is_dictionary_covered(schema, entries[:i] + entries[i + 1:])

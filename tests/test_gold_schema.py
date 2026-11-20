"""Testes do esquema Gold e do gerador de DDL (tarefa 7.3). Req. 4.5, 4.9, 11.5, 11.8."""

from __future__ import annotations

from infra.gen_gold_ddl import dictionary_rows, generate_ddl, load_schema

from platform_lib.docs_tools import SENSIBILIDADES, validate_data_dictionary

EXPECTED_TABLES = {
    "dim_cliente", "dim_produto", "dim_loja", "dim_calendario", "fato_vendas",
    "agg_vendas_dia", "fato_estoque", "features_demanda", "features_churn",
    "previsao_demanda", "previsao_churn", "config.ultima_atualizacao",
}
PII = {"nome", "cpf", "email", "telefone", "endereco", "documento"}


def test_schema_loads_with_all_tables_and_valid_columns():
    schema = load_schema()
    assert set(schema["tables"]) == EXPECTED_TABLES
    for spec in schema["tables"].values():
        for c in spec["columns"].values():
            assert c["tipo"] and c["descricao"].strip()
            assert c["sensibilidade"] in SENSIBILIDADES


def test_generated_dictionary_satisfies_validation():
    schema = load_schema()
    assert validate_data_dictionary(schema, dictionary_rows(schema)) == []


def test_features_have_no_direct_pii_columns():
    tables = load_schema()["tables"]
    for t in ("features_demanda", "features_churn"):
        assert not PII & set(tables[t]["columns"])


def test_ddl_generation_both_dialects():
    schema = load_schema()
    delta = generate_ddl(schema, "delta")
    tsql = generate_ddl(schema, "tsql")
    assert "CREATE TABLE IF NOT EXISTS `dbo`.`fato_vendas`" in delta
    assert "`valor_venda` DECIMAL(18,2) NOT NULL" in delta
    assert "`config`.`ultima_atualizacao`" in delta
    assert "[valor_venda] DECIMAL(18,2) NOT NULL" in tsql
    assert "[vigente] BIT NOT NULL" in tsql
    assert tsql.count("CREATE TABLE") == len(EXPECTED_TABLES)

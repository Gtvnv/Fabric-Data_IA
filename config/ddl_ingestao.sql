-- DDL (Spark SQL / Delta, Lakehouse de configuração) das tabelas da Pipeline_Ingestao.
-- Req. 3.1, 3.2, 3.5. Idempotente: pode ser reexecutado.
CREATE SCHEMA IF NOT EXISTS config;

CREATE TABLE IF NOT EXISTS config.ingestao_entidades (
    entidade          STRING  NOT NULL,
    ativo             BOOLEAN NOT NULL,
    origem_tipo       STRING  NOT NULL,  -- azure_sql | arquivo
    consulta          STRING  NOT NULL,
    chave             STRING  NOT NULL,  -- colunas separadas por vírgula
    coluna_watermark  STRING  NOT NULL,
    destino           STRING  NOT NULL
) USING DELTA;

CREATE TABLE IF NOT EXISTS config.ingestao_watermark (
    entidade           STRING    NOT NULL,
    ultimo_valor       STRING,             -- NULL = nunca ingerida (carga completa)
    atualizado_em_utc  TIMESTAMP NOT NULL
) USING DELTA;

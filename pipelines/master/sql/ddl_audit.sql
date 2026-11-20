-- Auditoria do pipeline mestre (Warehouse). Req. 9.5, 9.10, 10.2.
-- Idempotente. Gravada pelo pipeline mestre e por notebooks/nb_reexecucao.py em até 60 s do término.
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'audit')
    EXEC('CREATE SCHEMA audit');
GO

IF OBJECT_ID('audit.execucoes', 'U') IS NULL
CREATE TABLE audit.execucoes (
    run_id          VARCHAR(64)  NOT NULL,  -- id da execução do pipeline mestre
    run_original_id VARCHAR(64)  NULL,      -- execução original, quando é reexecução (Req. 9.10)
    inicio          DATETIME2(6) NOT NULL,  -- UTC
    fim             DATETIME2(6) NULL,      -- UTC; NULL enquanto 'em andamento'
    status          VARCHAR(32)  NOT NULL   -- 'em andamento' | 'sucesso' | 'falha'
);
GO

IF OBJECT_ID('audit.execucoes_etapas', 'U') IS NULL
CREATE TABLE audit.execucoes_etapas (
    run_id    VARCHAR(64)  NOT NULL,
    etapa     VARCHAR(32)  NOT NULL,        -- ingestao | silver | qualidade | gold | ia | semantico
    inicio    DATETIME2(6) NULL,            -- NULL para 'não executada'
    fim       DATETIME2(6) NULL,
    status    VARCHAR(32)  NOT NULL,        -- 'sucesso' | 'falha' | 'não executada'
    registros BIGINT       NOT NULL
);
GO

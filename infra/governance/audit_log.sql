-- Log de auditoria consultável (Req. 6.7). T-SQL (Warehouse). Idempotente.
-- Alimentada pelo job descrito em audit_export.json (a cada 5 minutos).
IF SCHEMA_ID(N'governanca') IS NULL EXEC(N'CREATE SCHEMA [governanca]');

IF OBJECT_ID(N'governanca.auditoria_acesso', N'U') IS NULL
CREATE TABLE [governanca].[auditoria_acesso] (
    [evento_id] VARCHAR(100) NOT NULL,
    [ocorrido_em_utc] DATETIME2(6) NOT NULL,
    [ingerido_em_utc] DATETIME2(6) NOT NULL,
    [usuario] VARCHAR(320) NULL,
    [operacao] VARCHAR(200) NULL,
    [item] VARCHAR(512) NULL,
    [resultado] VARCHAR(50) NOT NULL,
    [acesso_negado] BIT NOT NULL,
    [origem] VARCHAR(50) NOT NULL
);

-- Eventos de acesso negado, para consulta direta.
CREATE OR ALTER VIEW [governanca].[vw_acessos_negados] AS
SELECT [evento_id], [ocorrido_em_utc], [ingerido_em_utc], [usuario], [operacao], [item]
FROM [governanca].[auditoria_acesso]
WHERE [acesso_negado] = 1;

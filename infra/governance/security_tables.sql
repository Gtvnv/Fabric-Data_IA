-- Tabelas de segurança e governança (Req. 6.5, 6.8, 6.9). T-SQL (Warehouse). Idempotente.
IF SCHEMA_ID(N'seguranca') IS NULL EXEC(N'CREATE SCHEMA [seguranca]');
IF SCHEMA_ID(N'governanca') IS NULL EXEC(N'CREATE SCHEMA [governanca]');

-- RLS: lojas permitidas por usuário (UPN do Entra ID). Usuário sem linhas vê zero linhas.
IF OBJECT_ID(N'seguranca.usuario_loja', N'U') IS NULL
CREATE TABLE [seguranca].[usuario_loja] (
    [usuario] VARCHAR(320) NOT NULL,
    [loja_id] BIGINT NOT NULL
);

-- Catálogo das tabelas Gold: responsável e descrição (1 a 500 caracteres) obrigatórios;
-- tabelas sem responsável ou com descrição vazia/>500 são listadas como pendentes.
IF OBJECT_ID(N'governanca.catalogo_gold', N'U') IS NULL
CREATE TABLE [governanca].[catalogo_gold] (
    [tabela] VARCHAR(256) NOT NULL,
    [responsavel] VARCHAR(320) NULL,
    [descricao] VARCHAR(8000) NULL,
    [atualizado_em_utc] DATETIME2(6) NULL
);

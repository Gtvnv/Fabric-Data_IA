-- Mascaramento dinâmico de dados (Req. 6.4). Gerado por infra/governance/gen_masking.py
-- a partir de config/gold_schema.yaml (sensibilidade = confidencial). Idempotente.
IF DATABASE_PRINCIPAL_ID(N'rl_administrador') IS NULL EXEC(N'CREATE ROLE [rl_administrador]');

ALTER TABLE [dbo].[dim_cliente] ALTER COLUMN [cliente_id] BIGINT MASKED WITH (FUNCTION = 'default()');
ALTER TABLE [dbo].[dim_cliente] ALTER COLUMN [nome_mascarado] VARCHAR(8000) MASKED WITH (FUNCTION = 'partial(1, "XXXXXXXX", 0)');
ALTER TABLE [dbo].[fato_vendas] ALTER COLUMN [valor_venda] DECIMAL(18,2) MASKED WITH (FUNCTION = 'default()');
ALTER TABLE [dbo].[agg_vendas_dia] ALTER COLUMN [valor_venda] DECIMAL(18,2) MASKED WITH (FUNCTION = 'default()');
ALTER TABLE [dbo].[features_churn] ALTER COLUMN [valor_total] FLOAT MASKED WITH (FUNCTION = 'default()');
ALTER TABLE [dbo].[previsao_churn] ALTER COLUMN [prob_churn] FLOAT MASKED WITH (FUNCTION = 'default()');

-- UNMASK somente à função autorizada; nenhuma outra função recebe a permissão.
GRANT UNMASK TO [rl_administrador];

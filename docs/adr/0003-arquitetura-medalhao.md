# 0003. Arquitetura medalhão (Bronze, Silver e Gold)
Status: aceito
Data: 2026-11-20

## Contexto

Os dados chegam de fontes distintas, com duplicidade, nulos e datas inválidas (o gerador sintético injeta ruído de forma controlada). É preciso preservar o dado original para reprocessamento, entregar dados limpos e confiáveis e expor um modelo dimensional para relatórios e IA. A reexecução sobre as mesmas entradas deve gerar o mesmo resultado (Req. 3.7, 4.10) e o total de vendas deve reconciliar entre camadas (Req. 4.11).

## Decisão

Organizar os dados em três camadas:

- Bronze: cópia fiel da origem, acrescida de `_ingestion_ts_utc`, `_run_id` e `_source_system`. `MERGE` pela chave de carga, o que torna a carga idempotente.
- Silver: tipos fortes, datas em ISO 8601, texto com trim e caixa uniforme, um registro vigente por chave (mantém o de maior `_ingestion_ts_utc`). Registros inválidos vão para `silver._quarentena` com o motivo, sem interromper a execução.
- Gold: modelo estrela (`fato_vendas`, `dim_cliente` SCD2, `dim_produto`, `dim_loja`, `dim_calendario`, `agg_vendas_dia`, estoque, features e previsões). Chaves substitutas e membro "Desconhecido" (`sk = -1`) para fatos sem dimensão.

A Verificacao_Qualidade roda entre Silver e Gold. Regra bloqueante violada interrompe a execução e nada é promovido. A lógica fica em `platform_lib` (`silver.py`, `gold.py`, `dq.py`), e os notebooks são finos.

## Alternativas consideradas

- Duas camadas (raw e curated): menos tabelas, mas mistura limpeza e modelagem, e o modelo dimensional fica sem camada própria para validação e reconciliação.
- Data Vault 2.0 entre Silver e Gold: bom para integração de muitas fontes e auditoria histórica, mas é complexo demais para cinco entidades e adiciona uma camada extra a manter.
- Tabela única larga (one big table) para consumo: simples para o analista, mas dificulta o SCD2, o reuso de dimensões e o desempenho do modelo semântico.

## Consequências

- O dado bruto fica preservado, o que permite reprocessar Silver e Gold sem nova leitura da origem.
- O armazenamento cresce por manter três cópias lógicas; a retenção por camada (ADR 0005) limita esse custo.
- A latência de ponta a ponta aumenta com as etapas em sequência e com a verificação de qualidade, que é uma barreira intencional.
- Cada camada tem contrato próprio, testável por propriedades (idempotência, unicidade de chave vigente, reconciliação de soma).

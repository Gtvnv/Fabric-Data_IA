# 0004. Ingestão: Azure Data Factory versus Fabric Data Factory por tipo de fonte
Status: aceito
Data: 2026-11-20

## Contexto

A Fonte_Origem tem dois tipos de fonte: tabelas em Azure SQL Database (`clientes`, `produtos`, `lojas`, `vendas`) e arquivos CSV/Parquet de estoque em armazenamento de objetos (ADLS Gen2 ou OneLake). Duas ferramentas de orquestração e cópia estão disponíveis: Fabric Data Factory (pipelines dentro do workspace Fabric) e Azure Data Factory (ADF, serviço Azure separado). O pipeline é parametrizado por `config.ingestao_entidades` (até 500 entidades ativas), usa marca d'água, tenta a cópia até 4 vezes com 60 s de intervalo e lê credenciais somente do Azure Key Vault (Req. 3.1 a 3.12). A escolha por tipo de fonte deve ser registrada (Req. 3.9).

## Decisão

Critérios de decisão, nesta ordem: (1) a fonte é alcançável pela rede pública ou por gateway gerenciado, sem Self-hosted Integration Runtime; (2) o destino é um item do Fabric (Lakehouse Bronze); (3) existe pipeline ADF legado a preservar; (4) necessidade de conectores ou recursos que o Fabric ainda não oferece.

Escolha por tipo de fonte:

- Azure SQL Database: Fabric Data Factory. Atende aos critérios 1 e 2, e a atividade Copy grava direto no Lakehouse Bronze.
- Arquivos de estoque em OneLake ou ADLS Gen2: Fabric Data Factory, via atalho do OneLake ou atividade Copy.
- Fonte que exige Self-hosted Integration Runtime (rede privada ou local) ou que já tenha pipeline ADF legado: ADF, gravando no Lakehouse Bronze pelo conector do Fabric. Hoje nenhuma entidade do cenário se enquadra aqui. O tipo existe para o caso de expansão.

Em ambos os casos, o pipeline tem a mesma estrutura (Lookup de entidades, ForEach, Lookup de marca d'água, Copy para staging, notebook de `MERGE` na Bronze, atualização da marca d'água) e as conexões referenciam o Key Vault. A lógica de marca d'água, retentativa e status vive em `platform_lib/ingestion.py`, igual nas duas ferramentas.

## Alternativas consideradas

- Somente Azure Data Factory para todas as fontes: um único serviço de ingestão e suporte maduro a Self-hosted IR, mas fora do workspace Fabric, com implantação, identidade e monitoramento em separado.
- Somente Fabric Data Factory para todas as fontes: operação mais simples, mas não cobre fontes em rede privada que exijam Self-hosted IR e não reaproveita pipelines ADF existentes.
- Notebooks Spark com JDBC e leitura de arquivos, sem pipeline gerenciado: máximo controle em código e fácil de testar, mas perde o monitoramento, o gatilho e a cópia gerenciada, e exige tratar segredos e retentativas manualmente.

## Consequências

- Para as fontes atuais, ingestão, notebooks e monitoramento ficam no mesmo workspace e no mesmo processo de implantação (ADR 0007).
- Quando uma fonte exigir Self-hosted IR, será preciso operar o ADF em paralelo, com seu próprio deploy e monitoramento, e este ADR deve ser revisado ou ter um ADR complementar.
- As entidades novas entram só por configuração em `config/ingestao_entidades.yaml`, sem alterar pipelines.
- A falha de uma entidade não interrompe as demais, mas o status final da execução é falha.
- Se o Key Vault estiver indisponível, a entidade não acessa a origem (Req. 3.11).

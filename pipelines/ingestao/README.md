# Pipeline_Ingestao

Definições para Fabric Data Factory (`fabric/`) e Azure Data Factory (`adf/`). Req. 3.1, 3.2, 3.8 a 3.12.

## Fluxo

- `pl_ingestao` (pai): verifica o Key Vault, faz Lookup das entidades ativas (máx. 500) em `config.ingestao_entidades` e executa `pl_ingestao_entidade` em um ForEach com paralelismo configurável. Falha de uma entidade é registrada na variável `falhas` e as demais seguem. Ao final, o status é falha se houver alguma entidade com falha.
- `pl_ingestao_entidade` (filho, uma execução por entidade): lê o segredo no Key Vault, faz Lookup da marca d'água em `config.ingestao_watermark` (Filter pela entidade), executa o Copy origem -> staging (retry 3 x 60 s, ou seja, 4 tentativas), chama `nb_bronze_merge` (modo `merge`) e só então atualiza a marca (modo `atualizar_marca`).
- Se o Key Vault falhar, a atividade de segredo falha e todas as atividades seguintes ficam ignoradas. A origem nunca é acessada (Req. 3.11). No pai, a falha da verificação global encerra a execução com `KEYVAULT_INDISPONIVEL`.
- A saída das atividades de Key Vault é segura (`secureOutput`), então o valor do segredo não aparece nos logs.

## Credenciais (Req. 3.10)

Nenhum segredo nos arquivos. Os linked services do ADF (`adf/linked_services/`) usam `AzureKeyVaultSecret` para senha SQL, chave de storage e credencial do service principal. No Fabric, as conexões (`${CONN_*}`) são criadas no workspace com a credencial referenciando o Key Vault. Tokens `${NOME}` são substituídos no deploy por valores do ambiente (ver `.env.example`).

## Diferença entre ADF e Fabric

O ADF não tem atividade de notebook do Fabric. No ADF, `pl_ingestao_entidade` copia a origem para o staging do Lakehouse e dispara via REST (Web activity, MSI) o pipeline Fabric `fabric/pl_ingestao_merge_entidade`, que executa MERGE e atualização da marca. O disparo é assíncrono: o ADF confirma o início do job, não o resultado do MERGE. Falhas do MERGE ficam no monitor do Fabric. Por isso o ADF deve ser usado apenas nos casos previstos no ADR (Self-hosted IR ou pipeline legado).

## Carga da configuração

`config/ddl_ingestao.sql` cria as tabelas. `notebooks/nb_bronze_merge.py` com `modo=carregar_config` carrega `config/ingestao_entidades.yaml` em `config.ingestao_entidades`.

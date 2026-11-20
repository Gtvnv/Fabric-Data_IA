# 0002. Lakehouse versus Warehouse por camada, com Delta Lake e OneLake
Status: aceito
Data: 2026-11-20

## Contexto

O Fabric oferece Lakehouse (Spark, arquivos e tabelas Delta, SQL analytics endpoint somente leitura) e Warehouse (T-SQL com escrita, transações multitabela e mascaramento dinâmico de dados). É preciso escolher qual usar em cada camada (Req. 4.12). Também é preciso escolher o formato de tabela e a camada de armazenamento. Os dados têm origem em Azure SQL (estruturados) e em arquivos CSV/Parquet de estoque, exigem `MERGE` idempotente, evolução de esquema e versão de dados reproduzível para o MLflow. O Direct Lake só lê tabelas Delta no OneLake.

## Decisão

Por camada:

- Bronze: Lakehouse. Recebe dados brutos e semiestruturados, com evolução de esquema e processamento Spark.
- Silver: Lakehouse. Transformações PySpark, deduplicação e tabela de quarentena.
- Gold: Lakehouse como armazenamento principal do modelo estrela em tabelas Delta, que são a base do Direct Lake, e Warehouse na Camada_Gold como exposição T-SQL, para consumo SQL e mascaramento dinâmico de dados (DDM) das colunas confidenciais (Req. 6.4).

Formato e armazenamento: todas as tabelas são Delta Lake e ficam no OneLake. Delta fornece transações ACID, `MERGE` idempotente e time travel, usado para registrar a `delta_table_version` das features em cada execução MLflow (Req. 7.3). O OneLake é o armazenamento único do tenant, e os itens se referenciam por atalhos, sem cópia.

## Alternativas consideradas

- Warehouse em todas as camadas: simplifica o T-SQL e o controle de acesso por objeto, mas limita o processamento de arquivos e dados semiestruturados na Bronze, e o Spark e o MLflow trabalham de forma menos natural.
- Lakehouse em todas as camadas, sem Warehouse: menos itens para operar, mas o SQL analytics endpoint é somente leitura e não atende a escrita T-SQL nem o DDM, que o requisito de governança exige.
- Parquet puro ou Iceberg em vez de Delta: o Parquet puro não tem transações nem `MERGE`; o Iceberg não tem o mesmo nível de suporte nativo no Fabric e no Direct Lake.
- ADLS Gen2 próprio em vez do OneLake: dá controle direto de rede e ciclo de vida, mas duplica a governança e perde o acesso por atalho e o Direct Lake sem cópia.

## Consequências

- A Gold existe em dois lugares (Lakehouse e Warehouse). O Warehouse expõe as mesmas tabelas por carga ou atalho, e a reconciliação de valores entre eles entra nos testes de integração.
- O Direct Lake usa as tabelas Delta do Lakehouse Gold com `DirectLakeOnly`, sem fallback para DirectQuery.
- A manutenção Delta (`OPTIMIZE`, `VACUUM`) precisa ser agendada e respeitar a retenção definida no ADR 0005; o time travel só alcança versões ainda retidas.
- Equipes precisam conhecer Spark e T-SQL. A lógica compartilhada fica em `platform_lib` para reduzir a duplicação.

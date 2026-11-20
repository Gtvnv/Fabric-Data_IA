# 0001. Microsoft Fabric como plataforma de dados e IA
Status: aceito
Data: 2026-11-20

## Contexto

A plataforma de referência precisa cobrir ingestão, transformação em camadas, qualidade, governança, modelos de IA e relatórios para uma rede varejista fictícia. Montar essas capacidades com serviços Azure separados (armazenamento, Spark, SQL, orquestração, MLflow, Power BI) exige integrar identidade, rede, custos e implantação de cada serviço. O repositório deve ser reproduzível em 3 ambientes (dev, test e prod) por script, usando somente dados sintéticos.

## Decisão

Adotar o Microsoft Fabric como plataforma única, com um workspace por ambiente (`fdai-dev`, `fdai-test`, `fdai-prod`). Cada workspace contém 3 Lakehouses (`lh_bronze_<env>`, `lh_silver_<env>`, `lh_gold_<env>`) e 1 Warehouse (`wh_gold_<env>`). Os itens são criados por script idempotente sobre a Fabric REST API (Req. 1.5 a 1.8). Notebooks PySpark, pipelines, MLflow e o modelo semântico Direct Lake rodam no mesmo workspace e compartilham o OneLake e a mesma identidade (Entra ID).

## Alternativas consideradas

- Azure Synapse Analytics com ADLS Gen2 e Power BI Premium separados: maior flexibilidade de rede e SKU por serviço, mas exige integrar e operar vários recursos, e o Direct Lake não está disponível sobre ele.
- Azure Databricks com Delta Lake e Unity Catalog, mais Power BI: plataforma madura para Spark e ML, mas o consumo no Power BI seria por DirectQuery ou Import, sem o Direct Lake, e haveria um segundo plano de custos e governança.
- Stack open source (Spark, Airflow, MinIO, Superset) em Kubernetes: sem custo de licença, mas o esforço de operação e de segurança é muito maior e foge do escopo de uma plataforma de referência Microsoft.

## Consequências

- Uma única capacidade (SKU) por ambiente concentra o custo; a pausa e a retomada fora do horário de uso reduzem o gasto em ambientes não produtivos (ver `docs/capacidade-e-custos.md`).
- O Direct Lake lê Delta direto do OneLake, o que evita copiar dados para Import (Req. 8.1).
- Há dependência do fornecedor e do ritmo de evolução do Fabric. Recursos em prévia devem ser evitados em produção, e a lógica de negócio fica em módulos Python puros (`src/platform_lib`) para limitar o acoplamento.
- O provisionamento depende de um service principal com permissão na Fabric REST API, tratado no ADR 0008.

# Diagramas de arquitetura

Três diagramas em Mermaid (Req. 11.2): contexto, fluxo de dados medalhão e implantação. Adaptados de `.kiro/specs/fabric-data-ai-platform/design.md`. Cada rótulo está entre aspas para evitar erro de sintaxe com parênteses e símbolos.

## 1. Contexto

Componentes e integrações externas: fontes, gerador sintético, Key Vault, ingestão, camadas, IA, modelo semântico, relatório, governança (Purview), observabilidade e alertas, CI/CD e capacidade.

```mermaid
flowchart LR
    subgraph Origem["Fonte_Origem"]
        SQL[("Azure SQL Database<br/>clientes, produtos, lojas, vendas")]
        OBJ[("Armazenamento de objetos<br/>estoque CSV/Parquet")]
    end
    GEN["Gerador de Dados_Sinteticos<br/>platform_lib.synth"] --> SQL
    GEN --> OBJ
    KV["Azure Key Vault"]
    subgraph Fabric["Microsoft Fabric - Workspace dev, test e prod"]
        ING["Pipeline_Ingestao<br/>ADF / Fabric Data Factory"]
        MST["Pipeline mestre<br/>agendamento diario e lock"]
        LHB[("Lakehouse Bronze")]
        LHS[("Lakehouse Silver")]
        LHG[("Lakehouse Gold")]
        WH[("Warehouse Gold<br/>T-SQL e mascaramento")]
        NB["Notebooks PySpark<br/>chamam platform_lib"]
        DQ["Verificacao_Qualidade<br/>config/dq_rules.yaml"]
        ML["MLflow e registro de modelos<br/>demanda e churn"]
        SM["Modelo_Semantico<br/>Direct Lake"]
        MON["Painel de monitoramento<br/>audit e ops.logs"]
    end
    PBI["Relatorio_PowerBI<br/>5 paginas, RLS por loja"]
    PUR["Microsoft Purview<br/>catalogo, linhagem, classificacao"]
    ALR["Alertas<br/>webhook Teams / e-mail"]
    CAP["Capacidade Fabric<br/>pausa e retomada em nao produtivo"]
    GIT["Repositorio Git + Pipeline_CICD"]

    SQL --> ING
    OBJ --> ING
    KV -. segredos .-> ING
    MST --> ING
    ING --> LHB --> NB --> LHS --> DQ --> NB
    NB --> LHG
    LHG --> WH
    LHG --> ML --> LHG
    LHG --> SM --> PBI
    Fabric -. metadados e linhagem .-> PUR
    GIT -. deploy .-> Fabric
    ING --> MON
    NB --> MON
    MST -- falha em ate 5 min --> ALR
    CAP -. dimensiona .-> Fabric
```

## 2. Fluxo de dados medalhão

Fluxo da fonte ao relatório: marca d'água, Bronze, Silver, quarentena, qualidade, Gold (SCD2), features, treino, promoção de modelo, pontuação e modelo semântico.

```mermaid
flowchart TD
    A["Fonte_Origem"] -->|"copy incremental + marca d'agua"| B["Bronze: dados brutos + metadados de ingestao"]
    B -->|"tipos, ISO 8601, trim e caixa, dedup por chave"| C["Silver: 1 registro vigente por chave"]
    B -->|"registros invalidos"| Q[("quarentena + motivo")]
    C --> D{"Verificacao_Qualidade"}
    D --> R[("dq.resultados")]
    D -->|"regra bloqueante violada"| X["Falha: interrompe, nada promovido, alerta"]
    D -->|"ok ou so alertas"| E["Gold: dim_cliente SCD2, dim_produto, dim_loja, dim_calendario, fato_vendas, agg_vendas_dia, fato_estoque"]
    E --> F["Features de demanda e churn, sem dados pessoais"]
    F --> G["Treino MLflow"] --> H{"Candidato melhor<br/>em RMSE ou AUC?"}
    H -->|sim| I["Promove nova versao"]
    H -->|nao| J["Mantem producao e registra motivo"]
    I --> K["Pontuacao em lote: previsao_demanda e previsao_churn"]
    J --> K
    E --> L["Modelo_Semantico Direct Lake"]
    K --> L
    L --> P["Relatorio_PowerBI"]
    E --> W["Warehouse Gold com mascaramento dinamico"]
    X --> AUD[("audit.execucoes_etapas e ops.logs")]
    E --> AUD
    K --> AUD
```

## 3. Implantação e CI/CD

Do branch de trabalho até produção, com validação, aprovação manual, falha, service principal, segredos, provisionamento e pausa de capacidade.

```mermaid
flowchart LR
    DEV["Branch feature, fix, chore, docs ou test"] -->|"pull request"| CI["Validacao: ruff, sintaxe de notebooks, pytest, ADRs e dicionario, gitleaks"]
    CI -->|"reprovado"| BLK["PR bloqueado"]
    CI -->|"aprovado por 1 ou mais revisores + merge"| MAIN[("branch base protegida")]
    MAIN --> DT["Deploy automatico: workspace test<br/>infra.deploy"]
    DT --> APR{"Aprovacao manual<br/>1 ou mais aprovadores"}
    APR --> DP["Deploy: workspace prod"]
    DT -. falha .-> STOP["Interrompe fluxo e notifica ambiente e item"]
    DP -. falha .-> STOP
    SP["Service principal<br/>minimo privilegio"] -.-> DT
    SP -.-> DP
    KV["Key Vault / segredos do repositorio"] -.-> SP
    DT --> PRV["infra.provision idempotente<br/>1 workspace, 3 Lakehouses, 1 Warehouse por ambiente"]
    DP --> PRV
    PRV --> GITINT["Integracao Git do workspace"]
    CAPP["infra.capacity pause e resume<br/>somente dev e test"] -.-> DT
```

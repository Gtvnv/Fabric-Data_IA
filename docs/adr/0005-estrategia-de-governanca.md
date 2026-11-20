# 0005. Estratégia de governança: catálogo, classificação, retenção e acesso
Status: aceito
Data: 2026-11-20

## Contexto

A plataforma lida com dados pessoais sintéticos (nome, e-mail, telefone, documento) que devem ser tratados como reais para fins de demonstração. É preciso catalogar os ativos, expor a linhagem, classificar a sensibilidade, definir por quanto tempo cada tipo de dado é mantido e controlar quem acessa o quê (Req. 6.1 a 6.10).

## Decisão

Catálogo: Microsoft Purview integrado ao Fabric, com varredura agendada ao menos uma vez por dia (itens registrados em até 24 h), coleções por ambiente e linhagem do Relatorio_PowerBI até a Fonte_Origem. Toda tabela Gold tem responsável (data owner) e descrição de até 500 caracteres em `governanca.catalogo_gold`. Tabelas sem esses dados aparecem no relatório de pendências (`pending_governance`).

Classificação: quatro níveis, `pública`, `interna`, `confidencial` e `restrita`, aplicados a toda coluna do dicionário de dados. Regras do Purview e o verificador `platform_lib/governance.py` marcam nome, e-mail, documento e telefone como `confidencial`. Colunas `confidencial` recebem mascaramento dinâmico no Warehouse, e `UNMASK` é concedido só à função autorizada.

Retenção, em dias por tipo de dado:

| Tipo de dado | Retenção (dias) |
|---|---|
| Bronze (dados brutos, incluindo pessoais) | 365 |
| Silver | 730 |
| Gold (dimensões, fatos e agregações) | 1825 |
| Quarentena (`silver._quarentena`) | 90 |
| Resultados de qualidade (`dq.resultados`) | 365 |
| Features e previsões de ML | 365 |
| Logs estruturados (`ops.logs`) | 90 (mínimo exigido: 30) |
| Auditoria de execuções (`audit.*`) e de acesso | 365 |
| Versões antigas Delta (time travel, `VACUUM`) | 30 |

Ao fim do prazo, os registros são removidos por rotina agendada. A remoção de dado pessoal na Bronze respeita o prazo de 365 dias mesmo que a Silver e a Gold mantenham apenas chaves substitutas ou atributos mascarados.

Acesso: quatro funções (administrador, engenheiro, analista e consumidor), mapeadas a Admin, Member, Contributor e Viewer do workspace e a grupos do Entra ID, com matriz de permissões documentada. Acesso por linha (RLS) no Modelo_Semantico por `seguranca.usuario_loja`. Usuário sem lojas vê zero linhas. Eventos de acesso negado entram na tabela de auditoria em até 5 minutos.

## Alternativas consideradas

- Catálogo próprio em tabelas e YAML, sem Purview: baixo custo e totalmente versionado, mas não oferece varredura automática nem linhagem entre itens do Fabric.
- Retenção única de 365 dias para todos os dados: regra simples, mas apagaria a Gold que sustenta a análise histórica e o SCD2, e manteria logs e quarentena além do necessário.
- Retenção indefinida: maximiza a análise histórica, mas amplia o risco de dados pessoais e o custo de armazenamento.
- Controle de acesso apenas por papéis do workspace, sem RLS e DDM: administração simples, mas dá a quem lê o workspace acesso a todas as lojas e a colunas confidenciais.

## Consequências

- O Purview adiciona custo e exige permissões de varredura sobre o tenant e o workspace.
- Os prazos de retenção precisam ser implementados por rotinas agendadas e testados. O `VACUUM` com 30 dias limita o time travel a esse período, então a reprodutibilidade de um treino depende de registrar a `delta_table_version` no MLflow e de reter o modelo, não de voltar tabelas além do prazo.
- Mudar um prazo exige alterar este ADR (ou substituí-lo) e a configuração da rotina.
- O mascaramento é aplicado no Warehouse. Consumo direto do Lakehouse deve ser limitado por papel, pois o Delta do OneLake não aplica DDM.

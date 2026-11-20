# 0006. Estratégia de ML: bibliotecas, treinamento e pontuação
Status: aceito
Data: 2026-11-20

## Contexto

A plataforma entrega dois modelos: previsão de demanda por produto, loja e dia (regressão) e probabilidade de churn por cliente (classificação). Os dados são tabulares e de volume moderado, e o treino roda em notebooks do Fabric. É preciso rastrear experimentos, versionar modelos, evitar PII nas features e garantir que uma falha na pontuação não corrompa as previsões já publicadas (Req. 7.1 a 7.12).

## Decisão

Bibliotecas: scikit-learn e LightGBM para o modelo e para o pré-processamento. MLflow, nativo do Fabric, para experimentos e registro de modelos. A lógica testável (features, divisão treino/teste, decisão de promoção, versão e pontuação) fica em `platform_lib/ml/`.

Treinamento:

- Features vêm das tabelas Gold (`features_demanda`, `features_churn`) e usam apenas chaves substitutas. Nome, CPF, e-mail, telefone e endereço completo são removidos por `drop_direct_pii`.
- A divisão treino/teste é determinística (`seed=42`, 80% para treino).
- Demanda: LightGBM de regressão, métricas MAE e RMSE. Churn: LightGBM ou regressão logística, métricas AUC e F1.
- Cada execução MLflow registra a semente, os parâmetros, as métricas do teste e a `delta_table_version` de cada tabela de features. O modelo só é registrado se todas as métricas forem calculadas.
- Promoção: demanda promove se `RMSE_candidato <= RMSE_produção`; churn promove se `AUC_candidato >= AUC_produção`. Caso contrário, mantém a versão em produção e registra o motivo e os valores. A nova versão é `max(versões) + 1`.
- O model card em `docs/model_cards/<modelo>.md` descreve finalidade, dados de treino, métricas, limitações e riscos de viés.

Pontuação:

- Em lote, após o treino e a decisão de promoção, em cada execução orquestrada.
- Uma previsão por registro de entrada, com `modelo`, `versao_modelo` e `pontuado_em_utc`.
- A saída vai para staging e substitui a partição da execução por `overwrite` atômico. Se falhar, a previsão anterior permanece.

## Alternativas consideradas

- Spark MLlib: distribuído e integrado ao Spark, mas com menos algoritmos e ajuste fino para dados tabulares que o LightGBM, e o volume do cenário não exige treino distribuído.
- Deep learning com PyTorch ou TensorFlow: útil para séries longas ou dados não estruturados, mas é custoso e menos interpretável para features tabulares simples.
- AutoML do Fabric (FLAML): reduz o esforço de ajuste, mas dificulta a reprodutibilidade e o controle sobre as features e as métricas exigidas.
- Pontuação em tempo real com endpoint do modelo: baixa latência, mas o caso de uso (estoque e retenção) é diário, e o endpoint acrescenta custo e superfície de operação.

## Consequências

- O treino é reprodutível a partir da semente, dos parâmetros e da versão Delta, enquanto a versão estiver dentro da retenção definida no ADR 0005.
- Previsões ficam defasadas até a próxima execução diária.
- O LightGBM é uma dependência extra do ambiente de execução do Fabric, e as versões precisam ser fixadas no ambiente.
- A regra de promoção impede regressão de qualidade, mas pode manter um modelo antigo se os dados mudarem de padrão. O monitoramento das métricas por versão é necessário.

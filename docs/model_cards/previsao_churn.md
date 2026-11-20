# Model Card: previsao_churn

## Finalidade

Estimar a probabilidade de cancelamento (churn) de clientes para apoiar ações de retenção. O modelo é de classificação binária e grava as pontuações em tabela Gold consumida pelo Modelo_Semantico. Uso restrito a apoio à decisão; não deve ser usado para negar serviço ou tomar decisões automáticas sobre pessoas.

## Dados de treino

- Fonte: tabela de features `features_churn` da camada Gold, composta por dados sintéticos gerados para a plataforma.
- Divisão treino/teste: 80/20 com seed 42, para reprodutibilidade.
- Não contém dados pessoais diretos (nome, CPF, e-mail, telefone, endereço completo); apenas identificadores substitutos.
- Cada execução MLflow registra a seed, os parâmetros e a versão Delta (`delta_table_version`) da tabela de features.

## Métricas

- AUC (área sob a curva ROC): mede a capacidade de ordenar clientes por risco.
- F1: média harmônica de precisão e revocação no limiar de decisão adotado.
- Ambas são calculadas no conjunto de teste (20%) e registradas no MLflow.

## Limitações

- Treinado com dados sintéticos: as métricas não representam desempenho em dados reais.
- Possível desbalanceamento de classes, que afeta o F1 e a escolha do limiar.
- Não considera fatores externos ao conjunto de features (concorrência, contexto econômico).
- A probabilidade pode não estar calibrada; use-a para ranqueamento.

## Riscos de viés

- Grupos de clientes sub-representados podem receber pontuações menos precisas.
- Atributos correlacionados com características sensíveis podem gerar viés indireto, mesmo sem dados pessoais diretos.
- Falsos positivos podem direcionar ofertas desnecessárias; falsos negativos deixam clientes em risco sem ação.
- Recomenda-se avaliar as métricas por segmento e revisar o limiar periodicamente.

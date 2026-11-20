# Model Card: previsao_demanda

## Finalidade

Prever a demanda (quantidade de unidades) por produto e período para apoiar planejamento de estoque e análise de vendas na plataforma. O modelo é de regressão e grava as previsões em tabela Gold consumida pelo Modelo_Semantico. Uso restrito a apoio à decisão; não deve acionar ações automáticas.

## Dados de treino

- Fonte: tabela de features `features_demanda` da camada Gold, composta por dados sintéticos gerados para a plataforma.
- Divisão treino/teste: 80/20 com seed 42, para reprodutibilidade.
- Não contém dados pessoais diretos (nome, CPF, e-mail, telefone, endereço completo); apenas identificadores substitutos.
- Cada execução MLflow registra a seed, os parâmetros e a versão Delta (`delta_table_version`) da tabela de features.

## Métricas

- MAE (erro absoluto médio): mede o desvio médio das previsões em unidades de demanda.
- RMSE (raiz do erro quadrático médio): penaliza mais os erros grandes.
- Ambas são calculadas no conjunto de teste (20%) e registradas no MLflow.

## Limitações

- Treinado com dados sintéticos: as métricas não representam desempenho em dados reais.
- Não captura eventos raros, promoções ou choques externos ausentes nas features.
- Previsões degradam para produtos ou períodos sem histórico (partida a frio).
- A janela de dados é limitada; sazonalidades longas podem não ser aprendidas.

## Riscos de viés

- Produtos ou segmentos sub-representados nos dados sintéticos podem ter erro maior.
- A distribuição sintética pode refletir premissas do gerador e não o comportamento real.
- Subestimar a demanda de itens pouco frequentes pode levar a ruptura de estoque.
- Recomenda-se monitorar o erro por segmento e retreinar com dados reais validados.

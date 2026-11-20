# Dicionário de dados — camada Gold

Gerado de `config/gold_schema.yaml` por `python -m infra.gen_data_dictionary`. Não editar à mão.

## dim_cliente

| Coluna | Tipo | Descrição | Sensibilidade |
|---|---|---|---|
| `sk_cliente` | bigint | Chave substituta do cliente (-1 = Desconhecido) | interna |
| `cliente_id` | bigint | Chave de negócio do cliente na origem | confidencial |
| `nome_mascarado` | string | Nome do cliente mascarado (sem dado pessoal direto) | confidencial |
| `cidade` | string | Cidade do cliente | interna |
| `uf` | string | Unidade da federação do cliente | interna |
| `data_inicio` | date | Início de vigência da versão | interna |
| `data_fim` | date | Fim de vigência da versão (9999-12-31 se aberta) | interna |
| `vigente` | boolean | Indica a versão vigente do cliente | interna |

## dim_produto

| Coluna | Tipo | Descrição | Sensibilidade |
|---|---|---|---|
| `sk_produto` | bigint | Chave substituta do produto (-1 = Desconhecido) | interna |
| `produto_id` | bigint | Chave de negócio do produto na origem | interna |
| `nome` | string | Nome do produto | pública |
| `categoria` | string | Categoria do produto | pública |
| `subcategoria` | string | Subcategoria do produto | pública |
| `preco_lista` | decimal(18,2) | Preço de lista do produto em BRL | interna |

## dim_loja

| Coluna | Tipo | Descrição | Sensibilidade |
|---|---|---|---|
| `sk_loja` | bigint | Chave substituta da loja (-1 = Desconhecido) | interna |
| `loja_id` | bigint | Chave de negócio da loja na origem | interna |
| `nome` | string | Nome da loja | pública |
| `regiao` | string | Região da loja | pública |
| `cidade` | string | Cidade da loja | pública |
| `uf` | string | Unidade da federação da loja | pública |

## dim_calendario

| Coluna | Tipo | Descrição | Sensibilidade |
|---|---|---|---|
| `sk_data` | int | Chave substituta da data no formato yyyymmdd (-1 = Desconhecido) | pública |
| `data` | date | Data do calendário | pública |
| `ano` | int | Ano | pública |
| `trimestre` | int | Trimestre do ano (1 a 4) | pública |
| `mes` | int | Mês do ano (1 a 12) | pública |
| `dia` | int | Dia do mês | pública |
| `dia_semana` | int | Dia da semana (1 = segunda a 7 = domingo) | pública |

## fato_vendas

| Coluna | Tipo | Descrição | Sensibilidade |
|---|---|---|---|
| `venda_id` | bigint | Identificador da venda na origem | interna |
| `sk_cliente` | bigint | Chave substituta do cliente | interna |
| `sk_produto` | bigint | Chave substituta do produto | interna |
| `sk_loja` | bigint | Chave substituta da loja | interna |
| `sk_data` | int | Chave substituta da data da venda (yyyymmdd) | interna |
| `quantidade` | int | Quantidade de itens vendidos | interna |
| `valor_venda` | decimal(18,2) | Valor da venda em BRL | confidencial |
| `custo_total` | decimal(18,2) | Custo total da venda em BRL | restrita |

## agg_vendas_dia

| Coluna | Tipo | Descrição | Sensibilidade |
|---|---|---|---|
| `sk_data` | int | Chave substituta da data (yyyymmdd) | interna |
| `sk_produto` | bigint | Chave substituta do produto | interna |
| `sk_loja` | bigint | Chave substituta da loja | interna |
| `quantidade` | bigint | Quantidade total vendida no dia | interna |
| `valor_venda` | decimal(18,2) | Valor total vendido no dia em BRL | confidencial |
| `custo_total` | decimal(18,2) | Custo total do dia em BRL | restrita |

## fato_estoque

| Coluna | Tipo | Descrição | Sensibilidade |
|---|---|---|---|
| `sk_data` | int | Chave substituta da data da posição (yyyymmdd) | interna |
| `sk_produto` | bigint | Chave substituta do produto | interna |
| `sk_loja` | bigint | Chave substituta da loja | interna |
| `quantidade_estoque` | int | Quantidade em estoque na data | interna |

## features_demanda

| Coluna | Tipo | Descrição | Sensibilidade |
|---|---|---|---|
| `sk_produto` | bigint | Chave substituta do produto | interna |
| `sk_loja` | bigint | Chave substituta da loja | interna |
| `data` | date | Data da observação | interna |
| `ano` | int | Ano da data | interna |
| `mes` | int | Mês da data | interna |
| `dia` | int | Dia do mês | interna |
| `dia_semana` | int | Dia da semana (0 = segunda a 6 = domingo) | interna |
| `fim_de_semana` | boolean | Indica sábado ou domingo | interna |
| `lag_1` | double | Quantidade vendida 1 dia antes | interna |
| `lag_7` | double | Quantidade vendida 7 dias antes | interna |
| `lag_14` | double | Quantidade vendida 14 dias antes | interna |
| `media_movel_7` | double | Média da quantidade nos 7 dias anteriores | interna |
| `media_movel_28` | double | Média da quantidade nos 28 dias anteriores | interna |
| `qtd_alvo` | double | Quantidade vendida no dia (variável alvo) | interna |

## features_churn

| Coluna | Tipo | Descrição | Sensibilidade |
|---|---|---|---|
| `sk_cliente` | bigint | Chave substituta do cliente | interna |
| `data_ref` | date | Data de referência das features | interna |
| `recencia_dias` | int | Dias desde a última compra até a data de referência | interna |
| `frequencia` | int | Número de compras até a data de referência | interna |
| `valor_total` | double | Valor total comprado até a data de referência em BRL | confidencial |
| `churn_alvo` | int | 1 se não houve compra no horizonte seguinte (variável alvo) | interna |

## previsao_demanda

| Coluna | Tipo | Descrição | Sensibilidade |
|---|---|---|---|
| `sk_produto` | bigint | Chave substituta do produto | interna |
| `sk_loja` | bigint | Chave substituta da loja | interna |
| `data` | date | Data prevista | interna |
| `previsao` | double | Quantidade prevista | interna |
| `modelo` | string | Nome do modelo que gerou a previsão | interna |
| `versao_modelo` | string | Versão do modelo no registro MLflow | interna |
| `pontuado_em_utc` | timestamp | Momento da pontuação em UTC | interna |

## previsao_churn

| Coluna | Tipo | Descrição | Sensibilidade |
|---|---|---|---|
| `sk_cliente` | bigint | Chave substituta do cliente | interna |
| `data_ref` | date | Data de referência da pontuação | interna |
| `prob_churn` | double | Probabilidade de churn entre 0 e 1 | confidencial |
| `modelo` | string | Nome do modelo que gerou a previsão | interna |
| `versao_modelo` | string | Versão do modelo no registro MLflow | interna |
| `pontuado_em_utc` | timestamp | Momento da pontuação em UTC | interna |

## config.ultima_atualizacao

| Coluna | Tipo | Descrição | Sensibilidade |
|---|---|---|---|
| `ts_utc` | timestamp | Momento da última atualização em UTC | pública |
| `ts_sao_paulo_texto` | string | Momento da última atualização em America/Sao_Paulo, em texto | pública |

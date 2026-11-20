# Capacidade e custos

Atende aos Req. 10.4 e 10.5. **Os valores abaixo são uma estimativa baseada em premissas, não um preço oficial.** Confirme o preço vigente da capacidade Fabric (SKU F) na calculadora de preços do Azure, na região e na moeda do contrato, antes de usar os números para orçamento.

## Dimensionamento por ambiente

| Ambiente | SKU Fabric | CUs | Regime de uso | Horas/mês (premissa) |
|---|---|---|---|---|
| dev | F2 | 2 | Pausada fora do horário de uso | 200 (10 h/dia x 20 dias úteis) |
| test | F4 | 4 | Pausada fora do horário de uso | 200 (10 h/dia x 20 dias úteis) |
| prod | F8 | 8 | Ligada 24x7 | 730 (média de horas por mês) |

Justificativa do dimensionamento: volume sintético padrão pequeno (milhares a poucos milhões de linhas), uma execução diária do pipeline mestre e relatórios Direct Lake. `test` fica acima de `dev` para ensaiar a carga de prod. Se o painel de capacidade mostrar throttling em `prod`, suba o SKU antes de alterar o código.

## Premissas da estimativa

1. Preço de referência assumido: **US$ 0,18 por CU-hora** (pay-as-you-go, valor de referência a confirmar).
2. Câmbio assumido: **R$ 5,50 por US$ 1,00**, o que dá **R$ 0,99 por CU-hora**.
3. Custo mensal = CUs x horas/mês x R$ 0,99.
4. Fora da estimativa: armazenamento OneLake, licenças Power BI (Pro/PPU para consumidores com SKU abaixo de F64), Azure SQL, Key Vault, Purview, Data Factory pago à parte, tributos e descontos de reserva.
5. Os ambientes não produtivos ficam pausados nas noites, nos fins de semana e nos feriados.

## Estimativa mensal em BRL

| Ambiente | Cálculo (CUs x horas x R$ 0,99) | Custo mensal estimado |
|---|---|---|
| dev (F2) | 2 x 200 x 0,99 | R$ 396,00 |
| test (F4) | 4 x 200 x 0,99 | R$ 792,00 |
| prod (F8) | 8 x 730 x 0,99 | R$ 5.781,60 |
| **Total** | | **R$ 6.969,60** |

Para comparação, manter dev e test ligados 24x7 (730 h) custaria 2 x 730 x 0,99 = R$ 1.445,40 e 4 x 730 x 0,99 = R$ 2.890,80. A pausa reduz o custo de dev e test de R$ 4.336,20 para R$ 1.188,00 por mês nesta estimativa (cerca de 73%).

Revise esta tabela quando mudar SKU, horas de uso, preço ou câmbio.

## Pausa e retomada em ambientes não produtivos

Escopo: somente `dev` e `test`. O script `infra/capacity.py` recusa qualquer operação em `prod` (código de saída 2).

| Ação | Horário (America/Sao_Paulo) | Dias |
|---|---|---|
| Retomar (`resume`) | 08:00 | Segunda a sexta |
| Pausar (`pause`) | 18:00 | Segunda a sexta |

Fora dessa janela os ambientes ficam pausados, inclusive sábado, domingo e feriados.

### Pré-requisitos

- Python 3.11 com `azure-identity` e `requests` instalados (usados pelo cliente real do script).
- Login do Azure disponível para `DefaultAzureCredential` (por exemplo `az login` ou service principal em variáveis de ambiente).
- O ID ARM da capacidade, no formato `/subscriptions/<id>/resourceGroups/<rg>/providers/Microsoft.Fabric/capacities/<nome>`.
- Permissão de Contributor (ou função equivalente) somente sobre o recurso da capacidade do ambiente.

### Passos para pausar (18:00)

1. Confirme que não há execução do pipeline mestre em andamento: `SELECT TOP 1 run_id, status FROM audit.execucoes ORDER BY inicio DESC;` deve retornar status diferente de `em andamento`.
2. Execute: `python -m infra.capacity pause --env dev --capacity-id <id-arm-da-capacidade-dev>` (repita com `--env test` e o ID de test).
3. Verifique que a saída é `pause executado no ambiente dev` e o código de saída é 0.
4. No portal do Azure, confirme que o estado da capacidade é `Paused`.

### Passos para retomar (08:00)

1. Execute: `python -m infra.capacity resume --env dev --capacity-id <id-arm-da-capacidade-dev>` (repita para `test`).
2. Verifique a saída `resume executado no ambiente dev` e o código de saída 0.
3. No portal do Azure, confirme que o estado da capacidade é `Active` e abra o workspace `fdai-dev` para validar que os itens carregam.

### Automação sugerida

Agende os dois comandos em um agendador com fuso `America/Sao_Paulo` (por exemplo workflow agendado do GitHub Actions com service principal de mínimo privilégio, Azure Automation ou Agendador de Tarefas). Ajuste o horário de execução do pipeline mestre (`MASTER_SCHEDULE_TIME` e `MASTER_SCHEDULE_TZ`) para dentro da janela 08:00 a 18:00 nos ambientes não produtivos, com folga para a execução terminar antes da pausa. Em dev e test, o agendamento diário não deve rodar em dias pausados (fins de semana e feriados), ou a execução falhará e disparará alerta.

### Falhas

- Código de saída 2 com `Operação '...' recusada no ambiente 'prod'`: comportamento esperado, prod nunca é pausado por este script.
- Erro HTTP do ARM (401/403/404): confira login, permissão e `--capacity-id`. Nada é alterado quando a chamada falha.
- Capacidade pausada durante uma execução: reexecute a partir da etapa que falhou (ver `docs/runbook.md`, procedimento 5).

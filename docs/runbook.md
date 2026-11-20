# Runbook de operação

Guia de operação (Req. 11.6, 9.10, 10.2, 10.3, 10.5). Cada procedimento informa sintoma, passos, resultado esperado e critério de sucesso. Consultas T-SQL rodam no Warehouse `wh_gold_<env>`; consultas Spark/SQL sobre `ops.logs` e `dq.resultados` rodam no Lakehouse correspondente. Substitua `<run_id>` pelo identificador da execução.

Etapas do pipeline mestre, em ordem: `ingestao`, `silver`, `qualidade`, `gold`, `ia`, `semantico`. Status de etapa: `sucesso`, `falha`, `não executada`.

## 1. Ingestão com falha

**Sintoma.** Alerta de falha com etapa `ingestao`, ou `audit.execucoes_etapas` com `etapa = 'ingestao'` e `status = 'falha'`. Entidades seguintes das demais continuam (uma entidade com falha não interrompe as outras), mas o status final da etapa é `falha`.

**Passos.**
1. Identifique a execução e a causa:
   `SELECT * FROM audit.execucoes_etapas WHERE run_id = '<run_id>' ORDER BY inicio;`
   e consulte `ops.logs` filtrando por `run_id` e `nivel = 'ERROR'`.
2. Classifique a causa:
   - Falha ao ler segredo no Key Vault: verifique `KEY_VAULT_URI`, a permissão do service principal (leitura de segredos) e o nome do segredo. A origem não é acessada nesse caso.
   - Falha de conexão com Azure SQL ou armazenamento: verifique firewall, credenciais rotacionadas e disponibilidade da origem.
   - Falha em uma entidade após 3 retentativas de 60 s: veja o erro da atividade Copy no monitor do pipeline `pl_ingestao`.
3. Corrija a causa (segredo, rede, permissão, dados da origem).
4. Reexecute a partir da etapa que falhou (procedimento 5).

**Resultado esperado.** A etapa `ingestao` termina com `sucesso`, a marca d'água de cada entidade avança (`config.ingestao_watermark`) e as etapas seguintes executam.

**Critério de sucesso.** `audit.execucoes_etapas` da nova execução mostra `ingestao = sucesso`; para cada entidade, a contagem lida da origem é igual à gravada na Bronze para o intervalo; reexecutar não cria duplicados (MERGE por chave).

## 2. Falha bloqueante de qualidade

**Sintoma.** Alerta com etapa `qualidade` e o nome da verificação; `audit.execucoes.status = 'falha'`; as etapas `gold`, `ia` e `semantico` ficam `não executada`. Os dados Bronze e Silver já gravados permanecem (sem reversão).

**Passos.**
1. Liste as violações da execução:
   `SELECT regra, tabela, severidade, avaliados, violacoes FROM dq.resultados WHERE run_id = '<run_id>' AND violacoes > 0;`
2. Identifique a regra `blocking` violada (definida em `config/dq_rules.yaml`) e os registros afetados na tabela Silver; confira também `silver._quarentena` para motivos de rejeição.
3. Decida a ação:
   - Dado ruim na origem: corrija na origem ou aguarde a próxima carga; os dados do gerador com ruído habilitado geram violações propositais.
   - Regra incorreta: corrija `config/dq_rules.yaml` por pull request (não desative a regra bloqueante para "passar" a execução).
4. Após a correção, reexecute a partir da etapa `qualidade` (procedimento 5).

**Resultado esperado.** A verificação roda sem violação de regra bloqueante; regras de severidade `warning` apenas registram.

**Critério de sucesso.** `dq.resultados` da nova execução tem 1 linha por regra avaliada e nenhuma regra `blocking` com `violacoes >= 1`; as etapas `gold`, `ia` e `semantico` terminam com `sucesso`.

## 3. Deploy com falha

**Sintoma.** Workflow `Deploy` do GitHub Actions falha no job `Deploy test` ou `Deploy prod`; notificação com ambiente e item que falharam. O ambiente seguinte não é implantado.

**Passos.**
1. Abra a execução do workflow e leia o relatório `deploy-report.json` (campos `env`, `ok`, `failures[].item`).
2. Classifique a causa:
   - Autenticação (401/403): confira o service principal, o login OIDC e a permissão de Contributor no workspace.
   - Item inexistente ou conflito (4xx): confira nomes `fdai-<env>`, `lh_<camada>_<env>`, `wh_gold_<env>`.
   - Indisponibilidade (5xx) ou capacidade pausada: verifique o estado da capacidade (procedimento 6) e repita.
3. Corrija a causa. Para falha de código ou configuração, abra pull request em branch de trabalho.
4. Reexecute o workflow (`Re-run failed jobs`). O provisionamento é idempotente (`python -m infra.provision`): só cria o que falta e não exclui nada.

**Resultado esperado.** O deploy em `test` conclui com `ok = true`; em `prod`, após aprovação manual de pelo menos 1 aprovador, também conclui.

**Critério de sucesso.** Cada workspace do ambiente tem 3 Lakehouses e 1 Warehouse; uma segunda execução do deploy não cria itens novos; o workflow termina verde.

## 4. Alerta que não chegou (falha de alerta)

**Sintoma.** Uma execução falhou (`audit.execucoes.status = 'falha'`) mas ninguém recebeu notificação em até 5 minutos, ou `ops.logs` contém erro de falha de alerta com o `run_id`.

**Passos.**
1. Confirme a falha original em `audit.execucoes_etapas` (a falha original é sempre registrada, mesmo que o alerta falhe).
2. Consulte `ops.logs` por `nivel = 'ERROR'` e mensagem de falha de alerta para o `run_id`. O envio é tentado até 3 vezes com intervalo de 1 minuto antes de registrar esse erro.
3. Verifique o canal: webhook do Teams (segredo apontado por `TEAMS_WEBHOOK_SECRET_NAME` no Key Vault, conexão `CONN_ALERT_WEBHOOK`), SMTP e destinatários (`ALERT_EMAIL_*`). Teste o webhook manualmente com uma mensagem de teste.
4. Corrija o canal (webhook expirado, segredo rotacionado, firewall) e notifique manualmente as pessoas responsáveis pela falha original informando etapa, mensagem de erro e `run_id`.
5. Trate a falha original pelo procedimento correspondente (1, 2 ou 5).

**Resultado esperado.** Um alerta de teste chega ao canal; novas falhas geram alerta com etapa, mensagem e `run_id` em até 5 minutos.

**Critério de sucesso.** Mensagem de teste recebida no canal configurado do ambiente e nenhum novo erro de falha de alerta em `ops.logs` nas execuções seguintes.

## 5. Reexecução a partir da etapa que falhou

**Sintoma ou gatilho.** Execução com status `falha` cuja causa já foi corrigida.

**Passos.**
1. Confirme que não há outra execução em andamento: `SELECT run_id, status FROM audit.execucoes WHERE status = 'em andamento';` deve retornar zero linhas (o pipeline mestre recusa iniciar com `EXECUCAO_EM_ANDAMENTO`).
2. Obtenha o `run_id` da execução original com status `falha`.
3. Execute o notebook `nb_reexecucao` no workspace do ambiente com o parâmetro `original_run_id = '<run_id>'` (e `warehouse_name`, `workspace_id`, `key_vault_uri`, `webhook_secret_name` do ambiente). Ele calcula o ponto de retomada (primeira etapa com status diferente de `sucesso`) e não repete etapas concluídas.
4. Acompanhe a execução no monitor do Fabric e no painel de monitoramento.

**Resultado esperado.** A nova execução começa na etapa que falhou e percorre as seguintes até `semantico`.

**Critério de sucesso.** `audit.execucoes` tem uma nova linha com `run_original_id = '<run_id>'` e `status = 'sucesso'`; `audit.execucoes_etapas` da nova execução não contém etapas anteriores ao ponto de retomada; a execução original permanece registrada como `falha`.

## 6. Pausa e retomada de capacidade

**Sintoma ou gatilho.** Início ou fim da janela de uso de `dev` e `test`; ou execução/deploy falhando porque a capacidade está pausada. Nunca se aplica a `prod`.

**Passos.**
1. Antes de pausar, confirme que não há execução em andamento (consulta do procedimento 5, passo 1).
2. Pausar: `python -m infra.capacity pause --env <dev|test> --capacity-id <id-arm>`.
3. Retomar: `python -m infra.capacity resume --env <dev|test> --capacity-id <id-arm>`.
4. Se o ambiente foi retomado após uma falha por capacidade pausada, execute o procedimento 5.
5. Horários e detalhes: `docs/capacidade-e-custos.md`.

**Resultado esperado.** A saída é `pause executado no ambiente <env>` ou `resume executado no ambiente <env>`, com código de saída 0. Para `prod` o script termina com código 2 e recusa a ação.

**Critério de sucesso.** O portal do Azure mostra a capacidade `Paused` após a pausa e `Active` após a retomada, e o workspace do ambiente abre normalmente depois da retomada.

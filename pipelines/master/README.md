# Pipeline mestre
Req. 9.1 a 9.5, 9.10, 10.2, 10.3. Lógica pura em `src/platform_lib/orchestration.py`.
- `fabric/pl_master.json`: etapas `ingestao`, `silver`, `qualidade`, `gold`, `ia`, `semantico` em sequência (`OnSuccess`), `concurrency = 1`. Antes da primeira etapa, consulta `audit.execucoes`; se houver outra execução `em andamento`, falha com `EXECUCAO_EM_ANDAMENTO` (`can_start`). Depois registra a execução e, a cada etapa, grava `audit.execucoes_etapas` logo após o término.
- Falha de etapa: registra a falha e as etapas seguintes como `não executada`, notifica via webhook (etapa e id da execução; 3 retentativas a cada 60 s, timeout de 20 s por tentativa, total abaixo de 5 min) e encerra com `Fail`.
- `fabric/schedule_diario.json`: agenda diária; horário e fuso vêm de `MASTER_SCHEDULE_TIME` e `MASTER_SCHEDULE_TZ`.
- `fabric/pl_semantico.json`: atualização do modelo semântico (etapa `semantico`).
- `sql/ddl_audit.sql`: DDL de `audit.execucoes` e `audit.execucoes_etapas` (Warehouse).
- `notebooks/nb_reexecucao.py`: lê a execução original, usa `resume_point` e `run_pipeline(start_from=...)`; a nova execução grava `run_original_id`.
Tokens `${NOME}` são substituídos no deploy (ver `.env.example`). A contagem `registros` vem do `exitValue` JSON do notebook (campo `registros`); sem esse campo, grava 0.

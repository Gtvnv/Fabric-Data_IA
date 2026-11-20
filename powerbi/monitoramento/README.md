# Painel de monitoramento (PBIP)

Projeto separado de `powerbi/fdai.*`. Mostra, por execução dos últimos 30 dias, duração em segundos, status (`sucesso`, `falha`, `em execução`) e volume de registros processados (Requirement 10.6).

- Modelo semântico TMDL em modo Direct Lake sobre `audit.execucoes`, `audit.execucoes_etapas` e `ops.logs`. Substitua os placeholders em `expressions.tmdl` pelo endpoint SQL e pelo nome do Lakehouse.
- Duração: medida `Duracao (s)` com `DATEDIFF(..., SECOND)`. Todos os instantes estão em UTC; não há conversão de fuso no modelo.
- Status: `em execução` quando `fim` é vazio; caso contrário `sucesso` ou `falha`.
- Janela de 30 dias: medida `Na Janela 30 dias` (usa `UTCNOW()`), aplicada como filtro do visual.
- Atualização em até 15 minutos após o término: o Direct Lake sem cópia de dados lê as tabelas Delta direto do OneLake. Mantenha a opção "Manter os dados do Direct Lake atualizados" ativa no modelo semântico publicado, para o reframing acompanhar cada gravação do pipeline (que ocorre em até 60 s do término). Se desativada, agende refresh a cada 15 minutos ou menos.

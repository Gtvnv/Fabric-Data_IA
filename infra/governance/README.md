# Governança (`infra/governance/`)

Artefatos da seção 6 do design (Req. 6.1 a 6.9). Nenhum segredo: valores `${VAR}` vêm do
ambiente (ver `.env.example`).

| Artefato | Conteúdo | Req. |
|---|---|---|
| `purview/scan.json` | Varredura diária (Recurrence, 1 dia) do workspace Fabric; linhagem de Relatorio_PowerBI até Fonte_Origem | 6.1, 6.2 |
| `purview/collections.json` | Coleções `dev`, `test`, `prod` | 6.2 |
| `purview/classification_rules.json` | Regras para nome, e-mail, documento e telefone | 6.3 |
| `masking.sql` | `ADD MASKED WITH` das colunas `confidencial` e `GRANT UNMASK` só a `rl_administrador` | 6.4 |
| `security_tables.sql` | `seguranca.usuario_loja` (RLS) e `governanca.catalogo_gold` | 6.5, 6.8, 6.9 |
| `roles_matrix.json` | Funções, workspace roles e grupos Entra ID | 6.6 |
| `audit_log.sql`, `audit_export.json` | Tabela de auditoria e exportação a cada 5 min (acesso negado) | 6.7 |

`masking.sql` é gerado: `python -m infra.governance.gen_masking` (use `--check` no CI).

## Matriz de permissões

| Função | Workspace Fabric | Grupo Entra ID | Permissão mínima | UNMASK |
|---|---|---|---|---|
| administrador | Admin | `ENTRA_GROUP_ADMINISTRADOR_ID` | Gerir workspace, acessos e governança | Sim |
| engenheiro | Member | `ENTRA_GROUP_ENGENHEIRO_ID` | Construir e executar pipelines, notebooks e tabelas | Não |
| analista | Contributor | `ENTRA_GROUP_ANALISTA_ID` | Criar relatórios e consultas sobre o Gold | Não |
| consumidor | Viewer | `ENTRA_GROUP_CONSUMIDOR_ID` | Ler relatórios, filtrados por RLS | Não |

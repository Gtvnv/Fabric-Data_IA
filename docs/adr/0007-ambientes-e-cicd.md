# 0007. Ambientes e CI/CD
Status: aceito
Data: 2026-11-20

## Contexto

A plataforma precisa de ambientes isolados (dev, test e prod), promoção controlada entre eles e validação automática de qualidade e de segredos antes de qualquer merge. O repositório pode estar no GitHub pessoal (`github.com/Gtvnv`), em que a main aceita commits diretos em projeto novo, ou em outras contas, onde a main só recebe alterações por pull request revisado.

## Decisão

Ambientes: 3 workspaces Fabric (`fdai-dev`, `fdai-test`, `fdai-prod`), criados pelo mesmo script de provisionamento, cada um com a própria capacidade. Ambientes não produtivos podem ser pausados fora do horário de uso (`infra/capacity.py pause|resume`).

Fluxo:

1. Trabalho em branches `feature/*`, `fix/*` e similares.
2. No pull request, o pipeline executa lint, verificação de sintaxe dos notebooks, `pytest` (unitários e de propriedade) e varredura de segredos (gitleaks com `--redact`). A falha da ferramenta conta como falha da verificação.
3. Após o merge na branch base, deploy automático em test por service principal.
4. Produção exige aprovação manual de pelo menos 1 revisor (environment protegido), e só então ocorre o deploy em prod.
5. A falha em um ambiente interrompe o fluxo e notifica.

Controle da branch base: fora de `github.com/Gtvnv`, a política de branch exige PR e pelo menos 1 revisor humano. Configuração por ambiente (nomes, IDs, canal de notificação) fica em `config/` e em variáveis do ambiente. Segredos ficam no Key Vault ou nos segredos do repositório, nunca no código. O workflow é GitHub Actions (`.github/workflows`).

## Alternativas consideradas

- Azure DevOps Pipelines: integração forte com Azure, com boas políticas de branch e ambientes, mas o repositório é hospedado no GitHub, o que acrescentaria um segundo sistema.
- Deployment pipelines nativos do Fabric como única ferramenta de promoção: simples e integrados ao workspace, mas não validam lint, testes e segredos antes do merge, nem cobrem o código de `src/` e da infraestrutura.
- Dois ambientes (dev e prod): menor custo, mas elimina o ambiente de validação antes da produção e a aprovação manual entre eles.
- Deploy manual por scripts: sem dependência de ferramenta de CI, mas sem rastreabilidade nem bloqueio de regressão.

## Consequências

- Cada merge passa por testes e varredura de segredos antes de chegar ao test, e a produção só recebe versões aprovadas.
- Três capacidades Fabric aumentam o custo, e a pausa dos ambientes não produtivos reduz esse gasto.
- O service principal precisa de permissão mínima por workspace, e a rotação do segredo faz parte da operação.
- A política de branch depende do dono do repositório. A regra de exceção para `github.com/Gtvnv` não vale para outras contas.

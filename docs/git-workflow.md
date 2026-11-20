# Política de fluxo Git e proteção de branch

Requisitos 12.3 e 12.4. Implementação em `infra/branch_protection.py`.

## Regras

1. Proibido commit, push direto e `push --force` na `main` (e em `master`/`release`), além de `reset --hard` e reescrita de histórico.
2. Todo trabalho nasce em branch própria com um destes prefixos: `feature/`, `fix/`, `hotfix/`, `chore/`, `refactor/`, `docs/`, `test/`. Use kebab-case, por exemplo `feature/1234-cadastro-empresa`.
3. Mudanças chegam à `main` somente por Pull Request.
4. Em remotos fora de `github.com/Gtvnv`, o PR é obrigatório e exige pelo menos 1 revisor humano. Isso vale para Azure DevOps (rumosolucoes), ClickUs, StartVet, Assemed, Barigui, Datacar e repositórios de terceiros.
5. Exceção: repositório novo e pessoal em `github.com/Gtvnv/*` permite commit e push direto na `main`. `push --force` e `reset --hard` continuam proibidos.
6. Use `git add <arquivo>` (nunca `git add .`), não use `--no-verify`, não commite `.env`, chaves ou credenciais. Primeiro push com `git push -u origin <branch>`.

## Aplicar a proteção

O script roda em dry-run por padrão e só imprime o payload:

```
python -m infra.branch_protection --remote-url https://github.com/Org/repo.git --branch main
```

Para aplicar (altera o repositório remoto), defina `GITHUB_TOKEN` (ver `.env.example`; permissão de administração do repositório) e passe `--apply`. O payload exige ao menos 1 aprovação, descarta aprovações obsoletas, aplica a regra a administradores e bloqueia force push e exclusão da branch. Remotos `github.com/Gtvnv/*` são tratados como exceção e nada é aplicado. Em outros provedores, configure a política equivalente de branch no próprio provedor.

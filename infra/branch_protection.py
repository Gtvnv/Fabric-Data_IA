"""Política de proteção de branch e de fluxo Git (Req. 12.3, 12.4).

Funções puras (validação de nome de branch, exceção de remoto pessoal, regras
de proteção) mais uma CLI que aplica a proteção via GitHub REST API.

A CLI roda em dry-run por padrão: só imprime o payload. Para aplicar, use
``--apply`` e defina GITHUB_TOKEN no ambiente (nunca em código ou log).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from typing import Any

ALLOWED_BRANCH_PREFIXES: tuple[str, ...] = (
    "feature/",
    "fix/",
    "hotfix/",
    "chore/",
    "refactor/",
    "docs/",
    "test/",
)
PROTECTED_BRANCHES: tuple[str, ...] = ("main", "master", "release")
PERSONAL_OWNER = "gtvnv"
TOKEN_ENV_VAR = "GITHUB_TOKEN"

_REMOTE_RE = re.compile(
    r"^(?:https?://(?:[^@/]+@)?|git@|ssh://git@)github\.com[/:]"
    r"(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


def parse_github_remote(url: str) -> tuple[str, str] | None:
    """Retorna (owner, repo) de uma URL github.com, ou None se não for."""
    m = _REMOTE_RE.match(url.strip())
    if not m:
        return None
    return m.group("owner"), m.group("repo")


def is_personal_remote(url: str) -> bool:
    """True só para remotos em github.com/Gtvnv/* (exceção de projeto pessoal)."""
    parsed = parse_github_remote(url)
    return parsed is not None and parsed[0].lower() == PERSONAL_OWNER


def requires_pr_review(url: str) -> bool:
    """PR e >= 1 revisor humano são obrigatórios fora de github.com/Gtvnv."""
    return not is_personal_remote(url)


def is_protected_branch(name: str) -> bool:
    return name in PROTECTED_BRANCHES


def is_valid_branch_name(name: str) -> bool:
    """Prefixo permitido, seguido de kebab-case/ids não vazio (sem espaços)."""
    for prefix in ALLOWED_BRANCH_PREFIXES:
        if name.startswith(prefix):
            rest = name[len(prefix):]
            return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", rest)) and not rest.endswith(
                ("/", ".")
            )
    return False


def can_commit_or_push_directly(branch: str, remote_url: str) -> bool:
    """Commit/push direto em branch protegida só no remoto pessoal Gtvnv.

    Push --force e reescrita de histórico são sempre proibidos (não há retorno
    positivo para eles aqui).
    """
    if not is_protected_branch(branch):
        return True
    return is_personal_remote(remote_url)


def build_protection_payload(required_reviewers: int = 1) -> dict[str, Any]:
    """Payload de PUT /repos/{owner}/{repo}/branches/{branch}/protection."""
    if required_reviewers < 1:
        raise ValueError("required_reviewers deve ser >= 1")
    return {
        "required_status_checks": None,
        "enforce_admins": True,
        "required_pull_request_reviews": {
            "required_approving_review_count": required_reviewers,
            "dismiss_stale_reviews": True,
        },
        "restrictions": None,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }


def apply_protection(
    owner: str, repo: str, branch: str, token: str, payload: dict[str, Any]
) -> int:
    url = f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}/protection"
    req = urllib.request.Request(  # noqa: S310 - URL https fixa
        url,
        data=json.dumps(payload).encode(),
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return resp.status


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--remote-url", required=True)
    p.add_argument("--branch", default="main")
    p.add_argument("--reviewers", type=int, default=1)
    p.add_argument("--apply", action="store_true", help="aplica de fato (padrão: dry-run)")
    args = p.parse_args(argv)

    if not requires_pr_review(args.remote_url):
        print("Remoto pessoal github.com/Gtvnv: exceção da política, nada a aplicar.")
        return 0
    parsed = parse_github_remote(args.remote_url)
    if parsed is None:
        print("Remoto não é github.com; aplique a política equivalente no provedor.")
        return 0
    owner, repo = parsed
    payload = build_protection_payload(args.reviewers)
    print(f"[{'APPLY' if args.apply else 'DRY-RUN'}] {owner}/{repo}@{args.branch}")
    print(json.dumps(payload, indent=2))
    if not args.apply:
        return 0
    token = os.environ.get(TOKEN_ENV_VAR)
    if not token:
        print(f"{TOKEN_ENV_VAR} não definido.", file=sys.stderr)
        return 2
    status = apply_protection(owner, repo, args.branch, token, payload)
    print(f"HTTP {status}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())


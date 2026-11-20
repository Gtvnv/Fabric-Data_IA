"""Smoke tests dos workflows de CI/deploy e das regras do .gitignore.

Validates: Requirements 9.6, 9.7, 12.1, 12.5
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _load(name: str) -> dict:
    data = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _runs(job: dict) -> str:
    return "\n".join(str(s.get("run", "")) for s in job["steps"])


def test_ci_yaml_valid_with_lint_tests_and_secret_scan():
    ci = _load("ci.yml")
    jobs = ci["jobs"]
    assert jobs
    runs = "\n".join(_runs(j) for j in jobs.values())
    assert "ruff check" in runs
    assert "pytest" in runs
    assert "secrets_scan" in runs or "gitleaks" in runs


def test_deploy_yaml_valid_test_then_prod_with_failure_notification():
    deploy = _load("deploy.yml")
    jobs = deploy["jobs"]
    test_job, prod_job = jobs["deploy-test"], jobs["deploy-prod"]

    assert test_job["environment"] == "test"
    assert prod_job["environment"] == "prod"
    needs = prod_job["needs"]
    needs = [needs] if isinstance(needs, str) else needs
    assert "deploy-test" in needs

    for job in (test_job, prod_job):
        notify = [s for s in job["steps"] if s.get("if") == "failure()"]
        assert notify, "falta passo de notificacao de falha"
        assert "notify" in str(notify[0].get("run", ""))


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "certs/server.pem",
        "secrets/private.key",
        "certs/client.pfx",
        "data/generated/clientes.csv",
        "data/generated/sub/dir/file.parquet",
    ],
)
def test_sensitive_and_generated_paths_are_git_ignored(path: str):
    result = subprocess.run(
        ["git", "check-ignore", "-q", path],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, f"{path} nao esta ignorado pelo git"


def test_env_example_is_not_ignored():
    result = subprocess.run(
        ["git", "check-ignore", "-q", ".env.example"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1

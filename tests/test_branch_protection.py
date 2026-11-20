import pytest
from infra.branch_protection import (
    build_protection_payload,
    can_commit_or_push_directly,
    is_valid_branch_name,
    main,
    requires_pr_review,
)

PERSONAL = "https://github.com/Gtvnv/Fabric-Data_IA.git"
OTHER = "https://dev.azure.com/rumosolucoes/proj/_git/repo"


@pytest.mark.parametrize(
    "name", ["feature/fabric-data-ai-platform", "fix/123-bug", "hotfix/x", "chore/deps",
             "refactor/a", "docs/a", "test/a"]
)
def test_valid_branches(name):
    assert is_valid_branch_name(name)


@pytest.mark.parametrize("name", ["main", "feat/x", "feature/", "feature/a b", "random"])
def test_invalid_branches(name):
    assert not is_valid_branch_name(name)


def test_remote_exception():
    assert not requires_pr_review(PERSONAL)
    assert not requires_pr_review("git@github.com:gtvnv/x.git")
    assert requires_pr_review("https://github.com/OutraOrg/x.git")
    assert requires_pr_review(OTHER)
    assert requires_pr_review("https://github.com/Gtvnv-evil/x.git")


def test_direct_main_rules():
    assert can_commit_or_push_directly("main", PERSONAL)
    assert not can_commit_or_push_directly("main", OTHER)
    assert can_commit_or_push_directly("feature/x", OTHER)


def test_payload_forbids_force_push_and_requires_review():
    p = build_protection_payload()
    assert p["allow_force_pushes"] is False
    assert p["required_pull_request_reviews"]["required_approving_review_count"] >= 1
    with pytest.raises(ValueError):
        build_protection_payload(0)


def test_cli_dry_run_does_not_need_token(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert main(["--remote-url", "https://github.com/Org/repo.git"]) == 0
    assert "DRY-RUN" in capsys.readouterr().out

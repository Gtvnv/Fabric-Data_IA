import pathlib

import pytest
import yaml
from infra.deploy import deploy, failure_message
from infra.provision import FakeFabricClient


def test_deploy_ok():
    report = deploy("test", FakeFabricClient())
    assert report == {"env": "test", "ok": True, "failures": []}


def test_deploy_failure_reports_env_and_item():
    report = deploy("prod", FakeFabricClient(fail_on={"lh_gold_prod": "boom"}))
    assert not report["ok"]
    assert [f["item"] for f in report["failures"]] == ["lh_gold_prod"]
    msg = failure_message(report)
    assert "prod" in msg and "lh_gold_prod" in msg


def test_deploy_rejects_dev():
    with pytest.raises(ValueError):
        deploy("dev", FakeFabricClient())


def test_workflow_structure():
    wf = yaml.safe_load(
        pathlib.Path(".github/workflows/deploy.yml").read_text(encoding="utf-8")
    )
    jobs = wf["jobs"]
    assert jobs["deploy-prod"]["environment"] == "prod"
    assert jobs["deploy-prod"]["needs"] == "deploy-test"
    for job in jobs.values():
        assert any(s.get("if") == "failure()" for s in job["steps"])
        assert any(str(s.get("uses", "")).startswith("azure/login") for s in job["steps"])

"""Estrutura do pipeline mestre: ordem, concorrência, agenda e caminho de falha."""

import json
import re
from pathlib import Path

from platform_lib.orchestration import ALERT_RETRIES, ALERT_WAIT_S, STEPS

ROOT = Path(__file__).resolve().parents[1]
FABRIC = ROOT / "pipelines" / "master" / "fabric"


def _load(name):
    return json.loads((FABRIC / name).read_text(encoding="utf-8"))


def _acts():
    return {a["name"]: a for a in _load("pl_master.json")["properties"]["activities"]}


def test_steps_in_sequence_with_on_success():
    acts = _acts()
    prev = "RegistrarInicioExecucao"
    for step in STEPS:
        assert acts[step]["dependsOn"][0]["activity"] == prev
        assert acts[step]["dependsOn"][0]["dependencyConditions"] == ["Succeeded"]
        reg = acts[f"RegistrarSucesso_{step}"]
        assert reg["dependsOn"][0]["activity"] == step
        prev = reg["name"]


def test_concurrency_and_active_run_check():
    props = _load("pl_master.json")["properties"]
    assert props["concurrency"] == 1
    acts = _acts()
    assert (
        "audit.execucoes"
        in acts["VerificarExecucaoAtiva"]["typeProperties"]["scripts"][0]["text"]["value"]
    )
    assert acts["ValidarConcorrencia"]["typeProperties"]["ifTrueActivities"][0]["type"] == "Fail"


def test_daily_schedule_configurable():
    cfg = _load("schedule_diario.json")["configuration"]
    assert cfg["type"] == "Daily"
    assert cfg["times"] == ["${MASTER_SCHEDULE_TIME}"]
    assert cfg["localTimeZoneId"] == "${MASTER_SCHEDULE_TZ}"


def test_failure_path_notifies_with_step_and_run_id():
    acts = _acts()
    for step in STEPS:
        assert acts[f"RegistrarFalha_{step}"]["dependsOn"][0]["dependencyConditions"] == ["Failed"]
        notify = acts[f"Notificar_{step}"]
        assert notify["policy"]["retry"] == ALERT_RETRIES
        assert notify["policy"]["retryIntervalInSeconds"] == ALERT_WAIT_S
        body = notify["typeProperties"]["body"]["value"]
        assert step in body and "pipeline().RunId" in body
        assert acts[f"Falhar_{step}"]["type"] == "Fail"


def test_audit_ddl_columns():
    ddl = (ROOT / "pipelines" / "master" / "sql" / "ddl_audit.sql").read_text(encoding="utf-8")
    for col in ("run_id", "run_original_id", "inicio", "fim", "status", "etapa", "registros"):
        assert re.search(rf"\b{col}\b", ddl)


def test_env_tokens_declared_in_env_example():
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    text = "".join(p.read_text(encoding="utf-8") for p in FABRIC.glob("*.json"))
    for token in set(re.findall(r"\$\{([A-Z_]+)\}", text)):
        assert f"{token}=" in env, token

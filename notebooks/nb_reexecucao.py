# Fabric notebook: nb_reexecucao
# Reexecução do pipeline mestre a partir da etapa que falhou, ligada à execução original
# (Req. 9.10). Notebook fino: a lógica está em platform_lib.orchestration.
import re
import time
import uuid

import notebookutils  # disponível no runtime Fabric
import requests

from platform_lib.orchestration import (
    STATUS_SUCCESS,
    StepRecord,
    can_start,
    resume_point,
    run_pipeline,
)

# Parâmetros (célula de parâmetros do Fabric pode sobrescrever)
original_run_id = ""  # execução do pipeline mestre que falhou
warehouse_name = "wh_gold"  # Warehouse com o schema audit
workspace_id = ""
key_vault_uri = ""
webhook_secret_name = ""  # segredo do Key Vault com a URL do webhook de alerta
NOTEBOOKS = {  # etapa -> notebooks executados em sequência
    "silver": ["nb_silver"],
    "qualidade": ["nb_qualidade"],
    "gold": ["nb_gold"],
    "ia": ["nb_features", "nb_treino_churn", "nb_treino_demanda", "nb_pontuacao"],
}
PIPELINES = {"ingestao": "pl_ingestao", "semantico": "pl_semantico"}  # etapa -> pipeline
NOTEBOOK_TIMEOUT_S = 4 * 3600

if not re.fullmatch(r"[0-9a-fA-F-]{8,64}", original_run_id):
    raise ValueError("original_run_id inválido")  # também evita injeção nos comandos T-SQL

run_id = uuid.uuid4().hex
wh = notebookutils.data.connect_to_artifact(warehouse_name, workspace_id, "Warehouse")


def _ts(value):
    return f"'{value:%Y-%m-%d %H:%M:%S.%f}'" if value else "NULL"


def _runner_notebooks(names):
    def runner():
        for name in names:
            notebookutils.notebook.run(name, NOTEBOOK_TIMEOUT_S)
        return 0

    return runner


def _runner_pipeline(name):
    def runner():
        item_id = notebookutils.fabric.getItemId(name, "DataPipeline")
        headers = {"Authorization": f"Bearer {notebookutils.credentials.getToken('pbi')}"}
        url = f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items/{item_id}"
        resp = requests.post(f"{url}/jobs/instances?jobType=Pipeline", headers=headers, timeout=60)
        resp.raise_for_status()
        while True:
            state = requests.get(resp.headers["Location"], headers=headers, timeout=60).json()
            if state["status"] in ("Completed", "Failed", "Cancelled", "Deduped"):
                break
            time.sleep(30)
        if state["status"] != "Completed":
            raise RuntimeError(f"pipeline {name}: {state['status']}")
        return 0

    return runner


def _notify(message):
    url = notebookutils.credentials.getSecret(key_vault_uri, webhook_secret_name)
    requests.post(url, json={"text": message}, timeout=20).raise_for_status()


def _audit_step(rec):
    if rec.reutilizada:  # já auditada na execução original
        return
    wh.query(
        "INSERT INTO audit.execucoes_etapas (run_id, etapa, inicio, fim, status, registros) "
        f"VALUES ('{run_id}', '{rec.etapa}', {_ts(rec.inicio)}, {_ts(rec.termino)}, "
        f"N'{rec.status}', {rec.registros})"
    )


prior = [
    StepRecord(etapa=r["etapa"], status=r["status"])
    for r in wh.query(
        f"SELECT etapa, status FROM audit.execucoes_etapas WHERE run_id = '{original_run_id}'"
    ).to_dict("records")
]
start_from = resume_point(prior)
result = "nada a reexecutar"
if start_from is not None:
    active = wh.query("SELECT run_id FROM audit.execucoes WHERE status = N'em andamento'")
    if not can_start(active.to_dict("records")):
        raise RuntimeError("Existe execução em andamento; reexecução não iniciada")
    wh.query(
        "INSERT INTO audit.execucoes (run_id, run_original_id, inicio, fim, status) "
        f"VALUES ('{run_id}', '{original_run_id}', SYSUTCDATETIME(), NULL, N'em andamento')"
    )
    runners = {s: _runner_notebooks(n) for s, n in NOTEBOOKS.items()}
    runners.update({s: _runner_pipeline(p) for s, p in PIPELINES.items()})
    records = run_pipeline(
        runners,
        start_from=start_from,
        run_id=run_id,
        original_run_id=original_run_id,
        audit=_audit_step,
        notifier=_notify,
    )
    final = "sucesso" if all(r.status == STATUS_SUCCESS for r in records) else "falha"
    wh.query(
        f"UPDATE audit.execucoes SET fim = SYSUTCDATETIME(), status = N'{final}' "
        f"WHERE run_id = '{run_id}'"
    )
    result = f"{run_id}: {final} a partir de {start_from}"
notebookutils.notebook.exit(result)

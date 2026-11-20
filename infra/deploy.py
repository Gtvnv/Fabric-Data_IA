"""Implantação de um ambiente (test/prod) chamada pelo workflow de deploy (Req. 9.7 a 9.9).

Subcomandos:
  ``python -m infra.deploy deploy --env test``  provisiona o ambiente via ``infra.provision``,
      grava um relatório JSON (ambiente e itens com falha) e retorna código != 0 se algo falhar.
  ``python -m infra.deploy notify --env test``  envia o relatório de falha ao webhook.

Variáveis: ``FABRIC_TOKEN`` (token do service principal), ``DEPLOY_REPORT_PATH`` (opcional),
``DEPLOY_WEBHOOK_URL`` (vem de secret do repositório). Nenhum valor secreto é impresso.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

from infra.provision import FabricClient, HttpFabricClient, provision

ALLOWED_ENVS = ("test", "prod")
DEFAULT_REPORT = "deploy-report.json"


def deploy(env: str, client: FabricClient) -> dict:
    """Implanta ``env`` e devolve o relatório ``{env, ok, failures: [{item, cause}]}``."""
    if env not in ALLOWED_ENVS:
        raise ValueError(f"ambiente inválido para deploy: {env!r}")
    result = provision([env], client)
    return {
        "env": env,
        "ok": not result.failures,
        "failures": [{"item": f.name, "cause": f.cause} for f in result.failures],
    }


def failure_message(report: dict) -> str:
    """Mensagem de notificação com ambiente e itens que falharam (sem segredos)."""
    items = ", ".join(f["item"] for f in report.get("failures", [])) or "desconhecido"
    return f"Deploy falhou no ambiente '{report.get('env', '?')}'. Itens: {items}"


def send_webhook(url: str, message: str, timeout: float = 30.0) -> None:
    req = urllib.request.Request(
        url,
        data=json.dumps({"text": message}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout):  # noqa: S310
        pass


def _report_path() -> Path:
    return Path(os.environ.get("DEPLOY_REPORT_PATH") or DEFAULT_REPORT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy do ambiente no Microsoft Fabric")
    parser.add_argument("command", choices=("deploy", "notify"))
    parser.add_argument("--env", required=True, choices=ALLOWED_ENVS)
    args = parser.parse_args(argv)

    if args.command == "deploy":
        token = os.environ.get("FABRIC_TOKEN")
        if not token:
            print("erro: defina FABRIC_TOKEN", file=sys.stderr)
            return 2
        report = deploy(args.env, HttpFabricClient(token))
        _report_path().write_text(json.dumps(report), encoding="utf-8")
        for f in report["failures"]:
            print(f"FALHA: {f['item']}: {f['cause']}", file=sys.stderr)
        return 0 if report["ok"] else 1

    path = _report_path()
    report = (
        json.loads(path.read_text(encoding="utf-8"))
        if path.exists()
        else {"env": args.env, "failures": []}
    )
    message = failure_message(report)
    print(message)
    url = os.environ.get("DEPLOY_WEBHOOK_URL")
    if not url:
        print("aviso: DEPLOY_WEBHOOK_URL ausente; notificação não enviada", file=sys.stderr)
        return 1
    try:
        send_webhook(url, message)
    except Exception as exc:  # noqa: BLE001 - nunca incluir a URL na saída
        print(f"erro ao notificar: {type(exc).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

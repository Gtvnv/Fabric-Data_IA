"""Pausa e retomada de capacidade Fabric por ambiente (Req. 10.5).

Uso: ``python -m infra.capacity pause|resume --env dev|test --capacity-id <id>``.
A operação é recusada em ``prod``. O cliente HTTP é injetável para testes.
"""

from __future__ import annotations

import argparse
import sys
from typing import Protocol

ACTIONS = ("pause", "resume")
ENVIRONMENTS = ("dev", "test", "prod")
PROTECTED_ENVIRONMENTS = frozenset({"prod"})


class CapacityError(Exception):
    """Operação de capacidade inválida ou recusada."""


class CapacityClient(Protocol):
    """Cliente mínimo da API de capacidade (ARM `suspend`/`resume`)."""

    def suspend(self, capacity_id: str) -> None: ...

    def resume(self, capacity_id: str) -> None: ...


def _validate(action: str, env: str) -> None:
    if action not in ACTIONS:
        raise CapacityError(f"Ação inválida: {action!r}. Use pause ou resume.")
    if env not in ENVIRONMENTS:
        raise CapacityError(f"Ambiente inválido: {env!r}. Use dev, test ou prod.")
    if env in PROTECTED_ENVIRONMENTS:
        raise CapacityError(f"Operação '{action}' recusada no ambiente '{env}'.")


def run(action: str, env: str, capacity_id: str, client: CapacityClient) -> str:
    """Executa ``pause``/``resume`` para o ambiente; recusa em ``prod``."""
    _validate(action, env)
    if not capacity_id:
        raise CapacityError("capacity_id é obrigatório.")
    if action == "pause":
        client.suspend(capacity_id)
    else:
        client.resume(capacity_id)
    return f"{action} executado no ambiente {env}"


class AzureCapacityClient:
    """Cliente real via Azure Resource Manager (requer `azure-identity` e `requests`)."""

    _API = "2023-11-01"

    def __init__(self, token: str | None = None) -> None:
        self._token = token

    def _post(self, capacity_id: str, verb: str) -> None:
        import requests  # importação tardia: dependência opcional

        token = self._token
        if token is None:
            from azure.identity import DefaultAzureCredential

            token = (
                DefaultAzureCredential().get_token("https://management.azure.com/.default").token
            )
        url = f"https://management.azure.com{capacity_id}/{verb}?api-version={self._API}"
        resp = requests.post(url, headers={"Authorization": f"Bearer {token}"}, timeout=60)
        resp.raise_for_status()

    def suspend(self, capacity_id: str) -> None:
        self._post(capacity_id, "suspend")

    def resume(self, capacity_id: str) -> None:
        self._post(capacity_id, "resume")


def main(argv: list[str] | None = None, client: CapacityClient | None = None) -> int:
    parser = argparse.ArgumentParser(prog="infra.capacity")
    parser.add_argument("action", choices=ACTIONS)
    parser.add_argument("--env", required=True)
    parser.add_argument("--capacity-id", required=True, help="ID ARM do recurso da capacidade")
    args = parser.parse_args(argv)
    try:
        msg = run(args.action, args.env, args.capacity_id, client or AzureCapacityClient())
    except CapacityError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Provisionamento idempotente dos ambientes sobre a Fabric REST API.

Cada ambiente tem 1 workspace (``fdai-<env>``), 3 Lakehouses (``lh_bronze_<env>``,
``lh_silver_<env>``, ``lh_gold_<env>``) e 1 Warehouse (``wh_gold_<env>``).
O script nunca exclui nem altera itens existentes (Req. 1.6 a 1.8).

Uso: ``python -m infra.provision [--envs dev test prod]`` com o token de acesso do
service principal na variável de ambiente ``FABRIC_TOKEN`` (nunca registrado em log).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

WORKSPACE = "Workspace"
LAKEHOUSE = "Lakehouse"
WAREHOUSE = "Warehouse"
LAYERS = ("bronze", "silver", "gold")
DEFAULT_ENVS = ("dev", "test", "prod")
FABRIC_API = "https://api.fabric.microsoft.com/v1"


@dataclass(frozen=True)
class DesiredItem:
    workspace: str  # ex.: "fdai-dev"
    kind: str  # "Workspace" | "Lakehouse" | "Warehouse"
    name: str  # ex.: "lh_bronze_dev"


@dataclass(frozen=True)
class ItemFailure:
    name: str
    cause: str


@dataclass
class ProvisionResult:
    created: list[DesiredItem] = field(default_factory=list)
    failures: list[ItemFailure] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return 0 if not self.failures else 1


class FabricClient(ABC):
    """Fronteira de I/O com o Fabric (substituível por dublê nos testes)."""

    @abstractmethod
    def list_items(self) -> list[DesiredItem]:
        """Lista workspaces e itens existentes (Workspace, Lakehouse, Warehouse)."""

    @abstractmethod
    def create_item(self, item: DesiredItem) -> None:
        """Cria o item; levanta exceção com a causa em caso de falha."""

    @abstractmethod
    def git_pending_changes(self, workspace: str) -> list[str]:
        """Nomes dos itens com mudanças pendentes na integração Git do workspace."""


def workspace_name(env: str) -> str:
    return f"fdai-{env}"


def desired_state(envs: list[str]) -> list[DesiredItem]:
    items: list[DesiredItem] = []
    for env in envs:
        ws = workspace_name(env)
        items.append(DesiredItem(ws, WORKSPACE, ws))
        items.extend(DesiredItem(ws, LAKEHOUSE, f"lh_{layer}_{env}") for layer in LAYERS)
        items.append(DesiredItem(ws, WAREHOUSE, f"wh_gold_{env}"))
    return items


def plan(desired: list[DesiredItem], existing: list[DesiredItem]) -> list[DesiredItem]:
    """Retorna somente os itens ausentes, na ordem do estado desejado (Req. 1.6, 1.8)."""
    have = set(existing)
    seen: set[DesiredItem] = set()
    missing: list[DesiredItem] = []
    for item in desired:
        if item not in have and item not in seen:
            seen.add(item)
            missing.append(item)
    return missing


def apply(items: list[DesiredItem], client: FabricClient) -> ProvisionResult:
    """Cria item a item. Falhas são registradas (nome e causa) e nada é excluído (Req. 1.7).

    Após a criação, verifica que não há mudanças pendentes na integração Git (Req. 1.4);
    pendência ou erro na verificação conta como falha do workspace.
    """
    result = ProvisionResult()
    failed_workspaces: set[str] = set()
    for item in items:
        if item.kind != WORKSPACE and item.workspace in failed_workspaces:
            result.failures.append(
                ItemFailure(item.name, f"workspace '{item.workspace}' não foi criado")
            )
            continue
        try:
            client.create_item(item)
            result.created.append(item)
        except Exception as exc:  # noqa: BLE001 - a causa é registrada e a execução continua
            if item.kind == WORKSPACE:
                failed_workspaces.add(item.name)
            result.failures.append(ItemFailure(item.name, f"{type(exc).__name__}: {exc}"))

    for ws in dict.fromkeys(i.workspace for i in items):
        if ws in failed_workspaces:
            continue
        try:
            pending = client.git_pending_changes(ws)
        except Exception as exc:  # noqa: BLE001
            result.failures.append(
                ItemFailure(ws, f"falha ao verificar integração Git: {type(exc).__name__}: {exc}")
            )
            continue
        if pending:
            result.failures.append(
                ItemFailure(ws, "mudanças pendentes na integração Git: " + ", ".join(pending))
            )
    return result


def provision(envs: list[str], client: FabricClient) -> ProvisionResult:
    return apply(plan(desired_state(envs), client.list_items()), client)


class FakeFabricClient(FabricClient):
    """Cliente em memória para testes."""

    def __init__(
        self,
        existing: list[DesiredItem] | None = None,
        fail_on: dict[str, str] | None = None,
        git_pending: dict[str, list[str]] | None = None,
    ) -> None:
        self.items: list[DesiredItem] = list(existing or [])
        self.fail_on = fail_on or {}  # nome do item -> causa
        self.git_pending = git_pending or {}
        self.create_calls: list[DesiredItem] = []

    def list_items(self) -> list[DesiredItem]:
        return list(self.items)

    def create_item(self, item: DesiredItem) -> None:
        self.create_calls.append(item)
        if item.name in self.fail_on:
            raise RuntimeError(self.fail_on[item.name])
        if item in self.items:
            raise RuntimeError(f"item duplicado: {item.name}")
        self.items.append(item)

    def git_pending_changes(self, workspace: str) -> list[str]:
        return list(self.git_pending.get(workspace, []))


class HttpFabricClient(FabricClient):
    """Cliente real sobre a Fabric REST API (token Bearer; nunca é registrado em log)."""

    _PATHS = {LAKEHOUSE: "lakehouses", WAREHOUSE: "warehouses"}

    def __init__(self, token: str, base_url: str = FABRIC_API, timeout: float = 60.0,
                 lro_timeout: float = 900.0) -> None:
        self._token = token
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._lro_timeout = lro_timeout
        self._ws_ids: dict[str, str] = {}

    def _request(self, method: str, url: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self._token}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
                raw = resp.read()
                return resp.status, dict(resp.headers), (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:500]
            raise RuntimeError(f"HTTP {exc.code} em {method} {url}: {detail}") from None
        except urllib.error.URLError as exc:
            raise RuntimeError(f"erro de rede em {method} {url}: {exc.reason}") from None

    def _wait(self, headers: dict[str, str]) -> None:
        location = headers.get("Location")
        if not location:
            return
        deadline = time.monotonic() + self._lro_timeout
        while time.monotonic() < deadline:
            _, _, state = self._request("GET", location)
            status = state.get("status")
            if status == "Succeeded":
                return
            if status == "Failed":
                raise RuntimeError(f"operação falhou: {state.get('error')}")
            time.sleep(5)
        raise RuntimeError("tempo esgotado aguardando a operação assíncrona")

    def _workspaces(self) -> dict[str, str]:
        _, _, body = self._request("GET", f"{self._base}/workspaces")
        self._ws_ids = {w["displayName"]: w["id"] for w in body.get("value", [])}
        return self._ws_ids

    def list_items(self) -> list[DesiredItem]:
        out: list[DesiredItem] = []
        for name, ws_id in self._workspaces().items():
            out.append(DesiredItem(name, WORKSPACE, name))
            _, _, body = self._request("GET", f"{self._base}/workspaces/{ws_id}/items")
            for it in body.get("value", []):
                if it.get("type") in (LAKEHOUSE, WAREHOUSE):
                    out.append(DesiredItem(name, it["type"], it["displayName"]))
        return out

    def create_item(self, item: DesiredItem) -> None:
        if item.kind == WORKSPACE:
            _, _, body = self._request(
                "POST", f"{self._base}/workspaces", {"displayName": item.name}
            )
            self._ws_ids[item.name] = body["id"]
            return
        ws_id = self._ws_ids.get(item.workspace) or self._workspaces().get(item.workspace)
        if ws_id is None:
            raise RuntimeError(f"workspace '{item.workspace}' não encontrado")
        path = self._PATHS[item.kind]
        _, headers, _ = self._request(
            "POST", f"{self._base}/workspaces/{ws_id}/{path}", {"displayName": item.name}
        )
        self._wait(headers)

    def git_pending_changes(self, workspace: str) -> list[str]:
        ws_id = self._ws_ids.get(workspace) or self._workspaces().get(workspace)
        if ws_id is None:
            raise RuntimeError(f"workspace '{workspace}' não encontrado")
        status, headers, body = self._request(
            "GET", f"{self._base}/workspaces/{ws_id}/git/status"
        )
        if status == 202:
            self._wait(headers)
            _, _, body = self._request("GET", f"{headers['Location']}/result")
        return [
            c.get("itemMetadata", {}).get("displayName", "?") for c in body.get("changes", [])
        ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Provisiona os ambientes no Microsoft Fabric")
    parser.add_argument("--envs", nargs="+", default=list(DEFAULT_ENVS))
    args = parser.parse_args(argv)
    token = os.environ.get("FABRIC_TOKEN")
    if not token:
        print("erro: defina FABRIC_TOKEN", file=sys.stderr)
        return 2
    result = provision(args.envs, HttpFabricClient(token))
    for item in result.created:
        print(f"criado: {item.kind} {item.name}")
    for failure in result.failures:
        print(f"FALHA: {failure.name}: {failure.cause}", file=sys.stderr)
    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())

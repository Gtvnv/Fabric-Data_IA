"""Testes leves dos artefatos de ``infra/governance/`` (Req. 6.1 a 6.9)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from infra.gen_gold_ddl import load_schema, split_table
from infra.governance.gen_masking import AUTHORIZED_ROLE, generate_masking_sql

ROOT = Path(__file__).resolve().parents[1]
GOV = ROOT / "infra" / "governance"
JSON_FILES = [
    "purview/scan.json",
    "purview/collections.json",
    "purview/classification_rules.json",
    "roles_matrix.json",
    "audit_export.json",
]


@pytest.mark.parametrize("rel", JSON_FILES)
def test_json_parses(rel: str) -> None:
    assert isinstance(json.loads((GOV / rel).read_text(encoding="utf-8")), dict)


def test_env_tokens_declared_in_env_example() -> None:
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    declared = set(re.findall(r"^([A-Z0-9_]+)=", env, re.MULTILINE))
    used: set[str] = set()
    for rel in JSON_FILES:
        used |= set(re.findall(r"\$\{([A-Z0-9_]+)\}", (GOV / rel).read_text(encoding="utf-8")))
    assert used - declared == set()


def test_masking_sql_is_current_and_covers_every_confidential_column() -> None:
    schema = load_schema()
    sql = (GOV / "masking.sql").read_text(encoding="utf-8")
    assert sql == generate_masking_sql(schema)
    expected = 0
    for name, spec in schema["tables"].items():
        s, t = split_table(name)
        for col, c in spec["columns"].items():
            if c["sensibilidade"] == "confidencial":
                expected += 1
                assert re.search(
                    rf"ALTER TABLE \[{s}\]\.\[{t}\] ALTER COLUMN \[{col}\] .* MASKED WITH", sql
                )
    assert expected > 0
    assert sql.count("MASKED WITH") == expected


def test_unmask_granted_only_to_authorized_role() -> None:
    sql = (GOV / "masking.sql").read_text(encoding="utf-8")
    grants = re.findall(r"^GRANT UNMASK TO (\[\w+\]);", sql, re.MULTILINE)
    assert grants == [f"[{AUTHORIZED_ROLE}]"]
    matrix = json.loads((GOV / "roles_matrix.json").read_text(encoding="utf-8"))
    unmask = [p["sql_role"] for p in matrix["papeis"] if p["unmask"]]
    assert unmask == [AUTHORIZED_ROLE]


def test_role_matrix_maps_workspace_roles() -> None:
    matrix = json.loads((GOV / "roles_matrix.json").read_text(encoding="utf-8"))
    mapping = {p["funcao"]: p["workspace_role"] for p in matrix["papeis"]}
    assert mapping == {
        "administrador": "Admin",
        "engenheiro": "Member",
        "analista": "Contributor",
        "consumidor": "Viewer",
    }
    assert all(p["grupo_entra_id"].startswith("${ENTRA_GROUP_") for p in matrix["papeis"])


def test_purview_scan_daily_and_collections_per_environment() -> None:
    scan = json.loads((GOV / "purview/scan.json").read_text(encoding="utf-8"))
    assert (scan["gatilho"]["frequencia"], scan["gatilho"]["intervalo"]) == ("Day", 1)
    cols = json.loads((GOV / "purview/collections.json").read_text(encoding="utf-8"))
    assert {c["ambiente"] for c in cols["colecoes"]} == {"dev", "test", "prod"}
    rules = json.loads((GOV / "purview/classification_rules.json").read_text(encoding="utf-8"))
    assert {r["categoria"] for r in rules["regras"]} == {"nome", "email", "documento", "telefone"}


def test_tables_ddl_and_audit_export() -> None:
    ddl = (GOV / "security_tables.sql").read_text(encoding="utf-8")
    assert "[seguranca].[usuario_loja]" in ddl
    assert "[governanca].[catalogo_gold]" in ddl
    audit = json.loads((GOV / "audit_export.json").read_text(encoding="utf-8"))
    assert audit["agenda"]["intervalo_minutos"] <= 5
    assert audit["destino"]["tabela"] in (GOV / "audit_log.sql").read_text(
        encoding="utf-8"
    ).replace("[", "").replace("]", "")

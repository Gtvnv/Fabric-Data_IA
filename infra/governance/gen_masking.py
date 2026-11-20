"""Gera o T-SQL de mascaramento dinâmico (DDM) a partir de ``config/gold_schema.yaml``.

Toda coluna com ``sensibilidade: confidencial`` recebe ``ADD MASKED WITH (FUNCTION = ...)``
e ``UNMASK`` é concedido somente à função autorizada (Req. 6.4).

Uso: ``python -m infra.governance.gen_masking [--schema caminho] [--out arquivo] [--check]``.
``--check`` falha (código 1) se o SQL versionado (``masking.sql``) estiver desatualizado.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from infra.gen_gold_ddl import DEFAULT_SCHEMA_PATH, load_schema, map_type, split_table

CONFIDENTIAL = "confidencial"
AUTHORIZED_ROLE = "rl_administrador"
DEFAULT_OUT = Path(__file__).resolve().parent / "masking.sql"


def mask_function(tipo: str) -> str:
    """Função de máscara por tipo: texto parcial; demais tipos ``default()``."""
    if str(tipo).strip().lower() == "string":
        return 'partial(1, "XXXXXXXX", 0)'
    return "default()"


def confidential_columns(schema: Mapping[str, Any]) -> list[tuple[str, str, str, str]]:
    """Lista ``(schema_sql, tabela, coluna, tipo)`` das colunas confidenciais."""
    result = []
    for name, spec in schema["tables"].items():
        s, t = split_table(name)
        for col, c in spec["columns"].items():
            if str(c.get("sensibilidade", "")).strip().lower() == CONFIDENTIAL:
                result.append((s, t, col, c["tipo"]))
    return result


def generate_masking_sql(schema: Mapping[str, Any], role: str = AUTHORIZED_ROLE) -> str:
    lines = [
        "-- Mascaramento dinâmico de dados (Req. 6.4). Gerado por infra/governance/gen_masking.py",
        "-- a partir de config/gold_schema.yaml (sensibilidade = confidencial). Idempotente.",
        f"IF DATABASE_PRINCIPAL_ID(N'{role}') IS NULL EXEC(N'CREATE ROLE [{role}]');",
        "",
    ]
    for s, t, col, tipo in confidential_columns(schema):
        sql_type = map_type(tipo, "tsql")
        lines.append(
            f"ALTER TABLE [{s}].[{t}] ALTER COLUMN [{col}] {sql_type} "
            f"MASKED WITH (FUNCTION = '{mask_function(tipo)}');"
        )
    lines += [
        "",
        "-- UNMASK somente à função autorizada; nenhuma outra função recebe a permissão.",
        f"GRANT UNMASK TO [{role}];",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--check", action="store_true")
    args = p.parse_args(argv)
    sql = generate_masking_sql(load_schema(args.schema))
    out = Path(args.out)
    if args.check:
        if not out.exists() or out.read_text(encoding="utf-8") != sql:
            sys.stderr.write(f"{out} desatualizado; regenere com gen_masking\n")
            return 1
        return 0
    out.write_text(sql, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

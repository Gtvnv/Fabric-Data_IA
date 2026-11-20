"""Gera DDL Delta (Spark SQL) e T-SQL (Warehouse) a partir de ``config/gold_schema.yaml``.

Uso: ``python -m infra.gen_gold_ddl [--dialect delta|tsql] [--schema caminho] [--out arquivo]``.
Requisitos: 4.5, 4.9, 11.8.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "config" / "gold_schema.yaml"
DEFAULT_SCHEMA_NAME = "dbo"
DIALECTS = ("delta", "tsql")

_DECIMAL_RE = re.compile(r"^decimal\(\s*\d+\s*,\s*\d+\s*\)$", re.IGNORECASE)
_TSQL_TYPES = {
    "bigint": "BIGINT",
    "int": "INT",
    "string": "VARCHAR(8000)",
    "date": "DATE",
    "boolean": "BIT",
    "double": "FLOAT",
    "timestamp": "DATETIME2(6)",
}
_DELTA_TYPES = {k: k.upper() for k in _TSQL_TYPES}


def load_schema(path: Path | str = DEFAULT_SCHEMA_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, Mapping) or not isinstance(data.get("tables"), Mapping):
        raise ValueError("esquema Gold inválido: chave 'tables' ausente")
    return dict(data)


def split_table(name: str) -> tuple[str, str]:
    """``'config.x'`` -> ``('config', 'x')``; sem prefixo usa ``dbo``."""
    schema, _, table = name.rpartition(".")
    return (schema or DEFAULT_SCHEMA_NAME, table)


def map_type(tipo: str, dialect: str) -> str:
    t = str(tipo).strip().lower()
    if _DECIMAL_RE.match(t):
        return t.upper()
    table = _TSQL_TYPES if dialect == "tsql" else _DELTA_TYPES
    if t not in table:
        raise ValueError(f"tipo não suportado: {tipo}")
    return table[t]


def _q(name: str, dialect: str) -> str:
    return f"[{name}]" if dialect == "tsql" else f"`{name}`"


def table_ddl(name: str, spec: Mapping[str, Any], dialect: str) -> str:
    if dialect not in DIALECTS:
        raise ValueError(f"dialeto inválido: {dialect}")
    schema, table = split_table(name)
    cols = []
    for col, c in spec["columns"].items():
        null = "NOT NULL" if c.get("nullable") is False else "NULL"
        if dialect == "delta" and null == "NULL":
            null = ""
        cols.append(f"    {_q(col, dialect)} {map_type(c['tipo'], dialect)} {null}".rstrip())
    body = ",\n".join(cols)
    full = f"{_q(schema, dialect)}.{_q(table, dialect)}"
    if dialect == "delta":
        return f"CREATE TABLE IF NOT EXISTS {full} (\n{body}\n) USING DELTA;"
    return (
        f"IF OBJECT_ID(N'{schema}.{table}', N'U') IS NULL\n"
        f"CREATE TABLE {full} (\n{body}\n);"
    )


def generate_ddl(schema: Mapping[str, Any], dialect: str = "delta") -> str:
    if dialect not in DIALECTS:
        raise ValueError(f"dialeto inválido: {dialect}")
    tables = schema["tables"]
    schemas = sorted({split_table(t)[0] for t in tables})
    lines = [f"-- DDL Gold gerado de config/gold_schema.yaml ({dialect}). Idempotente."]
    for s in schemas:
        if s == DEFAULT_SCHEMA_NAME and dialect == "tsql":
            continue
        if dialect == "delta":
            lines.append(f"CREATE SCHEMA IF NOT EXISTS {_q(s, dialect)};")
        else:
            lines.append(
                f"IF SCHEMA_ID(N'{s}') IS NULL EXEC(N'CREATE SCHEMA {_q(s, dialect)}');"
            )
    for name, spec in tables.items():
        lines.append("")
        lines.append(table_ddl(name, spec, dialect))
    return "\n".join(lines) + "\n"


def dictionary_rows(schema: Mapping[str, Any]) -> list[dict[str, str]]:
    """Linhas do dicionário de dados (tabela, coluna, tipo, descricao, sensibilidade)."""
    rows = []
    for tname, spec in schema["tables"].items():
        for col, c in spec["columns"].items():
            rows.append(
                {
                    "tabela": tname,
                    "coluna": col,
                    "tipo": c["tipo"],
                    "descricao": c["descricao"],
                    "sensibilidade": c["sensibilidade"],
                }
            )
    return rows


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dialect", choices=DIALECTS, default="delta")
    p.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH))
    p.add_argument("--out")
    args = p.parse_args(argv)
    ddl = generate_ddl(load_schema(args.schema), args.dialect)
    if args.out:
        Path(args.out).write_text(ddl, encoding="utf-8")
    else:
        sys.stdout.write(ddl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

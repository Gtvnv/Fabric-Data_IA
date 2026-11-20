"""Gera o dicionário de dados (``docs/data-dictionary.md`` e ``.csv``) de ``config/gold_schema.yaml``.
Uso: ``python -m infra.gen_data_dictionary [--check] [--schema caminho] [--md arquivo] [--csv arquivo]``.
Com ``--check`` não escreve; retorna 1 se os arquivos commitados estiverem desatualizados.
Requisitos: 11.5, 11.8.
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from infra.gen_gold_ddl import DEFAULT_SCHEMA_PATH, dictionary_rows, load_schema

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MD_PATH = ROOT / "docs" / "data-dictionary.md"
DEFAULT_CSV_PATH = ROOT / "docs" / "data-dictionary.csv"
FIELDS = ("tabela", "coluna", "tipo", "descricao", "sensibilidade")


def render_csv(schema: Mapping[str, Any]) -> str:
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(dictionary_rows(schema))
    return buf.getvalue()


def _cell(v: str) -> str:
    return str(v).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def render_markdown(schema: Mapping[str, Any]) -> str:
    rows = dictionary_rows(schema)
    lines = [
        "# Dicionário de dados — camada Gold",
        "",
        "Gerado de `config/gold_schema.yaml` por `python -m infra.gen_data_dictionary`. Não editar à mão.",
    ]
    for tname in schema["tables"]:
        lines += ["", f"## {tname}", "", "| Coluna | Tipo | Descrição | Sensibilidade |", "|---|---|---|---|"]
        for r in (r for r in rows if r["tabela"] == tname):
            lines.append(
                f"| `{r['coluna']}` | {_cell(r['tipo'])} | {_cell(r['descricao'])} | {_cell(r['sensibilidade'])} |"
            )
    return "\n".join(lines) + "\n"


def _read(path: Path) -> str | None:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n") if path.exists() else None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH))
    p.add_argument("--md", default=str(DEFAULT_MD_PATH))
    p.add_argument("--csv", default=str(DEFAULT_CSV_PATH))
    p.add_argument("--check", action="store_true")
    args = p.parse_args(argv)
    schema = load_schema(args.schema)
    outputs = {Path(args.md): render_markdown(schema), Path(args.csv): render_csv(schema)}
    if args.check:
        stale = [str(path) for path, text in outputs.items() if _read(path) != text]
        for s in stale:
            sys.stderr.write(f"desatualizado: {s}\n")
        return 1 if stale else 0
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

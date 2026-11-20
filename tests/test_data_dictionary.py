"""Dicionário de dados commitado está atualizado e cobre o esquema Gold (tarefa 14.6). Req. 11.5, 11.8."""
from __future__ import annotations

import csv

from infra.gen_data_dictionary import (
    DEFAULT_CSV_PATH,
    DEFAULT_MD_PATH,
    main,
    render_csv,
    render_markdown,
)
from infra.gen_gold_ddl import load_schema

from platform_lib.docs_tools import validate_data_dictionary


def test_committed_files_are_up_to_date():
    assert main(["--check"]) == 0


def test_committed_csv_passes_validation():
    schema = load_schema()
    with open(DEFAULT_CSV_PATH, encoding="utf-8", newline="") as f:
        entries = list(csv.DictReader(f))
    assert validate_data_dictionary(schema, entries) == []


def test_markdown_lists_every_column():
    schema = load_schema()
    md = DEFAULT_MD_PATH.read_text(encoding="utf-8")
    assert md.replace("\r\n", "\n") == render_markdown(schema)
    for t, spec in schema["tables"].items():
        assert f"## {t}" in md
        for col in spec["columns"]:
            assert f"`{col}`" in md
    assert render_csv(schema).count("\n") > len(schema["tables"])

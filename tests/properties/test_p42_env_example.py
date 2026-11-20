"""Property 42: Arquivo de exemplo de variáveis de ambiente.

**Validates: Requirements 12.2**
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

ROOT = Path(__file__).resolve().parents[2]
ENV_EXAMPLE = ROOT / ".env.example"
CODE_DIRS = ["src", "infra", "notebooks", "pipelines", "config", "powerbi"]
# Variáveis lidas apenas pela infraestrutura de testes (tests/conftest.py).
TEST_INFRA_VARS = {"HYPOTHESIS_PROFILE"}

PLACEHOLDER = re.compile(r"^<[^<>\s][^<>]*>$")
# Formas típicas de segredo real.
SECRET_SHAPES = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]*"),  # JWT
    re.compile(r"(?i)\b(?:Password|Pwd|AccountKey|SharedAccessSignature)\s*=\s*\S+"),
    re.compile(r"(?i)[?&]sig=[A-Za-z0-9%+/=]{10,}"),
    re.compile(r"https://[^/\s]*webhook[^/\s]*/\S{20,}"),
    re.compile(r"^[A-Za-z0-9+/_-]{32,}={0,2}$"),  # blob longo base64/hex
    re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"),
]


def looks_like_secret(value: str) -> bool:
    return any(p.search(value) for p in SECRET_SHAPES)


def is_valid_value(value: str) -> bool:
    """Vazio ou placeholder identificável, sem forma de segredo real."""
    if value == "":
        return True
    return bool(PLACEHOLDER.match(value)) and not looks_like_secret(value)


def parse_env_example(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def _is_environ(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _const_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def scan_env_reads(source: str) -> set[str]:
    names: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and _is_environ(node.value):
            name = _const_str(node.slice)
            if name:
                names.add(name)
        elif isinstance(node, ast.Call) and node.args:
            f = node.func
            is_getenv = (
                isinstance(f, ast.Attribute)
                and f.attr == "getenv"
                and isinstance(f.value, ast.Name)
                and f.value.id == "os"
            ) or (isinstance(f, ast.Name) and f.id == "getenv")
            is_environ_get = (
                isinstance(f, ast.Attribute)
                and f.attr in {"get", "pop", "setdefault"}
                and _is_environ(f.value)
            )
            if is_getenv or is_environ_get:
                name = _const_str(node.args[0])
                if name:
                    names.add(name)
    return names


def scan_code_env_vars() -> set[str]:
    found: set[str] = set()
    for d in CODE_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if any(part in {"__pycache__", ".venv"} for part in path.parts):
                continue
            found |= scan_env_reads(path.read_text(encoding="utf-8"))
    return found | TEST_INFRA_VARS


ENV_VARS = sorted(scan_code_env_vars())
ENV = parse_env_example(ENV_EXAMPLE.read_text(encoding="utf-8")) if ENV_EXAMPLE.exists() else {}


# Feature: fabric-data-ai-platform, Property 42: Arquivo de exemplo de variáveis de ambiente
@settings(max_examples=100)
@given(st.data())
def test_env_example_covers_vars_read_by_code(data):
    assert ENV_EXAMPLE.exists(), ".env.example ausente na raiz"
    subset = data.draw(st.lists(st.sampled_from(ENV_VARS), min_size=1, unique=True))
    for name in subset:
        assert name in ENV, f"{name} é lida pelo código mas falta no .env.example"
        assert is_valid_value(ENV[name]), f"{name} deve ser vazio ou placeholder sem segredo"


# Feature: fabric-data-ai-platform, Property 42: Arquivo de exemplo de variáveis de ambiente
@settings(max_examples=100)
@given(st.data())
def test_every_env_example_value_is_empty_or_placeholder(data):
    keys = data.draw(st.lists(st.sampled_from(sorted(ENV)), min_size=1, unique=True))
    for k in keys:
        assert is_valid_value(ENV[k]), f"{k} tem valor que não é vazio/placeholder"
        assert not looks_like_secret(ENV[k])


# Feature: fabric-data-ai-platform, Property 42: Arquivo de exemplo de variáveis de ambiente
@settings(max_examples=100)
@given(
    names=st.sets(st.from_regex(r"[A-Z][A-Z0-9_]{2,20}", fullmatch=True), min_size=1, max_size=6),
    style=st.sampled_from(["getenv", "get", "index"]),
)
def test_scanner_detects_all_env_reads(names, style):
    templates = {
        "getenv": 'os.getenv("{n}")',
        "get": 'os.environ.get("{n}", "x")',
        "index": 'os.environ["{n}"]',
    }
    src = "import os\n" + "\n".join(f"v{i} = " + templates[style].format(n=n)
                                    for i, n in enumerate(sorted(names)))
    assert scan_env_reads(src) == set(names)


# Feature: fabric-data-ai-platform, Property 42: Arquivo de exemplo de variáveis de ambiente
@settings(max_examples=100)
@given(
    secret=st.one_of(
        st.from_regex(r"[A-Za-z0-9+/]{40,64}", fullmatch=True),
        st.from_regex(r"AKIA[0-9A-Z]{16}", fullmatch=True),
        st.from_regex(r"eyJ[A-Za-z0-9_-]{12,20}\.[A-Za-z0-9_-]{12,20}\.[A-Za-z0-9_-]{5,20}",
                      fullmatch=True),
        st.from_regex(r"(Password|AccountKey)=[A-Za-z0-9]{8,20}", fullmatch=True),
        st.uuids().map(str),
    ),
    placeholder=st.from_regex(r"<[a-z][a-z _-]{2,15}>", fullmatch=True),
)
def test_validator_rejects_secrets_and_accepts_placeholders(secret, placeholder):
    assert not is_valid_value(secret)
    assert is_valid_value(placeholder)
    assert is_valid_value("")


@pytest.mark.parametrize("name", ["KEY_VAULT_URI", "AZURE_SQL_SERVER", "PURVIEW_ENDPOINT"])
def test_expected_groups_present(name):
    assert name in ENV

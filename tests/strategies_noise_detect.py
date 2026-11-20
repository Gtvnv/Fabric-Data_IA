"""Estratégias e especificações para a detecção de ruído (Property 23)."""
from __future__ import annotations

from datetime import date

from hypothesis import strategies as st

from platform_lib.dq import Rule
from platform_lib.silver import META_TS, EntitySpec
from platform_lib.synth import (
    DATE_NOISE_COLUMN,
    ENTITIES,
    KEY_COLUMNS,
    NULL_NOISE_COLUMN,
    GenParams,
    NoiseParams,
)

INGESTION_TS = "2024-01-01T00:00:00+00:00"

_COLUMN_TYPES: dict[str, dict[str, str]] = {
    "clientes": {
        "cliente_id": "int",
        "nome": "str",
        "email": "str",
        "telefone": "str",
        "documento": "str",
        "cidade": "str",
        "uf": "str",
        "data_cadastro": "date",
        "atualizado_em": "timestamp",
    },
    "produtos": {
        "produto_id": "int",
        "nome": "str",
        "categoria": "str",
        "subcategoria": "str",
        "preco_lista": "decimal",
        "custo": "decimal",
        "atualizado_em": "timestamp",
    },
    "lojas": {
        "loja_id": "int",
        "nome": "str",
        "regiao": "str",
        "cidade": "str",
        "uf": "str",
        "atualizado_em": "timestamp",
    },
    "vendas": {
        "venda_id": "int",
        "cliente_id": "int",
        "produto_id": "int",
        "loja_id": "int",
        "data_venda": "date",
        "quantidade": "int",
        "valor_venda": "decimal",
        "custo_total": "decimal",
        "atualizado_em": "timestamp",
    },
    "estoque": {
        "produto_id": "int",
        "loja_id": "int",
        "data_posicao": "date",
        "quantidade_estoque": "int",
    },
}

SPECS: dict[str, EntitySpec] = {
    e: EntitySpec(name=e, key=KEY_COLUMNS[e], columns=_COLUMN_TYPES[e]) for e in ENTITIES
}

# Em estoque, data_posicao faz parte da chave e é a coluna que recebe data inválida: a
# linha ruidosa muda de chave e a cópia limpa ficaria sem par. Como data_posicao é única
# por geração, a unicidade por (produto_id, loja_id) equivale à chave limpa.
UNIQUE_COLUMNS: dict[str, tuple[str, ...]] = {
    **KEY_COLUMNS,
    "estoque": ("produto_id", "loja_id"),
}

RULES: dict[str, tuple[Rule, Rule]] = {
    e: (
        Rule(f"{e}_unique", e, "unique", UNIQUE_COLUMNS[e], "blocking"),
        Rule(f"{e}_not_null", e, "not_null", (NULL_NOISE_COLUMN[e],), "blocking"),
    )
    for e in ENTITIES
}

DATE_COLUMN = DATE_NOISE_COLUMN
TS_COLUMN = META_TS

_pct = st.floats(min_value=0.0, max_value=0.20, allow_nan=False)


@st.composite
def noisy_params(draw) -> GenParams:
    """Parâmetros pequenos com ruído em todos os tipos."""
    return GenParams(
        seed=draw(st.integers(0, 2_147_483_647)),
        n_customers=draw(st.integers(1, 40)),
        n_products=draw(st.integers(1, 15)),
        n_stores=draw(st.integers(1, 8)),
        start=date(2022, 1, 1),
        end=draw(st.dates(min_value=date(2022, 6, 1), max_value=date(2024, 12, 31))),
        noise=NoiseParams(
            dup_pct=draw(_pct), null_pct=draw(_pct), bad_date_pct=draw(_pct)
        ),
    )

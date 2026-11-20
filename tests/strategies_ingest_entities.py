"""Estratégias para a Propriedade 14 (lista de entidades e subconjunto com falha)."""

from __future__ import annotations

from hypothesis import strategies as st

from tests.strategies import business_keys

MAX_ENTITIES = 500


@st.composite
def entities_with_failures(draw, max_size: int = MAX_ENTITIES) -> tuple[list[str], set[str]]:
    """Lista de nomes únicos de entidades (até 500) e o subconjunto que falha."""
    names = draw(st.lists(business_keys, min_size=0, max_size=max_size, unique=True))
    failing = set(draw(st.sets(st.sampled_from(names)))) if names else set()
    return names, failing

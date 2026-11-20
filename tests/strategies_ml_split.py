"""Estratégias para a divisão treino/teste (Property 29)."""

from __future__ import annotations

import random

from hypothesis import strategies as st

from tests.strategies import business_keys, positive_ids

# Listas de ids únicos (inteiros ou chaves de negócio).
id_lists = st.one_of(
    st.lists(positive_ids, max_size=200, unique=True),
    st.lists(business_keys, max_size=200, unique=True),
)


@st.composite
def ids_with_permutation(draw):
    """Lista de ids únicos e uma permutação (ordem de entrada diferente)."""
    ids = draw(id_lists)
    seed = draw(st.integers(min_value=0, max_value=2**32 - 1))
    shuffled = list(ids)
    random.Random(seed).shuffle(shuffled)
    return ids, shuffled

"""Estratégias Hypothesis para o provisionamento (Property 1 a 3)."""

from __future__ import annotations

import string

from hypothesis import strategies as st

_ENV_ALPHABET = string.ascii_lowercase + string.digits

env_ids = st.text(alphabet=_ENV_ALPHABET, min_size=1, max_size=12)

# Listas de identificadores de ambiente distintos (inclui os ambientes padrão).
distinct_env_lists = st.lists(env_ids, min_size=0, max_size=6, unique=True)

"""Estratégias para o formato da data de atualização (Property 33)."""

from __future__ import annotations

from datetime import UTC, datetime

from hypothesis import strategies as st

# Instantes UTC gerais (inclui eras com horário de verão, antes de 2019).
utc_instants = st.datetimes(
    min_value=datetime(1990, 1, 1),
    max_value=datetime(2100, 1, 1),
    timezones=st.just(UTC),
)

# Instantes na era do horário de verão brasileiro (até fev/2019).
dst_era_instants = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2019, 3, 1),
    timezones=st.just(UTC),
)

any_utc_instant = st.one_of(utc_instants, dst_era_instants)

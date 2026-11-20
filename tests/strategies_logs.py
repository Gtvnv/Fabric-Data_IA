"""Estratégias para a Property 38 (logs estruturados completos)."""
from __future__ import annotations

from hypothesis import strategies as st

_ident_alphabet = st.characters(whitelist_categories=("Ll", "Lu", "Nd"), max_codepoint=0x7E)

run_ids = st.text(_ident_alphabet, min_size=1, max_size=36)
components = st.text(_ident_alphabet, min_size=1, max_size=30)
levels = st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
levels_mixed_case = levels.flatmap(lambda lv: st.sampled_from([lv, lv.lower(), lv.title()]))
# Mensagens em minúsculas/espaços: nunca colidem com os segredos gerados abaixo.
messages = st.text(st.sampled_from("abcdefghij klmnop"), min_size=1, max_size=60).filter(
    lambda s: s.strip() != ""
)
# Segredos têm prefixo maiúsculo distintivo para busca por substring.
secret_values = st.text(st.sampled_from("ABCDEFGH0123456789"), min_size=6, max_size=24).map(
    lambda s: "ZQX" + s
)
secret_keys = st.sampled_from(["password", "api_key", "token", "client_secret", "authorization"])
aware_datetimes = st.datetimes(timezones=st.timezones())
naive_datetimes = st.datetimes()
blank_values = st.sampled_from(["", " ", "   ", "\t", "\n"])
required_fields = st.sampled_from(["run_id", "component", "level", "message"])

"""Estratégias para o teste de falha parcial do provisionamento (Property 3)."""
from __future__ import annotations

from hypothesis import strategies as st
from infra.provision import desired_state

from tests.strategies_prov_idem import _extra_items, env_lists

_causes = st.text(alphabet="abcdefghij ", min_size=1, max_size=20).map(lambda s: f"causa-{s}")


@st.composite
def plan_existing_and_failures(draw):
    """(plano, existentes, fail_on): plano = itens ausentes; fail_on = subconjunto do plano."""
    desired = desired_state(draw(env_lists))
    existing_subset = [d for d in desired if draw(st.booleans())]
    existing = existing_subset + draw(_extra_items)
    missing = [d for d in desired if d not in set(existing_subset)]
    fail_on = {d.name: draw(_causes) for d in missing if draw(st.booleans())}
    return missing, existing, fail_on

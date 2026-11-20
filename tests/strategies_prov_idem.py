"""Estratégias para o teste de idempotência do provisionamento (Property 2)."""

from __future__ import annotations

from hypothesis import strategies as st
from infra.provision import DesiredItem, desired_state

_ENVS = ["dev", "test", "prod"]

env_lists = st.lists(st.sampled_from(_ENVS), min_size=1, max_size=3, unique=True)

_extra_items = st.lists(
    st.builds(
        DesiredItem,
        st.sampled_from(["fdai-sandbox", "outro-ws"]),
        st.sampled_from(["Lakehouse", "Warehouse"]),
        st.text(alphabet="abcdefgh_", min_size=1, max_size=8).map(lambda s: f"x_{s}"),
    ),
    max_size=4,
    unique_by=lambda i: (i.workspace, i.name),
)


@st.composite
def desired_and_existing(draw):
    """Estado desejado, subconjunto já existente e itens alheios ao estado desejado."""
    desired = desired_state(draw(env_lists))
    subset = [d for d in desired if draw(st.booleans())]
    extras = draw(_extra_items)
    existing = subset + extras
    draw(st.randoms(use_true_random=False)).shuffle(existing)
    return desired, existing

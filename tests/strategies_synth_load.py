"""Estratégias Hypothesis para carga com falhas injetadas nos destinos (Property 9)."""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import strategies as st

from platform_lib.synth import SQL_ENTITIES, GenParams
from tests.strategies_synth_fake import small_fake_params


@dataclass(frozen=True)
class LoadScenario:
    params: GenParams
    sql_fail_validate: bool
    sql_fail_entity: str | None
    obj_fail_validate: bool
    obj_fail_put: bool

    @property
    def sql_fails(self) -> bool:
        return self.sql_fail_validate or self.sql_fail_entity is not None

    @property
    def obj_fails(self) -> bool:
        return self.obj_fail_validate or self.obj_fail_put


@st.composite
def load_scenarios(draw) -> LoadScenario:
    return LoadScenario(
        params=draw(small_fake_params()),
        sql_fail_validate=draw(st.booleans()),
        sql_fail_entity=draw(st.one_of(st.none(), st.sampled_from(SQL_ENTITIES))),
        obj_fail_validate=draw(st.booleans()),
        obj_fail_put=draw(st.booleans()),
    )

"""Property 9: Carga total e reexecutável.
**Validates: Requirements 2.9, 2.10**
"""
from __future__ import annotations

import copy

from hypothesis import given, settings

from platform_lib import synth
from tests.strategies_synth_load import load_scenarios


def _sinks(s):
    sql = synth.InMemorySqlSink(fail_validate=s.sql_fail_validate, fail_entity=s.sql_fail_entity)
    obj = synth.InMemoryObjectSink(fail_validate=s.obj_fail_validate, fail_put=s.obj_fail_put)
    return sql, obj


# Feature: fabric-data-ai-platform, Property 9: Carga total e reexecutável
@settings(max_examples=100, deadline=None)
@given(load_scenarios())
def test_carga_total_e_reexecutavel(s):
    ds = synth.generate(s.params)
    sql, obj = _sinks(s)

    report = synth.load(ds, sql, obj)

    if not s.sql_fails and not s.obj_fails:
        assert report.success
        assert report.failed_destination is None
    else:
        assert not report.success
        failing = set()
        if s.sql_fails:
            failing.add(synth.DEST_SQL)
        if s.obj_fails:
            failing.add(synth.DEST_OBJECT)
        assert report.failed_destination in failing

    snap_sql = copy.deepcopy(sql.tables)
    snap_obj = dict(obj.files)

    report2 = synth.load(ds, sql, obj)

    assert report2.success == report.success
    assert report2.failed_destination == report.failed_destination
    assert report2.counts == report.counts
    assert sql.tables == snap_sql
    assert obj.files == snap_obj
    for entity, table in sql.tables.items():
        assert len(table) == len(snap_sql[entity])
    if report.success:
        for entity in synth.SQL_ENTITIES:
            assert len(sql.tables[entity]) == report.counts[entity]

# Feature: fabric-data-ai-platform, Property 38: Logs estruturados completos
"""Property 38: registros de log completos, JSON válido, UTC e sem segredos.

**Validates: Requirements 10.1**
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from platform_lib.logging import REDACTED, StructuredLogger, build_record, to_json
from tests.strategies_logs import (
    aware_datetimes,
    blank_values,
    components,
    levels,
    levels_mixed_case,
    messages,
    naive_datetimes,
    required_fields,
    run_ids,
    secret_keys,
    secret_values,
)

REQUIRED = ("run_id", "component", "level", "ts_utc", "message")


def _assert_complete(record: dict) -> None:
    for name in REQUIRED:
        assert isinstance(record[name], str) and record[name].strip(), name
    parsed = json.loads(to_json(record))
    assert parsed == json.loads(json.dumps(record))
    ts = datetime.fromisoformat(record["ts_utc"])
    assert ts.utcoffset() == timedelta(0)


@settings(max_examples=100)
@given(run_id=run_ids, component=components, level=levels_mixed_case, message=messages)
def test_build_record_complete_json_utc(run_id, component, level, message):
    record = build_record(run_id, component, level, message)
    _assert_complete(record)
    assert record["run_id"] == run_id
    assert record["component"] == component
    assert record["level"] == level.upper()


@settings(max_examples=100)
@given(run_id=run_ids, component=components, level=levels, message=messages,
       ts=st.one_of(aware_datetimes, naive_datetimes))
def test_ts_is_utc_for_any_input_timestamp(run_id, component, level, message, ts):
    record = build_record(run_id, component, level, message, ts_utc=ts)
    _assert_complete(record)
    expected = (ts if ts.tzinfo else ts.replace(tzinfo=UTC)).astimezone(UTC)
    assert datetime.fromisoformat(record["ts_utc"]) == expected


@settings(max_examples=100)
@given(run_id=run_ids, component=components, level=levels, message=messages,
       key=secret_keys, secret=secret_values, inline=secret_values)
def test_secrets_redacted(run_id, component, level, message, key, secret, inline):
    sink: list[dict] = []
    logger = StructuredLogger(run_id, component, sink.append)
    rec = logger.log(level, f"{message} password={inline}", **{key: secret})
    assert sink == [rec]
    _assert_complete(rec)
    out = to_json(rec)
    assert secret not in out
    assert inline not in out
    assert rec["extra"][key] == REDACTED


@settings(max_examples=100)
@given(run_id=run_ids, component=components, level=levels, message=messages,
       field=required_fields, blank=blank_values)
def test_empty_required_fields_raise(run_id, component, level, message, field, blank):
    args = {"run_id": run_id, "component": component, "level": level, "message": message}
    args[field] = blank
    with pytest.raises(ValueError):
        build_record(**args)
    if field in ("run_id", "component"):
        with pytest.raises(ValueError):
            StructuredLogger(args["run_id"], args["component"], lambda r: None)
    else:
        logger = StructuredLogger(run_id, component, lambda r: None)
        with pytest.raises(ValueError):
            logger.log(args["level"], args["message"])

"""Log estruturado em JSON gravado em ``ops.logs`` (Requirement 10.1).

Cada registro contém ``run_id``, ``component``, ``level``, ``ts_utc`` e
``message`` não vazios. Segredos são mascarados antes de qualquer saída.
A gravação ocorre por um sink injetável (``LogSink``); em produção o sink
grava na tabela Delta ``ops.logs`` (retenção >= 30 dias).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

# Retenção mínima da tabela ops.logs, em dias.
OPS_LOGS_TABLE = "ops.logs"
RETENTION_DAYS = 30

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
REDACTED = "***REDACTED***"

_SECRET_KEY_RE = re.compile(
    r"(password|passwd|pwd|secret|token|api[_-]?key|apikey|authorization|"
    r"credential|connection[_-]?string|private[_-]?key|sas|client[_-]?secret)",
    re.IGNORECASE,
)
# chave=valor / chave: valor embutidos em texto livre
_SECRET_INLINE_RE = re.compile(
    r"(?i)\b([\w.-]*(?:password|passwd|pwd|secret|token|api[_-]?key|"
    r"authorization|client[_-]?secret|accountkey|sharedaccesssignature)[\w.-]*)"
    r"(\s*[=:]\s*)(?:bearer\s+)?(\"[^\"]*\"|'[^']*'|[^\s,;&]+)"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}")
_SAS_RE = re.compile(r"(?i)([?&](?:sig|sv|se|sp|st|spr|srt|ss)=)[^&\s]+")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*")

LogSink = Callable[[dict[str, Any]], None]


def redact_text(text: str) -> str:
    """Mascara segredos em texto livre."""
    text = _SECRET_INLINE_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", text)
    text = _BEARER_RE.sub(f"Bearer {REDACTED}", text)
    text = _SAS_RE.sub(lambda m: f"{m.group(1)}{REDACTED}", text)
    return _JWT_RE.sub(REDACTED, text)


def redact(value: Any, key: str | None = None) -> Any:
    """Mascara segredos em valores arbitrários (por nome de chave e por padrão)."""
    if key is not None and _SECRET_KEY_RE.search(key):
        return REDACTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [redact(v) for v in value]
    if isinstance(value, int | float | bool) or value is None:
        return value
    return redact_text(str(value))


def _require(name: str, value: str | None) -> str:
    if value is None or not str(value).strip():
        raise ValueError(f"{name} não pode ser vazio")
    return str(value).strip()


def build_record(
    run_id: str,
    component: str,
    level: str,
    message: str,
    *,
    ts_utc: datetime | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Monta o registro estruturado, já com segredos mascarados."""
    level_norm = _require("level", level).upper()
    if level_norm not in LEVELS:
        raise ValueError(f"level inválido: {level!r}")
    ts = ts_utc or datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    record: dict[str, Any] = {
        "run_id": _require("run_id", run_id),
        "component": _require("component", component),
        "level": level_norm,
        "ts_utc": ts.astimezone(UTC).isoformat(),
        "message": redact_text(_require("message", message)),
    }
    if not record["message"].strip():
        raise ValueError("message não pode ser vazio")
    if fields:
        record["extra"] = redact(fields)
    return record


def to_json(record: Mapping[str, Any]) -> str:
    """Serializa o registro como uma linha JSON."""
    return json.dumps(record, ensure_ascii=False, default=str, sort_keys=True)


def to_ops_row(record: Mapping[str, Any]) -> dict[str, str]:
    """Mapeia o registro para as colunas de ``ops.logs``."""
    return {
        "run_id": record["run_id"],
        "componente": record["component"],
        "nivel": record["level"],
        "ts_utc": record["ts_utc"],
        "mensagem": record["message"],
    }


class StructuredLogger:
    """Logger JSON estruturado com sink injetável para ``ops.logs``."""

    def __init__(self, run_id: str, component: str, sink: LogSink) -> None:
        self.run_id = _require("run_id", run_id)
        self.component = _require("component", component)
        if sink is None:
            raise ValueError("sink é obrigatório")
        self._sink = sink

    def log(self, level: str, message: str, **fields: Any) -> dict[str, Any]:
        record = build_record(self.run_id, self.component, level, message, **fields)
        self._sink(record)
        return record

    def debug(self, message: str, **fields: Any) -> dict[str, Any]:
        return self.log("DEBUG", message, **fields)

    def info(self, message: str, **fields: Any) -> dict[str, Any]:
        return self.log("INFO", message, **fields)

    def warning(self, message: str, **fields: Any) -> dict[str, Any]:
        return self.log("WARNING", message, **fields)

    def error(self, message: str, **fields: Any) -> dict[str, Any]:
        return self.log("ERROR", message, **fields)

    def critical(self, message: str, **fields: Any) -> dict[str, Any]:
        return self.log("CRITICAL", message, **fields)


def get_logger(run_id: str, component: str, sink: LogSink) -> StructuredLogger:
    return StructuredLogger(run_id, component, sink)


def make_ops_logs_sink(
    writer: Callable[[str, list[dict[str, str]]], None],
) -> LogSink:
    """Sink que grava em ``ops.logs`` via ``writer(table, rows)`` (ex.: Delta append)."""

    def _sink(record: dict[str, Any]) -> None:
        writer(OPS_LOGS_TABLE, [to_ops_row(record)])

    return _sink

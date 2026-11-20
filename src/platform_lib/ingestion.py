"""Lógica pura da Pipeline_Ingestao (marca d'água, Bronze idempotente, retry, entidades).

Espelha o notebook/pipeline; testável sem Spark. Linhas são ``dict``.
Requisitos: 3.1, 3.3-3.8, 3.12, 4.1.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

Row = dict[str, Any]
Key = str | Sequence[str]

MAX_ENTITIES = 500
META_TS = "_ingestion_ts_utc"
META_RUN = "_run_id"
META_SRC = "_source_system"

STATUS_SUCCESS = "sucesso"
STATUS_FAILURE = "falha"


def select_incremental(rows: Iterable[Row], watermark_col: str, last_wm: Any) -> list[Row]:
    """Sem marca persistida -> todos; senão somente ``col > last_wm`` (Req. 3.4)."""
    if last_wm is None:
        return [dict(r) for r in rows]
    return [
        dict(r) for r in rows if r.get(watermark_col) is not None and r[watermark_col] > last_wm
    ]


def next_watermark(written_rows: Iterable[Row], watermark_col: str, previous: Any) -> Any:
    """Máximo da coluna entre os gravados; se nada gravado, mantém ``previous`` (Req. 3.5)."""
    values = [r[watermark_col] for r in written_rows if r.get(watermark_col) is not None]
    if not values:
        return previous
    new = max(values)
    return new if previous is None or new > previous else previous


def add_ingestion_metadata(
    row: Mapping[str, Any], run_id: str, source: str, now_utc: datetime
) -> Row:
    """Acrescenta metadados de ingestão sem alterar os valores de origem (Req. 3.3, 4.1)."""
    if not run_id or not source:
        raise ValueError("run_id e source são obrigatórios e não nulos")
    if now_utc.tzinfo is None:
        raise ValueError("now_utc deve ter fuso UTC")
    out = dict(row)
    out[META_TS] = now_utc.astimezone(UTC)
    out[META_RUN] = run_id
    out[META_SRC] = source
    return out


def _key_of(row: Mapping[str, Any], key: Key) -> tuple:
    cols = (key,) if isinstance(key, str) else tuple(key)
    return tuple(row.get(c) for c in cols)


def merge_bronze(existing: Iterable[Row], incoming: Iterable[Row], key: Key) -> list[Row]:
    """MERGE por chave de carga: atualiza existentes, insere novos, sem duplicados.

    Não altera as entradas (resultado só é visível ao chamador no final, Req. 3.6).
    Em duplicidade dentro do lote, vale o último registro. Idempotente (Req. 3.7).
    """
    merged: dict[tuple, Row] = {}
    for r in existing:
        merged[_key_of(r, key)] = dict(r)
    for r in incoming:
        merged[_key_of(r, key)] = dict(r)
    return list(merged.values())


@dataclass(frozen=True)
class Result:
    ok: bool
    value: Any = None
    attempts: int = 0
    error: BaseException | None = None


def run_with_retry(
    op: Callable[[], Any],
    retries: int = 3,
    wait_s: float = 60,
    sleep: Callable[[float], None] = time.sleep,
) -> Result:
    """Executa ``op`` até ``retries + 1`` vezes, com ``wait_s`` entre tentativas (Req. 3.8)."""
    if retries < 0:
        raise ValueError("retries deve ser >= 0")
    last: BaseException | None = None
    for attempt in range(1, retries + 2):
        try:
            return Result(ok=True, value=op(), attempts=attempt)
        except Exception as exc:  # noqa: BLE001 - qualquer falha da operação conta
            last = exc
            if attempt <= retries:
                sleep(wait_s)
    return Result(ok=False, attempts=retries + 1, error=last)


@dataclass(frozen=True)
class RunStatus:
    status: str
    succeeded: list[str] = field(default_factory=list)
    failed: dict[str, BaseException] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == STATUS_SUCCESS


def _entity_name(ent: Any) -> str:
    if isinstance(ent, Mapping):
        return str(ent.get("entidade", ent))
    return ent if isinstance(ent, str) else str(getattr(ent, "name", ent))


def _entity_name(ent: Any) -> str:
    if isinstance(ent, Mapping):
        return str(ent.get("entidade", ent))
    return ent if isinstance(ent, str) else str(getattr(ent, "name", ent))


def run_entities(entities: Sequence[Any], runner: Callable[[Any], Any]) -> RunStatus:
    """Processa todas as entidades; falha de uma não interrompe as demais (Req. 3.12).

    Status final é ``falha`` se e somente se alguma entidade falhou.
    """
    if len(entities) > MAX_ENTITIES:
        raise ValueError(f"máximo de {MAX_ENTITIES} entidades por execução")
    succeeded: list[str] = []
    failed: dict[str, BaseException] = {}
    for ent in entities:
        name = _entity_name(ent)
        try:
            runner(ent)
            succeeded.append(name)
        except Exception as exc:  # noqa: BLE001
            failed[name] = exc
    return RunStatus(STATUS_FAILURE if failed else STATUS_SUCCESS, succeeded, failed)


@dataclass(frozen=True)
class IngestOutcome:
    bronze: list[Row]
    watermark: Any
    written: int
    ok: bool
    error: BaseException | None = None


def ingest_entity(
    bronze: Sequence[Row],
    source_rows: Iterable[Row],
    *,
    key: Key,
    watermark_col: str,
    previous_watermark: Any,
    run_id: str,
    source: str,
    now_utc: datetime,
) -> IngestOutcome:
    """Gravação atômica: Bronze e marca só mudam no retorno com sucesso.

    Em falha, devolve o Bronze e a marca anteriores intactos (Req. 3.6).
    """
    try:
        selected = select_incremental(source_rows, watermark_col, previous_watermark)
        enriched = [add_ingestion_metadata(r, run_id, source, now_utc) for r in selected]
        new_bronze = merge_bronze(bronze, enriched, key)
        wm = next_watermark(selected, watermark_col, previous_watermark)
    except Exception as exc:  # noqa: BLE001
        return IngestOutcome(list(bronze), previous_watermark, 0, False, exc)
    return IngestOutcome(new_bronze, wm, len(selected), True)

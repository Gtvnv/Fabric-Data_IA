"""Lógica pura da orquestração do pipeline mestre (Req. 9.1-9.5, 9.10, 10.2, 10.3).

Sem dependência de Fabric: executores, relógio, auditoria, notificador, ``sleep`` e
logger são injetáveis.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from platform_lib.ingestion import run_with_retry

STEPS: list[str] = ["ingestao", "silver", "qualidade", "gold", "ia", "semantico"]

STATUS_SUCCESS = "sucesso"
STATUS_FAILED = "falha"
STATUS_NOT_RUN = "não executada"

ALERT_RETRIES = 3
ALERT_WAIT_S = 60

Logger = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class StepRecord:
    """Registro de auditoria de uma etapa (1 por etapa, Req. 9.5)."""

    etapa: str
    status: str
    inicio: datetime | None = None
    termino: datetime | None = None
    registros: int = 0
    erro: str | None = None
    verificacao: str | None = None  # verificação de qualidade que falhou (Req. 9.3)
    reutilizada: bool = False  # sucesso herdado da execução original (Req. 9.10)
    execucao_original: str | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _status_of(item: Any) -> str:
    return item.status if isinstance(item, StepRecord) else str(item)


def resume_point(prior: Sequence[StepRecord]) -> str | None:
    """Primeira etapa (na ordem de ``STEPS``) com status != sucesso (Req. 9.10).

    Etapas ausentes em ``prior`` contam como sem sucesso. Retorna ``None`` se todas tiveram sucesso.
    """
    by_step = {r.etapa: r.status for r in prior}
    for step in STEPS:
        if by_step.get(step) != STATUS_SUCCESS:
            return step
    return None


def can_start(active_runs: Iterable[Any]) -> bool:
    """Falso se e somente se existe outra execução em andamento (Req. 9.4)."""
    return not any(True for _ in active_runs)


def _count(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, Mapping):
        return int(value.get("registros", 0) or 0)
    return int(getattr(value, "registros", 0) or 0)


def run_pipeline(
    step_runners: Mapping[str, Callable[[], Any]],
    start_from: str | None = None,
    prior_statuses: Sequence[StepRecord] | Mapping[str, str] | None = None,
    *,
    run_id: str | None = None,
    original_run_id: str | None = None,
    clock: Callable[[], datetime] = _now,
    audit: Callable[[StepRecord], None] | None = None,
    notifier: Callable[[str], Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    logger: Logger | None = None,
) -> list[StepRecord]:
    """Executa as etapas em ordem, uma por vez; para na primeira falha.

    Cada runner retorna o número de registros (ou mapping/objeto com ``registros``) e levanta
    exceção para falhar. Etapas posteriores à falha ficam "não executada" (Req. 9.2). Na
    reexecução, etapas anteriores a ``start_from`` (por padrão o ``resume_point`` de
    ``prior_statuses``) não são repetidas e o registro referencia ``original_run_id`` (Req. 9.10).
    Retorna um registro por etapa de ``STEPS``.
    """
    if start_from is None and prior_statuses is not None:
        if isinstance(prior_statuses, Mapping):
            start_from = next((s for s in STEPS if prior_statuses.get(s) != STATUS_SUCCESS), None)
        else:
            start_from = resume_point(prior_statuses)
        if start_from is None:
            start_from = ""  # tudo já teve sucesso: nada a executar
    if start_from not in (None, "") and start_from not in STEPS:
        raise ValueError(f"etapa desconhecida: {start_from}")

    records: list[StepRecord] = []

    def emit(rec: StepRecord) -> None:
        if original_run_id is not None:
            rec = replace(rec, execucao_original=original_run_id)
        records.append(rec)
        if audit is not None:
            audit(rec)
        if logger is not None:
            _safe_log(logger, {"evento": "etapa", "execucao": run_id, "etapa": rec.etapa,
                               "status": rec.status, "registros": rec.registros})

    start_idx = len(STEPS) if start_from == "" else (STEPS.index(start_from) if start_from else 0)
    failed = False
    for idx, step in enumerate(STEPS):
        if failed:
            emit(StepRecord(etapa=step, status=STATUS_NOT_RUN))
            continue
        if idx < start_idx:
            emit(StepRecord(etapa=step, status=STATUS_SUCCESS, reutilizada=True))
            continue
        began = clock()
        try:
            n = _count(step_runners[step]())
        except Exception as exc:  # noqa: BLE001 - qualquer falha interrompe o pipeline
            emit(StepRecord(
                etapa=step, status=STATUS_FAILED, inicio=began, termino=clock(),
                erro=str(exc) or type(exc).__name__,
                verificacao=getattr(exc, "verificacao", None) if step == "qualidade" else None,
            ))
            failed = True
        else:
            emit(StepRecord(etapa=step, status=STATUS_SUCCESS, inicio=began, termino=clock(),
                            registros=n))

    failure = next((r for r in records if r.status == STATUS_FAILED), None)
    if failure is not None and notifier is not None:
        notify_failure(notifier, failure, run_id=run_id, sleep=sleep, logger=logger)
    return records


def failure_message(rec: StepRecord, run_id: str | None = None) -> str:
    msg = f"Pipeline mestre falhou na etapa '{rec.etapa}'"
    if rec.verificacao:
        msg += f" (verificação de qualidade: {rec.verificacao})"
    if run_id:
        msg += f" [execução {run_id}]"
    return msg


def notify_failure(
    notifier: Callable[[str], Any],
    rec: StepRecord,
    *,
    run_id: str | None = None,
    retries: int = ALERT_RETRIES,
    wait_s: float = ALERT_WAIT_S,
    sleep: Callable[[float], None] = time.sleep,
    logger: Logger | None = None,
) -> bool:
    """Envia o alerta com 3 retentativas a cada 60 s (Req. 10.3).

    Se todas falharem, registra o erro no log e retorna ``False`` sem levantar exceção, para
    não interromper o registro da falha original.
    """
    message = failure_message(rec, run_id)
    result = run_with_retry(lambda: notifier(message), retries=retries, wait_s=wait_s, sleep=sleep)
    if not result.ok and logger is not None:
        _safe_log(logger, {"evento": "falha_alerta", "nivel": "ERROR", "execucao": run_id,
                           "etapa": rec.etapa, "tentativas": result.attempts,
                           "erro": str(result.error)})
    return result.ok


def _safe_log(logger: Logger, entry: dict[str, Any]) -> None:
    try:
        logger(entry)
    except Exception:  # noqa: BLE001 - log nunca interrompe a orquestração
        pass

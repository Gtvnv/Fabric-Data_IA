"""Decisão da varredura de segredos (gitleaks) no pipeline de PR.

Aprova somente se a ferramenta executou com sucesso e reportou 0 achados. Achados, erro
ou timeout reprovam a verificação (falha da ferramenta = falha da verificação). O relatório
lista arquivo e linha de cada achado e nunca contém o valor do segredo.
Requisitos: 12.5, 12.6, 12.7.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_TIMEOUT = "timeout"

DEFAULT_TIMEOUT_SECONDS = 300


@dataclass(frozen=True)
class Finding:
    """Achado da varredura. Guarda apenas localização, nunca o valor do segredo."""

    file: str
    line: int


@dataclass(frozen=True)
class ScanResult:
    """Resultado bruto da execução da ferramenta."""

    status: str = STATUS_OK
    findings: Sequence[Finding] = field(default_factory=tuple)
    error: str | None = None


@dataclass(frozen=True)
class ScanDecision:
    passed: bool
    report: str
    findings: tuple[Finding, ...] = ()


def _to_finding(item: Finding | Mapping[str, Any]) -> Finding:
    """Normaliza um achado descartando qualquer campo além de arquivo e linha."""
    if isinstance(item, Finding):
        return Finding(file=item.file, line=item.line)
    file = item.get("file", item.get("File", ""))
    line = item.get("line", item.get("StartLine", 0))
    try:
        line_no = int(line)
    except (TypeError, ValueError):
        line_no = 0
    return Finding(file=str(file), line=line_no)


def decide_scan(result: ScanResult) -> ScanDecision:
    """Aprova somente se a ferramenta executou com sucesso e reportou 0 achados."""
    if result.status == STATUS_TIMEOUT:
        return ScanDecision(False, "Varredura de segredos falhou: timeout da ferramenta.")
    if result.status != STATUS_OK:
        return ScanDecision(False, "Varredura de segredos falhou: erro na execução da ferramenta.")

    findings = tuple(_to_finding(f) for f in result.findings)
    if not findings:
        return ScanDecision(True, "Varredura de segredos concluída: 0 achados.")

    lines = [f"Varredura de segredos reprovada: {len(findings)} achado(s)."]
    lines.extend(f"{f.file}:{f.line}" for f in findings)
    return ScanDecision(False, "\n".join(lines), findings)


def parse_gitleaks_report(raw: str) -> list[Finding]:
    """Extrai arquivo e linha do relatório JSON do gitleaks, ignorando o conteúdo do segredo."""
    raw = raw.strip()
    if not raw:
        return []
    data = json.loads(raw)
    if not isinstance(data, Iterable) or isinstance(data, (str, Mapping)):
        raise ValueError("relatório gitleaks inválido")
    return [_to_finding(item) for item in data if isinstance(item, Mapping)]


def run_gitleaks(
    source: str = ".",
    report_path: str = "gitleaks-report.json",
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> ScanResult:
    """Executa o gitleaks com --redact. Código 0 = limpo, 1 = achados, outro = erro."""
    cmd = [
        "gitleaks", "detect", "--source", source, "--redact", "--no-banner",
        "--report-format", "json", "--report-path", report_path, "--exit-code", "1",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return ScanResult(status=STATUS_TIMEOUT)
    except OSError as exc:
        return ScanResult(status=STATUS_ERROR, error=type(exc).__name__)

    if proc.returncode == 0:
        return ScanResult(status=STATUS_OK)
    if proc.returncode != 1:
        return ScanResult(status=STATUS_ERROR, error=f"exit code {proc.returncode}")
    try:
        with open(report_path, encoding="utf-8") as fh:
            findings = parse_gitleaks_report(fh.read())
    except (OSError, ValueError):
        return ScanResult(status=STATUS_ERROR, error="relatório ilegível")
    if not findings:
        # Código 1 sem achados legíveis: não confiar como aprovação.
        return ScanResult(status=STATUS_ERROR, error="exit code 1 sem achados")
    return ScanResult(status=STATUS_OK, findings=tuple(findings))


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    source = args[0] if args else "."
    decision = decide_scan(run_gitleaks(source))
    print(decision.report)
    return 0 if decision.passed else 1


if __name__ == "__main__":
    sys.exit(main())

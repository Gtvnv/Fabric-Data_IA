# Feature: fabric-data-ai-platform, Property 43: Decisão da varredura de segredos
"""**Validates: Requirements 12.5, 12.6, 12.7**"""
from __future__ import annotations

from hypothesis import given, settings

from src.platform_lib.secrets_scan import STATUS_OK, decide_scan
from tests.strategies_scan import finding_lists, scan_results
from hypothesis import strategies as st


@settings(max_examples=100)
@given(result=scan_results)
def test_passa_somente_se_ok_e_zero_achados(result):
    decision = decide_scan(result)
    assert decision.passed == (result.status == STATUS_OK and len(result.findings) == 0)


@settings(max_examples=100)
@given(findings=finding_lists.filter(bool))
def test_relatorio_lista_arquivo_linha_sem_segredo(findings):
    from src.platform_lib.secrets_scan import ScanResult, _to_finding

    decision = decide_scan(ScanResult(status=STATUS_OK, findings=tuple(findings)))
    assert not decision.passed
    for item in findings:
        f = _to_finding(item)
        assert f"{f.file}:{f.line}" in decision.report
        if isinstance(item, dict):
            assert item["Secret"] not in decision.report

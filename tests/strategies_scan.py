"""Estratégias para a Property 43 (decisão da varredura de segredos)."""
from __future__ import annotations

from hypothesis import strategies as st
from src.platform_lib.secrets_scan import (
    STATUS_ERROR,
    STATUS_OK,
    STATUS_TIMEOUT,
    Finding,
    ScanResult,
)

_path_part = st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=8)
file_paths = st.builds(
    lambda parts, ext: "/".join(parts) + ext,
    st.lists(_path_part, min_size=1, max_size=3),
    st.sampled_from([".py", ".json", ".yml", ".env"]),
)
line_numbers = st.integers(min_value=1, max_value=100000)
# Valor de segredo com marcador único, para checar que nunca aparece no relatório.
secret_values = st.text(alphabet="ABCDEFGHJKLMNPQRSTUVWXYZ23456789", min_size=20, max_size=40).map(
    lambda s: "SECRET" + s
)
findings = st.builds(Finding, file=file_paths, line=line_numbers)
finding_dicts = st.builds(
    lambda f, ln, s: {"File": f, "StartLine": ln, "Secret": s, "Match": s},
    file_paths, line_numbers, secret_values,
)
finding_lists = st.lists(st.one_of(findings, finding_dicts), min_size=0, max_size=6)
statuses = st.sampled_from([STATUS_OK, STATUS_ERROR, STATUS_TIMEOUT])
scan_results = st.builds(
    ScanResult, status=statuses, findings=finding_lists.map(tuple),
    error=st.one_of(st.none(), st.text(max_size=10)),
)

"""Configuração do pytest e dos perfis Hypothesis.

Perfis:
- ``default``: 100 exemplos (desenvolvimento local).
- ``ci``: 200 exemplos, ``derandomize=True`` (reprodutível no pipeline; sem banco,
  pois o Hypothesis não permite os dois juntos).

Seleção: variável de ambiente ``HYPOTHESIS_PROFILE`` (padrão ``default``).
O banco de exemplos de falhas fica em ``tests/hypothesis_examples`` (versionável).
"""

import os
from pathlib import Path

from hypothesis import HealthCheck, settings
from hypothesis.database import DirectoryBasedExampleDatabase

_DB = DirectoryBasedExampleDatabase(str(Path(__file__).parent / "hypothesis_examples"))

settings.register_profile(
    "default",
    max_examples=100,
    database=_DB,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile(
    "ci",
    max_examples=200,
    derandomize=True,
    database=None,  # Hypothesis proíbe banco de exemplos com derandomize=True
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))

# Fabric notebook: nb_ultima_atualizacao
# Executado ao final de cada execução do pipeline; grava config.ultima_atualizacao no Gold.
# Notebook fino: a lógica está em platform_lib.timefmt (Req. 8.5).
from datetime import UTC, datetime

from platform_lib.timefmt import ULTIMA_ATUALIZACAO_TABLE, build_ultima_atualizacao_row

row = build_ultima_atualizacao_row(datetime.now(UTC))
df = spark.createDataFrame(  # noqa: F821 - `spark` é fornecido pelo Fabric
    [(row["ts_utc"].replace(tzinfo=None), row["ts_sao_paulo_texto"])],
    "ts_utc timestamp, ts_sao_paulo_texto string",
)
df.write.format("delta").mode("overwrite").saveAsTable(ULTIMA_ATUALIZACAO_TABLE)

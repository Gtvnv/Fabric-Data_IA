# Fabric notebook: nb_bronze_merge
# Notebook fino da Pipeline_Ingestao (Req. 3.1, 3.3, 3.5, 3.6, 3.7). A lógica de metadados,
# marca d'água e chave está em platform_lib.ingestion; aqui só há I/O Spark.
# Modos: "merge" (staging -> Bronze), "atualizar_marca" (persiste a marca após o MERGE),
#        "carregar_config" (YAML -> config.ingestao_entidades).
import json
from datetime import UTC, datetime

from platform_lib.ingestion import (
    META_RUN,
    META_SRC,
    META_TS,
    add_ingestion_metadata,
    next_watermark,
)

# Parâmetros (célula "parameters"; sobrescritos pela atividade de notebook do pipeline)
modo = "merge"
entidade = ""
destino = ""
chave = ""  # colunas separadas por vírgula
coluna_watermark = ""
origem_tipo = ""
run_id = ""
marca_anterior = ""  # "" = sem marca
novo_valor = ""
caminho_config = "Files/config/ingestao_entidades.yaml"

now = datetime.now(UTC)
saida: dict = {"entidade": entidade, "modo": modo}

if modo == "merge":
    # Valida run_id/source não nulos pela mesma função usada nos testes (Req. 3.3).
    add_ingestion_metadata({}, run_id, origem_tipo, now)
    try:
        staged = spark.read.parquet(f"Files/staging/{entidade}/{run_id}")  # noqa: F821
    except Exception:  # noqa: BLE001 - nada copiado: sem linhas novas, marca preservada
        staged = None
    if staged is None or staged.rdd.isEmpty():  # noqa: F821
        saida.update(linhas=0, novo_valor=marca_anterior)
    else:
        from pyspark.sql import functions as F  # noqa: N812

        enriched = (
            staged.withColumn(META_TS, F.lit(now.replace(tzinfo=None)).cast("timestamp"))
            .withColumn(META_RUN, F.lit(run_id))
            .withColumn(META_SRC, F.lit(origem_tipo))
        )
        cond = " AND ".join(f"t.`{c.strip()}` <=> s.`{c.strip()}`" for c in chave.split(","))
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {destino.split('.')[0]}")  # noqa: F821
        enriched.limit(0).write.format("delta").mode("append").option(
            "mergeSchema", "true"
        ).saveAsTable(destino)
        from delta.tables import DeltaTable

        (
            DeltaTable.forName(spark, destino).alias("t")  # noqa: F821
            .merge(enriched.alias("s"), cond)
            .whenMatchedUpdateAll()
            .whenNotMatchedInsertAll()
            .execute()
        )
        maximo = staged.agg(F.max(coluna_watermark)).first()[0]
        previo = marca_anterior or None
        novo = next_watermark([{coluna_watermark: maximo}], coluna_watermark, previo)
        saida.update(linhas=staged.count(), novo_valor="" if novo is None else str(novo))
elif modo == "atualizar_marca":
    # Só é chamado após o MERGE confirmado (Req. 3.5, 3.6).
    spark.sql(  # noqa: F821
        "MERGE INTO config.ingestao_watermark t USING "
        "(SELECT :e AS entidade, NULLIF(:v, '') AS ultimo_valor, current_timestamp() AS ts) s "
        "ON t.entidade = s.entidade "
        "WHEN MATCHED THEN UPDATE SET ultimo_valor = s.ultimo_valor, atualizado_em_utc = s.ts "
        "WHEN NOT MATCHED THEN INSERT (entidade, ultimo_valor, atualizado_em_utc) "
        "VALUES (s.entidade, s.ultimo_valor, s.ts)",
        args={"e": entidade, "v": novo_valor},
    )
elif modo == "carregar_config":
    import yaml

    with open(f"/lakehouse/default/{caminho_config}", encoding="utf-8") as fh:
        itens = yaml.safe_load(fh)["entidades"]
    spark.createDataFrame(itens).createOrReplaceTempView("_ing_cfg")  # noqa: F821
    spark.sql(  # noqa: F821
        "INSERT OVERWRITE config.ingestao_entidades SELECT entidade, ativo, origem_tipo, "
        "consulta, chave, coluna_watermark, destino FROM _ing_cfg"
    )
else:
    raise ValueError(f"modo inválido: {modo}")

# Devolve o resultado ao pipeline (activity('...').output.result.exitValue)
notebookutils.notebook.exit(json.dumps(saida))  # noqa: F821

# Fabric notebook: nb_silver
# Camada_Silver: lê a Bronze, converte/normaliza/valida/deduplica e grava
# silver.clientes, produtos, lojas, vendas, estoque e silver._quarentena (Req. 4.2, 4.3, 4.4, 4.10).
# Equivalente PySpark das regras de platform_lib.silver (mesmos tipos, motivos e especificações).
# Staging por execução e promoção só depois que todas as tabelas foram preparadas:
# uma falha antes da promoção deixa a Silver anterior intacta.
import re
import uuid

from pyspark.sql import Window
from pyspark.sql import functions as F  # noqa: N812
from pyspark.sql.types import StringType

from platform_lib.silver import (
    REASON_BAD_DATE,
    REASON_BAD_TYPE,
    REASON_NEGATIVE_SALE,
    REASON_NULL_KEY,
    T_DATE,
    T_DECIMAL,
    T_INT,
    T_STR,
    T_TIMESTAMP,
    EntitySpec,
)

# Parâmetros (célula de parâmetros do Fabric pode sobrescrever)
run_id = uuid.uuid4().hex
bronze_schema = "bronze"
silver_schema = "silver"
QUARANTINE_TABLE = "_quarentena"
DECIMAL_TYPE = "decimal(18,2)"

# `spark` é fornecido pelo Fabric
spark.conf.set("spark.sql.ansi.enabled", "false")  # noqa: F821 - valor inválido vira null
spark.conf.set("spark.sql.legacy.timeParserPolicy", "CORRECTED")  # noqa: F821 - data inexistente vira null

SPECS = (
    EntitySpec(
        name="clientes",
        key=("cliente_id",),
        columns={
            "cliente_id": T_INT,
            "nome": T_STR,
            "email": T_STR,
            "telefone": T_STR,
            "documento": T_STR,
            "cidade": T_STR,
            "uf": T_STR,
            "data_cadastro": T_DATE,
            "atualizado_em": T_TIMESTAMP,
        },
    ),
    EntitySpec(
        name="produtos",
        key=("produto_id",),
        columns={
            "produto_id": T_INT,
            "nome": T_STR,
            "categoria": T_STR,
            "subcategoria": T_STR,
            "preco_lista": T_DECIMAL,
            "custo": T_DECIMAL,
            "atualizado_em": T_TIMESTAMP,
        },
        non_negative=("preco_lista", "custo"),
    ),
    EntitySpec(
        name="lojas",
        key=("loja_id",),
        columns={
            "loja_id": T_INT,
            "nome": T_STR,
            "regiao": T_STR,
            "cidade": T_STR,
            "uf": T_STR,
            "atualizado_em": T_TIMESTAMP,
        },
    ),
    EntitySpec(
        name="vendas",
        key=("venda_id",),
        columns={
            "venda_id": T_INT,
            "cliente_id": T_INT,
            "produto_id": T_INT,
            "loja_id": T_INT,
            "data_venda": T_DATE,
            "quantidade": T_INT,
            "valor_venda": T_DECIMAL,
            "custo_total": T_DECIMAL,
            "atualizado_em": T_TIMESTAMP,
        },
        non_negative=("valor_venda",),
    ),
    EntitySpec(
        name="estoque",
        key=("produto_id", "loja_id", "data_posicao"),
        columns={
            "produto_id": T_INT,
            "loja_id": T_INT,
            "data_posicao": T_DATE,
            "quantidade_estoque": T_INT,
        },
    ),
)


def convert_column(name, col_type, text_case):
    """Devolve a coluna convertida; valor vazio ou não convertível vira null."""
    text = F.trim(F.col(name).cast(StringType()))
    text = F.when(text == "", F.lit(None)).otherwise(text)
    if col_type == T_STR:
        return F.lower(text) if text_case == "lower" else F.upper(text)
    if col_type == T_INT:
        return text.cast("bigint")
    if col_type == T_DECIMAL:
        return F.regexp_replace(text, ",", ".").cast(DECIMAL_TYPE)
    if col_type == T_DATE:
        return F.coalesce(
            F.to_date(text, "yyyy-MM-dd"),
            F.to_date(text, "dd/MM/yyyy"),
            F.to_date(text, "yyyyMMdd"),
        )
    if col_type == T_TIMESTAMP:
        return text.cast("timestamp")
    raise ValueError(f"tipo desconhecido: {col_type}")


def has_value(name):
    return F.trim(F.col(name).cast(StringType())) != ""


def silver_transform(bronze_df, spec):
    """Aplica as regras de silver.to_silver: (válidos deduplicados, quarentena)."""
    raw_cols = bronze_df.columns
    work = bronze_df
    reasons = []
    for name, col_type in spec.columns.items():
        converted = convert_column(name, col_type, spec.text_case)
        code = REASON_BAD_DATE if col_type in (T_DATE, T_TIMESTAMP) else REASON_BAD_TYPE
        reasons.append(
            F.when(
                F.col(name).isNotNull() & has_value(name) & converted.isNull(),
                F.lit(f"{code}:{name}"),
            )
        )
        work = work.withColumn(f"__raw_{name}", F.col(name)).withColumn(name, converted)
    for name in spec.key:
        reasons.append(F.when(F.col(name).isNull(), F.lit(f"{REASON_NULL_KEY}:{name}")))
    for name in spec.non_negative:
        reasons.append(F.when(F.col(name) < 0, F.lit(f"{REASON_NEGATIVE_SALE}:{name}")))
    # sem data de ingestão válida não há como escolher a linha vigente
    ts_raw = F.col(spec.ts_col)
    ts_conv = ts_raw.cast("timestamp")
    reasons.append(F.when(ts_conv.isNull(), F.lit(f"{REASON_BAD_TYPE}:{spec.ts_col}")))
    work = work.withColumn("__raw_ts", ts_raw).withColumn(spec.ts_col, ts_conv)
    work = work.withColumn("_motivos", F.filter(F.array(*reasons), lambda r: r.isNotNull()))

    raw_fields = [
        F.col(f"__raw_{c}" if c in spec.columns else c).alias(c)
        for c in raw_cols
        if c != spec.ts_col
    ]
    raw_struct = F.struct(*raw_fields, F.col("__raw_ts").alias(spec.ts_col))
    rejected = work.where(F.size("_motivos") > 0)
    quarantine = rejected.select(
        F.lit(spec.name).alias("entidade"),
        F.to_json(raw_struct).alias("registro_json"),
        F.concat_ws(";", "_motivos").alias("_motivo"),
    )

    valid = work.where(F.size("_motivos") == 0).select(*raw_cols)
    # uma linha vigente por chave: maior _ingestion_ts_utc; empate -> a última do lote
    order = Window.partitionBy(*spec.key).orderBy(
        F.col(spec.ts_col).desc(), F.monotonically_increasing_id().desc()
    )
    silver = valid.withColumn("__rn", F.row_number().over(order)).where("__rn = 1").drop("__rn")
    return silver, quarantine


safe_run = re.sub(r"[^0-9a-zA-Z]", "", run_id)
staged = []  # (nome_staging, tabela_destino)


def staging_name(table):
    return f"{silver_schema}._stg_{safe_run}_{table.lstrip('_')}"


try:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {silver_schema}")  # noqa: F821
    quarantines = []
    # 1) prepara tudo em staging; nada de Silver é alterado nesta fase
    for spec in SPECS:
        bronze = spark.read.table(f"{bronze_schema}.{spec.name}")  # noqa: F821
        silver_df, quarantine_df = silver_transform(bronze, spec)
        stg = staging_name(spec.name)
        silver_df.write.format("delta").mode("overwrite").saveAsTable(stg)
        staged.append((stg, f"{silver_schema}.{spec.name}"))
        quarantines.append(quarantine_df)

    all_quarantine = quarantines[0]
    for q in quarantines[1:]:
        all_quarantine = all_quarantine.unionByName(q)
    all_quarantine = all_quarantine.withColumn("_run_id", F.lit(run_id)).withColumn(
        "_quarentena_ts_utc", F.current_timestamp()
    )
    stg_q = staging_name(QUARANTINE_TABLE)
    all_quarantine.write.format("delta").mode("overwrite").saveAsTable(stg_q)
    staged.append((stg_q, f"{silver_schema}.{QUARANTINE_TABLE}"))

    # 2) promove: cada overwrite Delta é atômico; reexecução gera o mesmo resultado (Req. 4.10)
    for stg, target in staged:
        (
            spark.read.table(stg)  # noqa: F821
            .write.format("delta")
            .mode("overwrite")
            .option("overwriteSchema", "true")
            .saveAsTable(target)
        )
finally:
    for stg, _ in staged:
        spark.sql(f"DROP TABLE IF EXISTS {stg}")  # noqa: F821

# Fabric notebook: nb_gold
# Camada_Gold: lê a Silver e constrói dim_cliente (SCD2), dim_produto, dim_loja, dim_calendario,
# fato_vendas, agg_vendas_dia e fato_estoque (Req. 4.5, 4.6, 4.7, 4.8, 4.9, 4.10).
# Equivalente PySpark das regras de platform_lib.gold (chaves substitutas, membro 'Desconhecido'
# com sk = -1, SCD2 com data_fim = as_of - 1 dia e 9999-12-31 na versão aberta).
# Staging por execução; a reconciliação Silver x Gold (diferença 0,00) roda sobre o staging e,
# se falhar, nada é promovido. Depois da promoção atômica no Lakehouse, as tabelas são expostas no
# Warehouse (DDL de referência: python -m infra.gen_gold_ddl --dialect tsql).
# O resultado da execução (notebook exit) traz a contagem de registros 'Desconhecido'.
import json
import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from pyspark.sql import Window
from pyspark.sql import functions as F  # noqa: N812

from platform_lib.gold import OPEN_END_DATE, UNKNOWN_LABEL, UNKNOWN_SK

# Parâmetros (célula de parâmetros do Fabric pode sobrescrever)
run_id = uuid.uuid4().hex
silver_schema = "silver"
gold_schema = "gold"
as_of = datetime.now(UTC).date().isoformat()  # data de vigência do SCD2
warehouse_name = "wh_gold"  # Warehouse que expõe a Gold; vazio desliga a exposição
expose_in_warehouse = True
MONEY = "decimal(18,2)"

# `spark` é fornecido pelo Fabric
spark.conf.set("spark.sql.ansi.enabled", "false")  # noqa: F821

GOLD_TABLES = (
    "dim_cliente",
    "dim_produto",
    "dim_loja",
    "dim_calendario",
    "fato_vendas",
    "agg_vendas_dia",
    "fato_estoque",
)
DIM_CLIENTE_SCHEMA = (
    "sk_cliente bigint, cliente_id bigint, nome_mascarado string, cidade string, uf string, "
    "data_inicio date, data_fim date, vigente boolean"
)
CLIENTE_ATTRS = ("nome_mascarado", "cidade", "uf")
DIM_CLIENTE_COLS = [
    "sk_cliente",
    "cliente_id",
    *CLIENTE_ATTRS,
    "data_inicio",
    "data_fim",
    "vigente",
]

safe_run = re.sub(r"[^0-9a-zA-Z]", "", run_id)
staged = {}  # tabela -> nome do staging


def staging_name(table):
    return f"{gold_schema}._stg_{safe_run}_{table}"


def stage(df, table):
    """Grava a tabela em staging e devolve a leitura do staging (fonte das etapas seguintes)."""
    name = staging_name(table)
    df.write.format("delta").mode("overwrite").saveAsTable(name)
    staged[table] = name
    return spark.read.table(name)  # noqa: F821


def silver(table):
    return spark.read.table(f"{silver_schema}.{table}")  # noqa: F821


def unknown_row(schema, values):
    return spark.createDataFrame([values], schema)  # noqa: F821


# ---------------------------------------------------------------------------
# dim_cliente (SCD2)
# ---------------------------------------------------------------------------
def build_dim_cliente(as_of_date):
    as_of_col = F.lit(as_of_date).cast("date")
    incoming = (
        silver("clientes")
        .where(F.col("cliente_id").isNotNull())
        .select(
            F.col("cliente_id").cast("bigint"),
            F.concat(F.substring(F.col("nome"), 1, 1), F.lit("***")).alias("nome_mascarado"),
            "cidade",
            "uf",
        )
        .dropDuplicates(["cliente_id"])
    )
    if spark.catalog.tableExists(f"{gold_schema}.dim_cliente"):  # noqa: F821
        existing = spark.read.table(f"{gold_schema}.dim_cliente")  # noqa: F821
        existing = existing.select(*DIM_CLIENTE_COLS)
    else:
        existing = spark.createDataFrame([], DIM_CLIENTE_SCHEMA)  # noqa: F821
    existing = existing.where(F.col("sk_cliente").isNotNull() & (F.col("sk_cliente") != UNKNOWN_SK))

    current = existing.where(F.col("vigente"))
    renamed = incoming.select("cliente_id", *[F.col(c).alias(f"n_{c}") for c in CLIENTE_ATTRS])
    joined = current.join(renamed, "cliente_id", "inner")
    same = F.lit(True)
    for c in CLIENTE_ATTRS:
        same = same & F.col(c).eqNullSafe(F.col(f"n_{c}"))
    changed = joined.where(~same).cache()

    if changed.where(as_of_col < F.col("data_inicio")).limit(1).count() > 0:
        raise ValueError("as_of anterior ao início de uma versão vigente de dim_cliente")

    # versões vigentes alteradas saem do conjunto mantido e são reescritas abaixo
    changed_sks = changed.select("sk_cliente", F.lit(True).alias("_chg"))
    keep = (
        existing.join(changed_sks, "sk_cliente", "left").where(F.col("_chg").isNull()).drop("_chg")
    )
    in_place = changed.where(as_of_col == F.col("data_inicio")).select(
        "sk_cliente",
        "cliente_id",
        *[F.col(f"n_{c}").alias(c) for c in CLIENTE_ATTRS],
        "data_inicio",
        "data_fim",
        "vigente",
    )
    reopened = changed.where(as_of_col > F.col("data_inicio"))
    closed = reopened.select(
        "sk_cliente",
        "cliente_id",
        *CLIENTE_ATTRS,
        "data_inicio",
        F.date_sub(as_of_col, 1).alias("data_fim"),
        F.lit(False).alias("vigente"),
    )
    new_src = reopened.select(
        "cliente_id", *[F.col(f"n_{c}").alias(c) for c in CLIENTE_ATTRS]
    ).unionByName(
        incoming.join(current.select("cliente_id"), "cliente_id", "left_anti").select(
            "cliente_id", *CLIENTE_ATTRS
        )
    )
    max_sk = existing.agg(F.max("sk_cliente")).first()[0] or 0
    order = Window.orderBy("cliente_id")
    opened = new_src.select(
        (F.row_number().over(order) + F.lit(int(max_sk))).cast("bigint").alias("sk_cliente"),
        "cliente_id",
        *CLIENTE_ATTRS,
        as_of_col.alias("data_inicio"),
        F.lit(OPEN_END_DATE.isoformat()).cast("date").alias("data_fim"),
        F.lit(True).alias("vigente"),
    )
    unknown = unknown_row(
        DIM_CLIENTE_SCHEMA,
        (
            UNKNOWN_SK,
            None,
            UNKNOWN_LABEL,
            UNKNOWN_LABEL,
            None,
            datetime(1900, 1, 1).date(),
            OPEN_END_DATE,
            True,
        ),
    )
    cols = DIM_CLIENTE_COLS
    return (
        keep.select(*cols)
        .unionByName(in_place.select(*cols))
        .unionByName(closed.select(*cols))
        .unionByName(opened.select(*cols))
        .unionByName(unknown.select(*cols))
    )


# ---------------------------------------------------------------------------
# dim_produto, dim_loja (tipo 1) e dim_calendario
# ---------------------------------------------------------------------------
def build_simple_dim(df, key, sk, columns, unknown_schema, unknown_values):
    base = (
        df.where(F.col(key).isNotNull())
        .select(F.col(key).cast("bigint").alias(key), *[c for c in columns if c != key])
        .dropDuplicates([key])
    )
    order = Window.orderBy(F.col(key).cast("string"))
    rows = base.select(
        F.row_number().over(order).cast("bigint").alias(sk), key, *[c for c in columns if c != key]
    )
    unknown = unknown_row(unknown_schema, unknown_values)
    return unknown.select(sk, key, *[c for c in columns if c != key]).unionByName(
        rows.select(sk, key, *[c for c in columns if c != key])
    )


def build_dim_produto():
    cols = ["produto_id", "nome", "categoria", "subcategoria", "preco_lista"]
    return build_simple_dim(
        silver("produtos").withColumn("preco_lista", F.col("preco_lista").cast(MONEY)),
        "produto_id",
        "sk_produto",
        cols,
        f"sk_produto bigint, produto_id bigint, nome string, categoria string, "
        f"subcategoria string, preco_lista {MONEY}",
        (UNKNOWN_SK, None, UNKNOWN_LABEL, UNKNOWN_LABEL, UNKNOWN_LABEL, None),
    )


def build_dim_loja():
    cols = ["loja_id", "nome", "regiao", "cidade", "uf"]
    return build_simple_dim(
        silver("lojas"),
        "loja_id",
        "sk_loja",
        cols,
        "sk_loja bigint, loja_id bigint, nome string, regiao string, cidade string, uf string",
        (UNKNOWN_SK, None, UNKNOWN_LABEL, UNKNOWN_LABEL, UNKNOWN_LABEL, None),
    )


def build_dim_calendario():
    bounds = (
        silver("vendas")
        .select(F.col("data_venda").alias("d"))
        .unionByName(silver("estoque").select(F.col("data_posicao").alias("d")))
        .agg(F.min("d").alias("d0"), F.max("d").alias("d1"))
        .first()
    )
    schema = "sk_data int, data date, ano int, trimestre int, mes int, dia int, dia_semana int"
    unknown = unknown_row(schema, (UNKNOWN_SK, None, None, None, None, None, None))
    if bounds["d0"] is None:
        return unknown
    days = spark.sql(  # noqa: F821
        f"SELECT explode(sequence(to_date('{bounds['d0']}'), to_date('{bounds['d1']}'),"
        " interval 1 day)) AS data"
    )
    cal = days.select(
        F.date_format("data", "yyyyMMdd").cast("int").alias("sk_data"),
        "data",
        F.year("data").alias("ano"),
        F.quarter("data").alias("trimestre"),
        F.month("data").alias("mes"),
        F.dayofmonth("data").alias("dia"),
        # 1 = segunda a 7 = domingo (isoweekday)
        (((F.dayofweek("data") + 5) % 7) + 1).alias("dia_semana"),
    )
    return unknown.unionByName(cal)


# ---------------------------------------------------------------------------
# Fatos e agregação
# ---------------------------------------------------------------------------
def lookup(df, dim, dim_key, sk_col, fact_key, out_col):
    """Resolve a chave substituta; sem correspondência -> sk = -1."""
    m = dim.where(F.col(dim_key).isNotNull() & (F.col(sk_col) != UNKNOWN_SK)).select(
        F.col(dim_key).alias("_k"), F.col(sk_col).alias("_sk")
    )
    return (
        df.join(F.broadcast(m), df[fact_key] == m["_k"], "left")
        .withColumn(out_col, F.coalesce(F.col("_sk"), F.lit(UNKNOWN_SK)).cast("bigint"))
        .drop("_k", "_sk")
    )


def resolve_sk_data(df, date_col, dim_calendario):
    sk = F.date_format(F.col(date_col), "yyyyMMdd").cast("int")
    cal = dim_calendario.where(F.col("sk_data") != UNKNOWN_SK).select(
        F.col("sk_data").alias("_cal")
    )
    return (
        df.withColumn("_sk_data", sk)
        .join(F.broadcast(cal), F.col("_sk_data") == F.col("_cal"), "left")
        .withColumn("sk_data", F.coalesce(F.col("_cal"), F.lit(UNKNOWN_SK)).cast("int"))
        .drop("_sk_data", "_cal")
    )


def build_fato_vendas(dim_cliente, dim_produto, dim_loja, dim_calendario):
    v = silver("vendas").withColumn("_data", F.col("data_venda"))
    # cliente: versão SCD2 que cobre a data da venda; senão a vigente; senão -1
    versions = dim_cliente.where(
        F.col("cliente_id").isNotNull() & (F.col("sk_cliente") != UNKNOWN_SK)
    )
    cover = versions.select(
        F.col("cliente_id").alias("_c_id"),
        F.col("sk_cliente").alias("_sk_cover"),
        F.col("data_inicio").alias("_ini"),
        F.col("data_fim").alias("_fim"),
    )
    vigente = versions.where("vigente").select(
        F.col("cliente_id").alias("_v_id"), F.col("sk_cliente").alias("_sk_vig")
    )
    v = (
        v.join(
            cover,
            (v["cliente_id"] == cover["_c_id"])
            & F.col("_data").isNotNull()
            & (F.col("_data") >= cover["_ini"])
            & (F.col("_data") <= cover["_fim"]),
            "left",
        )
        .join(vigente, v["cliente_id"] == vigente["_v_id"], "left")
        .withColumn(
            "sk_cliente",
            F.coalesce(F.col("_sk_cover"), F.col("_sk_vig"), F.lit(UNKNOWN_SK)).cast("bigint"),
        )
        .drop("_c_id", "_sk_cover", "_ini", "_fim", "_v_id", "_sk_vig")
    )
    v = lookup(v, dim_produto, "produto_id", "sk_produto", "produto_id", "sk_produto")
    v = lookup(v, dim_loja, "loja_id", "sk_loja", "loja_id", "sk_loja")
    v = resolve_sk_data(v, "_data", dim_calendario)
    return v.select(
        F.col("venda_id").cast("bigint").alias("venda_id"),
        "sk_cliente",
        "sk_produto",
        "sk_loja",
        "sk_data",
        F.coalesce(F.col("quantidade"), F.lit(0)).cast("int").alias("quantidade"),
        F.coalesce(F.col("valor_venda"), F.lit(0)).cast(MONEY).alias("valor_venda"),
        F.coalesce(F.col("custo_total"), F.lit(0)).cast(MONEY).alias("custo_total"),
    )


def build_agg_vendas_dia(fato):
    return fato.groupBy("sk_data", "sk_produto", "sk_loja").agg(
        F.sum("quantidade").cast("bigint").alias("quantidade"),
        F.sum("valor_venda").cast(MONEY).alias("valor_venda"),
        F.sum("custo_total").cast(MONEY).alias("custo_total"),
    )


def build_fato_estoque(dim_produto, dim_loja, dim_calendario):
    e = silver("estoque").withColumn("_data", F.col("data_posicao"))
    e = lookup(e, dim_produto, "produto_id", "sk_produto", "produto_id", "sk_produto")
    e = lookup(e, dim_loja, "loja_id", "sk_loja", "loja_id", "sk_loja")
    e = resolve_sk_data(e, "_data", dim_calendario)
    return e.select(
        "sk_data",
        "sk_produto",
        "sk_loja",
        F.coalesce(F.col("quantidade_estoque"), F.lit(0)).cast("int").alias("quantidade_estoque"),
    )


def count_unknown(df, *sk_cols):
    cond = F.lit(False)
    for c in sk_cols:
        cond = cond | (F.col(c) == UNKNOWN_SK)
    return df.where(cond).count()


def total_money(df, col):
    value = df.agg(F.sum(col).alias("s")).first()["s"]
    return Decimal(value) if value is not None else Decimal("0.00")


def reconcile(silver_vendas, fato, agg):
    """Soma de valor_venda na Silver, no fato e na agregação deve ser igual (diferença 0,00)."""
    s = total_money(silver_vendas.withColumn("v", F.col("valor_venda").cast(MONEY)), "v")
    g_fato, g_agg = total_money(fato, "valor_venda"), total_money(agg, "valor_venda")
    diffs = {"fato": abs(s - g_fato), "agg": abs(s - g_agg)}
    if any(d != Decimal("0.00") for d in diffs.values()):
        raise RuntimeError(
            f"Reconciliação Silver x Gold falhou: silver={s} fato={g_fato} agg={g_agg} "
            f"diferenças={ {k: str(d) for k, d in diffs.items()} }"
        )
    return s, abs(s - g_fato)


def expose_tables():
    """Expõe as tabelas Gold no Warehouse (conector Spark do Fabric)."""
    import com.microsoft.spark.fabric  # noqa: F401, PLC0415

    for table in GOLD_TABLES:
        df = spark.read.table(f"{gold_schema}.{table}")  # noqa: F821
        df.write.mode("overwrite").synapsesql(f"{warehouse_name}.dbo.{table}")


result = {}
try:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {gold_schema}")  # noqa: F821

    # 1) prepara tudo em staging; nada de Gold é alterado nesta fase
    dim_cliente = stage(build_dim_cliente(as_of), "dim_cliente")
    dim_produto = stage(build_dim_produto(), "dim_produto")
    dim_loja = stage(build_dim_loja(), "dim_loja")
    dim_calendario = stage(build_dim_calendario(), "dim_calendario")
    fato_vendas = stage(
        build_fato_vendas(dim_cliente, dim_produto, dim_loja, dim_calendario), "fato_vendas"
    )
    agg_vendas_dia = stage(build_agg_vendas_dia(fato_vendas), "agg_vendas_dia")
    fato_estoque = stage(build_fato_estoque(dim_produto, dim_loja, dim_calendario), "fato_estoque")

    # 2) reconciliação antes da promoção: falha impede a publicação (Req. 4.9)
    silver_vendas = silver("vendas")
    silver_total, diff = reconcile(silver_vendas, fato_vendas, agg_vendas_dia)
    if silver_vendas.count() != fato_vendas.count():
        raise RuntimeError("Reconciliação falhou: contagem de vendas Silver difere do fato_vendas")

    unknown_vendas = count_unknown(fato_vendas, "sk_cliente", "sk_produto", "sk_loja", "sk_data")
    unknown_estoque = count_unknown(fato_estoque, "sk_produto", "sk_loja", "sk_data")

    # 3) promove: cada overwrite Delta é atômico; reexecução gera o mesmo resultado (Req. 4.10)
    for table, stg in staged.items():
        (
            spark.read.table(stg)  # noqa: F821
            .write.format("delta")
            .mode("overwrite")
            .option("overwriteSchema", "true")
            .saveAsTable(f"{gold_schema}.{table}")
        )

    # 4) expõe no Warehouse
    if expose_in_warehouse and warehouse_name:
        expose_tables()

    result = {
        "run_id": run_id,
        "status": "success",
        "desconhecido_vendas": unknown_vendas,
        "desconhecido_estoque": unknown_estoque,
        "desconhecido_total": unknown_vendas + unknown_estoque,
        "reconciliacao_soma_silver": str(silver_total),
        "reconciliacao_diferenca": str(diff),
    }
finally:
    for stg in staged.values():
        spark.sql(f"DROP TABLE IF EXISTS {stg}")  # noqa: F821

# resultado da execução (visível ao pipeline); só chega aqui se tudo deu certo
try:
    from notebookutils import notebook as _nb  # noqa: PLC0415
except ImportError:  # runtimes antigos
    from mssparkutils import notebook as _nb  # noqa: PLC0415
_nb.exit(json.dumps(result))

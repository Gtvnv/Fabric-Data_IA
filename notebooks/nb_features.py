# Fabric notebook: nb_features
# Lê a Gold (fato_vendas) e grava gold.features_demanda e gold.features_churn conforme
# config/gold_schema.yaml (Req. 7.1, 7.10). A lógica está em platform_lib.ml.features.
# Staging por execução e promoção só depois de ambas as tabelas preparadas: falha deixa as
# features anteriores intactas.
import re
import uuid
from datetime import datetime, timedelta

from pyspark.sql import functions as F  # noqa: N812

from platform_lib.ml.features import (
    CHURN_HORIZON_DAYS,
    build_churn_features,
    build_demand_features,
    drop_direct_pii,
)

# Parâmetros (célula de parâmetros do Fabric pode sobrescrever)
run_id = uuid.uuid4().hex
gold_schema = "gold"
churn_ref_date = None  # None: última data de venda menos o horizonte (alvo observável)

DEMAND_SCHEMA = (
    "sk_produto bigint, sk_loja bigint, data date, ano int, mes int, dia int, "
    "dia_semana int, fim_de_semana boolean, lag_1 double, lag_7 double, lag_14 double, "
    "media_movel_7 double, media_movel_28 double, qtd_alvo double"
)
CHURN_SCHEMA = (
    "sk_cliente bigint, data_ref date, recencia_dias int, frequencia int, "
    "valor_total double, churn_alvo int"
)

safe_run = re.sub(r"[^0-9a-zA-Z]", "", run_id)
staged = []  # (nome_staging, tabela_destino)

try:
    # `spark` é fornecido pelo Fabric
    fato = spark.read.table(f"{gold_schema}.fato_vendas")  # noqa: F821
    cols = ["sk_data", "sk_produto", "sk_loja", "sk_cliente", "quantidade", "valor_venda"]
    gold = {"fato_vendas": [r.asDict() for r in fato.select(*cols).collect()]}

    # as features só carregam chaves substitutas e agregados (Req. 7.10)
    demand_rows = drop_direct_pii(build_demand_features(gold))

    if churn_ref_date is None:
        last_sk = fato.agg(F.max("sk_data")).collect()[0][0]
        last_day = datetime.strptime(str(last_sk), "%Y%m%d").date()
        ref_date = last_day - timedelta(days=CHURN_HORIZON_DAYS)
    else:
        ref_date = churn_ref_date
    churn_rows = drop_direct_pii(build_churn_features(gold, ref_date))

    for name, rows, schema in (
        ("features_demanda", demand_rows, DEMAND_SCHEMA),
        ("features_churn", churn_rows, CHURN_SCHEMA),
    ):
        stg = f"{gold_schema}._stg_{safe_run}_{name}"
        spark.createDataFrame(rows, schema).write.format("delta").mode(  # noqa: F821
            "overwrite"
        ).saveAsTable(stg)
        staged.append((stg, f"{gold_schema}.{name}"))

    # promove: cada overwrite Delta é atômico; reexecução gera o mesmo resultado
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

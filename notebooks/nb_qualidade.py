# Fabric notebook: nb_qualidade
# Verificacao_Qualidade: carrega as regras de config/dq_rules.yaml, avalia contra as tabelas
# Silver, grava dq.resultados (1 linha por regra) e interrompe a execução se alguma regra
# bloqueante falhar ou se a gravação falhar (Req. 5.1-5.5, 5.7, 5.8).
# Regra de negócio em platform_lib.dq; este notebook só faz a ponte com o Spark.
import uuid

from pyspark.sql.types import (
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from platform_lib.dq import (
    RulesConfigError,
    WriteError,
    decide_promotion,
    evaluate_all,
    load_rules,
    persist_results,
)

# Parâmetros (célula de parâmetros do Fabric pode sobrescrever)
run_id = uuid.uuid4().hex
rules_path = "config/dq_rules.yaml"
dq_schema = "dq"
results_table = "resultados"

RESULT_SCHEMA = StructType(
    [
        StructField("regra", StringType(), False),
        StructField("tabela", StringType(), False),
        StructField("severidade", StringType(), False),
        StructField("avaliados", LongType(), False),
        StructField("violacoes", LongType(), False),
        StructField("executado_em_utc", TimestampType(), False),
        StructField("run_id", StringType(), True),
    ]
)


class DeltaResultSink:
    """Acrescenta as linhas de resultado em dq.resultados (histórico por execução)."""

    def __init__(self, spark_session, schema_name, table_name):
        self.spark = spark_session
        self.schema_name = schema_name
        self.table_name = table_name

    def write(self, rows):
        self.spark.sql(f"CREATE SCHEMA IF NOT EXISTS {self.schema_name}")
        df = self.spark.createDataFrame(rows, schema=RESULT_SCHEMA)
        df.write.format("delta").mode("append").saveAsTable(f"{self.schema_name}.{self.table_name}")


# 1) configuração inválida interrompe antes de qualquer avaliação (Req. 5.8)
try:
    rules = load_rules(rules_path)
except RulesConfigError as exc:
    raise RuntimeError(
        f"Verificacao_Qualidade interrompida: configuração de regras inválida: {exc}"
    ) from exc

# 2) lê só as colunas e tabelas que as regras usam
needed = {}
for rule in rules:
    needed.setdefault(rule.table, set()).update(rule.columns)
    if rule.ref_table:
        needed.setdefault(rule.ref_table, set()).update(rule.ref_columns)

tables = {
    name: [row.asDict() for row in spark.read.table(name).select(*sorted(cols)).collect()]  # noqa: F821
    for name, cols in needed.items()
}

# 3) avalia e grava SEMPRE o resultado, mesmo quando vai bloquear (Req. 5.4)
results = evaluate_all(rules, tables)
try:
    persist_results(results, DeltaResultSink(spark, dq_schema, results_table), run_id)  # noqa: F821
except WriteError as exc:
    raise RuntimeError(
        f"Verificacao_Qualidade interrompida: falha ao gravar {dq_schema}.{results_table}: {exc}"
    ) from exc

# 4) bloqueia a promoção para Gold se alguma regra bloqueante falhou (Req. 5.2, 5.3)
decision = decide_promotion(results)
if not decision.promote:
    failed = ", ".join(f"{rule} ({table})" for rule, table in decision.failed_rules)
    raise RuntimeError(f"Verificacao_Qualidade bloqueou a promoção; regras com violação: {failed}")

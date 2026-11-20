# Fabric notebook: nb_pontuacao
# Pontuação em lote com a versão em produção de cada modelo (Req. 7.7, 7.8, 7.9):
# grava gold.previsao_demanda e gold.previsao_churn conforme config/gold_schema.yaml.
# Escrita em staging com promoção atômica (scoring.write_predictions); falha preserva as
# previsões anteriores.
import json
import re
import uuid
from datetime import UTC, datetime

import mlflow.sklearn
import numpy as np
from mlflow import MlflowClient

from platform_lib.ml.scoring import score_batch, write_predictions

# Parâmetros (célula de parâmetros do Fabric pode sobrescrever)
run_id = uuid.uuid4().hex
gold_schema = "gold"
production_alias = "production"

DEMAND_SCHEMA = (
    "sk_produto bigint, sk_loja bigint, data date, previsao double, "
    "modelo string, versao_modelo string, pontuado_em_utc timestamp"
)
CHURN_SCHEMA = (
    "sk_cliente bigint, data_ref date, prob_churn double, "
    "modelo string, versao_modelo string, pontuado_em_utc timestamp"
)

safe_run = re.sub(r"[^0-9a-zA-Z]", "", run_id)
client = MlflowClient()


class SparkPredictionStore:
    """Staging em tabela Delta; a promoção é um overwrite atômico da tabela de destino."""

    def __init__(self, target, schema, to_row):
        self.target = target
        self.schema = schema
        self.to_row = to_row

    def staging_name(self, run):
        return f"{self.target.replace('.', '._stg_' + re.sub(r'[^0-9a-zA-Z]', '', run) + '_')}"

    def write_staging(self, run, predictions):
        rows = [self.to_row(p) for p in predictions]
        # `spark` é fornecido pelo Fabric
        df = spark.createDataFrame(rows, self.schema)  # noqa: F821
        df.write.format("delta").mode("overwrite").saveAsTable(self.staging_name(run))

    def promote(self, run):
        (
            spark.read.table(self.staging_name(run))  # noqa: F821
            .write.format("delta")
            .mode("overwrite")
            .option("overwriteSchema", "true")
            .saveAsTable(self.target)
        )

    def discard_staging(self, run):
        spark.sql(f"DROP TABLE IF EXISTS {self.staging_name(run)}")  # noqa: F821


class ProductionModel:
    """Adapta o modelo sklearn ao protocolo Model (uma previsão por linha)."""

    def __init__(self, name, proba):
        mv = client.get_model_version_by_alias(name, production_alias)
        self.name = name
        self.version = int(mv.version)
        self.proba = proba
        self.model = mlflow.sklearn.load_model(f"models:/{name}/{self.version}")
        params = client.get_run(mv.run_id).data.params
        self.feature_cols = json.loads(params["feature_cols"])

    def predict(self, rows):
        x = np.array([[float(r[c]) for c in self.feature_cols] for r in rows], dtype=float)
        if self.proba:
            return [float(v) for v in self.model.predict_proba(x)[:, 1]]
        return [float(v) for v in self.model.predict(x)]


def pontuar(model_name, features_table, order, proba, store):
    model = ProductionModel(model_name, proba)
    rows = sorted(
        (r.asDict() for r in spark.read.table(features_table).collect()),  # noqa: F821
        key=lambda r: tuple(r[k] for k in order),
    )
    predictions = score_batch(model, rows, model_name, model.version, datetime.now(UTC))
    write_predictions(store, run_id, predictions)


def demand_row(p):
    return (
        p["sk_produto"],
        p["sk_loja"],
        p["data"],
        p["prediction"],
        p["model_name"],
        str(p["version"]),
        p["scored_at_utc"],
    )


def churn_row(p):
    return (
        p["sk_cliente"],
        p["data_ref"],
        min(1.0, max(0.0, p["prediction"])),
        p["model_name"],
        str(p["version"]),
        p["scored_at_utc"],
    )


# cada modelo é pontuado e promovido de forma independente; falha em um preserva as previsões
# anteriores dele e interrompe o notebook
pontuar(
    "previsao_demanda",
    f"{gold_schema}.features_demanda",
    ("sk_produto", "sk_loja", "data"),
    False,
    SparkPredictionStore(f"{gold_schema}.previsao_demanda", DEMAND_SCHEMA, demand_row),
)
pontuar(
    "previsao_churn",
    f"{gold_schema}.features_churn",
    ("sk_cliente", "data_ref"),
    True,
    SparkPredictionStore(f"{gold_schema}.previsao_churn", CHURN_SCHEMA, churn_row),
)

# Fabric notebook: nb_treino_demanda
# Treina LightGBM sobre gold.features_demanda e registra no MLflow (Req. 7.2 a 7.6):
# parâmetros, semente, MAE/RMSE no teste e delta_table_version da tabela de features.
# O modelo só é registrado com todas as métricas calculadas (registry.register_if_valid);
# caso contrário a run termina como FAILED com a causa. A promoção segue registry.should_promote.
import json
import math

import mlflow
import mlflow.sklearn
import numpy as np
from lightgbm import LGBMRegressor
from mlflow import MlflowClient

from platform_lib.ml.registry import (
    DEMAND,
    SEED,
    TRAIN_FRAC,
    register_if_valid,
    should_promote,
    split_train_test,
)

# Parâmetros (célula de parâmetros do Fabric pode sobrescrever)
gold_schema = "gold"
features_table = f"{gold_schema}.features_demanda"
experiment_name = "previsao_demanda"
model_name = "previsao_demanda"
production_alias = "production"
FEATURE_COLS = [
    "ano", "mes", "dia", "dia_semana", "fim_de_semana",
    "lag_1", "lag_7", "lag_14", "media_movel_7", "media_movel_28",
]  # fmt: skip
TARGET_COL = "qtd_alvo"
LGBM_PARAMS = {
    "n_estimators": 300,
    "learning_rate": 0.05,
    "num_leaves": 31,
    "random_state": SEED,
}

client = MlflowClient()


def delta_version(table):
    # `spark` é fornecido pelo Fabric
    return int(spark.sql(f"DESCRIBE HISTORY {table} LIMIT 1").collect()[0]["version"])  # noqa: F821


def version_of_run(run_id):
    versions = client.search_model_versions(f"name='{model_name}'")
    return next((int(v.version) for v in versions if v.run_id == run_id), None)


def production_metrics():
    try:
        mv = client.get_model_version_by_alias(model_name, production_alias)
    except Exception:  # noqa: BLE001 - sem alias = sem versão em produção
        return None
    return dict(client.get_run(mv.run_id).data.metrics)


mlflow.set_experiment(experiment_name)
run = mlflow.start_run()
try:
    table_version = delta_version(features_table)
    mlflow.log_params(
        {
            **{f"lgbm_{k}": v for k, v in LGBM_PARAMS.items()},
            "seed": SEED,
            "train_frac": TRAIN_FRAC,
            "feature_cols": json.dumps(FEATURE_COLS),
            "target": TARGET_COL,
            "features_table": features_table,
            "features_delta_table_version": table_version,
        }
    )
    mlflow.set_tag("delta_table_version", str(table_version))

    rows = sorted(
        (r.asDict() for r in spark.read.table(features_table).collect()),  # noqa: F821
        key=lambda r: (r["sk_produto"], r["sk_loja"], r["data"]),
    )
    x_all = np.array([[float(r[c]) for c in FEATURE_COLS] for r in rows], dtype=float)
    y_all = np.array([float(r[TARGET_COL]) for r in rows], dtype=float)
    train_idx, test_idx = split_train_test(list(range(len(rows))), seed=SEED)
    mlflow.log_params({"n_train": len(train_idx), "n_test": len(test_idx)})

    trained = {}

    def train_fn():
        model = LGBMRegressor(**LGBM_PARAMS)
        model.fit(x_all[train_idx], y_all[train_idx])
        pred = model.predict(x_all[test_idx])
        err = y_all[test_idx] - pred
        metrics = {
            "MAE": float(np.mean(np.abs(err))),
            "RMSE": float(math.sqrt(np.mean(err**2))),
        }
        for name, value in metrics.items():
            if math.isfinite(value):
                mlflow.log_metric(name, value)
        trained["model"] = model
        return metrics

    def register_fn(version):
        mlflow.sklearn.log_model(
            trained["model"], artifact_path="model", registered_model_name=model_name
        )

    existing = [int(v.version) for v in client.search_model_versions(f"name='{model_name}'")]
    result = register_if_valid(train_fn, register_fn, existing, DEMAND)

    if result.status != "sucesso":
        mlflow.set_tag("failure_cause", result.error)
        mlflow.end_run(status="FAILED")
        raise RuntimeError(f"treino de demanda falhou: {result.error}")

    version = version_of_run(run.info.run_id) or result.registered_version
    decision = should_promote(result.metrics, production_metrics(), DEMAND)
    mlflow.set_tag("promotion_decision", "promoted" if decision.promote else "not_promoted")
    mlflow.log_text(decision.reason, "promotion_reason.txt")
    mlflow.log_params({"model_version": version, "promotion_reason": decision.reason[:500]})
    if decision.promote:
        client.set_registered_model_alias(model_name, production_alias, str(version))
    mlflow.end_run()
except Exception as exc:
    if mlflow.active_run() is not None:
        mlflow.set_tag("failure_cause", str(exc))
        mlflow.end_run(status="FAILED")
    raise

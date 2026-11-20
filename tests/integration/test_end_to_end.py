"""Integração ponta a ponta com dublês em memória (Req. 4.11, 5.2, 9.1, 9.2, 9.5).

Fluxo: synth.generate/load -> ingestion.ingest_entity -> silver.to_silver -> dq -> gold.* ->
ml (features, treino, pontuação com modelo determinístico) -> config.ultima_atualizacao,
tudo encadeado por ``orchestration.run_pipeline``. Sem Fabric, Spark ou rede.
"""

from __future__ import annotations

import csv
import io
import math
import shutil
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from platform_lib import dq, gold, ingestion, orchestration, silver, synth
from platform_lib.ml import features, registry, scoring
from platform_lib.orchestration import (
    STATUS_FAILED,
    STATUS_NOT_RUN,
    STATUS_SUCCESS,
    STEPS,
    StepRecord,
)
from platform_lib.silver import EntitySpec
from platform_lib.timefmt import build_ultima_atualizacao_row

NOW = datetime(2024, 6, 1, 12, 0, tzinfo=UTC)

RAW_PARAMS: dict[str, Any] = {
    "seed": 7,
    "n_customers": 20,
    "n_products": 6,
    "n_stores": 3,
    "start": "2024-01-01",
    "end": "2024-03-31",
}

SPECS: dict[str, EntitySpec] = {
    "clientes": EntitySpec(
        "clientes", ("cliente_id",),
        {"cliente_id": "int", "nome": "str", "email": "str", "telefone": "str",
         "documento": "str", "cidade": "str", "uf": "str", "data_cadastro": "date",
         "atualizado_em": "timestamp"},
    ),
    "produtos": EntitySpec(
        "produtos", ("produto_id",),
        {"produto_id": "int", "nome": "str", "categoria": "str", "subcategoria": "str",
         "preco_lista": "decimal", "custo": "decimal", "atualizado_em": "timestamp"},
    ),
    "lojas": EntitySpec(
        "lojas", ("loja_id",),
        {"loja_id": "int", "nome": "str", "regiao": "str", "cidade": "str", "uf": "str",
         "atualizado_em": "timestamp"},
    ),
    "vendas": EntitySpec(
        "vendas", ("venda_id",),
        {"venda_id": "int", "cliente_id": "int", "produto_id": "int", "loja_id": "int",
         "data_venda": "date", "quantidade": "int", "valor_venda": "decimal",
         "custo_total": "decimal", "atualizado_em": "timestamp"},
        non_negative=("valor_venda",),
    ),
    "estoque": EntitySpec(
        "estoque", ("produto_id", "loja_id", "data_posicao"),
        {"produto_id": "int", "loja_id": "int", "data_posicao": "date",
         "quantidade_estoque": "int"},
    ),
}
WATERMARK = {"clientes": "atualizado_em", "produtos": "atualizado_em", "lojas": "atualizado_em",
             "vendas": "atualizado_em", "estoque": "data_posicao"}

RULES = [
    dq.Rule("vendas_pk_unica", "silver.vendas", "unique", ("venda_id",), "blocking"),
    dq.Rule("vendas_valor_nao_nulo", "silver.vendas", "not_null", ("valor_venda",), "blocking"),
    dq.Rule("vendas_cliente_fk", "silver.vendas", "referential", ("cliente_id",), "blocking",
            "silver.clientes", ("cliente_id",)),
    dq.Rule("estoque_qtd_nao_nula", "silver.estoque", "not_null", ("quantidade_estoque",),
            "warning"),
]


class QualityBlocked(Exception):
    def __init__(self, verificacao: str) -> None:
        super().__init__(f"qualidade bloqueante violada: {verificacao}")
        self.verificacao = verificacao


class ListSink:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def write(self, rows: list[dict[str, Any]]) -> None:
        self.rows.extend(rows)


class DemandBaseline:
    """Modelo determinístico: prevê a média móvel de 7 dias."""

    def predict(self, rows):
        return [r["media_movel_7"] for r in rows]


class ChurnBaseline:
    """Modelo determinístico: probabilidade de churn cai com a frequência de compra."""

    def predict(self, rows):
        return [1.0 / (1.0 + r["frequencia"]) for r in rows]


def _auc(labels: list[int], scores: list[float]) -> float:
    pos = [s for lab, s in zip(labels, scores, strict=True) if lab == 1]
    neg = [s for lab, s in zip(labels, scores, strict=True) if lab == 0]
    if not pos or not neg:
        return 0.5
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def _f1(labels: list[int], preds: list[int]) -> float:
    tp = sum(1 for lab, p in zip(labels, preds, strict=True) if lab == 1 and p == 1)
    fp = sum(1 for lab, p in zip(labels, preds, strict=True) if lab == 0 and p == 1)
    fn = sum(1 for lab, p in zip(labels, preds, strict=True) if lab == 1 and p == 0)
    return 0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn)


class Platform:
    """Estado em memória das camadas e implementação das etapas do pipeline mestre."""

    def __init__(self, raw_params: dict[str, Any]) -> None:
        self.params = synth.validate(raw_params)
        self.dataset = synth.generate(self.params)
        self.sql = synth.InMemorySqlSink()
        self.obj = synth.InMemoryObjectSink()
        report = synth.load(self.dataset, self.sql, self.obj)
        assert report.success, report.error
        self.bronze: dict[str, list[dict]] = {e: [] for e in synth.ENTITIES}
        self.watermarks: dict[str, Any] = dict.fromkeys(synth.ENTITIES)
        self.silver: dict[str, list[dict]] = {}
        self.quarantine: dict[str, list[dict]] = {}
        self.dq_sink = ListSink()
        self.dq_results: list[dq.RuleResult] = []
        # Publicado somente ao fim de cada etapa bem-sucedida.
        self.gold: dict[str, list[dict]] = {}
        self.recon: dict[str, Decimal] = {}
        self.predictions = {
            "demanda": scoring.InMemoryPredictionStore(),
            "churn": scoring.InMemoryPredictionStore(),
        }
        self.model_versions: dict[str, list[int]] = {"demanda": [], "churn": []}
        self.ultima_atualizacao: list[dict] = []

    # -- fonte ---------------------------------------------------------------
    def _source_rows(self, entity: str) -> list[dict]:
        if entity == "estoque":
            data = self.obj.files[synth.object_name(entity, self.params)].decode("utf-8")
            return [
                {k: (None if v == "" else v) for k, v in row.items()}
                for row in csv.DictReader(io.StringIO(data))
            ]
        return [dict(r) for r in self.sql.tables[entity].values()]

    # -- etapas --------------------------------------------------------------
    def ingestao(self) -> int:
        total = 0

        def run_one(entity: str) -> None:
            nonlocal total
            out = ingestion.ingest_entity(
                self.bronze[entity], self._source_rows(entity),
                key=synth.KEY_COLUMNS[entity], watermark_col=WATERMARK[entity],
                previous_watermark=self.watermarks[entity], run_id="run-1",
                source="fonte_origem", now_utc=NOW,
            )
            if not out.ok:
                raise out.error  # type: ignore[misc]
            self.bronze[entity], self.watermarks[entity] = out.bronze, out.watermark
            total += out.written

        status = ingestion.run_entities(list(synth.ENTITIES), run_one)
        if not status.ok:
            raise RuntimeError(f"ingestão falhou: {sorted(status.failed)}")
        return total

    def silver_step(self) -> int:
        silver_new: dict[str, list[dict]] = {}
        quarantine_new: dict[str, list[dict]] = {}
        for entity, spec in SPECS.items():
            res = silver.to_silver(self.bronze[entity], spec)
            silver_new[entity], quarantine_new[entity] = res.silver_rows, res.quarantine_rows
        self.silver, self.quarantine = silver_new, quarantine_new
        return sum(len(v) for v in silver_new.values())

    def qualidade(self) -> int:
        tables = {f"silver.{e}": rows for e, rows in self.silver.items()}
        results = dq.evaluate_all(RULES, tables, NOW)
        dq.persist_results(results, self.dq_sink, run_id="run-1")
        self.dq_results = results
        decision = dq.decide_promotion(results)
        if not decision.promote:
            raise QualityBlocked(", ".join(rule for rule, _ in decision.failed_rules))
        return len(results)

    def gold_step(self) -> int:
        s = self.silver
        incoming = [
            {"cliente_id": c["cliente_id"], "nome_mascarado": "***", "cidade": c["cidade"],
             "uf": c["uf"]}
            for c in s["clientes"]
        ]
        dim_cliente = gold.add_unknown_cliente(
            gold.build_dim_cliente_scd2([], incoming, self.params.start)
        )
        dims = {
            "dim_cliente": dim_cliente,
            "dim_produto": gold.build_dim_produto(s["produtos"]),
            "dim_loja": gold.build_dim_loja(s["lojas"]),
            "dim_calendario": gold.build_dim_calendario(self.params.start, self.params.end),
        }
        fact = gold.resolve_fact(s["vendas"], dims)
        agg = gold.aggregate_daily(fact.rows)
        recon = {
            "fato": gold.reconcile_sales(s["vendas"], fact.rows),
            "agg": gold.reconcile_sales(s["vendas"], agg),
        }
        if any(diff != Decimal("0.00") for diff in recon.values()):
            raise RuntimeError(f"reconciliação Silver x Gold divergente: {recon}")
        estoque = gold.build_fato_estoque(s["estoque"], dims)
        self.recon = recon
        self.gold = {**dims, "fato_vendas": fact.rows, "agg_vendas_dia": agg,
                     "fato_estoque": estoque.rows}
        return len(fact.rows)

    def ia(self) -> int:
        ref = self.params.end - timedelta(days=30)
        feats = {
            "demanda": features.drop_direct_pii(features.build_demand_features(self.gold)),
            "churn": features.drop_direct_pii(features.build_churn_features(self.gold, ref)),
        }
        models = {"demanda": DemandBaseline(), "churn": ChurnBaseline()}
        total = 0
        for kind, rows in feats.items():
            if not rows:
                raise RuntimeError(f"sem features de {kind}")
            ids = list(range(len(rows)))
            _, test_ids = registry.split_train_test(ids)
            test = [rows[i] for i in test_ids] or rows
            model = models[kind]

            def train(kind: str = kind, test: list = test, model: Any = model) -> dict:
                preds = list(model.predict(test))
                if kind == "demanda":
                    err = [p - r["qtd_alvo"] for p, r in zip(preds, test, strict=True)]
                    return {"MAE": sum(abs(e) for e in err) / len(err),
                            "RMSE": math.sqrt(sum(e * e for e in err) / len(err))}
                labels = [r["churn_alvo"] for r in test]
                return {"AUC": _auc(labels, preds),
                        "F1": _f1(labels, [int(p >= 0.5) for p in preds])}

            result = registry.register_if_valid(
                train, lambda v, kind=kind: self.model_versions[kind].append(v),
                self.model_versions[kind], kind,
            )
            if result.status != "sucesso":
                raise RuntimeError(result.error)
            decision = registry.should_promote(result.metrics, None, kind)
            assert decision.promote
            preds = scoring.score_batch(model, rows, f"modelo_{kind}",
                                        result.registered_version, NOW)
            scoring.write_predictions(self.predictions[kind], "run-1", preds)
            total += len(preds)
        return total

    def semantico(self) -> int:
        self.ultima_atualizacao = [build_ultima_atualizacao_row(NOW)]
        return len(self.ultima_atualizacao)

    def runners(self) -> dict[str, Any]:
        return {"ingestao": self.ingestao, "silver": self.silver_step,
                "qualidade": self.qualidade, "gold": self.gold_step, "ia": self.ia,
                "semantico": self.semantico}


def _clock():
    state = {"t": datetime(2024, 6, 1, 12, 0, tzinfo=UTC)}

    def tick() -> datetime:
        state["t"] += timedelta(seconds=1)
        return state["t"]

    return tick


def _run(platform: Platform, runners: dict[str, Any] | None = None):
    audit: list[StepRecord] = []
    notes: list[str] = []
    records = orchestration.run_pipeline(
        runners or platform.runners(), run_id="run-1", clock=_clock(), audit=audit.append,
        notifier=notes.append, sleep=lambda _s: None,
    )
    return records, audit, notes


# ---------------------------------------------------------------------------
# Caminho feliz
# ---------------------------------------------------------------------------


def test_pipeline_end_to_end_success():
    p = Platform(RAW_PARAMS)
    records, audit, notes = _run(p)

    # Auditoria por etapa: início, término, status e registros (Req. 9.5)
    assert [r.etapa for r in records] == STEPS
    assert audit == records
    for r in records:
        assert r.status == STATUS_SUCCESS
        assert r.inicio is not None and r.termino is not None and r.inicio < r.termino
        assert r.registros > 0
    assert notes == []

    # Bronze com metadados e Silver sem perdas (dados sem ruído)
    for entity in synth.ENTITIES:
        assert len(p.bronze[entity]) == len(p.silver[entity]) > 0
        assert p.quarantine[entity] == []
    assert all("_run_id" in r for r in p.bronze["vendas"])

    # Reconciliação Silver x Gold: diferença 0,00 (Req. 4.11)
    assert p.recon == {"fato": Decimal("0.00"), "agg": Decimal("0.00")}
    assert gold.reconcile_sales(p.silver["vendas"], p.gold["fato_vendas"]) == Decimal("0.00")
    assert gold.reconcile_sales(p.silver["vendas"], p.gold["agg_vendas_dia"]) == Decimal("0.00")

    # Qualidade: 1 linha por regra, sem violações
    assert len(p.dq_sink.rows) == len(RULES)
    assert all(r["violacoes"] == 0 for r in p.dq_sink.rows if r["severidade"] == "blocking")

    # IA: previsões publicadas, 1 por registro de features, com versão 1
    for kind in ("demanda", "churn"):
        preds = p.predictions[kind].current
        assert preds and all(x["version"] == 1 for x in preds)
        assert all(x["model_name"] == f"modelo_{kind}" for x in preds)
    assert len(p.predictions["demanda"].current) == len(
        features.build_demand_features(p.gold)
    )

    # Última atualização em America/Sao_Paulo (UTC-3 em junho)
    assert p.ultima_atualizacao[0]["ts_sao_paulo_texto"] == "01/06/2024 09:00"


def test_ingestion_rerun_is_idempotent():
    p = Platform(RAW_PARAMS)
    p.ingestao()
    first = {e: len(rows) for e, rows in p.bronze.items()}
    assert p.ingestao() == 0  # marca d'água: nada novo
    assert {e: len(rows) for e, rows in p.bronze.items()} == first


# ---------------------------------------------------------------------------
# Falha bloqueante de qualidade
# ---------------------------------------------------------------------------


def test_blocking_dq_failure_stops_pipeline_and_promotes_nothing():
    noisy = {**RAW_PARAMS, "noise": {"dup_pct": 0.0, "null_pct": 0.2, "bad_date_pct": 0.0}}
    p = Platform(noisy)
    records, audit, notes = _run(p)

    status = {r.etapa: r.status for r in records}
    assert status == {
        "ingestao": STATUS_SUCCESS, "silver": STATUS_SUCCESS, "qualidade": STATUS_FAILED,
        "gold": STATUS_NOT_RUN, "ia": STATUS_NOT_RUN, "semantico": STATUS_NOT_RUN,
    }
    assert len(audit) == len(STEPS)
    failed = next(r for r in records if r.etapa == "qualidade")
    assert failed.verificacao == "vendas_valor_nao_nulo"
    assert failed.inicio is not None and failed.termino is not None
    for r in records:
        if r.status == STATUS_NOT_RUN:
            assert r.inicio is None and r.termino is None and r.registros == 0

    # Resultados registrados, com a contagem de nulos injetados (Req. 5.2, 5.4)
    injected = len(p.dataset.noise_manifest["vendas"].nulls)
    assert injected > 0
    by_rule = {r["regra"]: r for r in p.dq_sink.rows}
    assert by_rule["vendas_valor_nao_nulo"]["violacoes"] == injected
    assert by_rule["vendas_pk_unica"]["violacoes"] == 0

    # Nada promovido
    assert p.gold == {} and p.recon == {}
    assert p.predictions["demanda"].current == [] and p.predictions["churn"].current == []
    assert p.ultima_atualizacao == []

    # Falha notificada
    assert len(notes) == 1 and "qualidade" in notes[0]


@pytest.mark.parametrize("failing", STEPS)
def test_pipeline_stops_at_first_failure_in_any_step(failing: str):
    p = Platform(RAW_PARAMS)
    runners = p.runners()

    def boom() -> int:
        raise RuntimeError("erro injetado")

    runners[failing] = boom
    records, _, notes = _run(p, runners)

    idx = STEPS.index(failing)
    assert [r.status for r in records[:idx]] == [STATUS_SUCCESS] * idx
    assert records[idx].status == STATUS_FAILED and records[idx].erro == "erro injetado"
    assert [r.status for r in records[idx + 1:]] == [STATUS_NOT_RUN] * (len(STEPS) - idx - 1)
    assert len(notes) == 1
    if idx < STEPS.index("gold"):
        assert p.gold == {}
    if idx < STEPS.index("semantico"):
        assert p.ultima_atualizacao == []


# ---------------------------------------------------------------------------
# PySpark (opcional)
# ---------------------------------------------------------------------------


@pytest.mark.spark
def test_pyspark_daily_aggregation_matches_reference():
    pytest.importorskip("pyspark")
    if shutil.which("java") is None:
        pytest.skip("JVM não disponível")
    from pyspark.sql import SparkSession  # noqa: PLC0415
    from pyspark.sql import functions as F  # noqa: PLC0415
    from pyspark.sql.types import DecimalType, IntegerType, StructField, StructType  # noqa: PLC0415

    try:
        spark = SparkSession.builder.master("local[1]").appName("it").getOrCreate()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Spark local indisponível: {exc}")
    try:
        d = Decimal
        fact = [
            {"sk_data": 20240101, "sk_produto": 1, "sk_loja": 1, "quantidade": 2,
             "valor_venda": d("10.50"), "custo_total": d("6.00")},
            {"sk_data": 20240101, "sk_produto": 1, "sk_loja": 1, "quantidade": 1,
             "valor_venda": d("5.25"), "custo_total": d("3.00")},
            {"sk_data": 20240102, "sk_produto": 2, "sk_loja": 1, "quantidade": 4,
             "valor_venda": d("40.00"), "custo_total": d("25.00")},
        ]
        schema = StructType([
            StructField("sk_data", IntegerType()), StructField("sk_produto", IntegerType()),
            StructField("sk_loja", IntegerType()), StructField("quantidade", IntegerType()),
            StructField("valor_venda", DecimalType(18, 2)),
            StructField("custo_total", DecimalType(18, 2)),
        ])
        df = spark.createDataFrame([tuple(r.values()) for r in fact], schema)
        got = {
            (r["sk_data"], r["sk_produto"], r["sk_loja"]): (
                r["q"], r["v"], r["c"])
            for r in df.groupBy("sk_data", "sk_produto", "sk_loja").agg(
                F.sum("quantidade").alias("q"), F.sum("valor_venda").alias("v"),
                F.sum("custo_total").alias("c")).collect()
        }
        ref = {
            (r["sk_data"], r["sk_produto"], r["sk_loja"]): (
                r["quantidade"], r["valor_venda"], r["custo_total"])
            for r in gold.aggregate_daily(fact)
        }
        assert got == ref
    finally:
        spark.stop()


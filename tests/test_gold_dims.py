from datetime import date, timedelta

from platform_lib.gold import (
    OPEN_END_DATE,
    UNKNOWN_SK,
    add_unknown_cliente,
    build_dim_calendario,
    build_dim_cliente_scd2,
    build_dim_loja,
    build_dim_produto,
    build_surrogate_keys,
)


def test_scd2_change_closes_and_opens():
    dim = build_dim_cliente_scd2([], [{"cliente_id": "A", "cidade": "SP"}], date(2024, 1, 1))
    dim = build_dim_cliente_scd2(dim, [{"cliente_id": "A", "cidade": "RJ"}], date(2024, 3, 1))
    assert len(dim) == 2
    old, new = dim
    assert old["vigente"] is False and old["data_fim"] == date(2024, 2, 29)
    assert new["vigente"] is True and new["data_fim"] == OPEN_END_DATE
    assert new["data_inicio"] == date(2024, 3, 1) and new["sk_cliente"] != old["sk_cliente"]


def test_scd2_idempotent_and_single_current():
    inc = [{"cliente_id": "A", "cidade": "SP"}]
    d1 = build_dim_cliente_scd2([], inc, "2024-01-01")
    d2 = build_dim_cliente_scd2(d1, inc, "2024-01-01")
    assert d1 == d2
    assert sum(r["vigente"] for r in d2) == 1


def test_scd2_no_overlap_over_many_changes():
    dim = []
    day = date(2024, 1, 1)
    for city in ["SP", "RJ", "MG", "SP"]:
        dim = build_dim_cliente_scd2(dim, [{"cliente_id": "A", "cidade": city}], day)
        day += timedelta(days=10)
    rows = sorted(dim, key=lambda r: r["data_inicio"])
    assert sum(r["vigente"] for r in rows) == 1
    for a, b in zip(rows, rows[1:], strict=False):
        assert a["data_fim"] < b["data_inicio"]


def test_surrogate_keys_current_only_and_unknown_ignored():
    dim = build_dim_cliente_scd2([], [{"cliente_id": "A", "cidade": "SP"}], "2024-01-01")
    dim = build_dim_cliente_scd2(dim, [{"cliente_id": "A", "cidade": "RJ"}], "2024-02-01")
    dim = add_unknown_cliente(dim)
    assert dim[0]["sk_cliente"] == UNKNOWN_SK
    assert build_surrogate_keys(dim) == {"A": 2}


def test_simple_dims_and_calendar():
    prod = build_dim_produto([{"produto_id": "P1", "nome": "x"}])
    assert prod[0]["sk_produto"] == UNKNOWN_SK and prod[1]["sk_produto"] == 1
    loja = build_dim_loja([{"loja_id": "L1", "nome": "y"}])
    assert build_surrogate_keys(loja, "loja_id", "sk_loja") == {"L1": 1}
    cal = build_dim_calendario("2024-02-28", "2024-03-01")
    assert [r["sk_data"] for r in cal] == [-1, 20240228, 20240229, 20240301]

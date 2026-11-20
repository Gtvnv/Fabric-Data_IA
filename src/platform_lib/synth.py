"""Gerador de dados sintéticos: parâmetros, validação e geração (Req. 2.1-2.8)."""

from __future__ import annotations

import dataclasses
import math
import random
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from faker import Faker

SEED_MIN, SEED_MAX = 0, 2_147_483_647
CUSTOMERS_MIN, CUSTOMERS_MAX = 1, 1_000_000
PRODUCTS_MIN, PRODUCTS_MAX = 1, 100_000
STORES_MIN, STORES_MAX = 1, 1_000
NOISE_MIN, NOISE_MAX = 0.0, 0.20
MAX_RANGE_YEARS = 5

_INT_LIMITS: dict[str, tuple[int, int]] = {
    "seed": (SEED_MIN, SEED_MAX),
    "n_customers": (CUSTOMERS_MIN, CUSTOMERS_MAX),
    "n_products": (PRODUCTS_MIN, PRODUCTS_MAX),
    "n_stores": (STORES_MIN, STORES_MAX),
}
_NOISE_FIELDS = ("dup_pct", "null_pct", "bad_date_pct")


class ParamError(ValueError):
    """Parâmetro inválido; `param` carrega o nome do parâmetro."""

    param: str

    def __init__(self, param: str, message: str | None = None) -> None:
        self.param = param
        super().__init__(message or f"Parâmetro inválido: {param}")


@dataclass(frozen=True)
class NoiseParams:
    dup_pct: float = 0.0
    null_pct: float = 0.0
    bad_date_pct: float = 0.0


@dataclass(frozen=True)
class GenParams:
    seed: int
    n_customers: int
    n_products: int
    n_stores: int
    start: date
    end: date
    noise: NoiseParams | None = None


def _get_int(raw: Mapping[str, Any], name: str) -> int:
    if name not in raw or raw[name] is None:
        raise ParamError(name, f"Parâmetro ausente: {name}")
    value = raw[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ParamError(name, f"Parâmetro {name} deve ser inteiro")
    low, high = _INT_LIMITS[name]
    if not low <= value <= high:
        raise ParamError(name, f"Parâmetro {name} fora do limite [{low}, {high}]")
    return value


def _get_date(raw: Mapping[str, Any], name: str) -> date:
    if name not in raw or raw[name] is None:
        raise ParamError(name, f"Parâmetro ausente: {name}")
    value = raw[name]
    if isinstance(value, datetime):
        raise ParamError(name, f"Parâmetro {name} deve ser uma data")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ParamError(name, f"Parâmetro {name} deve ser uma data válida")


def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29/02 em ano não bissexto
        return d.replace(year=d.year + years, day=28)


def _get_noise(raw: Mapping[str, Any]) -> NoiseParams | None:
    value = raw.get("noise")
    if value is None:
        return None
    if isinstance(value, NoiseParams):
        data: Mapping[str, Any] = {f: getattr(value, f) for f in _NOISE_FIELDS}
    elif isinstance(value, Mapping):
        data = value
    else:
        raise ParamError("noise", "Parâmetro noise deve ser um mapeamento")
    parsed: dict[str, float] = {}
    for field in _NOISE_FIELDS:
        v = data.get(field, 0.0)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ParamError(field, f"Parâmetro {field} deve ser numérico")
        if math.isnan(v) or not NOISE_MIN <= v <= NOISE_MAX:
            raise ParamError(field, f"Parâmetro {field} fora do limite [0, 0.20]")
        parsed[field] = float(v)
    return NoiseParams(**parsed)


def validate(raw: Mapping[str, Any]) -> GenParams:
    """Valida presença, tipo e limites; levanta `ParamError` com o nome do parâmetro."""
    if not isinstance(raw, Mapping):
        raise ParamError("params", "Parâmetros devem ser um mapeamento")
    ints = {name: _get_int(raw, name) for name in _INT_LIMITS}
    start = _get_date(raw, "start")
    end = _get_date(raw, "end")
    if start > end:
        raise ParamError("start", "Data inicial deve ser menor ou igual à final")
    if end > _add_years(start, MAX_RANGE_YEARS):
        raise ParamError("end", f"Intervalo máximo de {MAX_RANGE_YEARS} anos excedido")
    noise = _get_noise(raw)
    return GenParams(start=start, end=end, noise=noise, **ints)


# ---------------------------------------------------------------------------
# Geração (Req. 2.1, 2.2, 2.5, 2.6, 2.7, 2.8)
# ---------------------------------------------------------------------------

ENTITIES = ("clientes", "produtos", "lojas", "vendas", "estoque")

#: Colunas da chave de negócio de cada entidade.
KEY_COLUMNS: dict[str, tuple[str, ...]] = {
    "clientes": ("cliente_id",),
    "produtos": ("produto_id",),
    "lojas": ("loja_id",),
    "vendas": ("venda_id",),
    "estoque": ("produto_id", "loja_id", "data_posicao"),
}

#: Colunas na ordem do modelo de dados da Fonte_Origem.
COLUMNS: dict[str, tuple[str, ...]] = {
    "clientes": (
        "cliente_id",
        "nome",
        "email",
        "telefone",
        "documento",
        "cidade",
        "uf",
        "data_cadastro",
        "atualizado_em",
    ),
    "produtos": (
        "produto_id",
        "nome",
        "categoria",
        "subcategoria",
        "preco_lista",
        "custo",
        "atualizado_em",
    ),
    "lojas": ("loja_id", "nome", "regiao", "cidade", "uf", "atualizado_em"),
    "vendas": (
        "venda_id",
        "cliente_id",
        "produto_id",
        "loja_id",
        "data_venda",
        "quantidade",
        "valor_venda",
        "custo_total",
        "atualizado_em",
    ),
    "estoque": ("produto_id", "loja_id", "data_posicao", "quantidade_estoque"),
}

#: Coluna obrigatória (não chave) que recebe ruído de nulo, por entidade.
NULL_NOISE_COLUMN: dict[str, str] = {
    "clientes": "nome",
    "produtos": "nome",
    "lojas": "nome",
    "vendas": "valor_venda",
    "estoque": "quantidade_estoque",
}

#: Coluna de data que recebe ruído de data inválida, por entidade.
DATE_NOISE_COLUMN: dict[str, str] = {
    "clientes": "data_cadastro",
    "produtos": "atualizado_em",
    "lojas": "atualizado_em",
    "vendas": "data_venda",
    "estoque": "data_posicao",
}

SALES_PER_CUSTOMER = 3
STOCK_ROWS_PER_ENTITY = 5  # linhas de estoque ~ 5 * max(produtos, lojas), limitado a P*L
FICTITIOUS_EMAIL_DOMAINS = ("example.com", "example.org")
FICTITIOUS_PHONE_PREFIX = "90000"  # (DD) 90000-XXXX é a faixa fictícia reservada

_CATEGORIES: dict[str, tuple[str, ...]] = {
    "Alimentos": ("Grãos", "Bebidas", "Laticínios"),
    "Limpeza": ("Casa", "Lavanderia"),
    "Higiene": ("Cabelo", "Corpo", "Bucal"),
    "Eletrônicos": ("Áudio", "Acessórios"),
    "Papelaria": ("Escritório", "Escolar"),
}
_REGIONS = ("Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul")
_DDDS = ("11", "21", "31", "41", "51", "61", "71", "81")
# Pares (mês, dia) que nunca existem em nenhum ano.
_IMPOSSIBLE_MD = ((2, 30), (2, 31), (4, 31), (6, 31), (9, 31), (13, 1), (0, 10), (1, 32))


@dataclass(frozen=True)
class NoiseEntry:
    """Registros afetados pelo ruído em uma entidade (chaves de negócio originais)."""

    duplicates: tuple[tuple[Any, ...], ...] = ()
    nulls: tuple[tuple[Any, ...], ...] = ()
    bad_dates: tuple[tuple[Any, ...], ...] = ()
    null_column: str = ""
    date_column: str = ""


@dataclass(frozen=True)
class Dataset:
    params: GenParams
    tables: dict[str, list[dict[str, Any]]]
    noise_manifest: dict[str, NoiseEntry] = dataclasses.field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        return {name: len(rows) for name, rows in self.tables.items()}


def cpf_check_digits_valid(doc: str) -> bool:
    """Valida os dígitos de controle de um CPF (11 dígitos)."""
    if len(doc) != 11 or not doc.isdigit() or len(set(doc)) == 1:
        return False
    digits = [int(c) for c in doc]
    for n in (9, 10):
        total = sum(d * w for d, w in zip(digits[:n], range(n + 1, 1, -1), strict=True))
        check = (total * 10 % 11) % 10
        if digits[n] != check:
            return False
    return True


def is_fictitious_email(email: str) -> bool:
    return email.rpartition("@")[2] in FICTITIOUS_EMAIL_DOMAINS


def is_fictitious_phone(phone: str) -> bool:
    return (
        len(phone) == 15
        and phone[0] == "("
        and phone[1:3].isdigit()
        and phone[3:5] == ") "
        and phone[5:10] == FICTITIOUS_PHONE_PREFIX
        and phone[10] == "-"
        and phone[11:].isdigit()
    )


def _invalid_cpf(rng: random.Random) -> str:
    """CPF de 11 dígitos cujos dígitos de controle são propositalmente inválidos."""
    while True:
        base = [rng.randint(0, 9) for _ in range(9)]
        digits = list(base)
        for n in (9, 10):
            total = sum(d * w for d, w in zip(digits, range(n + 1, 1, -1), strict=True))
            digits.append((total * 10 % 11) % 10)
        digits[9] = (digits[9] + rng.randint(1, 9)) % 10  # corrompe o 1º dígito de controle
        doc = "".join(map(str, digits))
        if not cpf_check_digits_valid(doc):
            return doc


def _fake_phone(rng: random.Random) -> str:
    return f"({rng.choice(_DDDS)}) {FICTITIOUS_PHONE_PREFIX}-{rng.randint(0, 9999):04d}"


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _iso_dt(d: date, rng: random.Random) -> str:
    h, m, s = rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59)
    return f"{d.isoformat()}T{h:02d}:{m:02d}:{s:02d}"


def _gen_clientes(p: GenParams, rng: random.Random, fake: Faker, span: int) -> list[dict[str, Any]]:
    rows = []
    for i in range(1, p.n_customers + 1):
        cadastro = p.start + timedelta(days=rng.randint(0, span))
        rows.append(
            {
                "cliente_id": i,
                "nome": fake.name(),
                "email": f"cliente{i}@{rng.choice(FICTITIOUS_EMAIL_DOMAINS)}",
                "telefone": _fake_phone(rng),
                "documento": _invalid_cpf(rng),
                "cidade": fake.city(),
                "uf": fake.state_abbr(),
                "data_cadastro": cadastro.isoformat(),
                "atualizado_em": _iso_dt(cadastro, rng),
            }
        )
    return rows


def _gen_produtos(p: GenParams, rng: random.Random, fake: Faker, span: int) -> list[dict[str, Any]]:
    categories = sorted(_CATEGORIES)
    rows = []
    for i in range(1, p.n_products + 1):
        categoria = rng.choice(categories)
        preco = _money(Decimal(rng.randint(500, 50_000)) / 100)
        custo = _money(preco * Decimal(rng.randint(40, 80)) / 100)
        rows.append(
            {
                "produto_id": i,
                "nome": f"{fake.word().capitalize()} {i}",
                "categoria": categoria,
                "subcategoria": rng.choice(_CATEGORIES[categoria]),
                "preco_lista": preco,
                "custo": custo,
                "atualizado_em": _iso_dt(p.start + timedelta(days=rng.randint(0, span)), rng),
            }
        )
    return rows


def _gen_lojas(p: GenParams, rng: random.Random, fake: Faker, span: int) -> list[dict[str, Any]]:
    rows = []
    for i in range(1, p.n_stores + 1):
        rows.append(
            {
                "loja_id": i,
                "nome": f"Loja {i} {fake.last_name()}",
                "regiao": rng.choice(_REGIONS),
                "cidade": fake.city(),
                "uf": fake.state_abbr(),
                "atualizado_em": _iso_dt(p.start + timedelta(days=rng.randint(0, span)), rng),
            }
        )
    return rows


def _gen_vendas(
    p: GenParams, rng: random.Random, produtos: list[dict[str, Any]], span: int
) -> list[dict[str, Any]]:
    rows = []
    for i in range(1, p.n_customers * SALES_PER_CUSTOMER + 1):
        produto = produtos[rng.randrange(p.n_products)]
        quantidade = rng.randint(1, 10)
        dia = p.start + timedelta(days=rng.randint(0, span))
        rows.append(
            {
                "venda_id": i,
                "cliente_id": rng.randint(1, p.n_customers),
                "produto_id": produto["produto_id"],
                "loja_id": rng.randint(1, p.n_stores),
                "data_venda": dia.isoformat(),
                "quantidade": quantidade,
                "valor_venda": _money(produto["preco_lista"] * quantidade),
                "custo_total": _money(produto["custo"] * quantidade),
                "atualizado_em": _iso_dt(dia, rng),
            }
        )
    return rows


def _gen_estoque(p: GenParams, rng: random.Random) -> list[dict[str, Any]]:
    total = p.n_products * p.n_stores
    n = min(total, STOCK_ROWS_PER_ENTITY * max(p.n_products, p.n_stores))
    rows = []
    for idx in sorted(rng.sample(range(total), n)):
        produto, loja = divmod(idx, p.n_stores)
        rows.append(
            {
                "produto_id": produto + 1,
                "loja_id": loja + 1,
                "data_posicao": p.end.isoformat(),
                "quantidade_estoque": rng.randint(0, 500),
            }
        )
    return rows


def _bad_date(rng: random.Random, original: Any) -> str:
    month, day = rng.choice(_IMPOSSIBLE_MD)
    year = int(str(original)[:4])
    bad = f"{year:04d}-{month:02d}-{day:02d}"
    return bad + str(original)[10:]  # preserva a parte de hora, se houver


def _apply_noise(
    entity: str, rows: list[dict[str, Any]], noise: NoiseParams | None, rng: random.Random
) -> tuple[list[dict[str, Any]], NoiseEntry]:
    """Aplica `round(pct * n)` nulos, datas inválidas e duplicados (Req. 2.6, 2.7)."""
    null_col, date_col = NULL_NOISE_COLUMN[entity], DATE_NOISE_COLUMN[entity]
    if noise is None:
        return rows, NoiseEntry(null_column=null_col, date_column=date_col)
    n = len(rows)
    keys = KEY_COLUMNS[entity]

    def key_of(row: dict[str, Any]) -> tuple[Any, ...]:
        return tuple(row[c] for c in keys)

    k_null = min(round(noise.null_pct * n), n)
    k_bad = min(round(noise.bad_date_pct * n), n - k_null)
    k_dup = min(round(noise.dup_pct * n), n)
    picked = rng.sample(range(n), k_null + k_bad)
    null_idx, bad_idx = picked[:k_null], picked[k_null:]
    dup_idx = sorted(rng.sample(range(n), k_dup))

    # Duplicados são cópias das linhas limpas, para não contaminar os outros tipos.
    out = [dict(r) for r in rows]
    duplicates = [dict(rows[i]) for i in dup_idx]
    nulls = tuple(key_of(rows[i]) for i in null_idx)
    bads = tuple(key_of(rows[i]) for i in bad_idx)
    for i in null_idx:
        out[i][null_col] = None
    for i in bad_idx:
        out[i][date_col] = _bad_date(rng, rows[i][date_col])
    out.extend(duplicates)
    entry = NoiseEntry(
        duplicates=tuple(key_of(r) for r in duplicates),
        nulls=nulls,
        bad_dates=bads,
        null_column=null_col,
        date_column=date_col,
    )
    return out, entry


def generate(p: GenParams) -> Dataset:
    """Gera o dataset de forma determinística a partir de `p` (Req. 2.1, 2.2).

    Usa apenas `random.Random(seed)` e uma instância própria de Faker (pt_BR) com
    semente; não lê relógio nem altera estado global.
    """
    rng = random.Random(p.seed)
    fake = Faker("pt_BR")
    fake.seed_instance(p.seed)
    span = (p.end - p.start).days

    clean = {
        "clientes": _gen_clientes(p, rng, fake, span),
        "produtos": _gen_produtos(p, rng, fake, span),
        "lojas": _gen_lojas(p, rng, fake, span),
    }
    clean["vendas"] = _gen_vendas(p, rng, clean["produtos"], span)
    clean["estoque"] = _gen_estoque(p, rng)

    tables: dict[str, list[dict[str, Any]]] = {}
    manifest: dict[str, NoiseEntry] = {}
    for entity in ENTITIES:
        tables[entity], manifest[entity] = _apply_noise(entity, clean[entity], p.noise, rng)
    return Dataset(params=p, tables=tables, noise_manifest=manifest)

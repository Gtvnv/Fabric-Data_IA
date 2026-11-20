"""Estratégias para a classificação de dados pessoais (Property 25)."""

from __future__ import annotations

from hypothesis import strategies as st

PII_TOKENS = ["nome", "name", "email", "e_mail", "cpf", "cnpj", "rg", "documento",
              "doc", "telefone", "fone", "celular", "phone", "tel"]
SAFE_TOKENS = ["valor", "quantidade", "preco", "data", "loja", "produto", "total",
               "status", "categoria", "regiao", "id", "codigo", "margem"]

_affix = st.lists(st.sampled_from(SAFE_TOKENS), max_size=2)


@st.composite
def _name_with(draw, token_strategy):
    pre, post = draw(_affix), draw(_affix)
    token = draw(token_strategy)
    name = "_".join([*pre, token, *post])
    return draw(st.sampled_from([name, name.upper(), name.title()]))


pii_column_names = _name_with(st.sampled_from(PII_TOKENS))
non_pii_column_names = _name_with(st.sampled_from(SAFE_TOKENS))

# Valores sem padrão de dado pessoal (apenas letras).
plain_values = st.one_of(
    st.none(),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", max_size=15),
)

_digits = lambda n: st.text(alphabet="0123456789", min_size=n, max_size=n)  # noqa: E731

email_values = st.builds(
    lambda u, d, t: f"{u}@{d}.{t}",
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10),
    st.sampled_from(["com", "br", "org"]),
)
cpf_values = _digits(11)
cnpj_values = _digits(14)
phone_values = st.builds(lambda a, b: f"9{a}-{b}", _digits(4), _digits(4))

pii_content_values = st.one_of(email_values, cpf_values, cnpj_values, phone_values)

@st.composite
def pii_content_column(draw):
    """Lista homogênea de valores de um mesmo tipo de dado pessoal."""
    kind = draw(st.sampled_from([email_values, cpf_values, cnpj_values, phone_values]))
    return draw(st.lists(kind, min_size=1, max_size=10))


plain_samples = st.lists(plain_values, max_size=10)

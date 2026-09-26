"""
Padmini (versão ocidental) — TAROT: tiragem de 3 cartas (Situação · Desafio · Conselho).

  - 78 cartas do baralho Rider-Waite-Smith: 22 arcanos maiores e 56 menores
    (Paus, Copas, Espadas, Ouros; Ás a Dez, Valete, Cavaleiro, Rainha, Rei).
    Nesta versão, só na posição normal (sem cartas invertidas).
  - Sorteio no servidor com gerador criptográfico (`secrets`).
  - A tiragem ganha um ID que CARREGA as três cartas, com um selo HMAC do
    servidor: não depende de banco (o site funciona sem ele), ninguém monta
    uma tiragem na mão, e o link pago — que assina esse ID — abre exatamente
    as cartas que a pessoa viu na amostra.

Sem imagens de terceiros: as cartas são desenhadas na página (tipografia e um
símbolo simples nosso).
"""

import base64
import hashlib
import hmac
import secrets

import acesso

POSICOES = ("situacao", "desafio", "conselho")
POSICAO_PT = {"situacao": "Situação", "desafio": "Desafio", "conselho": "Conselho"}

_MAIORES = [
    ("o_louco", "O Louco"), ("o_mago", "O Mago"), ("a_sacerdotisa", "A Sacerdotisa"),
    ("a_imperatriz", "A Imperatriz"), ("o_imperador", "O Imperador"), ("o_hierofante", "O Hierofante"),
    ("os_enamorados", "Os Enamorados"), ("o_carro", "O Carro"), ("a_forca", "A Força"),
    ("o_eremita", "O Eremita"), ("a_roda_da_fortuna", "A Roda da Fortuna"), ("a_justica", "A Justiça"),
    ("o_enforcado", "O Enforcado"), ("a_morte", "A Morte"), ("a_temperanca", "A Temperança"),
    ("o_diabo", "O Diabo"), ("a_torre", "A Torre"), ("a_estrela", "A Estrela"), ("a_lua", "A Lua"),
    ("o_sol", "O Sol"), ("o_julgamento", "O Julgamento"), ("o_mundo", "O Mundo"),
]
NAIPES = [("paus", "Paus"), ("copas", "Copas"), ("espadas", "Espadas"), ("ouros", "Ouros")]
_FIGURAS = [("as", "Ás"), ("dois", "Dois"), ("tres", "Três"), ("quatro", "Quatro"), ("cinco", "Cinco"),
            ("seis", "Seis"), ("sete", "Sete"), ("oito", "Oito"), ("nove", "Nove"), ("dez", "Dez"),
            ("valete", "Valete"), ("cavaleiro", "Cavaleiro"), ("rainha", "Rainha"), ("rei", "Rei")]
ROMANOS = ["0", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV",
           "XV", "XVI", "XVII", "XVIII", "XIX", "XX", "XXI"]

CARTAS: list[dict] = (
    [{"indice": i, "chave": c, "nome": n, "arcano": "maior", "numero": i, "rotulo": ROMANOS[i], "naipe": None}
     for i, (c, n) in enumerate(_MAIORES)]
    + [{"indice": 22 + 14 * j + k, "chave": f"{fc}_de_{nc}", "nome": f"{fn} de {nn}", "arcano": "menor",
        "numero": k + 1, "rotulo": ("A" if k == 0 else str(k + 1)) if k < 10 else fn, "naipe": nc}
       for j, (nc, nn) in enumerate(NAIPES) for k, (fc, fn) in enumerate(_FIGURAS)]
)
assert len(CARTAS) == 78 and [c["indice"] for c in CARTAS] == list(range(78))

_TAM_NONCE, _TAM_SELO = 5, 4


def _selo(corpo: bytes) -> bytes:
    chave = (acesso.SEGREDO or "padmini-sem-segredo").encode("utf-8")
    return hmac.new(chave, b"tarot|" + corpo, hashlib.sha256).digest()[:_TAM_SELO]


def tirar() -> str:
    """Sorteia 3 cartas diferentes (gerador criptográfico) e devolve o ID da tiragem."""
    cartas = secrets.SystemRandom().sample(range(78), 3)
    corpo = bytes(cartas) + secrets.token_bytes(_TAM_NONCE)
    return base64.urlsafe_b64encode(corpo + _selo(corpo)).decode().rstrip("=")


def cartas_da_tiragem(tiragem: str) -> list[dict]:
    """As 3 cartas (na ordem Situação, Desafio, Conselho). ValueError se o ID não
    foi emitido por nós (selo errado) ou está corrompido."""
    try:
        bruto = base64.urlsafe_b64decode(str(tiragem) + "=" * (-len(str(tiragem)) % 4))
    except Exception:
        raise ValueError("Tiragem inválida.")
    if len(bruto) != 3 + _TAM_NONCE + _TAM_SELO:
        raise ValueError("Tiragem inválida.")
    corpo, selo = bruto[:-_TAM_SELO], bruto[-_TAM_SELO:]
    if not hmac.compare_digest(selo, _selo(corpo)):
        raise ValueError("Tiragem inválida.")
    indices = list(corpo[:3])
    if len(set(indices)) != 3 or max(indices) >= 78:
        raise ValueError("Tiragem inválida.")
    return [{**CARTAS[i], "posicao": p, "posicao_pt": POSICAO_PT[p]} for i, p in zip(indices, POSICOES)]

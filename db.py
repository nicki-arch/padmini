"""
Padmini — banco de dados (Postgres; funciona com Supabase ou Render Postgres).

Liga só se `DATABASE_URL` existir. Sem ela, todas as funções viram no-op e o
site funciona como antes (stateless).

REGRA DE OURO: o banco nunca pode impedir uma entrega. Qualquer erro aqui é
registrado no log e a função devolve um valor neutro — o comprador recebe o
link mesmo com o banco fora do ar.

O que guardamos (e o que NÃO guardamos):
  - pedidos: id do pedido na Cakto, produto, e-mail/nome/telefone, dados de
    nascimento, valor, taxas, forma de pagamento, utm/sck, link entregue.
  - NÃO guardamos CPF nem dados de cartão, mesmo vindo no payload da Cakto.
  - leads: lista de espera do lançamento (nome, e-mail, WhatsApp opcional,
    consentimentos separados por canal — LGPD — e a origem ref/utm).
  - textos_ia: o texto gerado pela IA para cada mapa, para gerar uma vez só
    (sem isso, cada clique no botão chama a API de novo).
"""
import json
import logging
import os

log = logging.getLogger("padmini.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS pedidos (
    id               BIGSERIAL PRIMARY KEY,
    criado_em        TIMESTAMPTZ NOT NULL DEFAULT now(),
    cakto_id         TEXT UNIQUE,
    cakto_ref        TEXT,
    evento           TEXT,
    status           TEXT,
    produto          TEXT NOT NULL,
    email            TEXT,
    nome             TEXT,
    telefone         TEXT,
    dados_nascimento JSONB,
    valor            NUMERIC(10, 2),
    taxas            NUMERIC(10, 2),
    forma_pagamento  TEXT,
    oferta_id        TEXT,
    tipo_oferta      TEXT,
    rastreio         JSONB,
    link             TEXT,
    email_enviado    BOOLEAN NOT NULL DEFAULT false,
    entregue_em      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS pedidos_email_idx ON pedidos (lower(email));

CREATE TABLE IF NOT EXISTS textos_ia (
    chave      TEXT PRIMARY KEY,
    produto    TEXT NOT NULL,
    texto      TEXT NOT NULL,
    modelo     TEXT,
    criado_em  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS leads (
    id                  BIGSERIAL PRIMARY KEY,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
    nome                TEXT,
    email               TEXT NOT NULL,
    whatsapp            TEXT,
    aceita_email        BOOLEAN NOT NULL DEFAULT false,
    aceita_whatsapp     BOOLEAN NOT NULL DEFAULT false,
    interesse           TEXT,
    origem              JSONB
);
CREATE UNIQUE INDEX IF NOT EXISTS leads_email_idx ON leads (lower(email));

-- Supabase: a API pública (chave anon) enxerga o schema public. RLS ligado e
-- sem políticas = ninguém lê nem grava por ela. O site conecta como dono do
-- banco, que não é afetado pelo RLS.
ALTER TABLE pedidos ENABLE ROW LEVEL SECURITY;
ALTER TABLE textos_ia ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;

-- Defesa em profundidade (só existe no Supabase): tira das roles da API
-- pública qualquer permissão nas tabelas, além do RLS.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE pedidos, textos_ia, leads FROM anon;
        REVOKE ALL ON SEQUENCE pedidos_id_seq, leads_id_seq FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE pedidos, textos_ia, leads FROM authenticated;
        REVOKE ALL ON SEQUENCE pedidos_id_seq, leads_id_seq FROM authenticated;
    END IF;
END $$;
"""

CAMPOS_RASTREIO = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "sck")


def url() -> str:
    return os.environ.get("DATABASE_URL", "")


def ativo() -> bool:
    return bool(url())


def _conectar():
    import psycopg
    return psycopg.connect(url(), connect_timeout=5, autocommit=True)


def iniciar() -> bool:
    """Cria as tabelas se não existirem. Chamado na subida do app."""
    if not ativo():
        return False
    try:
        with _conectar() as c:
            c.execute(SCHEMA)
        return True
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao iniciar o schema")
        return False


def saude() -> bool | None:
    """None = sem banco configurado; True/False = banco respondeu ou não."""
    if not ativo():
        return None
    try:
        with _conectar() as c:
            c.execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001
        log.exception("banco: falha no teste de saúde")
        return False


def _dados(evento: dict) -> dict:
    d = evento.get("data") if isinstance(evento, dict) else None
    return d if isinstance(d, dict) else {}


def _num(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def pedido_entregue(cakto_id: str) -> str | None:
    """Se este pedido já foi entregue, devolve o link (para não mandar e-mail de novo)."""
    if not (ativo() and cakto_id):
        return None
    try:
        with _conectar() as c:
            row = c.execute("SELECT link FROM pedidos WHERE cakto_id = %s AND email_enviado",
                            (cakto_id,)).fetchone()
        return row[0] if row else None
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao consultar pedido %s", cakto_id)
        return None


def registrar_pedido(evento: dict, produto: str, dados: dict, email: str,
                     link: str, email_enviado: bool) -> bool:
    """Grava (ou atualiza) o pedido. Idempotente pelo id da Cakto."""
    if not ativo():
        return False
    d = _dados(evento)
    cliente = d.get("customer") if isinstance(d.get("customer"), dict) else {}
    oferta = d.get("offer") if isinstance(d.get("offer"), dict) else {}
    rastreio = {k: d[k] for k in CAMPOS_RASTREIO if d.get(k)}
    cakto_id = str(d.get("id") or "") or None
    try:
        with _conectar() as c:
            c.execute(
                """
                INSERT INTO pedidos (cakto_id, cakto_ref, evento, status, produto, email, nome,
                    telefone, dados_nascimento, valor, taxas, forma_pagamento, oferta_id,
                    tipo_oferta, rastreio, link, email_enviado, entregue_em)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                        CASE WHEN %s THEN now() END)
                ON CONFLICT (cakto_id) DO UPDATE SET
                    link = EXCLUDED.link,
                    email_enviado = pedidos.email_enviado OR EXCLUDED.email_enviado,
                    entregue_em = COALESCE(pedidos.entregue_em, EXCLUDED.entregue_em)
                """,
                (cakto_id, d.get("refId"), evento.get("event"), d.get("status"), produto,
                 email or None, cliente.get("name") or dados.get("nome"), cliente.get("phone"),
                 json.dumps(dados, ensure_ascii=False), _num(d.get("amount")), _num(d.get("fees")),
                 d.get("paymentMethod"), oferta.get("id"), d.get("offer_type"),
                 json.dumps(rastreio, ensure_ascii=False), link, email_enviado, email_enviado),
            )
        return True
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao registrar pedido %s", cakto_id)
        return False


def texto_ia(chave: str) -> str | None:
    if not ativo():
        return None
    try:
        with _conectar() as c:
            row = c.execute("SELECT texto FROM textos_ia WHERE chave = %s", (chave,)).fetchone()
        return row[0] if row else None
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao ler texto_ia")
        return None


def guardar_texto_ia(chave: str, produto: str, texto: str, modelo: str | None = None) -> bool:
    if not ativo():
        return False
    try:
        with _conectar() as c:
            c.execute("INSERT INTO textos_ia (chave, produto, texto, modelo) VALUES (%s,%s,%s,%s) "
                      "ON CONFLICT (chave) DO NOTHING", (chave, produto, texto, modelo))
        return True
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao guardar texto_ia")
        return False


def registrar_lead(nome: str, email: str, whatsapp: str, aceita_email: bool,
                   aceita_whatsapp: bool, interesse: str, origem: dict) -> bool:
    """Grava (ou atualiza, pelo e-mail) um inscrito da lista de espera."""
    if not ativo():
        return False
    try:
        with _conectar() as c:
            c.execute(
                """
                INSERT INTO leads (nome, email, whatsapp, aceita_email, aceita_whatsapp, interesse, origem)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (lower(email)) DO UPDATE SET
                    nome = COALESCE(EXCLUDED.nome, leads.nome),
                    whatsapp = COALESCE(EXCLUDED.whatsapp, leads.whatsapp),
                    aceita_email = EXCLUDED.aceita_email,
                    aceita_whatsapp = EXCLUDED.aceita_whatsapp,
                    interesse = COALESCE(EXCLUDED.interesse, leads.interesse),
                    atualizado_em = now()
                """,
                (nome or None, email, whatsapp or None, aceita_email, aceita_whatsapp,
                 interesse or None, json.dumps(origem or {}, ensure_ascii=False)),
            )
        return True
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao registrar lead")
        return False

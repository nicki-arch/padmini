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

CREATE TABLE IF NOT EXISTS live_geracoes (
    id         BIGSERIAL PRIMARY KEY,
    criado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    produto    TEXT NOT NULL,
    nome       TEXT,
    cidade     TEXT,
    nascimento TEXT
);

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

-- Quem pediu a amostra grátis por e-mail. `aceita_lembrete` = autorizou UM
-- lembrete depois (marketing: só com consentimento). `dados` são os dados de
-- nascimento da amostra, para o lembrete e o link do checkout saírem prontos.
CREATE TABLE IF NOT EXISTS amostras_email (
    id                  BIGSERIAL PRIMARY KEY,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT now(),
    email               TEXT NOT NULL,
    produto             TEXT NOT NULL,
    dados               JSONB NOT NULL,
    aceita_lembrete     BOOLEAN NOT NULL DEFAULT false,
    origem              JSONB,
    lembrete_enviado_em TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS amostras_email_idx ON amostras_email (lower(email));

-- Carrinho abandonado (evento checkout_abandonment da Cakto): um e-mail de
-- recuperação por pessoa e oferta.
CREATE TABLE IF NOT EXISTS abandonos (
    id          BIGSERIAL PRIMARY KEY,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
    email       TEXT NOT NULL,
    nome        TEXT,
    oferta_id   TEXT,
    checkout    TEXT,
    email_enviado BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS abandonos_email_idx ON abandonos (lower(email));

-- Rodada 4: a versão do site (vedica | ocidental) viaja com o registro. O
-- lembrete sai na versão em que a pessoa estava, não na que está no ar na hora
-- do envio (mesma regra dos links de entrega). Linhas antigas ficam 'vedica'.
ALTER TABLE amostras_email ADD COLUMN IF NOT EXISTS sistema TEXT NOT NULL DEFAULT 'vedica';
ALTER TABLE abandonos ADD COLUMN IF NOT EXISTS sistema TEXT NOT NULL DEFAULT 'vedica';

-- Rodada 6: na ocidental a amostra só sai com e-mail, e a caixa "pode me mandar
-- mais sobre a minha leitura (até 3 e-mails)" é gravada aqui. É a autorização da
-- sequência de boas-vindas; linhas antigas ficam false.
ALTER TABLE amostras_email ADD COLUMN IF NOT EXISTS aceita_sequencia BOOLEAN NOT NULL DEFAULT false;

-- Quem clicou em "não quero mais receber": nenhum e-mail de marketing
-- (lembrete, recuperação) sai para este endereço. E-mail de entrega de compra sai.
CREATE TABLE IF NOT EXISTS email_optout (
    email      TEXT PRIMARY KEY,
    criado_em  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Supabase: a API pública (chave anon) enxerga o schema public. RLS ligado e
-- sem políticas = ninguém lê nem grava por ela. O site conecta como dono do
-- banco, que não é afetado pelo RLS.
ALTER TABLE pedidos ENABLE ROW LEVEL SECURITY;
ALTER TABLE textos_ia ENABLE ROW LEVEL SECURITY;
ALTER TABLE live_geracoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE amostras_email ENABLE ROW LEVEL SECURITY;
ALTER TABLE abandonos ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_optout ENABLE ROW LEVEL SECURITY;

-- Rodada 6: sequências de e-mail (boas-vindas depois da amostra, pós-compra).
-- Uma linha por passo enviado; o índice único garante que o mesmo passo nunca
-- sai duas vezes para o mesmo e-mail. A linha é gravada ANTES do envio (reserva);
-- se o envio falha, ela é apagada e o passo tenta de novo no dia seguinte.
CREATE TABLE IF NOT EXISTS envios_sequencia (
    id          BIGSERIAL PRIMARY KEY,
    enviado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    email       TEXT NOT NULL,
    sequencia   TEXT NOT NULL,
    passo       INTEGER NOT NULL,
    sistema     TEXT NOT NULL DEFAULT 'ocidental',
    referencia  BIGINT,
    pulado      BOOLEAN NOT NULL DEFAULT false
);
CREATE UNIQUE INDEX IF NOT EXISTS envios_sequencia_passo_idx ON envios_sequencia (lower(email), sequencia, passo);
ALTER TABLE envios_sequencia ENABLE ROW LEVEL SECURITY;

-- Defesa em profundidade (só existe no Supabase): tira das roles da API
-- pública qualquer permissão nas tabelas, além do RLS.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE pedidos, textos_ia, leads, live_geracoes,
            amostras_email, abandonos, email_optout FROM anon;
        REVOKE ALL ON SEQUENCE pedidos_id_seq, leads_id_seq, live_geracoes_id_seq,
            amostras_email_id_seq, abandonos_id_seq FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE pedidos, textos_ia, leads, live_geracoes,
            amostras_email, abandonos, email_optout FROM authenticated;
        REVOKE ALL ON SEQUENCE pedidos_id_seq, leads_id_seq, live_geracoes_id_seq,
            amostras_email_id_seq, abandonos_id_seq FROM authenticated;
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


def registrar_live(produto: str, nome: str, cidade: str, nascimento: str) -> bool:
    """Log das leituras geradas no modo live (quem o Pedro leu, e quando)."""
    if not ativo():
        return False
    try:
        with _conectar() as c:
            c.execute("INSERT INTO live_geracoes (produto, nome, cidade, nascimento) "
                      "VALUES (%s,%s,%s,%s)", (produto, nome or None, cidade or None, nascimento or None))
        return True
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao registrar geração do modo live")
        return False


# ---------------------------------------------------------------------------
# Amostra por e-mail, lembrete, carrinho abandonado, descadastro
# ---------------------------------------------------------------------------
def descadastrado(email: str) -> bool:
    """True se a pessoa pediu para não receber mais e-mails de marketing.
    Sem banco, ou com erro, responde True: na dúvida, não manda marketing."""
    if not ativo():
        return True
    try:
        with _conectar() as c:
            row = c.execute("SELECT 1 FROM email_optout WHERE email = lower(%s)", (email,)).fetchone()
        return row is not None
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao consultar descadastro")
        return True


def descadastrar(email: str) -> bool:
    if not ativo():
        return False
    try:
        with _conectar() as c:
            c.execute("INSERT INTO email_optout (email) VALUES (lower(%s)) ON CONFLICT DO NOTHING", (email,))
            c.execute("UPDATE amostras_email SET aceita_lembrete = false WHERE lower(email) = lower(%s)",
                      (email,))
        return True
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao descadastrar")
        return False


def amostras_enviadas_hoje(email: str) -> int:
    """Quantas amostras este e-mail recebeu nas últimas 24h (anti-spam)."""
    if not ativo():
        return 0
    try:
        with _conectar() as c:
            row = c.execute("SELECT count(*) FROM amostras_email WHERE lower(email) = lower(%s) "
                            "AND criado_em > now() - interval '24 hours'", (email,)).fetchone()
        return int(row[0])
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao contar amostras")
        return 0


def registrar_amostra_email(email: str, produto: str, dados: dict, aceita_lembrete: bool,
                            origem: dict, sistema: str = "vedica", aceita_sequencia: bool = False) -> bool:
    if not ativo():
        return False
    try:
        with _conectar() as c:
            c.execute("INSERT INTO amostras_email (email, produto, dados, aceita_lembrete, origem, sistema, "
                      "aceita_sequencia) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                      (email, produto, json.dumps(dados, ensure_ascii=False), aceita_lembrete,
                       json.dumps(origem or {}, ensure_ascii=False), sistema, aceita_sequencia))
        return True
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao registrar amostra por e-mail")
        return False


def lembretes_pendentes(limite: int = 50) -> list[dict]:
    """
    Amostras com lembrete autorizado, pedidas entre 24h e 72h atrás, que ainda
    não receberam lembrete, cujo e-mail não comprou nada depois e não se
    descadastrou. Um lembrete por e-mail (o mais recente).
    """
    if not ativo():
        return []
    try:
        with _conectar() as c:
            rows = c.execute(
                """
                SELECT DISTINCT ON (lower(a.email)) a.id, a.email, a.produto, a.dados, a.sistema
                FROM amostras_email a
                WHERE a.aceita_lembrete AND a.lembrete_enviado_em IS NULL
                  -- rodada 6: quem marcou a caixa nova recebe a sequência de boas-vindas, não o lembrete
                  AND NOT a.aceita_sequencia
                  AND a.criado_em < now() - interval '24 hours'
                  AND a.criado_em > now() - interval '72 hours'
                  AND NOT EXISTS (SELECT 1 FROM email_optout o WHERE o.email = lower(a.email))
                  AND NOT EXISTS (SELECT 1 FROM pedidos p WHERE lower(p.email) = lower(a.email)
                                  AND p.criado_em > a.criado_em)
                  AND NOT EXISTS (SELECT 1 FROM amostras_email b WHERE lower(b.email) = lower(a.email)
                                  AND b.lembrete_enviado_em IS NOT NULL)
                ORDER BY lower(a.email), a.criado_em DESC
                LIMIT %s
                """, (limite,)).fetchall()
        return [{"id": r[0], "email": r[1], "produto": r[2], "dados": r[3], "sistema": r[4]} for r in rows]
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao buscar lembretes")
        return []


def marcar_lembrete_enviado(amostra_id: int) -> None:
    if not ativo():
        return
    try:
        with _conectar() as c:
            c.execute("UPDATE amostras_email SET lembrete_enviado_em = now() WHERE id = %s", (amostra_id,))
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao marcar lembrete")


def abandono_ja_tratado(email: str, oferta_id: str) -> bool:
    """True se esta pessoa já recebeu recuperação desta oferta nos últimos 7 dias,
    ou já comprou depois. Sem banco, True (não arrisca mandar repetido)."""
    if not ativo():
        return True
    try:
        with _conectar() as c:
            row = c.execute(
                """
                SELECT 1 FROM abandonos WHERE lower(email) = lower(%s) AND oferta_id IS NOT DISTINCT FROM %s
                  AND email_enviado AND criado_em > now() - interval '7 days'
                UNION ALL
                SELECT 1 FROM pedidos WHERE lower(email) = lower(%s) AND criado_em > now() - interval '1 day'
                LIMIT 1
                """, (email, oferta_id or None, email)).fetchone()
        return row is not None
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao consultar abandono")
        return True


def registrar_abandono(email: str, nome: str, oferta_id: str, checkout: str, enviado: bool,
                       sistema: str = "vedica") -> bool:
    if not ativo():
        return False
    try:
        with _conectar() as c:
            c.execute("INSERT INTO abandonos (email, nome, oferta_id, checkout, email_enviado, sistema) "
                      "VALUES (%s,%s,%s,%s,%s,%s)",
                      (email, nome or None, oferta_id or None, checkout or None, enviado, sistema))
        return True
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao registrar abandono")
        return False


# Tabelas de marketing que a política de privacidade promete apagar (seção 7):
# "até você se descadastrar ou até 24 meses sem nenhuma interação".
TABELAS_MARKETING = ("leads", "amostras_email", "abandonos", "envios_sequencia")
MESES_SEM_INTERACAO = 24

# Última interação de cada e-mail com o site: entrar/atualizar a lista de espera,
# pedir amostra, receber o lembrete, abandonar ou fazer uma compra.
_ULTIMA_INTERACAO = """
WITH ultima AS (
    SELECT email, max(quando) AS quando FROM (
        SELECT lower(email) AS email, atualizado_em AS quando FROM leads
        UNION ALL SELECT lower(email), greatest(criado_em, coalesce(lembrete_enviado_em, criado_em)) FROM amostras_email
        UNION ALL SELECT lower(email), criado_em FROM abandonos
        UNION ALL SELECT lower(email), criado_em FROM pedidos WHERE email IS NOT NULL
    ) x GROUP BY email
),
apagar AS (
    SELECT email FROM ultima WHERE quando < now() - make_interval(months => %(meses)s)
    UNION SELECT email FROM email_optout
)
"""


def limpar_marketing() -> dict | None:
    """Apaga os dados de marketing de quem se descadastrou ou está há 24 meses
    sem nenhuma interação (lista de espera, amostras por e-mail, abandonos).
    Não toca em `pedidos` (compra: prazo legal, em geral 5 anos) nem em
    `email_optout` (é o que garante que a pessoa não recebe mais nada).
    Devolve quantas linhas saíram de cada tabela; None sem banco ou com erro."""
    if not ativo():
        return None
    try:
        apagadas = {}
        with _conectar() as c, c.transaction():
            for tabela in TABELAS_MARKETING:
                cur = c.execute(_ULTIMA_INTERACAO + f"DELETE FROM {tabela} t USING apagar a "
                                f"WHERE lower(t.email) = a.email", {"meses": MESES_SEM_INTERACAO})
                apagadas[tabela] = cur.rowcount
        return apagadas
    except Exception:  # noqa: BLE001
        log.exception("banco: falha na limpeza de marketing")
        return None


# ---------------------------------------------------------------- sequências (rodada 6)
_MESMO_DIA = ("NOT e.pulado AND (e.enviado_em AT TIME ZONE 'America/Sao_Paulo')::date = "
              "(now() AT TIME ZONE 'America/Sao_Paulo')::date")


def candidatos_boas_vindas(limite: int = 200) -> list[dict]:
    """A amostra mais recente de cada e-mail que marcou a caixa (ocidental), dos
    últimos 30 dias, sem compra depois dela e sem descadastro — com quantos passos
    da boas-vindas já saíram e se o e-mail já recebeu algo hoje."""
    if not ativo():
        return []
    try:
        with _conectar() as c:
            rows = c.execute(
                f"""
                SELECT * FROM (
                    SELECT DISTINCT ON (lower(a.email)) a.id, lower(a.email), a.produto, a.dados, a.sistema, a.criado_em
                    FROM amostras_email a
                    WHERE a.aceita_sequencia AND a.sistema = 'ocidental'
                      AND a.criado_em > now() - interval '30 days'
                    ORDER BY lower(a.email), a.criado_em DESC
                ) u
                WHERE NOT EXISTS (SELECT 1 FROM email_optout o WHERE o.email = u.lower)
                  AND NOT EXISTS (SELECT 1 FROM pedidos p WHERE lower(p.email) = u.lower AND p.criado_em > u.criado_em)
                LIMIT %s
                """, (limite,)).fetchall()
            saida = []
            for r in rows:
                feitos, hoje = c.execute(
                    f"SELECT coalesce(max(passo) FILTER (WHERE sequencia = 'boas_vindas'), 0), "
                    f"coalesce(bool_or({_MESMO_DIA}), false) FROM envios_sequencia e WHERE lower(e.email) = %s",
                    (r[1],)).fetchone()
                saida.append({"id": r[0], "email": r[1], "produto": r[2], "dados": r[3], "sistema": r[4],
                              "criado_em": r[5], "feitos": int(feitos), "recebeu_hoje": bool(hoje)})
        return saida
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao buscar a boas-vindas")
        return []


def candidatos_pos_compra(limite: int = 200) -> list[dict]:
    """A compra mais recente (ocidental, entregue) de cada e-mail nos últimos 30
    dias, sem descadastro — com o que o e-mail já comprou, quantos passos do
    pós-compra já saíram e se recebeu algo hoje."""
    if not ativo():
        return []
    try:
        with _conectar() as c:
            rows = c.execute(
                """
                SELECT * FROM (
                    SELECT DISTINCT ON (lower(p.email)) p.id, lower(p.email), p.produto, p.criado_em, p.nome
                    FROM pedidos p
                    WHERE p.produto LIKE 'ocidental:%%' AND coalesce(p.link, '') <> '' AND p.email IS NOT NULL
                      AND p.criado_em > now() - interval '30 days'
                    ORDER BY lower(p.email), p.criado_em DESC
                ) u
                WHERE NOT EXISTS (SELECT 1 FROM email_optout o WHERE o.email = u.lower)
                LIMIT %s
                """, (limite,)).fetchall()
            saida = []
            for r in rows:
                feitos, hoje = c.execute(
                    f"SELECT coalesce(max(passo) FILTER (WHERE sequencia = 'pos_compra'), 0), "
                    f"coalesce(bool_or({_MESMO_DIA}), false) FROM envios_sequencia e WHERE lower(e.email) = %s",
                    (r[1],)).fetchone()
                comprados = [x[0] for x in c.execute(
                    "SELECT DISTINCT produto FROM pedidos WHERE lower(email) = %s", (r[1],)).fetchall()]
                saida.append({"id": r[0], "email": r[1], "produto": r[2], "criado_em": r[3], "nome": r[4],
                              "comprados": comprados, "feitos": int(feitos), "recebeu_hoje": bool(hoje)})
        return saida
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao buscar o pós-compra")
        return []


def reservar_passo(email: str, sequencia: str, passo: int, referencia: int | None, pulado: bool = False,
                   sistema: str = "ocidental") -> int | None:
    """Grava o passo ANTES de enviar. Devolve o id da reserva, ou None se o passo
    já existia (nunca o mesmo passo duas vezes) ou se o banco falhou."""
    if not ativo():
        return None
    try:
        with _conectar() as c:
            row = c.execute(
                "INSERT INTO envios_sequencia (email, sequencia, passo, sistema, referencia, pulado) "
                "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING id",
                (email.strip().lower(), sequencia, passo, sistema, referencia, pulado)).fetchone()
        return row[0] if row else None
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao reservar passo de sequência")
        return None


def desfazer_reserva(id_reserva: int) -> None:
    """O envio falhou: libera o passo para tentar de novo amanhã."""
    if not ativo():
        return
    try:
        with _conectar() as c:
            c.execute("DELETE FROM envios_sequencia WHERE id = %s", (id_reserva,))
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao desfazer reserva de sequência")


def leituras_do_email(email: str) -> list[dict]:
    """As leituras compradas por um e-mail, com o link já entregue (rodada 6,
    "recuperar minhas leituras"). Só pedidos com link: os pendentes de entrega
    manual não entram. Do mais antigo ao mais novo."""
    if not ativo():
        return []
    try:
        with _conectar() as c:
            rows = c.execute("SELECT produto, criado_em, link FROM pedidos "
                             "WHERE lower(email) = lower(%s) AND coalesce(link, '') <> '' "
                             "ORDER BY criado_em", (email,)).fetchall()
        return [{"produto": r[0], "criado_em": r[1], "link": r[2]} for r in rows]
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao buscar as leituras de um e-mail")
        return []

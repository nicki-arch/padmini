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
  - pedidos_pendentes (rodada 11, Stripe): o pedido antes do pagamento, com os dados
    de cada leitura. Não pago sai em 7 dias. Nenhum dado de cartão passa por aqui
    (o cartão é digitado no checkout da Stripe, dentro do iframe dela).
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

-- Rodada 11: checkout próprio (Stripe). O pedido nasce aqui ANTES do pagamento, com
-- os dados de cada leitura; a Stripe recebe só o `id` opaco (metadata e
-- client_reference_id) e o e-mail. `itens` = [{chave, dados, valor_centavos}], com a
-- chave do catálogo e o preço CALCULADO no servidor (pendentes.py), nunca o do
-- navegador. Não pago (aberto, expirado, falhou) é apagado depois de 7 dias
-- (db.limpar_pendentes, na tarefa diária de limpeza).
CREATE TABLE IF NOT EXISTS pedidos_pendentes (
    id                TEXT PRIMARY KEY,
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    sistema           TEXT NOT NULL DEFAULT 'ocidental',
    itens             JSONB NOT NULL,
    email             TEXT NOT NULL,
    nome              TEXT,
    consentimentos    JSONB NOT NULL DEFAULT '{}'::jsonb,
    rastreio          JSONB NOT NULL DEFAULT '{}'::jsonb,
    cupom             TEXT,
    valor_centavos    INTEGER NOT NULL CHECK (valor_centavos > 0),
    moeda             TEXT NOT NULL DEFAULT 'brl',
    stripe_session_id TEXT UNIQUE,
    estado            TEXT NOT NULL DEFAULT 'aberto'
                      CHECK (estado IN ('aberto', 'pago', 'expirado', 'falhou'))
);
CREATE INDEX IF NOT EXISTS pedidos_pendentes_limpeza_idx ON pedidos_pendentes (estado, criado_em);
-- O client_secret da Checkout Session: é o que monta o checkout na página /checkout/{id}
-- (inclusive se a pessoa recarregar). Só serve para pagar aquela sessão.
ALTER TABLE pedidos_pendentes ADD COLUMN IF NOT EXISTS stripe_client_secret TEXT;
ALTER TABLE pedidos_pendentes ENABLE ROW LEVEL SECURITY;

-- Rodada 11: de onde veio o pagamento. Linhas antigas (e toda compra da Cakto) ficam
-- 'cakto'. Na Stripe, `stripe_id` é a Checkout Session (cs_…, idempotência da entrega) e
-- `stripe_pagamento` o PaymentIntent (pi_…), que liga reembolso e contestação ao pedido.
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS origem_pagamento TEXT NOT NULL DEFAULT 'cakto';
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS stripe_id TEXT;
ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS stripe_pagamento TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS pedidos_stripe_id_idx ON pedidos (stripe_id);
CREATE INDEX IF NOT EXISTS pedidos_stripe_pagamento_idx ON pedidos (stripe_pagamento);

-- Eventos do webhook da Stripe já recebidos (a Stripe pode mandar o mesmo evento mais de
-- uma vez: docs.stripe.com/webhooks#handle-duplicate-events). Só o id e o tipo.
CREATE TABLE IF NOT EXISTS eventos_stripe (
    id          TEXT PRIMARY KEY,
    tipo        TEXT NOT NULL,
    recebido_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE eventos_stripe ENABLE ROW LEVEL SECURITY;

-- Rodada 15: o estado do site decidido no /painel (modo, venda, estado de cada produto,
-- páginas escondidas). Uma linha por chave; sem linha, vale o padrão do YAML / da
-- variável (estado_site.py). Cada serviço (produção, prévia) tem o próprio banco, então
-- os estados são independentes. O histórico guarda toda mudança: o quê, de quê para quê,
-- quando e quem (o nome digitado no painel, nunca dado de cliente).
CREATE TABLE IF NOT EXISTS config_site (
    chave        TEXT PRIMARY KEY,
    valor        JSONB NOT NULL,
    alterado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    alterado_por TEXT
);
CREATE TABLE IF NOT EXISTS config_site_historico (
    id           BIGSERIAL PRIMARY KEY,
    alterado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    chave        TEXT NOT NULL,
    de           JSONB,
    para         JSONB,
    alterado_por TEXT
);
CREATE INDEX IF NOT EXISTS config_site_historico_idx ON config_site_historico (alterado_em DESC);
ALTER TABLE config_site ENABLE ROW LEVEL SECURITY;
ALTER TABLE config_site_historico ENABLE ROW LEVEL SECURITY;

-- Defesa em profundidade (só existe no Supabase): tira das roles da API
-- pública qualquer permissão nas tabelas, além do RLS.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE pedidos, textos_ia, leads, live_geracoes,
            amostras_email, abandonos, email_optout, pedidos_pendentes, eventos_stripe,
            config_site, config_site_historico FROM anon;
        REVOKE ALL ON SEQUENCE pedidos_id_seq, leads_id_seq, live_geracoes_id_seq,
            amostras_email_id_seq, abandonos_id_seq FROM anon;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE pedidos, textos_ia, leads, live_geracoes,
            amostras_email, abandonos, email_optout, pedidos_pendentes, eventos_stripe,
            config_site, config_site_historico FROM authenticated;
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
                    -- vários "me avise" do mesmo e-mail somam os interesses ("mapa,tarot")
                    interesse = CASE
                        WHEN leads.interesse IS NULL THEN EXCLUDED.interesse
                        WHEN EXCLUDED.interesse IS NULL
                             OR ',' || leads.interesse || ',' LIKE '%%,' || EXCLUDED.interesse || ',%%'
                            THEN leads.interesse
                        ELSE leads.interesse || ',' || EXCLUDED.interesse END,
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


def candidatos_aniversario(mes_dia: list[str], limite: int = 500, ja_tem: list[str] | None = None) -> list[dict]:
    """E-mail de aniversário de "O seu ano" (rodada 13): a amostra mais recente (ocidental, com
    a data de nascimento: mapa ou previsão) de cada e-mail que MARCOU a caixa de marketing,
    dos últimos 24 meses (a retenção de marketing), sem descadastro, cujo aniversário cai em
    um dos `mes_dia` ("MM-DD"). Sem a caixa marcada, nunca.
    Rodada 20: fora quem comprou, nos últimos 12 meses, um dos produtos de `ja_tem` (os
    rótulos de `pedidos.produto`: "O seu ano" e o kit que o inclui): o ano dele está coberto."""
    if not ativo() or not mes_dia:
        return []
    ja_tem = list(ja_tem or [])
    try:
        with _conectar() as c:
            rows = c.execute(
                """
                SELECT * FROM (
                    SELECT DISTINCT ON (lower(a.email)) a.id, lower(a.email), a.produto, a.dados
                    FROM amostras_email a
                    WHERE a.aceita_sequencia AND a.sistema = 'ocidental' AND a.produto IN ('mapa', 'previsao')
                      AND a.criado_em > now() - interval '24 months'
                    ORDER BY lower(a.email), a.criado_em DESC
                ) u
                WHERE NOT EXISTS (SELECT 1 FROM email_optout o WHERE o.email = u.lower)
                  AND substr(u.dados->>'data', 6, 5) = ANY(%s)
                  AND NOT EXISTS (SELECT 1 FROM pedidos p WHERE lower(p.email) = u.lower
                                  AND p.produto = ANY(%s) AND p.criado_em > now() - interval '12 months')
                LIMIT %s
                """, (list(mes_dia), ja_tem, limite)).fetchall()
        return [{"id": r[0], "email": r[1], "produto": r[2], "dados": r[3]} for r in rows]
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao buscar os aniversários")
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


# ---------------------------------------------------------------- pedidos pendentes (rodada 11)
ESTADOS_PENDENTE = ("aberto", "pago", "expirado", "falhou")
DIAS_PENDENTE = 7
_COLUNAS_PENDENTE = ("id", "criado_em", "sistema", "itens", "email", "nome", "consentimentos",
                     "rastreio", "cupom", "valor_centavos", "moeda", "stripe_session_id",
                     "stripe_client_secret", "estado")


def criar_pendente(p: dict) -> bool:
    """Grava o pedido pendente montado por `pendentes.montar` (preço já calculado no
    servidor). False sem banco ou com erro: aí o checkout não abre (falha fechada)."""
    if not ativo():
        return False
    try:
        with _conectar() as c:
            c.execute(
                """
                INSERT INTO pedidos_pendentes (id, sistema, itens, email, nome, consentimentos,
                    rastreio, cupom, valor_centavos, moeda)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (p["id"], p["sistema"], json.dumps(p["itens"], ensure_ascii=False), p["email"],
                 p.get("nome") or None, json.dumps(p.get("consentimentos") or {}),
                 json.dumps(p.get("rastreio") or {}, ensure_ascii=False), p.get("cupom") or None,
                 int(p["valor_centavos"]), p.get("moeda") or "brl"),
            )
        return True
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao criar pedido pendente")
        return False


def _pendente_onde(coluna: str, valor: str) -> dict | None:
    if not (ativo() and valor):
        return None
    try:
        with _conectar() as c:
            row = c.execute(f"SELECT {', '.join(_COLUNAS_PENDENTE)} FROM pedidos_pendentes "
                            f"WHERE {coluna} = %s", (valor,)).fetchone()
        return dict(zip(_COLUNAS_PENDENTE, row)) if row else None
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao ler pedido pendente")
        return None


def pendente(id_pendente: str) -> dict | None:
    return _pendente_onde("id", id_pendente)


def pendente_da_sessao(stripe_session_id: str) -> dict | None:
    return _pendente_onde("stripe_session_id", stripe_session_id)


def ligar_sessao(id_pendente: str, stripe_session_id: str, client_secret: str | None = None) -> bool:
    """Guarda a Checkout Session criada para este pendente (uma vez só)."""
    if not ativo():
        return False
    try:
        with _conectar() as c:
            cur = c.execute("UPDATE pedidos_pendentes SET stripe_session_id = %s, stripe_client_secret = %s, "
                            "atualizado_em = now() WHERE id = %s AND stripe_session_id IS NULL",
                            (stripe_session_id, client_secret, id_pendente))
        return cur.rowcount == 1
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao ligar a sessão ao pedido pendente")
        return False


def marcar_pendente(id_pendente: str, estado: str) -> bool:
    """Muda o estado. `pago` é final: nada o tira de lá (um evento atrasado de
    expiração não desfaz uma compra). True se a linha mudou."""
    if estado not in ESTADOS_PENDENTE:
        raise ValueError(f"estado de pendente desconhecido: {estado!r}")
    if not ativo():
        return False
    try:
        with _conectar() as c:
            cur = c.execute("UPDATE pedidos_pendentes SET estado = %s, atualizado_em = now() "
                            "WHERE id = %s AND estado <> 'pago' AND estado <> %s",
                            (estado, id_pendente, estado))
        return cur.rowcount == 1
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao marcar pedido pendente")
        return False


def limpar_pendentes(dias: int = DIAS_PENDENTE) -> int | None:
    """Apaga os pedidos pendentes NÃO pagos com mais de `dias` dias (têm dados de
    nascimento e e-mail de quem não comprou). Os pagos ficam: a compra em si está em
    `pedidos`. Também esquece os ids de evento da Stripe com mais de 30 dias.
    Devolve quantos pendentes saíram; None sem banco ou com erro."""
    if not ativo():
        return None
    try:
        with _conectar() as c:
            cur = c.execute("DELETE FROM pedidos_pendentes WHERE estado <> 'pago' "
                            "AND criado_em < now() - make_interval(days => %s)", (int(dias),))
            # os ids de evento do webhook só servem enquanto a Stripe pode reenviar (3 dias)
            c.execute("DELETE FROM eventos_stripe WHERE recebido_em < now() - interval '30 days'")
        return cur.rowcount
    except Exception:  # noqa: BLE001
        log.exception("banco: falha na limpeza dos pedidos pendentes")
        return None


def desfazer_pago(id_pendente: str) -> None:
    """A entrega quebrou depois de marcar `pago` (exceção): volta para `aberto`, para o
    reenvio do webhook pela Stripe tentar de novo. Só o webhook usa."""
    if not ativo():
        return
    try:
        with _conectar() as c:
            c.execute("UPDATE pedidos_pendentes SET estado = 'aberto', atualizado_em = now() WHERE id = %s",
                      (id_pendente,))
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao desfazer o pago do pedido pendente")


# ---------------------------------------------------------------- webhook da Stripe (rodada 11)
def evento_stripe_novo(id_evento: str, tipo: str) -> bool:
    """Reserva o evento: True na primeira vez, False se já foi recebido (duplicado).
    Levanta erro se o banco falhar (o webhook responde 500 e a Stripe reenvia)."""
    with _conectar() as c:
        cur = c.execute("INSERT INTO eventos_stripe (id, tipo) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
                        (id_evento, tipo))
        return cur.rowcount == 1


def esquecer_evento_stripe(id_evento: str) -> None:
    """O tratamento do evento quebrou: apaga a reserva para o reenvio ser tratado."""
    try:
        with _conectar() as c:
            c.execute("DELETE FROM eventos_stripe WHERE id = %s", (id_evento,))
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao esquecer o evento da Stripe")


def pedido_stripe_entregue(stripe_id: str) -> str | None:
    """O link, se esta Checkout Session já foi entregue (e-mail enviado)."""
    if not (ativo() and stripe_id):
        return None
    try:
        with _conectar() as c:
            row = c.execute("SELECT link FROM pedidos WHERE stripe_id = %s AND email_enviado",
                            (stripe_id,)).fetchone()
        return row[0] if row else None
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao consultar pedido da Stripe")
        return None


def registrar_pedido_stripe(sessao: dict, pendente: dict, produto: str, dados: dict, link: str | None,
                            email_enviado: bool, evento: str, forma_pagamento: str | None) -> bool:
    """Grava (ou atualiza) a compra feita na Stripe em `pedidos`, como a da Cakto, com
    origem 'stripe'. Idempotente pela Checkout Session. Nada de dado de cartão: a sessão
    nem os traz."""
    if not ativo():
        return False
    item = pendente["itens"][0]
    try:
        with _conectar() as c:
            c.execute(
                """
                INSERT INTO pedidos (origem_pagamento, stripe_id, stripe_pagamento, evento, status, produto,
                    email, nome, dados_nascimento, valor, forma_pagamento, oferta_id, tipo_oferta, rastreio,
                    link, email_enviado, entregue_em)
                VALUES ('stripe',%s,%s,%s,'paid',%s,%s,%s,%s,%s,%s,%s,'main',%s,%s,%s, CASE WHEN %s THEN now() END)
                ON CONFLICT (stripe_id) DO UPDATE SET
                    link = EXCLUDED.link,
                    email_enviado = pedidos.email_enviado OR EXCLUDED.email_enviado,
                    entregue_em = COALESCE(pedidos.entregue_em, EXCLUDED.entregue_em)
                """,
                (sessao["id"], sessao.get("payment_intent"), evento, produto, pendente["email"],
                 pendente.get("nome") or dados.get("nome"), json.dumps(dados, ensure_ascii=False),
                 _num((sessao.get("amount_total") or 0) / 100), forma_pagamento, f"stripe:{item['chave']}",
                 json.dumps(pendente.get("rastreio") or {}, ensure_ascii=False), link, email_enviado, email_enviado),
            )
        return True
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao registrar pedido da Stripe %s", sessao.get("id"))
        return False


def marcar_pedido_stripe(stripe_pagamento: str, status: str) -> int:
    """Reembolso ou contestação: muda o `status` do pedido pelo PaymentIntent. Quantas
    linhas mudaram (0 = pedido não encontrado)."""
    if not (ativo() and stripe_pagamento):
        return 0
    try:
        with _conectar() as c:
            cur = c.execute("UPDATE pedidos SET status = %s WHERE stripe_pagamento = %s", (status, stripe_pagamento))
        return cur.rowcount
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao marcar pedido da Stripe")
        return 0


def compras_do_email(email: str) -> list[str]:
    """Os produtos que este e-mail já comprou e recebeu ("ocidental:kit", "mapa"…), para
    nenhum e-mail oferecer o que a pessoa já tem (rodada 20: o kit conta como os três,
    catalogo.que_tem). Sem banco ou com erro, [] (quem chama decide)."""
    if not (ativo() and email):
        return []
    try:
        with _conectar() as c:
            rows = c.execute("SELECT DISTINCT produto FROM pedidos WHERE lower(email) = lower(%s) "
                             "AND coalesce(link, '') <> ''", (email,)).fetchall()
        return [r[0] for r in rows]
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao buscar as compras de um e-mail")
        return []


def comprou_desde(email: str, quando) -> bool:
    """Este e-mail tem compra registrada desde `quando`? (Abandono da Stripe: a sessão
    expira 24 h depois de criada, e a pessoa pode ter comprado em outra no meio tempo.)
    Sem banco ou com erro, True (não arrisca mandar a recuperação para quem comprou)."""
    if not ativo():
        return True
    try:
        with _conectar() as c:
            row = c.execute("SELECT 1 FROM pedidos WHERE lower(email) = lower(%s) AND criado_em >= %s LIMIT 1",
                            (email, quando)).fetchone()
        return row is not None
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao consultar compra")
        return True


def produtos_dos_pagamentos_stripe() -> dict:
    """{PaymentIntent: produto} das compras da Stripe (relatório de vendas). Só ids e
    produto: nada de dado pessoal."""
    if not ativo():
        return {}
    with _conectar() as c:
        rows = c.execute("SELECT stripe_pagamento, produto FROM pedidos WHERE origem_pagamento = 'stripe' "
                         "AND stripe_pagamento IS NOT NULL").fetchall()
    return {pi: produto for pi, produto in rows}


# Relatório de origem (rodada 19, scripts/relatorio_origem.py): por utm_source, quantas
# amostras, "me avise" e pedidos pagos desde uma data. Só contagens: nem e-mail, nem nome.
SEM_ORIGEM = "(sem origem)"
_POR_ORIGEM = {
    "amostras": "SELECT COALESCE(NULLIF(origem->>'utm_source', ''), %s), count(*) FROM amostras_email "
                "WHERE criado_em >= %s GROUP BY 1",
    "me_avise": "SELECT COALESCE(NULLIF(origem->>'utm_source', ''), %s), count(*) FROM leads "
                "WHERE interesse IS NOT NULL AND atualizado_em >= %s GROUP BY 1",
    "pedidos_pagos": "SELECT COALESCE(NULLIF(rastreio->>'utm_source', ''), %s), count(*) FROM pedidos "
                     "WHERE status = 'paid' AND criado_em >= %s GROUP BY 1",
}


def contagem_por_origem(desde) -> dict:
    """{utm_source: {"amostras": n, "me_avise": n, "pedidos_pagos": n}} desde `desde`
    (date ou datetime). Sem banco, {}."""
    if not ativo():
        return {}
    saida: dict = {}
    with _conectar() as c:
        for coluna, sql in _POR_ORIGEM.items():
            for fonte, n in c.execute(sql, (SEM_ORIGEM, desde)).fetchall():
                saida.setdefault(fonte, dict.fromkeys(_POR_ORIGEM, 0))[coluna] = n
    return saida


# ---------------------------------------------------------------- estado do site (rodada 15, /painel)
# Exceção à regra de ouro, de propósito: `ler_config_site` LEVANTA o erro em vez de devolver
# vazio. Quem chama (estado_site.py) precisa distinguir "nada salvo" (vale o YAML) de "banco
# fora do ar" (vale o último estado conhecido); devolver {} na falha faria o site voltar
# para o YAML no meio de uma "lista de espera".
def ler_config_site() -> dict:
    """{chave: valor} do que o painel salvou. Sem banco configurado: {}. Falha: levanta."""
    if not ativo():
        return {}
    with _conectar() as c:
        return {k: v for k, v in c.execute("SELECT chave, valor FROM config_site").fetchall()}


def gravar_config_site(mudancas: dict, quem: str) -> list[tuple]:
    """Grava as mudanças (chave → valor) numa transação, com uma linha de histórico por
    chave que mudou de verdade. Devolve [(chave, de, para)] do que mudou. Levanta se falhar:
    o painel precisa dizer "não salvou", nunca "pronto"."""
    from psycopg.types.json import Jsonb
    feitas = []
    with _conectar() as c, c.transaction():
        for chave, valor in mudancas.items():
            row = c.execute("SELECT valor FROM config_site WHERE chave = %s FOR UPDATE", (chave,)).fetchone()
            de = row[0] if row else None
            if row and de == valor:
                continue
            c.execute("INSERT INTO config_site (chave, valor, alterado_em, alterado_por) VALUES (%s, %s, now(), %s) "
                      "ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor, alterado_em = now(), "
                      "alterado_por = EXCLUDED.alterado_por", (chave, Jsonb(valor), quem))
            c.execute("INSERT INTO config_site_historico (chave, de, para, alterado_por) VALUES (%s, %s, %s, %s)",
                      (chave, Jsonb(de) if row else None, Jsonb(valor), quem))
            feitas.append((chave, de, valor))
    return feitas


def historico_config_site(limite: int = 20) -> list[dict]:
    """As últimas mudanças do painel, da mais nova para a mais velha. Falha: []."""
    if not ativo():
        return []
    try:
        with _conectar() as c:
            rows = c.execute("SELECT alterado_em, chave, de, para, alterado_por FROM config_site_historico "
                             "ORDER BY alterado_em DESC, id DESC LIMIT %s", (limite,)).fetchall()
        return [{"quando": r[0], "chave": r[1], "de": r[2], "para": r[3], "quem": r[4]} for r in rows]
    except Exception:  # noqa: BLE001
        log.exception("banco: falha ao ler o histórico do painel")
        return []

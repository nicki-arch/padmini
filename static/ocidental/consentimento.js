/* ==========================================================================
   Padmini (ocidental) — consentimento de cookies e pixels de anúncio (rodada 6).

   LGPD / guia de cookies da ANPD:
   - Nada de marketing nem de métricas carrega antes do "Aceitar": Meta Pixel,
     TikTok Pixel, tag do Google (Ads/GA4) e o PostHog (analytics.js espera o
     evento "pad:consentimento" nas páginas com <meta name="pad-consentimento">).
   - "Aceitar" e "Recusar" com o mesmo destaque, sem caixa pré-marcada, com link
     para a política. A escolha vale 12 meses; "Preferências de cookies", no
     rodapé, reabre o aviso. Recusou = o site funciona igual, sem nenhum deles.
   - IDs vêm de /api/config (variáveis de ambiente). Vazio = não carrega; sem
     nenhum configurado, nem o aviso aparece (a página fica como antes).

   Eventos (nomes padrão de cada plataforma): PageView; ViewContent ao abrir a
   página de um produto; Lead quando a amostra é enviada (Meta "Lead", TikTok
   "SubmitForm", GA4 "generate_lead"), com event_id único. Checkout e compra NÃO
   saem daqui: são os pixels configurados no painel da Cakto (não contar em dobro).

   Nenhum dado pessoal vai para os pixels: só o nome do produto. Sem "advanced
   matching", sem configuração automática do Meta (que leria botões e campos) e,
   em página com dado pessoal na URL (link de entrega: data, hora, cidade, nome,
   token…), os pixels nem carregam.
   ========================================================================== */
(function () {
  var CHAVE = "pad_consentimento";
  var VALIDADE_MS = 365 * 24 * 60 * 60 * 1000;  // 12 meses
  var URL_SENSIVEL = /[?&](token|sck|data|hora|lat|lon|nome|cidade|email|previa|[ab]_[a-z]+)=/i;
  var PRODUTOS = { "/mapa": "mapa", "/compatibilidade": "sinastria", "/numerologia": "numerologia", "/tarot": "tarot" };

  function escolhaGuardada() {
    try {
      var v = JSON.parse(localStorage.getItem(CHAVE) || "null");
      if (v && (v.escolha === "aceito" || v.escolha === "recusado") && Date.now() - v.em < VALIDADE_MS) return v.escolha;
    } catch (e) {}
    return null;
  }
  function guardar(escolha) {
    try { localStorage.setItem(CHAVE, JSON.stringify({ escolha: escolha, em: Date.now(), v: 1 })); } catch (e) {}
  }
  function avisar(escolha) {
    try { window.dispatchEvent(new CustomEvent("pad:consentimento", { detail: escolha })); } catch (e) {}
  }

  // ------------------------------------------------------------------ pixels
  var cfg = null, carregados = false, fila = [];
  function novoId() {
    try { if (window.crypto && crypto.randomUUID) return crypto.randomUUID(); } catch (e) {}
    return Date.now().toString(36) + Math.random().toString(36).slice(2);
  }
  function script(src) {
    var s = document.createElement("script"); s.async = true; s.src = src;
    document.head.appendChild(s);
  }
  function carregarMeta(id) {
    // snippet oficial do Meta Pixel (developers.facebook.com/docs/meta-pixel)
    !function (f, b, e, v, n, t, s) { if (f.fbq) return; n = f.fbq = function () { n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments) }; if (!f._fbq) f._fbq = n; n.push = n; n.loaded = !0; n.version = "2.0"; n.queue = []; t = b.createElement(e); t.async = !0; t.src = v; s = b.getElementsByTagName(e)[0]; s.parentNode.insertBefore(t, s) }(window, document, "script", "https://connect.facebook.net/en_US/fbevents.js");
    window.fbq("set", "autoConfig", false, id);  // não ler botões nem campos da página
    window.fbq("init", id);                      // sem dados do usuário (sem advanced matching)
    window.fbq("track", "PageView");
  }
  function carregarTikTok(id) {
    // snippet oficial do TikTok Pixel (ads.tiktok.com/help, "set up the pixel")
    !function (w, d, t) { w.TiktokAnalyticsObject = t; var ttq = w[t] = w[t] || []; ttq.methods = ["page", "track", "identify", "instances", "debug", "on", "off", "once", "ready", "alias", "group", "enableCookie", "disableCookie", "holdConsent", "revokeConsent", "grantConsent"]; ttq.setAndDefer = function (t, e) { t[e] = function () { t.push([e].concat(Array.prototype.slice.call(arguments, 0))) } }; for (var i = 0; i < ttq.methods.length; i++) ttq.setAndDefer(ttq, ttq.methods[i]); ttq.instance = function (t) { for (var e = ttq._i[t] || [], n = 0; n < ttq.methods.length; n++) ttq.setAndDefer(e, ttq.methods[n]); return e }; ttq.load = function (e, n) { var r = "https://analytics.tiktok.com/i18n/pixel/events.js"; ttq._i = ttq._i || {}, ttq._i[e] = [], ttq._i[e]._u = r, ttq._t = ttq._t || {}, ttq._t[e] = +new Date, ttq._o = ttq._o || {}, ttq._o[e] = n || {}; var o = d.createElement("script"); o.type = "text/javascript", o.async = !0, o.src = r + "?sdkid=" + e + "&lib=" + t; var a = d.getElementsByTagName("script")[0]; a.parentNode.insertBefore(o, a) } }(window, document, "ttq");
    window.ttq.load(id);
    window.ttq.page();
  }
  function carregarGoogle(ids) {
    // tag do Google (gtag.js): GA4 (G-…) e Google Ads (AW-…) no mesmo carregamento
    script("https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(ids[0]));
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag("js", new Date());
    ids.forEach(function (id) { window.gtag("config", id); });
  }

  function lista(v) { return String(v || "").split(",").map(function (x) { return x.trim(); }).filter(Boolean); }
  function algumPixel(c) { return !!(c && (c.meta_pixel || c.tiktok_pixel || lista(c.google_tag).length)); }

  function carregar() {
    if (carregados || !cfg || URL_SENSIVEL.test(location.search)) return;
    carregados = true;
    if (cfg.meta_pixel) carregarMeta(cfg.meta_pixel);
    if (cfg.tiktok_pixel) carregarTikTok(cfg.tiktok_pixel);
    var g = lista(cfg.google_tag);
    if (g.length) carregarGoogle(g);
    var produto = PRODUTOS[location.pathname];
    if (produto) evento("ViewContent", produto);
    fila.splice(0).forEach(function (e) { evento(e[0], e[1]); });
  }

  // evento padrão em cada plataforma ligada; só o nome do produto, nada pessoal
  function evento(tipo, produto) {
    if (!carregados) { fila.push([tipo, produto]); return; }
    var id = novoId(), props = { content_name: produto, content_category: "leitura" };
    try {
      if (window.fbq) window.fbq("track", tipo, props, { eventID: id });
      if (window.ttq) window.ttq.track(tipo === "Lead" ? "SubmitForm" : tipo, props, { event_id: id });
      if (window.gtag) {
        if (tipo === "Lead") {
          window.gtag("event", "generate_lead", { item_category: produto, transaction_id: id });
          if (cfg.google_ads_lead) window.gtag("event", "conversion", { send_to: cfg.google_ads_lead, transaction_id: id });
        } else if (tipo === "ViewContent") {
          window.gtag("event", "view_item", { item_category: produto });
        }
      }
    } catch (e) {}
  }
  window.padPixel = function (tipo, produto) {
    if (escolhaGuardada() === "aceito") evento(tipo, produto);
  };

  // A amostra enviada vira "Lead": as páginas já avisam o analytics.js com
  // padTrack("amostra_gerada", {produto}); aqui só se escuta (sem mexer nelas).
  function ouvirAmostras() {
    var original = window.padTrack;
    if (typeof original !== "function" || original.__pixel) return;
    var embrulho = function (nome, props) {
      if (nome === "amostra_gerada") window.padPixel("Lead", (props && props.produto) === "compat" ? "sinastria" : (props && props.produto) || "");
      return original.apply(this, arguments);
    };
    embrulho.__pixel = true;
    window.padTrack = embrulho;
  }

  // ------------------------------------------------------------------ aviso
  function apagarCookies() {
    // o que os pixels e o PostHog gravam no nosso domínio
    document.cookie.split(";").forEach(function (c) {
      var nome = c.split("=")[0].trim();
      if (/^(_fbp|_fbc|_ttp|_ga|_gcl_|ph_|_tt_)/.test(nome)) {
        [location.hostname, "." + location.hostname.replace(/^www\./, "")].forEach(function (d) {
          document.cookie = nome + "=; Max-Age=0; path=/; domain=" + d;
        });
        document.cookie = nome + "=; Max-Age=0; path=/";
      }
    });
  }

  // O visual é o do pacote de design da Valderez (.cookie, em /static/valderez/casca.css):
  // "Aceitar" e "Recusar" com o mesmo tamanho e o mesmo destaque. O bloco herda
  // o tema da página (claro nas páginas novas; escuro nas que ainda usam o base.css).
  function tema() {
    var t = document.documentElement.getAttribute("data-theme") || (document.body && document.body.getAttribute("data-theme"));
    return t === "light" ? "light" : "dark";
  }

  function fecharAviso() { var el = document.getElementById("aviso-cookies"); if (el) el.remove(); }
  function mostrarAviso() {
    if (document.getElementById("aviso-cookies")) return;
    var el = document.createElement("aside");
    el.id = "aviso-cookies"; el.className = "cookie"; el.setAttribute("role", "dialog");
    el.setAttribute("data-theme", tema());
    el.setAttribute("aria-labelledby", "aviso-cookies-titulo"); el.setAttribute("aria-live", "polite");
    el.innerHTML =
      '<h2 id="aviso-cookies-titulo">Cookies</h2>' +
      '<p>Com a sua permissão, usamos cookies para medir as visitas e o resultado dos nossos ' +
      'anúncios (Meta, TikTok e Google). Sem ela, nada disso é ativado e o site funciona igual. ' +
      '<a href="/privacidade#cookies">Saiba mais</a>.</p>' +
      '<div class="cookie-actions">' +
      '<button type="button" class="button" data-cookies="aceito">Aceitar</button>' +
      '<button type="button" class="button" data-cookies="recusado">Recusar</button></div>';
    el.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-cookies]");
      if (!b) return;
      var escolha = b.getAttribute("data-cookies"), antes = escolhaGuardada();
      guardar(escolha); fecharAviso(); avisar(escolha);
      if (escolha === "aceito") carregar();
      else if (antes === "aceito" || carregados) { apagarCookies(); location.reload(); }  // tira o que já rodou
    });
    document.body.appendChild(el);
  }

  function linkNoRodape() {
    // O rodapé da Valderez (_rodape.html) já traz o link, escondido até haver o
    // que consentir; em página sem ele, o link é criado no fim do rodapé.
    var a = document.getElementById("preferencias-cookies");
    if (a && a.getAttribute("data-ligado")) return;
    if (!a) {
      var rodape = document.querySelector("footer nav") || document.querySelector("footer");
      if (!rodape) return;
      a = document.createElement("a");
      a.href = "#"; a.id = "preferencias-cookies"; a.textContent = "Preferências de cookies";
      rodape.appendChild(a);
    }
    a.hidden = false; a.setAttribute("data-ligado", "1");
    a.addEventListener("click", function (ev) { ev.preventDefault(); mostrarAviso(); });
  }

  window.padConsentimento = { escolha: escolhaGuardada, mostrar: mostrarAviso };

  function iniciar(c) {
    cfg = c || {};
    // sem nenhum pixel nem métrica configurados, não há o que consentir
    if (!algumPixel(cfg) && !cfg.posthog_key) return;
    linkNoRodape();
    ouvirAmostras();
    var e = escolhaGuardada();
    if (e === "aceito") { avisar("aceito"); carregar(); }
    else if (e === null) mostrarAviso();
  }

  var aoCarregar = function () {
    fetch("/api/config").then(function (r) { return r.json(); }).then(iniciar).catch(function () {});
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", aoCarregar);
  else aoCarregar();
})();

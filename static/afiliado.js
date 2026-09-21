/* ==========================================================================
   Padmini — atribuição de afiliado / campanha (compartilhado).
   Captura ?ref (e cupom + utm_*) na chegada, guarda na sessão e repassa ao
   link do checkout. Same-origin: o sessionStorage sobrevive à navegação entre
   as páginas do site, então basta capturar uma vez ao entrar.

   IMPORTANTE: ajustar PARAM_AFILIADO para o nome de parâmetro que a Cakto usa
   no checkout (ex.: "ref", "afiliado", "aff"). Confirmar na conta da Cakto.
   ========================================================================== */
(function () {
  var PARAM_AFILIADO = "ref"; // <-- ajustar quando tivermos o checkout da Cakto
  var CHAVES = [PARAM_AFILIADO, "cupom", "coupon",
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"];

  // captura da URL atual e guarda (não sobrescreve com valor vazio)
  try {
    var p = new URLSearchParams(location.search);
    CHAVES.forEach(function (k) {
      var v = p.get(k);
      if (v) { try { sessionStorage.setItem("pad_" + k, v); } catch (e) {} }
    });
  } catch (e) {}

  // { ref: "PEDRO", utm_source: "tiktok", ... } — para o checkout e o PostHog
  window.padAtribuicao = function () {
    var o = {};
    try {
      CHAVES.forEach(function (k) {
        var v = sessionStorage.getItem("pad_" + k);
        if (v) o[k] = v;
      });
    } catch (e) {}
    return o;
  };

  // anexa a atribuição a uma URL de checkout (só se houver algo guardado)
  window.linkComAfiliado = function (base) {
    if (!base) return base;
    var attr = window.padAtribuicao();
    var keys = Object.keys(attr);
    if (!keys.length) return base;
    try {
      var u = new URL(base, location.origin);
      keys.forEach(function (k) { u.searchParams.set(k, attr[k]); });
      return u.toString();
    } catch (e) {
      var qs = keys.map(function (k) {
        return encodeURIComponent(k) + "=" + encodeURIComponent(attr[k]);
      }).join("&");
      return base + (base.indexOf("?") >= 0 ? "&" : "?") + qs;
    }
  };

  // Empacota os dados de nascimento numa string compacta para o campo `sck`.
  //
  // POR QUE `sck`: a Cakto só repassa ao webhook os campos utm_source,
  // utm_medium, utm_campaign, utm_term, utm_content e sck — não existe campo
  // livre de metadata. Qualquer parâmetro customizado na URL do checkout é
  // descartado. O `sck` é o campo de rastreamento livre, então é por ele que
  // os dados viajam. (docs.cakto.com.br/conceitos/webhooks)
  //
  // Formato (separado por "~", campos na ordem):
  //   mapa:   m~data~hora~lat~lon~nome~cidade
  //   casal:  c~dataA~horaA~latA~lonA~nomeA~cidadeA~dataB~...~cidadeB
  // Nome e cidade são cosméticos (o cálculo usa data/hora/lat/lon) e vão
  // truncados para manter a URL curta.
  function _t(v, n) {
    return String(v == null ? "" : v).replace(/~/g, "-").slice(0, n || 24);
  }
  function _pessoa(p) {
    p = p || {};
    return [_t(p.data, 10), _t(p.hora, 5), _t(p.lat, 12), _t(p.lon, 12),
            _t(p.nome, 20), _t(p.cidade, 24)].join("~");
  }
  window.padEmpacotar = function (dados) {
    if (!dados) return "";
    if (dados.produto === "mapa") return "m~" + _pessoa(dados);
    if (dados.produto === "compat") return "c~" + _pessoa(dados.a) + "~" + _pessoa(dados.b);
    return "";
  };

  // monta o link do checkout carregando os dados de nascimento (no `sck`) +
  // a atribuição de afiliado/campanha, para a Cakto repassá-los ao webhook.
  window.linkCheckout = function (base, dados) {
    if (!base) return base;
    var extra = {};
    var pacote = window.padEmpacotar(dados);
    if (pacote) extra.sck = pacote;
    var attr = window.padAtribuicao ? window.padAtribuicao() : {};
    var todos = Object.assign({}, attr, extra);
    var keys = Object.keys(todos);
    if (!keys.length) return base;
    try {
      var u = new URL(base, location.origin);
      keys.forEach(function (k) { u.searchParams.set(k, todos[k]); });
      return u.toString();
    } catch (e) {
      var qs = keys.map(function (k) {
        return encodeURIComponent(k) + "=" + encodeURIComponent(todos[k]);
      }).join("&");
      return base + (base.indexOf("?") >= 0 ? "&" : "?") + qs;
    }
  };
})();

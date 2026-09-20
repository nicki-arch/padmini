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

  // monta o link do checkout carregando os dados de nascimento (pd_*) + afiliado,
  // para a Cakto repassá-los ao webhook e a gente gerar o completo depois.
  window.linkCheckout = function (base, dados) {
    if (!base) return base;
    var extra = {};
    if (dados && dados.produto === "mapa") {
      extra.pd_produto = "mapa";
      ["nome", "data", "hora", "lat", "lon", "cidade"].forEach(function (k) {
        if (dados[k] != null && dados[k] !== "") extra["pd_" + k] = dados[k];
      });
    } else if (dados && dados.produto === "compat") {
      extra.pd_produto = "compat";
      var a = dados.a || {}, b = dados.b || {};
      ["nome", "data", "hora", "lat", "lon", "cidade"].forEach(function (k) {
        if (a[k] != null && a[k] !== "") extra["pd_a_" + k] = a[k];
        if (b[k] != null && b[k] !== "") extra["pd_b_" + k] = b[k];
      });
    }
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

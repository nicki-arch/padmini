/* ==========================================================================
   Padmini — métricas de funil (PostHog), simples e opcional.

   - Só carrega o PostHog se /api/config devolver uma posthog_key (env
     PADMINI_POSTHOG_KEY). Em branco, o site funciona igual e nada é carregado.
   - window.padTrack(evento, props) pode ser chamado a qualquer momento: os
     eventos ficam numa fila até o PostHog estar pronto e então são enviados.
     Se as métricas estiverem desligadas, vira um no-op silencioso.
   - Toda a atribuição de afiliado/campanha (ref, utm_*) entra automaticamente
     em cada evento, para medir a conversão por origem (TikTok, afiliado, etc.).

   Funil: pageview (automático) → amostra_gerada → checkout_click → completo_aberto.
   ========================================================================== */
(function () {
  var fila = [];
  var pronto = false;
  var ligado = false;

  function atribuicao() {
    try { return window.padAtribuicao ? window.padAtribuicao() : {}; }
    catch (e) { return {}; }
  }

  // API pública: sempre disponível, mesmo antes de o PostHog carregar.
  window.padTrack = function (evento, props) {
    if (!evento) return;
    var dados = Object.assign({}, atribuicao(), props || {});
    if (pronto && ligado && window.posthog) {
      try { window.posthog.capture(evento, dados); } catch (e) {}
    } else if (!pronto) {
      fila.push([evento, dados]); // guarda até saber se está ligado
    }
  };

  function iniciar(key, host) {
    // Snippet oficial do PostHog (carrega a lib do CDN deles de forma assíncrona).
    !function (t, e) { var o, n, p, r; e.__SV || (window.posthog = e, e._i = [], e.init = function (i, s, a) { function g(t, e) { var o = e.split("."); 2 == o.length && (t = t[o[0]], e = o[1]), t[e] = function () { t.push([e].concat(Array.prototype.slice.call(arguments, 0))) } } (p = t.createElement("script")).type = "text/javascript", p.crossOrigin = "anonymous", p.async = !0, p.src = s.api_host.replace(".i.posthog.com", "-assets.i.posthog.com") + "/static/array.js", (r = t.getElementsByTagName("script")[0]).parentNode.insertBefore(p, r); var u = e; for (void 0 !== a ? u = e[a] = [] : a = "posthog", u.people = u.people || [], u.toString = function (t) { var e = "posthog"; return "posthog" !== a && (e += "." + a), t || (e += " (stub)"), e }, u.people.toString = function () { return u.toString(1) + ".people (stub)" }, o = "init capture register register_once register_for_session unregister unregister_for_session getFeatureFlag getFeatureFlagPayload isFeatureEnabled reloadFeatureFlags updateEarlyAccessFeatureEnrollment getEarlyAccessFeatures on onFeatureFlags onSessionId getSurveys getActiveMatchingSurveys renderSurvey canRenderSurvey identify setPersonProperties group resetGroups setPersonPropertiesForFlags resetPersonPropertiesForFlags setGroupPropertiesForFlags resetGroupPropertiesForFlags reset get_distinct_id getGroups get_session_id get_session_replay_url alias set_config startSessionRecording stopSessionRecording capturePageView opt_out_capturing opt_in_capturing toggle_session_recording register_once unregister_for_session get_property getSessionProperty createPersonProfile opt_in_capturing opt_out_capturing".split(" "), n = 0; n < o.length; n++) g(u, o[n]); e._i.push([i, s, a]) }, e.__SV = 1) }(document, window.posthog || []);
    try {
      window.posthog.init(key, {
        api_host: host || "https://us.i.posthog.com",
        capture_pageview: true,
        persistence: "localStorage+cookie",
      });
      ligado = true;
    } catch (e) { ligado = false; }
  }

  // Widget "isso fez sentido?" — injeta 3 botões num container e manda o
  // feedback como evento (funciona junto do funil no PostHog). Sem backend.
  window.padFeedback = function (container, produto) {
    var el = typeof container === "string" ? document.querySelector(container) : container;
    if (!el) return;
    el.innerHTML =
      '<p class="fb-pergunta">Isso fez sentido para você?</p>' +
      '<div class="fb-botoes">' +
      '<button type="button" class="btn btn-outline" data-fb="sim">Sim, me reconheci</button>' +
      '<button type="button" class="btn btn-outline" data-fb="mais_ou_menos">Mais ou menos</button>' +
      '<button type="button" class="btn btn-outline" data-fb="nao">Não bateu</button>' +
      "</div>";
    el.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-fb]");
      if (!b) return;
      window.padTrack("feedback", { produto: produto || "", resposta: b.getAttribute("data-fb") });
      el.innerHTML = '<p class="fb-pergunta">Obrigado pelo retorno 🙏</p>';
    });
  };

  fetch("/api/config").then(function (r) { return r.json(); }).then(function (c) {
    if (c && c.posthog_key) iniciar(c.posthog_key, c.posthog_host);
  }).catch(function () {}).finally(function () {
    pronto = true;
    if (ligado && window.posthog) {
      fila.forEach(function (ev) {
        try { window.posthog.capture(ev[0], ev[1]); } catch (e) {}
      });
    }
    fila = [];
  });
})();

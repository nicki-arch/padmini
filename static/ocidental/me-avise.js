/* "Me avise quando abrir" (rodada 9): qualquer <form data-me-avise="<produto>">
   da página, inclusive os que entram depois (a amostra do /mapa é desenhada por
   JavaScript). Manda para /api/lista com interesse = produto. O servidor valida
   tudo de novo (nome, e-mail, WhatsApp e a autorização); aqui é só para a pessoa
   não esperar a ida e volta. Foco no primeiro campo com erro. */
(function () {
  "use strict";
  function erro(form, msg, campo) {
    const el = form.querySelector(".form-erro");
    el.textContent = msg || ""; el.hidden = !msg;
    form.querySelectorAll("[aria-invalid]").forEach((x) => x.removeAttribute("aria-invalid"));
    if (campo) { campo.setAttribute("aria-invalid", "true"); campo.focus(); }
  }
  // máscara do WhatsApp: (51) 99999-9999
  document.addEventListener("input", (e) => {
    const zap = e.target;
    if (!zap.matches || !zap.matches("form[data-me-avise] input[name=whatsapp]")) return;
    const d = zap.value.replace(/\D/g, "").slice(0, 11);
    let f = d;
    if (d.length > 2) f = "(" + d.slice(0, 2) + ") " + d.slice(2);
    if (d.length > 7) f = "(" + d.slice(0, 2) + ") " + d.slice(2, d.length - 4) + "-" + d.slice(-4);
    zap.value = f;
  });
  document.addEventListener("submit", async (e) => {
    const form = e.target;
    if (!form.matches || !form.matches("form[data-me-avise]")) return;
    e.preventDefault();
    erro(form, "");
    const campo = (n) => form.querySelector("[name=" + n + "]");
    const nome = campo("nome").value.trim(), email = campo("email").value.trim();
    const zap = campo("whatsapp").value.replace(/\D/g, "");
    if (nome.length < 2) return erro(form, "Preencha o seu nome.", campo("nome"));
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return erro(form, "Confira o e-mail.", campo("email"));
    if (zap.length < 10 || zap.length > 13) return erro(form, "Preencha o seu WhatsApp com DDD.", campo("whatsapp"));
    if (!campo("aceita_email").checked) return erro(form, "Marque a autorização para receber o aviso por e-mail.", campo("aceita_email"));
    const botao = form.querySelector("button[type=submit]"), texto = botao.textContent;
    botao.disabled = true; botao.setAttribute("aria-busy", "true"); botao.textContent = "Enviando…";
    try {
      const corpo = { nome, email, whatsapp: zap, aceita_email: true, aceita_whatsapp: campo("aceita_whatsapp").checked,
                      interesse: form.dataset.meAvise, site: campo("site").value,
                      origem: window.padAtribuicao ? window.padAtribuicao() : {} };
      const r = await fetch("/api/lista", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "Não conseguimos salvar agora. Tente de novo.");
      const pronto = form.parentElement.querySelector(".me-avise-pronto");
      form.hidden = true; pronto.hidden = false; pronto.querySelector("h3").focus();
      if (window.padTrack) padTrack("me_avise", { produto: form.dataset.meAvise, sistema: "ocidental" });
    } catch (err) {
      erro(form, err.message);
    } finally {
      botao.disabled = false; botao.removeAttribute("aria-busy"); botao.textContent = texto;
    }
  });
  // preenche nome e e-mail que a pessoa já digitou na página (ex.: o formulário do mapa)
  window.padMeAvise = {
    preencher(raiz, dados) {
      (raiz || document).querySelectorAll("form[data-me-avise]").forEach((f) => {
        for (const [k, v] of Object.entries(dados || {})) { const c = f.querySelector("[name=" + k + "]"); if (c && v && !c.value) c.value = v; }
      });
    },
  };
})();

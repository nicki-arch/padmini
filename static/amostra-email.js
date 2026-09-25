/* ==========================================================================
   Padmini — "Receber esta amostra por e-mail" (mapa e compatibilidade).

   Quem gera a amostra e não compra na hora sumia para sempre. Este bloco
   pede o e-mail, manda a amostra (com o botão de compra já preenchido) e,
   SE a pessoa marcar, um único lembrete depois (ver marketing.py).

   Só aparece se o servidor disser que o envio está configurado
   (/api/config → amostra_email). Uso:
     padAmostraEmail(elementoOuSeletor, "mapa", () => ({ pessoa: {...} }))
     padAmostraEmail(elementoOuSeletor, "compat", () => ({ a: {...}, b: {...} }))
   ========================================================================== */
(function () {
  var disponivel = null; // null = ainda não sabe
  var espera = [];
  fetch("/api/config").then(function (r) { return r.json(); })
    .then(function (c) { disponivel = !!(c && c.amostra_email); })
    .catch(function () { disponivel = false; })
    .finally(function () { espera.forEach(function (f) { f(); }); espera = []; });

  function el(tag, attrs, texto) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (texto) e.textContent = texto;
    return e;
  }

  function montar(alvo, produto, pegarDados) {
    if (!disponivel || !alvo) return;
    alvo.innerHTML = "";
    alvo.hidden = false;
    var titulo = el("h3", {}, produto === "compat" ? "Receber a amostra de vocês por e-mail" : "Receber esta amostra por e-mail");
    var form = el("form", { novalidate: "" });
    var rotulo = el("label", { for: "amostra-email-campo", class: "nota" }, "Seu e-mail");
    var campo = el("input", { id: "amostra-email-campo", type: "email", autocomplete: "email",
                              inputmode: "email", maxlength: "160", required: "", placeholder: "voce@email.com" });
    var linhaCheck = el("label", { class: "nota", style: "display:flex;gap:10px;align-items:flex-start;margin:12px 0;cursor:pointer" });
    var check = el("input", { type: "checkbox", id: "amostra-email-lembrete",
                              style: "width:18px;height:18px;min-height:0;flex:0 0 auto;margin:2px 0 0;padding:0" });
    linhaCheck.appendChild(check);
    linhaCheck.appendChild(el("span", {}, "Pode me mandar um lembrete depois (um só, e dá para descadastrar)."));
    var botao = el("button", { type: "submit", class: "btn btn-outline" }, "Enviar para meu e-mail");
    var status = el("p", { class: "nota", role: "status", style: "margin-top:8px" });
    [rotulo, campo, linhaCheck, botao, status].forEach(function (x) { form.appendChild(x); });
    alvo.appendChild(titulo);
    alvo.appendChild(form);

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var email = (campo.value || "").trim();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { status.textContent = "Confira o e-mail."; campo.focus(); return; }
      var corpo = Object.assign({ email: email, produto: produto, aceita_lembrete: check.checked,
                                  origem: window.padAtribuicao ? window.padAtribuicao() : {} }, pegarDados());
      botao.disabled = true; status.textContent = "Enviando…";
      fetch("/api/amostra/email", { method: "POST", headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify(corpo) })
        .then(function (r) { return r.json().then(function (c) { return [r.ok, c]; }); })
        .then(function (res) {
          if (!res[0]) throw new Error(typeof res[1].detail === "string" ? res[1].detail : "Não deu certo. Tente de novo.");
          alvo.innerHTML = "";
          alvo.appendChild(el("p", { class: "fb-pergunta" }, "Enviado! Confira sua caixa de entrada (e o spam, por via das dúvidas)."));
          if (window.padTrack) window.padTrack("amostra_email", { produto: produto, lembrete: check.checked });
        })
        .catch(function (e) { status.textContent = e.message; botao.disabled = false; });
    });
  }

  window.padAmostraEmail = function (alvo, produto, pegarDados) {
    var no = typeof alvo === "string" ? document.querySelector(alvo) : alvo;
    if (disponivel === null) espera.push(function () { montar(no, produto, pegarDados); });
    else montar(no, produto, pegarDados);
  };
})();

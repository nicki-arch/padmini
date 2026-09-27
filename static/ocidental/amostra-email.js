// Padmini (ocidental) — e-mail antes da amostra (rodada 6). O campo e a caixa
// estão em ocidental/_campo_email.html; quem decide o que vai para a tela e o
// que vai por e-mail é o servidor (rotas_ocidental.entregar_amostra).
(function () {
  const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // { email, aceita_sequencia, origem } para juntar ao corpo do pedido — ou { erro }
  function ler() {
    const el = document.getElementById("email");
    const email = (el && el.value || "").trim();
    if (!EMAIL.test(email)) return { erro: "Deixe um e-mail válido: o resto da sua leitura chega nele." };
    const caixa = document.getElementById("aceita-sequencia");
    const attr = window.padAtribuicao ? window.padAtribuicao() : {};
    return { email, aceita_sequencia: !!(caixa && caixa.checked), origem: attr };
  }

  // o aviso no lugar do que foi para o e-mail (nada, se o e-mail não saiu: aí a tela já tem tudo)
  function aviso(d) {
    if (!d.email || !d.email.enviado) return "";
    return `<div class="card aviso-email" id="aviso-email">
      <p style="margin:0"><b>O resto da sua leitura chegou em ${esc(d.email.para)}.</b></p>
      <p class="nota" style="margin:6px 0 12px">Não chegou? Confira o spam e a aba Promoções — ou peça de novo.</p>
      <button type="button" class="btn btn-outline" id="reenviar-amostra">Reenviar o e-mail</button>
      <span class="nota" id="reenvio-status" aria-live="polite" style="margin-left:10px"></span>
    </div>`;
  }

  // `pedirDeNovo()` repete o mesmo pedido (conta no limite por e-mail e por IP)
  function ligar(pedirDeNovo) {
    const b = document.getElementById("reenviar-amostra");
    if (!b) return;
    b.addEventListener("click", async () => {
      const st = document.getElementById("reenvio-status");
      b.disabled = true; st.textContent = "Enviando…";
      try {
        const d = await pedirDeNovo();
        st.textContent = d.email && d.email.enviado ? "Reenviado." : "Não conseguimos reenviar agora. Tente mais tarde.";
      } catch (e) { st.textContent = e.message || "Não conseguimos reenviar agora."; }
      finally { setTimeout(() => { b.disabled = false; }, 4000); }
    });
  }

  window.padEmail = { ler, aviso, ligar };
})();

/* ==========================================================================
   Valderez Astrologia — o botão de compra do checkout próprio (rodada 11, Stripe).
   Só é carregado no modo de pagamento "stripe" (com a Cakto, o botão continua sendo o
   link do afiliado.js → linkCheckout).

   O botão leva `data-comprar="<produto>"`; a página define window.padCorpoCompra(produto)
   com os dados da leitura e o contato. Este arquivo manda isso para POST /api/checkout,
   que valida, grava o pedido e devolve /checkout/{id}. Preço NENHUM sai daqui: o servidor
   calcula do catálogo. Nenhum dado pessoal vai na URL (no lugar do `sck` da Cakto).
   A origem (ref, cupom, utm_*) vem da sessão (afiliado.js → padAtribuicao).
   ========================================================================== */
(function () {
  var ERRO = "Não conseguimos abrir o pagamento agora. Tente de novo em instantes.";

  window.padComprar = function (botao, corpo) {
    if (botao.getAttribute("aria-busy") === "true") return;
    var antes = botao.innerHTML;
    var aviso = botao.parentNode && botao.parentNode.querySelector(".comprar-erro");
    if (aviso) aviso.remove();
    botao.setAttribute("aria-busy", "true");
    botao.textContent = "Abrindo o pagamento…";
    var origem = window.padAtribuicao ? window.padAtribuicao() : {};
    fetch("/api/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({}, corpo, { origem: origem }))
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (c) {
        if (!r.ok || !c.url) throw new Error(typeof c.detail === "string" ? c.detail : ERRO);
        location.assign(c.url);
      });
    }).catch(function (e) {
      botao.innerHTML = antes;
      botao.removeAttribute("aria-busy");
      var p = document.createElement("p");
      p.className = "form-erro comprar-erro";
      p.setAttribute("role", "alert");
      p.textContent = (e && e.message && e.message !== "Failed to fetch") ? e.message : ERRO;
      botao.insertAdjacentElement("afterend", p);
    });
  };

  document.addEventListener("click", function (e) {
    var b = e.target && e.target.closest ? e.target.closest("[data-comprar]") : null;
    if (!b || !window.padCorpoCompra) return;
    e.preventDefault();
    var corpo = window.padCorpoCompra(b.getAttribute("data-comprar"));
    if (corpo) window.padComprar(b, corpo);
  });
})();

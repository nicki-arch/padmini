// Rodada 15: só carrega com a faixa "Modo teste" (navegador logado no /painel em "tudo
// liberado"; o público nunca recebe este script). Quando a amostra chega, a API manda junto
// o link do completo (com token de verdade, só neste modo): a faixa passa a mostrar
// "Abrir a leitura completa". Não muda nada na página em si.
(function () {
  const original = window.fetch;
  window.fetch = async function (...args) {
    const resposta = await original.apply(this, args);
    try {
      if (String(args[0] || "").startsWith("/api/ocidental/")) {
        resposta.clone().json().then((d) => {
          if (d && d.link_completo) {
            const link = document.getElementById("faixa-teste-link");
            link.href = d.link_completo;
            link.closest(".faixa-teste-completo").hidden = false;
          }
        }).catch(() => {});
      }
    } catch (e) { /* a faixa é enfeite: nunca atrapalha a página */ }
    return resposta;
  };
})();

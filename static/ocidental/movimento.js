// Padmini (ocidental) — movimento (round 5). Marca com .revelado o que entra na
// tela; o CSS (movimento.css) faz o resto. Sem suporte ou com "reduzir
// movimento" ligado, não faz nada e a página fica como está.
(function () {
  if (!("IntersectionObserver" in window)) return;
  if (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  document.documentElement.classList.add("mov");
  const obs = new IntersectionObserver((itens) => {
    itens.forEach((it) => { if (it.isIntersecting) { it.target.classList.add("revelado"); obs.unobserve(it.target); } });
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
  function observar(raiz) {
    (raiz || document).querySelectorAll("[data-revelar]:not(.revelado), .cardc:not(.revelado)").forEach((el) => obs.observe(el));
  }
  document.addEventListener("DOMContentLoaded", () => observar());
  // resultados montados depois (amostra, completo): o que entra no #resultado também anima
  document.addEventListener("DOMContentLoaded", () => {
    const res = document.getElementById("resultado");
    if (!res) return;
    new MutationObserver(() => {
      res.querySelectorAll(".rosa, .cardc").forEach((el) => {
        const alvo = el.closest("div") || el;
        if (!alvo.hasAttribute("data-revelar")) alvo.setAttribute("data-revelar", "");
      });
      observar(res);
    }).observe(res, { childList: true });
  });
})();

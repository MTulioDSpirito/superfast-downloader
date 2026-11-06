// content.js — injeta o botao "SFD" ao passar o mouse sobre links de download
(function () {
  if (window.__sfdInjected) return;
  window.__sfdInjected = true;

  const btn = document.createElement("a");
  btn.id = "sfd-fab";
  btn.textContent = "SFD";
  btn.title = "Baixar com SuperFast DM";
  btn.href = "#";
  btn.style.display = "none";
  document.documentElement.appendChild(btn);

  let hoverLink = null;

  function showFor(a) {
    const href = a.href || "";
    if (!/^https?:/i.test(href)) return;
    const r = a.getBoundingClientRect();
    btn.style.display = "block";
    btn.style.top = (r.top + r.height / 2 - 11) + window.scrollY + "px";
    btn.style.left = (r.right + 4) + "px";
    hoverLink = { url: a.href, referer: location.href };
    // nome sugerido
    const base = (a.textContent || "").trim().split(/[\\/]/).pop();
    if (base && base.length < 180 && /\.[a-z0-9]{1,8}$/i.test(base)) {
      hoverLink.filename = base;
    }
  }

  document.addEventListener("mouseover", (e) => {
    const a = e.target.closest && e.target.closest("a[href]");
    if (a) showFor(a);
  }, true);

  document.addEventListener("mouseout", (e) => {
    if (hoverLink && (!e.relatedTarget || e.relatedTarget !== btn)) {
      // esconde ao sair do link (mas mantém se foi pro botao)
      const toBtn = e.relatedTarget === btn;
      if (!toBtn) { btn.style.display = "none"; hoverLink = null; }
    }
  }, true);

  btn.addEventListener("click", (e) => {
    e.preventDefault();
    if (!hoverLink) return;
    const rt = (window.browser && browser.runtime) || (window.chrome && chrome.runtime);
    if (rt && rt.sendMessage) {
      rt.sendMessage({
        type: "sfd-download", url: hoverLink.url,
        filename: hoverLink.filename || undefined,
        referer: hoverLink.referer
      }, () => {
        btn.style.display = "none"; hoverLink = null;
      });
    }
  });
})();

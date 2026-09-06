(function () {
  const path = location.pathname;
  const base = path === "/todo" || path.startsWith("/todo/") ? "/todo/" : "/";
  window.NOTETASK_BASE = base === "/todo/" ? "/todo" : "";
  window.NOTETASK_SCOPE = base;

  const link = document.createElement("link");
  link.rel = "manifest";
  link.href = `${base}manifest.webmanifest`;
  document.head.appendChild(link);

  const theme = document.createElement("meta");
  theme.name = "theme-color";
  theme.content = "#1f6b4e";
  document.head.appendChild(theme);

  const apple = document.createElement("meta");
  apple.name = "apple-mobile-web-app-capable";
  apple.content = "yes";
  document.head.appendChild(apple);

  const touch = document.createElement("link");
  touch.rel = "apple-touch-icon";
  touch.href = `${base}assets/icons/icon-192.png`;
  document.head.appendChild(touch);

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register(`${base}sw.js?v=25`, { scope: base }).catch(() => {});
    });
  }
})();

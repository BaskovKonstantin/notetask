(function () {
  function isMobile() {
    return (
      /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent) ||
      window.matchMedia("(max-width: 860px)").matches
    );
  }

  function isStandalone() {
    return (
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true ||
      /NoteTaskAndroid|NoteTaskDesktop|Photino/i.test(navigator.userAgent || "")
    );
  }

  if (!isMobile() || isStandalone()) return;

  function onLoginScreen() {
    const login = document.getElementById("login");
    return login && !login.classList.contains("hidden");
  }

  function showBanner() {
    if (onLoginScreen()) return;
    banner.classList.remove("hidden");
  }

  let deferredPrompt = null;
  const banner = document.createElement("div");
  banner.className = "pwa-install hidden";
  banner.innerHTML = `
    <div class="pwa-install-body">
      <strong>Установить NoteTask</strong>
      <p class="pwa-install-text">Виджет «Сегодня» на главном экране — задачи и быстрое добавление.</p>
      <div class="pwa-install-actions">
        <button type="button" class="btn small" id="pwa-install-btn">Скачать</button>
        <button type="button" class="btn ghost small" id="pwa-install-dismiss">Позже</button>
      </div>
      <p class="pwa-install-ios hidden" id="pwa-ios-hint">iPhone: «Поделиться» → «На экран Домой»</p>
    </div>`;
  document.body.appendChild(banner);

  const dismissedKey = "notetask_pwa_dismissed";
  if (localStorage.getItem(dismissedKey) === "1") return;

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    showBanner();
  });

  const isIos = /iPhone|iPad|iPod/i.test(navigator.userAgent);
  if (isIos && !deferredPrompt) {
    showBanner();
    banner.querySelector("#pwa-install-btn").textContent = "Как установить";
    banner.querySelector("#pwa-ios-hint").classList.remove("hidden");
  } else if (!isIos) {
    window.setTimeout(() => {
      if (!deferredPrompt && !isStandalone()) showBanner();
    }, 1500);
  }

  banner.querySelector("#pwa-install-dismiss").onclick = () => {
    localStorage.setItem(dismissedKey, "1");
    banner.classList.add("hidden");
  };

  banner.querySelector("#pwa-install-btn").onclick = async () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      await deferredPrompt.userChoice;
      deferredPrompt = null;
      banner.classList.add("hidden");
      return;
    }
    if (isIos) {
      banner.querySelector("#pwa-ios-hint").classList.remove("hidden");
    }
  };
})();

/** Standalone login — works even if app.js fails to load/parse. */
(function () {
  const TOKEN_KEY = "notetask_token";
  const CLIENT_KEY = "notetask_client";
  const LAN_ORIGIN = "http://192.168.0.6:8100";
  const LOGIN_TIMEOUT_MS = 8000;
  const form = document.getElementById("login-form");
  const pass = document.getElementById("password");
  const err = document.getElementById("login-error");
  const btn = document.getElementById("login-btn");
  const base = window.NOTETASK_BASE || "";

  function isDesktopClient() {
    try {
      if (sessionStorage.getItem(CLIENT_KEY) === "desktop") return true;
    } catch {
      /* ignore */
    }
    try {
      const q = new URLSearchParams(location.search).get("client");
      if (q === "desktop") {
        try {
          sessionStorage.setItem(CLIENT_KEY, "desktop");
        } catch {
          /* ignore */
        }
        return true;
      }
    } catch {
      /* ignore */
    }
    if (window.__TAURI__ || window.__TAURI_INTERNALS__) return true;
    if (window.chrome && window.chrome.webview) return true;
    if (/NoteTaskDesktop|Photino/i.test(navigator.userAgent || "")) return true;
    return false;
  }

  function isLanHost() {
    return location.hostname === "192.168.0.6" || location.hostname === "127.0.0.1";
  }

  function goLanFallback() {
    if (isLanHost()) return false;
    const params = new URLSearchParams(location.search);
    if (isDesktopClient()) params.set("client", "desktop");
    const q = params.toString();
    location.replace(`${LAN_ORIGIN}/${q ? `?${q}` : ""}`);
    return true;
  }

  function isNetworkError(ex) {
    const name = String(ex && ex.name ? ex.name : "");
    const msg = String(ex && ex.message ? ex.message : "");
    return (
      name === "AbortError" ||
      /Failed to fetch|NetworkError|Load failed|aborted|network/i.test(msg)
    );
  }

  function hideDesktopDownloads() {
    if (!isDesktopClient()) return;
    ["login-download", "download-apps-btn"].forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.hidden = true;
      el.style.display = "none";
    });
  }

  async function fetchWithTimeout(url, opts, ms) {
    const ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = ctrl ? setTimeout(() => ctrl.abort(), ms) : null;
    try {
      return await fetch(url, {
        ...opts,
        signal: ctrl ? ctrl.signal : opts && opts.signal,
      });
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  async function postLogin(password, ms) {
    const res = await fetchWithTimeout(
      `${base}/api/login`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      },
      ms,
    );
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : "auth";
      throw new Error(detail);
    }
    if (!data.token) throw new Error("no token");
    return data;
  }

  async function finishLogin(token) {
    localStorage.setItem(TOKEN_KEY, token);
    if (typeof window.__notetaskAfterLogin === "function") {
      await window.__notetaskAfterLogin(token);
      return;
    }
    location.reload();
  }

  hideDesktopDownloads();

  const dl = document.getElementById("login-download");
  if (dl) {
    dl.setAttribute("href", `${base}/download` || "/download");
  }

  if (!form || !pass || !err || !btn) return;

  window.__notetaskLoginBound = true;

  async function doLogin() {
    err.classList.add("hidden");

    try {
      pass.focus({ preventScroll: true });
    } catch {
      pass.focus();
    }
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

    const password = String(pass.value || "");
    if (!password) {
      err.textContent = "Введи пароль (кликни в поле, если браузер подставил сам)";
      err.classList.remove("hidden");
      pass.focus();
      return;
    }

    const prev = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Вход…";

    try {
      const data = await postLogin(password, LOGIN_TIMEOUT_MS);
      await finishLogin(data.token);
      btn.disabled = false;
      btn.textContent = prev || "Войти";
    } catch (ex) {
      const msg = String(ex && ex.message ? ex.message : "");
      if (/wrong password|auth/i.test(msg)) {
        err.textContent = "Неверный пароль";
      } else if (isNetworkError(ex)) {
        if (isDesktopClient() && goLanFallback()) return;
        err.innerHTML =
          'Сеть не отвечает. Дома: открой <a href="' +
          LAN_ORIGIN +
          '/">локальный адрес</a> или DNS 192.168.0.6';
      } else {
        err.textContent = "Не удалось войти. Обнови страницу (Ctrl+F5).";
      }
      err.classList.remove("hidden");
      btn.disabled = false;
      btn.textContent = prev || "Войти";
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    e.stopPropagation();
    doLogin();
  });
})();

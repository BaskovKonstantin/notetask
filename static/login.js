/** Standalone login — works even if app.js fails to load/parse. */
(function () {
  const TOKEN_KEY = "notetask_token";
  const LOGIN_TIMEOUT_MS = 8000;
  const form = document.getElementById("login-form");
  const pass = document.getElementById("password");
  const err = document.getElementById("login-error");
  const btn = document.getElementById("login-btn");
  if (!form || !pass || !err || !btn) return;

  const base = window.NOTETASK_BASE || "";
  window.__notetaskLoginBound = true;

  // Autofill often shows dots while .value is still empty until focus.
  btn.addEventListener("pointerdown", () => {
    try {
      pass.focus({ preventScroll: true });
    } catch {
      pass.focus();
    }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    e.stopPropagation();
    err.classList.add("hidden");

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

    const ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = ctrl ? setTimeout(() => ctrl.abort(), LOGIN_TIMEOUT_MS) : null;

    try {
      const res = await fetch(`${base}/api/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
        signal: ctrl ? ctrl.signal : undefined,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = typeof data.detail === "string" ? data.detail : "auth";
        throw new Error(detail);
      }
      if (!data.token) throw new Error("no token");
      localStorage.setItem(TOKEN_KEY, data.token);
      location.reload();
    } catch (ex) {
      const name = String(ex && ex.name ? ex.name : "");
      const msg = String(ex && ex.message ? ex.message : "");
      const network =
        name === "AbortError" ||
        /Failed to fetch|NetworkError|Load failed|aborted/i.test(msg);
      if (/wrong password|auth/i.test(msg)) {
        err.textContent = "Неверный пароль";
      } else if (network) {
        err.textContent =
          "Сеть не отвечает (домашний Wi‑Fi). Открой http://192.168.0.6:8100/ или в hosts: 192.168.0.6 todo.baski.pro";
      } else {
        err.textContent = "Не удалось войти. Обнови страницу (Ctrl+F5).";
      }
      err.classList.remove("hidden");
      btn.disabled = false;
      btn.textContent = prev || "Войти";
    } finally {
      if (timer) clearTimeout(timer);
    }
  });
})();

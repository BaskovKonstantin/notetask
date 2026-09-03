const TOKEN_KEY = "notetask_token";
const BASE = window.NOTETASK_BASE ?? "";

function $(id) {
  return document.getElementById(id);
}

function closeOverlay() {
  try {
    if (window.__TAURI__) {
      window.__TAURI__.window.getCurrentWindow().hide();
      return;
    }
  } catch {
    /* ignore */
  }
  window.close();
  setTimeout(() => {
    document.body.innerHTML = '<p class="capture-status">Можно закрыть окно</p>';
  }, 50);
}

async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opts.body) headers["Content-Type"] = "application/json";
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (res.status === 401) throw new Error("auth");
  if (!res.ok) throw new Error(String(res.status));
  return res.status === 204 ? null : res.json();
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function showStatus(text, ok = true) {
  const el = $("capture-status");
  el.textContent = text;
  el.classList.remove("hidden");
  el.style.color = ok ? "#1f6b4e" : "#b42318";
}

async function ensureAuth() {
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) {
    $("capture-login").classList.remove("hidden");
    $("capture-form").classList.add("hidden");
    return false;
  }
  try {
    await api("/api/projects");
    $("capture-login").classList.add("hidden");
    $("capture-form").classList.remove("hidden");
    $("capture-title")?.focus();
    return true;
  } catch {
    localStorage.removeItem(TOKEN_KEY);
    $("capture-login").classList.remove("hidden");
    $("capture-form").classList.add("hidden");
    return false;
  }
}

$("capture-login-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const data = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({ password: $("capture-password").value }),
    });
    localStorage.setItem(TOKEN_KEY, data.token);
    await ensureAuth();
  } catch {
    showStatus("Неверный пароль", false);
  }
});

$("capture-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const title = ($("capture-title").value || "").trim();
  if (!title) return;
  $("capture-submit").disabled = true;
  try {
    await api("/api/tasks", {
      method: "POST",
      body: JSON.stringify({
        title,
        kind: "task",
        priority: 4,
        due_at: todayIso(),
      }),
    });
    $("capture-title").value = "";
    showStatus("Добавлено");
    setTimeout(closeOverlay, 450);
  } catch {
    showStatus("Не удалось сохранить", false);
  } finally {
    $("capture-submit").disabled = false;
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    e.preventDefault();
    closeOverlay();
  }
});

ensureAuth();

const TOKEN_KEY = "notetask_token";
const BASE = window.NOTETASK_BASE ?? "";

function $(id) {
  return document.getElementById(id);
}

async function api(path, opts = {}) {
  const headers = { ...(opts.headers || {}), Authorization: `Bearer ${localStorage.getItem(TOKEN_KEY)}` };
  if (opts.body) headers["Content-Type"] = "application/json";
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (res.status === 401) throw new Error("auth");
  if (!res.ok) throw new Error(String(res.status));
  return res.status === 204 ? null : res.json();
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatTodayHeader() {
  return new Date().toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long" });
}

function renderTask(t) {
  const done = t.status === "done";
  const meta = [];
  if (t.priority && t.priority < 4) meta.push(`P${t.priority}`);
  if (t.location) meta.push(escapeHtml(t.location.slice(0, 24)));
  return `<li class="widget-item${done ? " is-done" : ""}" data-id="${t.id}">
    <button type="button" class="widget-check${done ? " done" : ""}" data-complete="${t.id}" aria-label="${done ? "Выполнено" : "Готово"}"></button>
    <div>
      <div class="widget-title">${escapeHtml(t.title)}</div>
      ${meta.length ? `<div class="widget-meta">${meta.map((m) => `<span>${m}</span>`).join("")}</div>` : ""}
    </div>
  </li>`;
}

async function loadWidgetTasks() {
  const tasks = await api("/api/tasks?view=today");
  const open = tasks.filter((t) => t.status !== "done");
  const done = tasks.filter((t) => t.status === "done");
  const list = $("widget-list");
  if (!open.length && !done.length) {
    list.innerHTML = '<li class="widget-empty">Нет задач на сегодня. Добавь ниже.</li>';
    return;
  }
  list.innerHTML = open.map(renderTask).join("") + done.map(renderTask).join("");
}

function showLogin() {
  $("widget-login").classList.remove("hidden");
  $("widget-app").classList.add("hidden");
}

function showApp() {
  $("widget-login").classList.add("hidden");
  $("widget-app").classList.remove("hidden");
  $("widget-date").textContent = formatTodayHeader();
}

async function boot() {
  $("widget-date").textContent = formatTodayHeader();
  const params = new URLSearchParams(location.search);
  if (params.get("add") === "1") {
    window.setTimeout(() => $("widget-input")?.focus(), 300);
  }

  if (!localStorage.getItem(TOKEN_KEY)) {
    showLogin();
    return;
  }
  try {
    await api("/api/health");
    await api("/api/projects");
    showApp();
    await loadWidgetTasks();
  } catch {
    showLogin();
  }
}

$("widget-login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("widget-login-error").classList.add("hidden");
  try {
    const data = await fetch(`${BASE}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: $("widget-password").value }),
    }).then((r) => (r.ok ? r.json() : Promise.reject()));
    localStorage.setItem(TOKEN_KEY, data.token);
    $("widget-password").value = "";
    showApp();
    await loadWidgetTasks();
  } catch {
    $("widget-login-error").classList.remove("hidden");
  }
});

$("widget-add").addEventListener("submit", async (e) => {
  e.preventDefault();
  const title = $("widget-input").value.trim();
  if (!title) return;
  await api("/api/tasks", {
    method: "POST",
    body: JSON.stringify({ title, kind: "task", priority: 4, due_at: todayIso() }),
  });
  $("widget-input").value = "";
  await loadWidgetTasks();
});

$("widget-list").addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-complete]");
  if (!btn) return;
  const id = btn.dataset.complete;
  const item = btn.closest(".widget-item");
  if (item?.classList.contains("is-done")) return;
  await api(`/api/tasks/${id}/complete`, { method: "POST" });
  await loadWidgetTasks();
});

boot();

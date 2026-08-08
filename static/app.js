const TOKEN_KEY = "notetask_token";
const BASE = window.NOTETASK_BASE ?? (() => {
  const path = window.location.pathname;
  if (path === "/todo" || path.startsWith("/todo/")) return "/todo";
  return "";
})();

const state = {
  view: "today",
  token: localStorage.getItem(TOKEN_KEY) || "",
};

const titles = {
  today: ["Сегодня", "Задачи на сегодня и просроченные"],
  inbox: ["Inbox", "Задачи без срока — сюда попадают новые"],
  someday: ["Идеи / планы", "Захватить мысль — разобрать потом"],
  upcoming: ["Предстоящие", "Срок позже сегодняшнего"],
  notes: ["Заметки", "Структурированные записи"],
  workouts: ["Тренировки", "Дневник подходов и прогресса"],
  history: ["История", "Ничего не теряется"],
  stats: ["Статистика", "Streak и активность за 30 дней"],
};

const emptyHints = {
  today: "Нет задач на сегодня. Добавь задачу ниже (срок подставится) или открой Inbox / Идеи.",
  inbox: "Inbox пуст. Добавь задачу без даты.",
  someday: "Пока нет идей. Выбери тип «Идея» или «План».",
  upcoming: "Нет задач с будущим сроком.",
};

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const url = path.startsWith("http") ? path : `${BASE}${path}`;
  const res = await fetch(url, { ...opts, headers });
  if (res.status === 401) {
    logout(false);
    throw new Error("auth");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText);
  }
  if (res.status === 204) return null;
  return res.json();
}

async function track(action, entityType = "ui", entityId = null, payload = {}) {
  if (!state.token) return;
  try {
    await api("/api/events", {
      method: "POST",
      body: JSON.stringify({
        action,
        entity_type: entityType,
        entity_id: entityId,
        payload,
      }),
    });
  } catch {
    /* history must not break UX */
  }
}

function $(id) {
  return document.getElementById(id);
}

function logout(reload = true) {
  if (state.token) track("logout", "session", null, {});
  state.token = "";
  localStorage.removeItem(TOKEN_KEY);
  if (reload) location.reload();
  else showLogin();
}

function showLogin() {
  $("login").classList.remove("hidden");
  $("app").classList.add("hidden");
}

function showApp() {
  $("login").classList.add("hidden");
  $("app").classList.remove("hidden");
}

const kindLabels = { task: "Задача", idea: "Идея", plan: "План" };

function fmtShortDay(isoDate) {
  if (!isoDate) return "";
  try {
    return new Date(`${isoDate}T12:00:00`).toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "short",
    });
  } catch {
    return isoDate;
  }
}

function fmtShortDateTime(value) {
  if (!value) return "";
  try {
    return new Date(value).toLocaleString("ru-RU", {
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

function closeTaskPopovers() {
  document.querySelectorAll(".chip-menu").forEach((menu) => menu.classList.add("hidden"));
  document.querySelectorAll(".chip-btn").forEach((btn) => {
    btn.classList.remove("active");
    btn.setAttribute("aria-expanded", "false");
  });
}

function updateTaskChips() {
  const kind = $("task-kind").value;
  $("chip-kind-label").textContent = kindLabels[kind] || kind;
  document.querySelectorAll("[data-set-kind]").forEach((btn) => {
    btn.classList.toggle("selected", btn.dataset.setKind === kind);
  });

  const priority = $("task-priority").value;
  $("chip-priority-label").textContent = `P${priority}`;
  $("chip-priority").classList.toggle("has-value", priority !== "4");
  document.querySelectorAll("[data-set-priority]").forEach((btn) => {
    btn.classList.toggle("selected", btn.dataset.setPriority === priority);
  });

  const due = $("task-due").value;
  $("chip-due-label").textContent = due ? fmtShortDay(due) : "Срок";
  $("chip-due").classList.toggle("has-value", !!due);

  const remind = $("task-remind").value;
  $("chip-remind-label").textContent = remind ? fmtShortDateTime(remind) : "Напомн.";
  $("chip-remind").classList.toggle("has-value", !!remind);
}

function initTaskMetaChips() {
  document.querySelectorAll(".chip-popover .chip-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const menu = btn.parentElement.querySelector(".chip-menu");
      const wasOpen = menu && !menu.classList.contains("hidden");
      closeTaskPopovers();
      if (menu && !wasOpen) {
        menu.classList.remove("hidden");
        btn.classList.add("active");
        btn.setAttribute("aria-expanded", "true");
        const input = menu.querySelector("input");
        if (input?.showPicker) {
          window.setTimeout(() => input.showPicker(), 0);
        } else if (input) {
          input.focus();
        }
      }
    });
  });

  document.querySelectorAll("[data-set-kind]").forEach((btn) => {
    btn.addEventListener("click", () => {
      $("task-kind").value = btn.dataset.setKind;
      updateTaskChips();
      closeTaskPopovers();
    });
  });

  document.querySelectorAll("[data-set-priority]").forEach((btn) => {
    btn.addEventListener("click", () => {
      $("task-priority").value = btn.dataset.setPriority;
      updateTaskChips();
      closeTaskPopovers();
    });
  });

  $("task-due").addEventListener("change", () => {
    updateTaskChips();
    closeTaskPopovers();
  });
  $("task-remind").addEventListener("change", updateTaskChips);

  document.querySelectorAll("[data-clear]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const el = $(btn.dataset.clear);
      if (el) el.value = "";
      updateTaskChips();
      closeTaskPopovers();
    });
  });

  document.addEventListener("click", closeTaskPopovers);
  document.querySelectorAll(".chip-menu").forEach((menu) => {
    menu.addEventListener("click", (e) => e.stopPropagation());
  });

  updateTaskChips();
}

function fmtDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function setView(view) {
  state.view = view;
  document.querySelectorAll("#nav button").forEach((b) => {
    b.classList.toggle("active", b.dataset.view === view);
  });
  const [t, s] = titles[view];
  $("view-title").textContent = t;
  $("view-sub").textContent = s;

  const taskViews = ["today", "inbox", "someday", "upcoming"];
  $("view-tasks").classList.toggle("hidden", !taskViews.includes(view));
  $("view-notes").classList.toggle("hidden", view !== "notes");
  $("view-workouts").classList.toggle("hidden", view !== "workouts");
  $("view-history").classList.toggle("hidden", view !== "history");
  $("view-stats").classList.toggle("hidden", view !== "stats");

  if (view === "someday") $("task-kind").value = "idea";
  else if (taskViews.includes(view)) $("task-kind").value = "task";

  const dueInput = $("task-due");
  if (view === "today") dueInput.value = todayIso();
  else if (view !== "upcoming") dueInput.value = "";

  updateTaskChips();
  track("view_opened", "ui", null, { view });
  refresh();
}

async function refresh() {
  const v = state.view;
  if (["today", "inbox", "someday", "upcoming"].includes(v)) await loadTasks(v);
  else if (v === "notes") await loadNotes();
  else if (v === "workouts") await loadWorkouts();
  else if (v === "history") await loadHistory();
  else if (v === "stats") await loadStats();
}

function priorityBadge(p) {
  if (p === 1) return '<span class="badge p1">P1</span>';
  if (p === 2) return '<span class="badge p2">P2</span>';
  return `<span class="badge">P${p}</span>`;
}

async function loadTasks(view) {
  const tasks = await api(`/api/tasks?view=${view}`);
  const root = $("task-list");
  if (!tasks.length) {
    root.innerHTML = `<div class="empty">${emptyHints[view] || "Пусто."}</div>`;
    return;
  }
  root.innerHTML = tasks
    .map((t) => {
      const kind =
        t.kind === "idea"
          ? '<span class="badge idea">идея</span>'
          : t.kind === "plan"
            ? '<span class="badge idea">план</span>'
            : "";
      const due = t.due_at ? `<span class="badge">${t.due_at.slice(0, 10)}</span>` : "";
      const promote =
        t.kind !== "task"
          ? `<button class="btn ghost small" data-promote="${t.id}">В задачу</button>`
          : "";
      return `
      <div class="item" data-id="${t.id}">
        <button class="check ${t.status === "done" ? "done" : ""}" data-complete="${t.id}" aria-label="done"></button>
        <div>
          <div class="item-title">${escapeHtml(t.title)}</div>
          <div class="item-meta">${priorityBadge(t.priority)}${kind}${due}</div>
        </div>
        <div class="item-actions">
          ${promote}
          <button class="btn ghost small btn-del" data-del-task="${t.id}" aria-label="Удалить">×</button>
        </div>
      </div>`;
    })
    .join("");
}

async function loadNotes() {
  const notes = await api("/api/notes");
  const root = $("note-list");
  if (!notes.length) {
    root.innerHTML = '<div class="empty">Заметок пока нет.</div>';
    return;
  }
  root.innerHTML = notes
    .map(
      (n) => `
    <article class="note-card">
      <h3>${escapeHtml(n.title)}</h3>
      <pre>${escapeHtml(n.body || "")}</pre>
      <div class="item-meta" style="margin-top:10px">
        <span>${fmtDate(n.updated_at)}</span>
        <button class="btn ghost small btn-del" data-del-note="${n.id}" aria-label="Удалить">×</button>
      </div>
    </article>`
    )
    .join("");
}

function addWorkoutSetRow(data = {}) {
  const wrap = document.createElement("div");
  wrap.className = "workout-set-row";
  wrap.innerHTML = `
    <input type="text" class="wo-ex" placeholder="Упражнение" value="${escapeAttr(data.exercise || "")}" required />
    <input type="number" class="wo-w" step="0.5" placeholder="Вес" value="${data.weight ?? ""}" />
    <input type="number" class="wo-r" placeholder="Повт." value="${data.reps ?? ""}" />
    <button type="button" class="btn ghost small wo-rm">×</button>`;
  wrap.querySelector(".wo-rm").onclick = () => wrap.remove();
  $("wo-sets").appendChild(wrap);
}

async function loadWorkouts() {
  const list = await api("/api/workouts");
  const root = $("workout-list");
  if (!list.length) {
    root.innerHTML = '<div class="empty">Тренировок пока нет — запиши первую.</div>';
    return;
  }
  root.innerHTML = list
    .map((w) => {
      const sets = (w.sets || [])
        .map(
          (s) =>
            `<div class="item-meta">${escapeHtml(s.exercise)} · ${s.weight ?? "—"} кг × ${s.reps ?? "—"}</div>`
        )
        .join("");
      return `
      <div class="item" style="grid-template-columns:1fr auto">
        <div>
          <div class="item-title">${escapeHtml(w.title)}</div>
          <div class="item-meta">${fmtDate(w.started_at)}</div>
          ${sets}
        </div>
        <button class="btn ghost small btn-del" data-del-wo="${w.id}" aria-label="Удалить">×</button>
      </div>`;
    })
    .join("");
}

const actionLabels = {
  created: "создано",
  updated: "изменено",
  deleted: "удалено",
  completed: "выполнено",
  reopened: "снова открыто",
  promoted: "в задачу",
  workout_logged: "тренировка",
  login: "вход",
  logout: "выход",
  view_opened: "экран",
  shortcut_used: "шорткат",
  backup_exported: "бэкап",
  app_opened: "открытие",
};

const entityLabels = {
  task: "задача",
  note: "заметка",
  workout: "тренировка",
  project: "проект",
  session: "сессия",
  ui: "интерфейс",
  system: "система",
};

function formatChanges(changes) {
  if (!changes || typeof changes !== "object") return "";
  return Object.entries(changes)
    .map(([field, diff]) => {
      const from = diff?.from ?? "—";
      const to = diff?.to ?? "—";
      return `${field}: ${from} → ${to}`;
    })
    .join(" · ");
}

async function loadHistory() {
  const rows = await api("/api/history?limit=150");
  const root = $("history-list");
  if (!rows.length) {
    root.innerHTML = '<div class="empty">История появится после первых действий.</div>';
    return;
  }
  root.innerHTML = rows
    .map((r) => {
      const title = r.payload?.title || r.payload?.name || r.payload?.view || "";
      const action = actionLabels[r.action] || r.action;
      const entity = entityLabels[r.entity_type] || r.entity_type;
      const changes = formatChanges(r.payload?.changes);
      const extra = r.payload?.shortcut ? ` · ${r.payload.shortcut}` : "";
      return `
      <div class="tl-item">
        <div class="tl-time">${fmtDate(r.at)}</div>
        <div>
          <div class="tl-action">${escapeHtml(action)} · ${escapeHtml(entity)}</div>
          <div class="item-meta">${escapeHtml(String(title))}${extra} ${r.entity_id ? "#" + r.entity_id : ""}</div>
          ${changes ? `<div class="item-meta tl-changes">${escapeHtml(changes)}</div>` : ""}
        </div>
      </div>`;
    })
    .join("");
}

async function loadStats() {
  const s = await api("/api/stats");
  $("stats-cards").innerHTML = `
    <div class="stat"><div class="n">${s.streak}</div><div class="l">Streak (дни)</div></div>
    <div class="stat"><div class="n">${s.completions_30d}</div><div class="l">Задач за 30д</div></div>
    <div class="stat"><div class="n">${s.workouts_30d}</div><div class="l">Тренировок за 30д</div></div>
    <div class="stat"><div class="n">${s.open_tasks}/${s.ideas}</div><div class="l">Открыто / идей</div></div>`;
  const max = Math.max(1, ...s.series.map((d) => d.completions + d.workouts));
  $("stats-bars").innerHTML = s.series
    .map((d) => {
      const h = Math.round(((d.completions + d.workouts) / max) * 100);
      const cls = d.workouts > d.completions ? "bar w" : d.completions ? "bar has" : "bar";
      return `<div class="${cls}" style="height:${Math.max(4, h)}%" title="${d.day}: ${d.completions}/${d.workouts}"></div>`;
    })
    .join("");
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttr(str) {
  return escapeHtml(str).replaceAll("'", "&#39;");
}

function openTaskCapture() {
  if ($("app").classList.contains("hidden")) return;
  track("shortcut_used", "ui", null, { shortcut: "ctrl+space", target: "task_capture" });
  setView("today");
  const panel = $("view-tasks");
  panel.classList.add("capture-focus");
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  window.setTimeout(() => $("task-title").focus(), 50);
  window.setTimeout(() => panel.classList.remove("capture-focus"), 1400);
}

function isTypingTarget(el) {
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}

function localInputValue(dt = new Date()) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
}

document.addEventListener("keydown", (e) => {
  if (!e.ctrlKey || e.code !== "Space") return;
  if (isTypingTarget(document.activeElement) && document.activeElement?.id !== "task-title") return;
  e.preventDefault();
  openTaskCapture();
});

// events
$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("login-error").classList.add("hidden");
  try {
    const data = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({ password: $("password").value }),
    });
    state.token = data.token;
    localStorage.setItem(TOKEN_KEY, state.token);
    showApp();
    setView("today");
  } catch {
    $("login-error").classList.remove("hidden");
  }
});

$("nav").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-view]");
  if (btn) setView(btn.dataset.view);
});

$("logout-btn").onclick = () => logout(true);

$("backup-btn").onclick = async () => {
  const data = await api("/api/backup");
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `notetask-backup-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
};

$("task-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const kind = $("task-kind").value;
  let due = $("task-due").value || null;
  if (kind === "task" && !due && state.view === "today") due = todayIso();
  const remind = $("task-remind").value ? new Date($("task-remind").value).toISOString() : null;
  await api("/api/tasks", {
    method: "POST",
    body: JSON.stringify({
      title: $("task-title").value.trim(),
      kind,
      priority: Number($("task-priority").value),
      due_at: due,
      remind_at: remind,
    }),
  });
  $("task-title").value = "";
  updateTaskChips();
  if (kind === "idea" || kind === "plan") setView("someday");
  else if (!due) setView("inbox");
  else await refresh();
});

$("task-list").addEventListener("click", async (e) => {
  const complete = e.target.closest("[data-complete]");
  const del = e.target.closest("[data-del-task]");
  const promote = e.target.closest("[data-promote]");
  if (complete) {
    await api(`/api/tasks/${complete.dataset.complete}/complete`, { method: "POST" });
    await refresh();
  } else if (del) {
    await api(`/api/tasks/${del.dataset.delTask}`, { method: "DELETE" });
    await refresh();
  } else if (promote) {
    await api(`/api/tasks/${promote.dataset.promote}/promote`, { method: "POST" });
    await refresh();
  }
});

$("note-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  await api("/api/notes", {
    method: "POST",
    body: JSON.stringify({
      title: $("note-title").value.trim(),
      body: $("note-body").value,
    }),
  });
  $("note-title").value = "";
  $("note-body").value = "";
  await refresh();
});

$("note-list").addEventListener("click", async (e) => {
  const del = e.target.closest("[data-del-note]");
  if (del) {
    await api(`/api/notes/${del.dataset.delNote}`, { method: "DELETE" });
    await refresh();
  }
});

$("wo-add-set").onclick = () => addWorkoutSetRow();

$("workout-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const sets = [...$("wo-sets").querySelectorAll(".workout-set-row")].map((row, i) => ({
    exercise: row.querySelector(".wo-ex").value.trim(),
    weight: row.querySelector(".wo-w").value ? Number(row.querySelector(".wo-w").value) : null,
    reps: row.querySelector(".wo-r").value ? Number(row.querySelector(".wo-r").value) : null,
    set_index: i + 1,
  })).filter((s) => s.exercise);
  const started = $("wo-started").value
    ? new Date($("wo-started").value).toISOString()
    : null;
  await api("/api/workouts", {
    method: "POST",
    body: JSON.stringify({
      title: $("wo-title").value.trim() || "Тренировка",
      notes: $("wo-notes").value,
      started_at: started,
      sets,
    }),
  });
  $("wo-notes").value = "";
  $("wo-sets").innerHTML = "";
  addWorkoutSetRow();
  await refresh();
});

$("workout-list").addEventListener("click", async (e) => {
  const del = e.target.closest("[data-del-wo]");
  if (del) {
    await api(`/api/workouts/${del.dataset.delWo}`, { method: "DELETE" });
    await refresh();
  }
});

async function boot() {
  addWorkoutSetRow();
  $("wo-started").value = localInputValue();
  initTaskMetaChips();
  if (!state.token) {
    showLogin();
    return;
  }
  try {
    await api("/api/health");
    // validate token via protected endpoint
    await api("/api/projects");
    showApp();
    track("app_opened", "ui", null, { path: location.pathname });
    setView("today");
  } catch {
    showLogin();
  }
}

boot();

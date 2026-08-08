const TOKEN_KEY = "notetask_token";
const BASE = window.NOTETASK_BASE ?? (() => {
  const path = window.location.pathname;
  if (path === "/todo" || path.startsWith("/todo/")) return "/todo";
  return "";
})();

const state = {
  view: "today",
  token: localStorage.getItem(TOKEN_KEY) || "",
  projects: [],
  projectId: null,
};

const titles = {
  today: ["Сегодня", "Задачи на сегодня и просроченные"],
  history: ["История", "Ничего не теряется"],
  stats: ["Статистика", "Streak и активность за 30 дней"],
  project: ["Раздел", "Задачи раздела"],
};

const emptyHints = {
  today: "Нет задач на сегодня. Добавь задачу ниже (срок подставится).",
  project: "Нет задач. P4 и новые без @раздела — сюда.",
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

const RU_MONTHS = {
  янв: 0, январ: 0, фев: 1, феврал: 1, мар: 2, март: 2, апр: 3, апрел: 3,
  май: 4, мая: 4, июн: 5, июн: 5, июл: 6, июл: 6, авг: 7, август: 7,
  сен: 8, сент: 8, окт: 9, октябр: 9, ноя: 10, нояб: 10, дек: 11, декабр: 11,
};

function addDays(base, days) {
  const d = new Date(base);
  d.setDate(d.getDate() + days);
  return d;
}

function toIsoDate(d) {
  return d.toISOString().slice(0, 10);
}

function parseDateToken(text) {
  const lower = text.toLowerCase().trim();
  const now = new Date();
  if (/^(?:сегодня|today)$/.test(lower)) return toIsoDate(now);
  if (/^(?:завтра|tomorrow)$/.test(lower)) return toIsoDate(addDays(now, 1));
  if (/^послезавтра$/.test(lower)) return toIsoDate(addDays(now, 2));

  const iso = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;

  const dmy = text.match(/^(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?$/);
  if (dmy) {
    const day = Number(dmy[1]);
    const month = Number(dmy[2]) - 1;
    let year = dmy[3] ? Number(dmy[3]) : now.getFullYear();
    if (year < 100) year += 2000;
    return toIsoDate(new Date(year, month, day));
  }

  const named = lower.match(/^(\d{1,2})\s+([a-zа-я]+)/);
  if (named) {
    const day = Number(named[1]);
    const monthKey = Object.keys(RU_MONTHS).find((k) => named[2].startsWith(k));
    if (monthKey) {
      let year = now.getFullYear();
      const candidate = new Date(year, RU_MONTHS[monthKey], day);
      if (candidate < now) year += 1;
      return toIsoDate(new Date(year, RU_MONTHS[monthKey], day));
    }
  }
  return null;
}

function parsePriorityToken(text) {
  const bang = text.match(/^!{1,4}$/);
  if (bang) return 5 - bang[0].length;
  const p = text.match(/^p\s*([1-4])$/i);
  return p ? Number(p[1]) : null;
}

function parseKindToken(text) {
  const lower = text.toLowerCase();
  if (/^(?:идея|idea)$/.test(lower)) return "idea";
  if (/^(?:план|plan)$/.test(lower)) return "plan";
  return null;
}

function findProjectId(name) {
  const raw = name.toLowerCase();
  const compact = raw.replace(/[\s_-]+/g, "");
  const hit = state.projects.find((p) => {
    const pn = p.name.toLowerCase();
    const pc = pn.replace(/[\s_-]+/g, "");
    return pn === raw || pc === compact || pc.startsWith(compact);
  });
  return hit?.id ?? null;
}

function collectTaskTokens(text) {
  const patterns = [
    {
      type: "date",
      re: /\b(?:сегодня|today|завтра|tomorrow|послезавтра)\b/gi,
      meta: (m) => ({ due: parseDateToken(m[0]) }),
    },
    {
      type: "date",
      re: /\b\d{4}-\d{2}-\d{2}\b/g,
      meta: (m) => ({ due: parseDateToken(m[0]) }),
    },
    {
      type: "date",
      re: /\b\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\b/g,
      meta: (m) => ({ due: parseDateToken(m[0]) }),
    },
    {
      type: "date",
      re: /\b\d{1,2}\s+(?:янв(?:[а-я]*?)?|фев(?:[а-я]*?)?|мар(?:[а-я]*?)?|апр(?:[а-я]*?)?|мая|май|июн(?:[а-я]*?)?|июл(?:[а-я]*?)?|авг(?:[а-я]*?)?|сен(?:[а-я]*?)?|окт(?:[а-я]*?)?|ноя(?:[а-я]*?)?|дек(?:[а-я]*?)?)\b/gi,
      meta: (m) => ({ due: parseDateToken(m[0]) }),
    },
    {
      type: "priority",
      re: /!{1,4}\b/g,
      meta: (m) => ({ priority: parsePriorityToken(m[0]) }),
    },
    {
      type: "priority",
      re: /\bp\s*[1-4]\b/gi,
      meta: (m) => ({ priority: parsePriorityToken(m[0].replace(/\s+/g, "")) }),
    },
    {
      type: "project",
      re: /@([a-zA-Zа-яА-ЯёЁ0-9_-]+)/g,
      meta: (m) => ({ projectName: m[1], projectId: findProjectId(m[1]) }),
    },
    {
      type: "label",
      re: /#([a-zA-Zа-яА-ЯёЁ0-9_-]+)/g,
      meta: (m) => ({ label: m[1] }),
    },
    {
      type: "kind",
      re: /\b(?:идея|idea|план|plan)\b/gi,
      meta: (m) => ({ kind: parseKindToken(m[0]) }),
    },
  ];

  const found = [];
  for (const rule of patterns) {
    for (const match of text.matchAll(rule.re)) {
      found.push({
        type: rule.type,
        start: match.index,
        end: match.index + match[0].length,
        text: match[0],
        meta: rule.meta(match),
      });
    }
  }

  found.sort((a, b) => a.start - b.start || b.end - a.end);
  const tokens = [];
  let cursor = -1;
  for (const token of found) {
    if (token.start < cursor) continue;
    tokens.push(token);
    cursor = token.end;
  }
  return tokens;
}

function mergeTaskMeta(tokens) {
  const meta = { labels: [] };
  for (const token of tokens) {
    const m = token.meta || {};
    if (m.due) meta.due = m.due;
    if (m.priority) meta.priority = m.priority;
    if (m.kind) meta.kind = m.kind;
    if (m.projectName) {
      meta.projectName = m.projectName;
      if (m.projectId) meta.projectId = m.projectId;
    }
    if (m.label) meta.labels.push(m.label);
  }
  return meta;
}

function cleanTitleFromTokens(text, tokens) {
  let out = "";
  let pos = 0;
  for (const token of tokens) {
    out += text.slice(pos, token.start);
    pos = token.end;
  }
  out += text.slice(pos);
  return out.replace(/\s+/g, " ").trim();
}

function buildTaskHighlightHtml(text, tokens) {
  if (!text) return "";
  let html = "";
  let pos = 0;
  for (const token of tokens) {
    if (token.start > pos) html += escapeHtml(text.slice(pos, token.start));
    html += `<span class="hl-${token.type}">${escapeHtml(text.slice(token.start, token.end))}</span>`;
    pos = token.end;
  }
  if (pos < text.length) html += escapeHtml(text.slice(pos));
  return html;
}

function parseTaskInput(text) {
  const tokens = collectTaskTokens(text);
  return {
    tokens,
    meta: mergeTaskMeta(tokens),
    cleanTitle: cleanTitleFromTokens(text, tokens),
  };
}

function applyParsedMeta(meta) {
  if (meta.due) $("task-due").value = meta.due;
  if (meta.priority) $("task-priority").value = String(meta.priority);
  if (meta.kind) $("task-kind").value = meta.kind;
  updateTaskChips();
}

function syncTaskTitleHighlight() {
  const input = $("task-title");
  const layer = $("task-title-highlight");
  const text = input.value;
  const parsed = parseTaskInput(text);
  layer.innerHTML = buildTaskHighlightHtml(text, parsed.tokens) || "&nbsp;";
  layer.scrollLeft = input.scrollLeft;
  applyParsedMeta(parsed.meta);
}

function initTaskTitleHighlight() {
  const input = $("task-title");
  input.addEventListener("input", syncTaskTitleHighlight);
  input.addEventListener("scroll", () => {
    $("task-title-highlight").scrollLeft = input.scrollLeft;
  });
  syncTaskTitleHighlight();
}

async function loadProjectsCache() {
  try {
    state.projects = await api("/api/projects");
    renderProjectNav();
  } catch {
    state.projects = [];
    renderProjectNav();
  }
}

function renderProjectNav() {
  const nav = $("project-nav");
  if (!nav) return;
  const sections = [...state.projects].sort((a, b) => a.sort - b.sort || a.id - b.id);
  nav.innerHTML = sections
    .map((p) => {
      const label = p.name === "Inbox" ? "Разобрать" : p.name;
      return `
    <button type="button" data-view="project" data-project-id="${p.id}">
      <span class="project-dot" style="background:${escapeAttr(p.color)}"></span>
      ${escapeHtml(label)}
    </button>`;
    })
    .join("");
}

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

function setView(view, opts = {}) {
  state.view = view;
  state.projectId = opts.projectId ?? null;

  document.querySelectorAll("#nav button, #project-nav button").forEach((b) => {
    const pid = b.dataset.projectId ? Number(b.dataset.projectId) : null;
    const active =
      view === "project" ? pid === state.projectId : b.dataset.view === view && !b.dataset.projectId;
    b.classList.toggle("active", active);
  });

  if (view === "project") {
    const proj = state.projects.find((p) => p.id === state.projectId);
    $("view-title").textContent = proj?.name || "Раздел";
    $("view-sub").textContent =
      proj?.name === "Inbox" ? "P4 и задачи без раздела — разложи по проектам" : "Задачи раздела";
  } else {
    const [t, s] = titles[view] || ["", ""];
    $("view-title").textContent = t;
    $("view-sub").textContent = s;
  }

  const taskViews = ["today", "project"];
  $("view-tasks").classList.toggle("hidden", !taskViews.includes(view));
  $("view-notes").classList.add("hidden");
  $("view-workouts").classList.add("hidden");
  $("view-history").classList.toggle("hidden", view !== "history");
  $("view-stats").classList.toggle("hidden", view !== "stats");

  if (taskViews.includes(view)) $("task-kind").value = "task";

  const dueInput = $("task-due");
  if (view === "today") dueInput.value = todayIso();
  else if (view === "project") dueInput.value = "";

  updateTaskChips();
  track("view_opened", "ui", null, { view, project_id: state.projectId });
  refresh();
}

async function refresh() {
  const v = state.view;
  if (["today", "project"].includes(v)) await loadTasks(v);
  else if (v === "history") await loadHistory();
  else if (v === "stats") await loadStats();
}

function priorityBadge(p) {
  if (p === 1) return '<span class="badge p1">P1</span>';
  if (p === 2) return '<span class="badge p2">P2</span>';
  return `<span class="badge">P${p}</span>`;
}

function taskDayKey(task) {
  if (!task.due_at) return "none";
  return task.due_at.slice(0, 10);
}

function taskTimeSortKey(task) {
  const iso =
    task.due_at && task.due_at.includes("T")
      ? task.due_at
      : task.remind_at && task.remind_at.includes("T")
        ? task.remind_at
        : null;
  if (!iso) return 0;
  try {
    const d = new Date(iso);
    return d.getHours() * 60 + d.getMinutes() + 1;
  } catch {
    return 0;
  }
}

function formatTaskTime(task) {
  const iso =
    task.due_at && task.due_at.includes("T")
      ? task.due_at
      : task.remind_at && task.remind_at.includes("T")
        ? task.remind_at
        : null;
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function formatDayHeader(dayKey) {
  if (dayKey === "none") return "Без срока";
  const today = todayIso();
  const tomorrow = toIsoDate(addDays(new Date(), 1));
  if (dayKey === today) return "Сегодня";
  if (dayKey === tomorrow) return "Завтра";
  try {
    return new Date(`${dayKey}T12:00:00`).toLocaleDateString("ru-RU", {
      weekday: "long",
      day: "numeric",
      month: "long",
    });
  } catch {
    return dayKey;
  }
}

function sortTasksInDayGroup(tasks) {
  return [...tasks].sort((a, b) => {
    const ta = taskTimeSortKey(a);
    const tb = taskTimeSortKey(b);
    if (ta !== tb) return ta - tb;
    if (a.priority !== b.priority) return a.priority - b.priority;
    return b.id - a.id;
  });
}

function groupTasksByDay(tasks) {
  const groups = new Map();
  for (const task of tasks) {
    const key = taskDayKey(task);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(task);
  }
  const keys = [...groups.keys()].sort((a, b) => {
    if (a === "none") return 1;
    if (b === "none") return -1;
    return a.localeCompare(b);
  });
  return keys.map((key) => ({
    day: key,
    tasks: sortTasksInDayGroup(groups.get(key)),
  }));
}

async function loadTasks(view) {
  let url = `/api/tasks?view=${view === "project" ? "all" : view}`;
  if (view === "project" && state.projectId) url += `&project_id=${state.projectId}`;
  const tasks = await api(url);
  const root = $("task-list");
  const projectMap = Object.fromEntries(state.projects.map((p) => [p.id, p.name]));
  if (!tasks.length) {
    root.innerHTML = `<div class="empty">${emptyHints[view] || "Пусто."}</div>`;
    return;
  }

  const openTasks = tasks.filter((t) => t.status !== "done");
  const doneTasks = tasks.filter((t) => t.status === "done");
  let html = "";

  for (const group of groupTasksByDay(openTasks)) {
    html += `<div class="day-group-header">${escapeHtml(formatDayHeader(group.day))}</div>`;
    for (const t of group.tasks) html += renderTaskItem(t, view, projectMap);
  }

  if (doneTasks.length) {
    html += '<div class="list-divider">Выполнено</div>';
    for (const group of groupTasksByDay(doneTasks)) {
      html += `<div class="day-group-header day-group-header-done">${escapeHtml(formatDayHeader(group.day))}</div>`;
      for (const t of group.tasks) html += renderTaskItem(t, view, projectMap);
    }
  }

  root.innerHTML = html;
}

function renderTaskItem(t, view, projectMap) {
  const done = t.status === "done";
  const kind =
    t.kind === "idea"
      ? '<span class="badge idea">идея</span>'
      : t.kind === "plan"
        ? '<span class="badge idea">план</span>'
        : "";
  const time = formatTaskTime(t);
  const timeBadge = time ? `<span class="badge time">${time}</span>` : "";
  const project =
    t.project_id && projectMap[t.project_id] && view !== "project"
      ? `<span class="badge">${escapeHtml(projectMap[t.project_id])}</span>`
      : "";
  const promote =
    t.kind !== "task" && !done
      ? `<button class="btn ghost small" data-promote="${t.id}">В задачу</button>`
      : "";
  return `
      <div class="item${done ? " is-done" : ""}" data-id="${t.id}">
        <button class="check${done ? " done" : ""}" data-complete="${t.id}" aria-label="${done ? "Выполнено" : "Отметить выполненным"}"></button>
        <div>
          <div class="item-title${done ? " done-title" : ""}">${escapeHtml(t.title)}</div>
          <div class="item-meta">${timeBadge}${priorityBadge(t.priority)}${kind}${project}</div>
        </div>
        <div class="item-actions">
          ${promote}
          <button class="btn ghost small btn-del" data-del-task="${t.id}" aria-label="Удалить">×</button>
        </div>
      </div>`;
}

let completeAudioCtx;

function playCompleteSound() {
  try {
    completeAudioCtx = completeAudioCtx || new AudioContext();
    const ctx = completeAudioCtx;
    if (ctx.state === "suspended") void ctx.resume();

    const t0 = ctx.currentTime + 0.001;

    const master = ctx.createGain();
    master.gain.setValueAtTime(0.85, t0);
    master.connect(ctx.destination);

    const toneBus = ctx.createGain();
    toneBus.gain.setValueAtTime(1, t0);
    toneBus.connect(master);

    const warm = ctx.createBiquadFilter();
    warm.type = "lowpass";
    warm.Q.value = 0.85;
    warm.frequency.setValueAtTime(3600, t0);
    warm.frequency.exponentialRampToValueAtTime(1200, t0 + 0.32);
    warm.connect(toneBus);

    const playTone = (type, start, stop, freqStart, freqEnd, peak, attack, decay) => {
      const osc = ctx.createOscillator();
      osc.type = type;
      osc.frequency.setValueAtTime(freqStart, start);
      if (freqEnd !== freqStart) osc.frequency.exponentialRampToValueAtTime(freqEnd, stop - 0.02);

      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.linearRampToValueAtTime(peak, start + attack);
      gain.gain.exponentialRampToValueAtTime(0.0001, stop);

      osc.connect(gain);
      gain.connect(warm);
      osc.start(start);
      osc.stop(stop + 0.01);
    };

    // Soft checkbox thump
    playTone("sine", t0, t0 + 0.07, 196, 98, 0.42, 0.004, 0.07);

    // Main marimba-like note (Todoist: warm descending chime)
    playTone("sine", t0 + 0.008, t0 + 0.34, 880, 659.25, 0.52, 0.006, 0.34);

    // Fifth overtone — "smaчный" sparkle
    playTone("sine", t0 + 0.01, t0 + 0.22, 1318.5, 987.77, 0.22, 0.004, 0.22);

    // High shimmer, very short
    playTone("triangle", t0 + 0.014, t0 + 0.12, 1760, 1567.98, 0.08, 0.003, 0.12);

    // Tactile click — filtered noise burst
    const clickDur = 0.018;
    const buffer = ctx.createBuffer(1, Math.ceil(ctx.sampleRate * clickDur), ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i += 1) {
      const env = 1 - i / data.length;
      data[i] = (Math.random() * 2 - 1) * env * env;
    }
    const noise = ctx.createBufferSource();
    noise.buffer = buffer;
    const clickFilter = ctx.createBiquadFilter();
    clickFilter.type = "bandpass";
    clickFilter.frequency.value = 2200;
    clickFilter.Q.value = 0.9;
    const clickGain = ctx.createGain();
    clickGain.gain.setValueAtTime(0.16, t0);
    clickGain.gain.exponentialRampToValueAtTime(0.0001, t0 + clickDur);
    noise.connect(clickFilter);
    clickFilter.connect(clickGain);
    clickGain.connect(master);
    noise.start(t0);
    noise.stop(t0 + clickDur + 0.01);
  } catch {
    /* audio optional */
  }
}

async function completeTaskItem(completeBtn) {
  if (completeBtn.classList.contains("done")) return;
  const item = completeBtn.closest(".item");
  const id = completeBtn.dataset.complete;

  playCompleteSound();
  completeBtn.classList.add("done");
  item.classList.add("item-completing");

  try {
    await api(`/api/tasks/${id}/complete`, { method: "POST" });
  } catch {
    completeBtn.classList.remove("done");
    item.classList.remove("item-completing");
    return;
  }

  window.setTimeout(async () => {
    await loadTasks(state.view);
  }, 320);
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
    await loadProjectsCache();
    setView("today");
  } catch {
    $("login-error").classList.remove("hidden");
  }
});

$("nav").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-view]");
  if (!btn || btn.closest("#project-nav")) return;
  setView(btn.dataset.view);
});

$("project-nav").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-project-id]");
  if (!btn) return;
  setView("project", { projectId: Number(btn.dataset.projectId) });
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
  const parsed = parseTaskInput($("task-title").value);
  const kind = parsed.meta.kind || $("task-kind").value;
  let due = parsed.meta.due || $("task-due").value || null;
  if (kind === "task" && !due && state.view === "today") due = todayIso();
  const remind = $("task-remind").value ? new Date($("task-remind").value).toISOString() : null;
  const priority = parsed.meta.priority || Number($("task-priority").value);
  const title = parsed.cleanTitle || $("task-title").value.trim();
  const labelsNote = parsed.meta.labels?.length ? `Метки: ${parsed.meta.labels.join(", ")}` : "";
  await api("/api/tasks", {
    method: "POST",
    body: JSON.stringify({
      title,
      notes: labelsNote,
      kind,
      priority,
      due_at: due,
      remind_at: remind,
      project_id: parsed.meta.projectId || (state.view === "project" ? state.projectId : null) || null,
    }),
  });
  $("task-title").value = "";
  syncTaskTitleHighlight();
  updateTaskChips();
  if (kind === "idea" || kind === "plan") {
    const ideas = state.projects.find((p) => p.name === "Идеи");
    if (ideas) setView("project", { projectId: ideas.id });
    else await refresh();
  } else {
    await refresh();
  }
});

$("task-list").addEventListener("click", async (e) => {
  const complete = e.target.closest("[data-complete]");
  const del = e.target.closest("[data-del-task]");
  const promote = e.target.closest("[data-promote]");
  if (complete) {
    await completeTaskItem(complete);
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
  initTaskTitleHighlight();
  if (!state.token) {
    showLogin();
    return;
  }
  try {
    await api("/api/health");
    // validate token via protected endpoint
    await api("/api/projects");
    await loadProjectsCache();
    showApp();
    track("app_opened", "ui", null, { path: location.pathname });
    setView("today");
  } catch {
    showLogin();
  }
}

boot();

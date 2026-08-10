const TOKEN_KEY = "notetask_token";
const SIDEBAR_KEY = "notetask_sidebar_collapsed";
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
  workProjects: [],
  panelKind: null,
  healthSelected: "chest",
  motion: { enterId: null, completeId: null, pulseId: null },
};

const SECTION_PANELS = {
  "Личные дела": "finance",
  Работа: "work",
  Здоровье: "health",
  Тренировки: "workout",
};

const HEALTH_REGIONS = [
  { id: "head", label: "Голова" },
  { id: "chest", label: "Грудь" },
  { id: "arms", label: "Руки" },
  { id: "stomach", label: "Живот" },
  { id: "back", label: "Спина" },
  { id: "legs", label: "Ноги" },
];

const HEALTH_METRIC_FIELDS = [
  { key: "weight", label: "Вес" },
  { key: "height", label: "Рост" },
  { key: "sleep", label: "Сон" },
  { key: "pressure", label: "Давление" },
  { key: "pulse", label: "Пульс" },
  { key: "mood", label: "Самочувствие" },
];

const titles = {
  today: "Сегодня",
  history: "История",
  stats: "Статистика",
  project: "Раздел",
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

const MOTION = {
  out: 220,
  move: 240,
  enter: 320,
  complete: 340,
  pulse: 360,
};

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function waitMs(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function animateLeave(el, kind = "out") {
  if (!el) return;
  if (prefersReducedMotion()) {
    el.classList.add("anim-gone");
    return;
  }
  el.classList.remove("anim-enter", "anim-pulse", "item-completing", "item-slide-down");
  el.classList.add(`anim-${kind}`);
  await waitMs(MOTION[kind] || MOTION.out);
  el.classList.add("anim-gone");
}

function applyListMotion(root, selector = ".item, .note-card, .work-item, .goal-item") {
  const { enterId, completeId, pulseId } = state.motion;
  state.motion.enterId = null;
  state.motion.completeId = null;
  state.motion.pulseId = null;
  if (!root || prefersReducedMotion()) return;
  if (enterId == null && completeId == null && pulseId == null) return;
  root.querySelectorAll(selector).forEach((el) => {
    const id = el.dataset.id || el.dataset.workId || el.dataset.goalId || el.dataset.noteId;
    if (enterId != null && String(id) === String(enterId)) el.classList.add("anim-enter-strong");
    if (completeId != null && String(id) === String(completeId)) el.classList.add("item-slide-down");
    if (pulseId != null && String(id) === String(pulseId)) el.classList.add("anim-pulse");
  });
}

function findTaskItem(taskId) {
  return document.querySelector(`.item[data-id="${taskId}"]`);
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

const CHIP_ICON = {
  project: '<svg viewBox="0 0 16 16" width="13" height="13"><path fill="currentColor" d="M2 4.5h5v7H2v-7zm7 0h5v7H9v-7z"/></svg>',
  priority: '<svg viewBox="0 0 16 16" width="13" height="13"><path fill="currentColor" d="M3 2.5l5 2.8 5-2.8v11L8 10.7 3 13.5V2.5z"/></svg>',
  time: '<svg viewBox="0 0 16 16" width="13" height="13"><path fill="currentColor" d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zm0 1.2a5.3 5.3 0 1 1 0 10.6 5.3 5.3 0 0 1 0-10.6zm.6 2.5v3.2l2.4 1.4-.6 1-3-1.8V5.2h1.2z"/></svg>',
  location: '<svg viewBox="0 0 16 16" width="13" height="13"><path fill="currentColor" d="M8 1.2a4.8 4.8 0 0 0-4.8 4.8c0 3.6 4.8 8.8 4.8 8.8s4.8-5.2 4.8-8.8A4.8 4.8 0 0 0 8 1.2zm0 6.5a1.7 1.7 0 1 1 0-3.4 1.7 1.7 0 0 1 0 3.4z"/></svg>',
  cost: '<svg viewBox="0 0 16 16" width="13" height="13"><path fill="currentColor" d="M2.5 4.5h11v7h-11v-7zm1.5 1.5v4h8V6h-8zm2 3.5H5V7h1v2.5zm3 0H8V7h1.5v2.5z"/></svg>',
  work: '<svg viewBox="0 0 16 16" width="13" height="13"><path fill="currentColor" d="M5 3.5h6l.8 1.5H14v8H2v-8h2.2L5 3.5zm1.2 1.5-.5 1H10.3l-.5-1H6.2zM3.5 7v4.5h9V7h-9z"/></svg>',
};

const RU_MONTHS = {
  янв: 0, январ: 0,
  фев: 1, феврал: 1,
  мар: 2, март: 2,
  апр: 3, апрел: 3,
  май: 4, мая: 4, мае: 4,
  июн: 5, июнь: 5, июня: 5, июне: 5,
  июл: 6, июль: 6, июля: 6, июле: 6,
  авг: 7, август: 7,
  сен: 8, сент: 8, сентябр: 8,
  окт: 9, октябр: 9,
  ноя: 10, нояб: 10,
  дек: 11, декабр: 11,
};

const RU_WEEKDAYS = [
  { re: /воскресен/, dow: 0 },
  { re: /понедельник/, dow: 1 },
  { re: /вторник/, dow: 2 },
  { re: /сред/, dow: 3 },
  { re: /четверг/, dow: 4 },
  { re: /пятниц/, dow: 5 },
  { re: /суббот/, dow: 6 },
];

const MONTH_NAME_RE =
  "январ[ьяе]|феврал[ьяе]|март[ае]?|апрел[ьяе]|ма[йяе]|июн[ьяе]|июл[ьяе]|август[ае]?|сентябр[ьяе]|октябр[ьяе]|ноябр[ьяе]|декабр[ьяе]";
const WEEKDAY_NAME_RE =
  "понедельник|вторник|сред[ауые]|четверг|пятниц[ауые]|суббот[ауые]|воскресень[еяю]";

function ruTokenRe(body, flags = "giu") {
  const f = flags.includes("u") ? flags : `${flags}u`;
  return new RegExp(`(?<![\\p{L}\\p{N}_])(?:${body})(?![\\p{L}\\p{N}_])`, f);
}

function addDays(base, days) {
  const d = new Date(base);
  d.setDate(d.getDate() + days);
  return d;
}

function toIsoDate(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function nextWeekdayDate(dow, from = new Date()) {
  const now = new Date(from);
  now.setHours(12, 0, 0, 0);
  const add = (dow - now.getDay() + 7) % 7;
  return toIsoDate(addDays(now, add));
}

function resolveMonthIndex(word) {
  const w = String(word || "").toLowerCase();
  const keys = Object.keys(RU_MONTHS).sort((a, b) => b.length - a.length);
  const key = keys.find((k) => w === k || w.startsWith(k));
  return key == null ? null : RU_MONTHS[key];
}

function nextMonthDate(monthIndex, day = 1, from = new Date()) {
  const now = new Date(from);
  now.setHours(12, 0, 0, 0);
  let year = now.getFullYear();
  let candidate = new Date(year, monthIndex, day, 12, 0, 0, 0);
  if (candidate < now) {
    year += 1;
    candidate = new Date(year, monthIndex, day, 12, 0, 0, 0);
  }
  return toIsoDate(candidate);
}

function quickDueDate(kind) {
  const now = new Date();
  now.setHours(12, 0, 0, 0);
  switch (kind) {
    case "tomorrow":
      return toIsoDate(addDays(now, 1));
    case "weekend": {
      const day = now.getDay();
      if (day === 6 || day === 0) return toIsoDate(now);
      return toIsoDate(addDays(now, 6 - day));
    }
    case "next_week": {
      const day = now.getDay();
      const add = day === 0 ? 1 : 8 - day;
      return toIsoDate(addDays(now, add));
    }
    case "next_month": {
      const d = new Date(now);
      d.setMonth(d.getMonth() + 1);
      return toIsoDate(d);
    }
    default:
      return null;
  }
}

function quickDueButtonsHtml() {
  return `
    <div class="due-quick">
      <button type="button" class="chip-option" data-quick-due="tomorrow">Завтра</button>
      <button type="button" class="chip-option" data-quick-due="weekend">На выходных</button>
      <button type="button" class="chip-option" data-quick-due="next_week">На след. неделе</button>
      <button type="button" class="chip-option" data-quick-due="next_month">Через месяц</button>
    </div>`;
}

function parseDateToken(text) {
  const lower = text.toLowerCase().trim().replace(/\s+/g, " ");
  const now = new Date();
  now.setHours(12, 0, 0, 0);
  if (/^(?:сегодня|today)$/.test(lower)) return toIsoDate(now);
  if (/^(?:завтра|tomorrow)$/.test(lower)) return toIsoDate(addDays(now, 1));
  if (/^послезавтра$/.test(lower)) return toIsoDate(addDays(now, 2));
  if (/^(?:на\s+выходн(?:ых|ой)|в\s+выходн(?:ые|ой))$/.test(lower)) return quickDueDate("weekend");
  if (/^(?:на\s+след(?:ующей|\.)?\s+неделе|следующая\s+неделя)$/.test(lower)) return quickDueDate("next_week");
  if (/^(?:через\s+месяц|на\s+след(?:ующий|\.)?\s+месяц)$/.test(lower)) return quickDueDate("next_month");

  const inDays = lower.match(/^через\s+(\d+)\s*(?:дн(?:я|ей|ь)?|d)$/);
  if (inDays) return toIsoDate(addDays(now, Number(inDays[1])));

  const inWeeks = lower.match(/^через\s+(\d+)\s*(?:недел(?:ю|и|ь)?|нед\.?|w)$/);
  if (inWeeks) return toIsoDate(addDays(now, Number(inWeeks[1]) * 7));

  const inMonths = lower.match(/^через\s+(\d+)\s*(?:месяц(?:а|ев)?|мес\.?|m)$/);
  if (inMonths) {
    const d = new Date(now);
    d.setMonth(d.getMonth() + Number(inMonths[1]));
    return toIsoDate(d);
  }

  if (/^через\s+неделю$/.test(lower)) return toIsoDate(addDays(now, 7));

  const weekday = lower.match(new RegExp(`^(?:во?|к)?\\s*(${WEEKDAY_NAME_RE})$`));
  if (weekday) {
    const hit = RU_WEEKDAYS.find((w) => w.re.test(weekday[1]));
    if (hit) return nextWeekdayDate(hit.dow, now);
  }

  const iso = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;

  const dmy = text.match(/^(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?$/);
  if (dmy) {
    const day = Number(dmy[1]);
    const month = Number(dmy[2]) - 1;
    let year = dmy[3] ? Number(dmy[3]) : now.getFullYear();
    if (year < 100) year += 2000;
    return toIsoDate(new Date(year, month, day, 12, 0, 0, 0));
  }

  const named = lower.match(/^(\d{1,2})\s+([a-zа-яё]+)$/);
  if (named) {
    const day = Number(named[1]);
    const monthIndex = resolveMonthIndex(named[2]);
    if (monthIndex != null) return nextMonthDate(monthIndex, day, now);
  }

  const bareMonth = lower.match(new RegExp(`^(?:во?|к)?\\s*(${MONTH_NAME_RE})$`));
  if (bareMonth) {
    const monthIndex = resolveMonthIndex(bareMonth[1]);
    if (monthIndex != null) return nextMonthDate(monthIndex, 1, now);
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
      re: ruTokenRe("сегодня|today|завтра|tomorrow|послезавтра"),
      meta: (m) => ({ due: parseDateToken(m[0]) }),
    },
    {
      type: "date",
      re: ruTokenRe("через\\s+\\d+\\s*(?:дн(?:я|ей|ь)?|недел(?:ю|и|ь)?|нед\\.?|месяц(?:а|ев)?|мес\\.?|[dwm])"),
      meta: (m) => ({ due: parseDateToken(m[0]) }),
    },
    {
      type: "date",
      re: ruTokenRe("через\\s+(?:неделю|месяц)"),
      meta: (m) => ({ due: parseDateToken(m[0]) }),
    },
    {
      type: "date",
      re: ruTokenRe("на\\s+след(?:ующей|\\.)?\\s+неделе"),
      meta: (m) => ({ due: parseDateToken(m[0]) }),
    },
    {
      type: "date",
      re: ruTokenRe("на\\s+след(?:ующий|\\.)?\\s+месяц"),
      meta: (m) => ({ due: parseDateToken(m[0]) }),
    },
    {
      type: "date",
      re: ruTokenRe("на\\s+выходн(?:ых|ой)|в\\s+выходн(?:ые|ой)"),
      meta: (m) => ({ due: parseDateToken(m[0]) }),
    },
    {
      type: "date",
      re: ruTokenRe("\\d{4}-\\d{2}-\\d{2}"),
      meta: (m) => ({ due: parseDateToken(m[0]) }),
    },
    {
      type: "date",
      re: ruTokenRe("\\d{1,2}[./]\\d{1,2}(?:[./]\\d{2,4})?"),
      meta: (m) => ({ due: parseDateToken(m[0]) }),
    },
    {
      type: "date",
      re: ruTokenRe(`\\d{1,2}\\s+(?:${MONTH_NAME_RE})`),
      meta: (m) => ({ due: parseDateToken(m[0]) }),
    },
    {
      type: "date",
      re: ruTokenRe(`(?:во?|к)\\s+(?:${WEEKDAY_NAME_RE})`),
      meta: (m) => ({ due: parseDateToken(m[0]) }),
    },
    {
      type: "date",
      re: ruTokenRe(WEEKDAY_NAME_RE),
      meta: (m) => ({ due: parseDateToken(m[0]) }),
    },
    {
      type: "date",
      re: ruTokenRe(`(?:во?|к)\\s+(?:${MONTH_NAME_RE})`),
      meta: (m) => ({ due: parseDateToken(m[0]) }),
    },
    {
      type: "date",
      re: ruTokenRe(MONTH_NAME_RE),
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
      re: ruTokenRe("идея|idea|план|plan"),
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

function highlightableTokens(tokens) {
  return tokens.filter((token) => {
    const m = token.meta || {};
    switch (token.type) {
      case "date":
        return !!m.due;
      case "priority":
        return m.priority != null;
      case "project":
        return !!m.projectName;
      case "label":
        return !!m.label;
      case "kind":
        return !!m.kind;
      default: {
        const _exhaustive = token.type;
        return false;
      }
    }
  });
}

function buildTaskHighlightHtml(text, tokens) {
  if (!text) return "";
  const marks = highlightableTokens(tokens);
  let html = "";
  let pos = 0;
  for (const token of marks) {
    if (token.start > pos) html += escapeHtml(text.slice(pos, token.start));
    html += `<span class="hl-${token.type}">${escapeHtml(text.slice(token.start, token.end))}</span>`;
    pos = token.end;
  }
  if (pos < text.length) html += escapeHtml(text.slice(pos));
  if (text.endsWith(" ")) html += "&nbsp;";
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
  if (!input) return;
  const parsed = parseTaskInput(input.value);
  applyParsedMeta(parsed.meta);
  if (layer) {
    layer.innerHTML = buildTaskHighlightHtml(input.value, parsed.tokens) || "";
    layer.scrollLeft = input.scrollLeft;
  }
  input.closest(".task-title-wrap")?.classList.toggle("has-value", !!input.value);
}

function initTaskTitleHighlight() {
  const input = $("task-title");
  if (!input) return;
  input.addEventListener("input", syncTaskTitleHighlight);
  input.addEventListener("scroll", () => {
    const layer = $("task-title-highlight");
    if (layer) layer.scrollLeft = input.scrollLeft;
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
  await loadWorkProjectsCache();
  syncWorkProjectChipVisibility();
}

function renderProjectNav() {
  const nav = $("project-nav");
  if (!nav) return;
  const sections = [...state.projects]
    .filter((p) => p.name !== "Inbox" || (p.open_count || 0) > 0)
    .sort((a, b) => a.sort - b.sort || a.id - b.id);
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

function inboxProject() {
  return state.projects.find((p) => p.name === "Inbox") || null;
}

function leaveEmptyInboxIfNeeded() {
  if (state.view !== "project" || !state.projectId) return false;
  const inbox = inboxProject();
  if (!inbox || inbox.id !== state.projectId) return false;
  if ((inbox.open_count || 0) > 0) return false;
  setView("today", { keepTaskForm: true });
  return true;
}

function workSectionId() {
  return state.projects.find((p) => p.name === "Работа")?.id ?? null;
}

function isWorkSectionId(projectId) {
  const wid = workSectionId();
  return wid != null && Number(projectId) === Number(wid);
}

async function loadWorkProjectsCache() {
  try {
    state.workProjects = await api("/api/work-projects");
  } catch {
    state.workProjects = [];
  }
  renderComposerWorkMenu();
}

function activeWorkProjects() {
  return (state.workProjects || []).filter((p) => p.status !== "done");
}

function workProjectTitle(id) {
  if (id == null || id === "") return "";
  const hit = (state.workProjects || []).find((p) => Number(p.id) === Number(id));
  return hit?.title || "";
}

function renderComposerWorkMenu() {
  const menu = $("pop-work");
  if (!menu) return;
  const selected = $("task-work-project")?.value || "";
  const items = activeWorkProjects();
  menu.innerHTML = [
    `<button type="button" class="chip-option${!selected ? " selected" : ""}" data-set-work-project="">Без проекта</button>`,
    ...items.map(
      (p) =>
        `<button type="button" class="chip-option${String(p.id) === String(selected) ? " selected" : ""}" data-set-work-project="${p.id}">${escapeHtml(p.title)}</button>`,
    ),
    items.length
      ? ""
      : `<div class="empty" style="padding:8px">Сначала добавь проект справа</div>`,
  ].join("");
}

function composerTargetProjectId() {
  const parsed = parseTaskInput($("task-title")?.value || "");
  if (parsed.meta.projectId) return parsed.meta.projectId;
  if (state.view === "project") return state.projectId;
  return null;
}

function syncWorkProjectChipVisibility() {
  const wrap = $("chip-work-wrap");
  if (!wrap) return;
  const show = isWorkSectionId(composerTargetProjectId()) || !!$("task-work-project")?.value;
  wrap.classList.toggle("hidden", !show);
  if (!show && $("task-work-project")) $("task-work-project").value = "";
  renderComposerWorkMenu();
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
  document.querySelectorAll(".chip-popover.is-open").forEach((el) => el.classList.remove("is-open"));
  document.querySelectorAll(".item.popover-open").forEach((el) => el.classList.remove("popover-open"));
}

function openChipPopover(btn, menu) {
  if (!menu) return;
  menu.classList.remove("hidden");
  btn.classList.add("active");
  btn.setAttribute("aria-expanded", "true");
  btn.closest(".chip-popover")?.classList.add("is-open");
  btn.closest(".item")?.classList.add("popover-open");
}

function toggleChipPopover(btn, menu) {
  const wasOpen = menu && !menu.classList.contains("hidden");
  closeTaskPopovers();
  if (menu && !wasOpen) openChipPopover(btn, menu);
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

  const location = $("task-location").value.trim();
  $("chip-location-label").textContent = location ? truncateText(location, 14) : "Место";
  $("chip-location").classList.toggle("has-value", !!location);

  const costRaw = $("task-cost").value;
  const costType = $("task-cost-type-value").value || "expense";
  const cost = costRaw ? Number(costRaw) : null;
  $("chip-cost-label").textContent = cost ? formatMoney(cost, costType) : "Сумма";
  $("chip-cost").classList.toggle("has-value", !!cost);
  $("chip-cost").classList.toggle("cost-expense", costType === "expense");
  $("chip-cost").classList.toggle("cost-income", costType === "income");
  document.querySelectorAll("[data-set-cost-type]").forEach((btn) => {
    btn.classList.toggle("selected", btn.dataset.setCostType === costType);
  });

  syncWorkProjectChipVisibility();
  const workId = $("task-work-project")?.value || "";
  const workTitle = workProjectTitle(workId);
  if ($("chip-work-label")) {
    $("chip-work-label").textContent = workTitle ? truncateText(workTitle, 14) : "Проект";
  }
  if ($("chip-work")) {
    $("chip-work").classList.toggle("has-value", !!workId);
  }
}

function initTaskMetaChips() {
  document.querySelectorAll(".chip-popover .chip-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const menu = btn.parentElement.querySelector(".chip-menu");
      toggleChipPopover(btn, menu);
      if (menu && !menu.classList.contains("hidden")) {
        const input = menu.querySelector("input");
        if (input && !["date", "time", "datetime-local"].includes(input.type)) {
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

  document.querySelectorAll("[data-composer-quick-due]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const date = quickDueDate(btn.dataset.composerQuickDue);
      if (!date) return;
      $("task-due").value = date;
      updateTaskChips();
      closeTaskPopovers();
    });
  });
  $("task-remind").addEventListener("change", updateTaskChips);
  $("task-location").addEventListener("input", updateTaskChips);
  $("task-cost").addEventListener("input", updateTaskChips);

  document.querySelectorAll("[data-set-cost-type]").forEach((btn) => {
    btn.addEventListener("click", () => {
      $("task-cost-type-value").value = btn.dataset.setCostType;
      updateTaskChips();
    });
  });

  document.querySelectorAll("[data-clear]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const el = $(btn.dataset.clear);
      if (el) el.value = "";
      updateTaskChips();
      closeTaskPopovers();
    });
  });

  $("pop-work")?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-set-work-project]");
    if (!btn) return;
    $("task-work-project").value = btn.dataset.setWorkProject || "";
    updateTaskChips();
    closeTaskPopovers();
  });

  document.addEventListener("click", (e) => {
    if (e.target.closest(".chip-popover, .chip-menu")) return;
    closeTaskPopovers();
  });
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

function hideTaskForm() {
  $("task-form").classList.add("hidden");
  $("task-add-trigger")?.classList.remove("hidden");
  closeTaskPopovers();
}

function setSidebarCollapsed(collapsed) {
  $("app").classList.toggle("sidebar-collapsed", collapsed);
  localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
  const btn = $("sidebar-toggle");
  if (!btn) return;
  btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
  btn.setAttribute("aria-label", collapsed ? "Показать меню" : "Скрыть меню");
  btn.title = collapsed ? "Показать меню" : "Скрыть меню";
}

function initSidebarToggle() {
  setSidebarCollapsed(localStorage.getItem(SIDEBAR_KEY) === "1");
  $("sidebar-toggle")?.addEventListener("click", () => {
    const collapsed = !$("app").classList.contains("sidebar-collapsed");
    setSidebarCollapsed(collapsed);
    track("sidebar_toggle", "ui", null, { collapsed });
  });
}

function showTaskForm() {
  $("task-form").classList.remove("hidden");
  $("task-add-trigger")?.classList.add("hidden");
  window.setTimeout(() => $("task-title").focus(), 30);
}

const DEFAULT_THEME = "#1f6b4a";

function hexToRgb(hex) {
  const raw = String(hex || "").replace("#", "").trim();
  if (raw.length !== 6) return { r: 31, g: 107, b: 74 };
  return {
    r: parseInt(raw.slice(0, 2), 16),
    g: parseInt(raw.slice(2, 4), 16),
    b: parseInt(raw.slice(4, 6), 16),
  };
}

function mixHex(hex, toward, amount) {
  const a = hexToRgb(hex);
  const t = hexToRgb(toward);
  const mix = (x, y) => Math.round(x + (y - x) * amount);
  const r = mix(a.r, t.r);
  const g = mix(a.g, t.g);
  const b = mix(a.b, t.b);
  return `#${[r, g, b].map((n) => n.toString(16).padStart(2, "0")).join("")}`;
}

function applySectionTheme(hex) {
  const color = hex || DEFAULT_THEME;
  const { r, g, b } = hexToRgb(color);
  const root = document.documentElement;
  root.style.setProperty("--accent", color);
  root.style.setProperty("--ok", color);
  root.style.setProperty("--accent-rgb", `${r}, ${g}, ${b}`);
  root.style.setProperty("--theme-glow", mixHex(color, "#ffffff", 0.78));
  root.style.setProperty("--theme-glow-2", mixHex(color, "#f7f4ec", 0.72));
  root.style.setProperty("--theme-wash", mixHex(color, "#ebe6da", 0.82));
  document.body.dataset.theme = color;
}

function currentPanelKind() {
  if (state.view !== "project" || !state.projectId) return null;
  const proj = state.projects.find((p) => p.id === state.projectId);
  return proj ? SECTION_PANELS[proj.name] || null : null;
}

function hideSectionPanel() {
  state.panelKind = null;
  const panel = $("section-panel");
  const main = document.querySelector(".main");
  if (panel) {
    panel.classList.add("hidden");
    $("section-panel-inner").innerHTML = "";
  }
  if (main) main.classList.remove("with-section-panel");
}

function monthLabel(ym) {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(y, m - 1, 1);
  return d.toLocaleDateString("ru-RU", { month: "long", year: "numeric" });
}

function moneyPlain(amount) {
  const n = Number(amount) || 0;
  return `${n.toLocaleString("ru-RU", { maximumFractionDigits: 2 })} ₽`;
}

async function loadSectionPanel() {
  const kind = currentPanelKind();
  const panel = $("section-panel");
  const main = document.querySelector(".main");
  if (!kind) {
    hideSectionPanel();
    return;
  }
  state.panelKind = kind;
  panel.classList.remove("hidden");
  main.classList.add("with-section-panel");
  $("section-panel-inner").innerHTML = `<p class="sp-sub">Загрузка…</p>`;
  try {
    if (kind === "finance") await renderFinancePanel();
    else if (kind === "work") await renderWorkPanel();
    else if (kind === "health") await renderHealthPanel();
    else if (kind === "workout") await renderWorkoutPanel();
  } catch (err) {
    $("section-panel-inner").innerHTML = `<p class="error">${escapeHtml(err.message || "Ошибка")}</p>`;
  }
}

async function renderFinancePanel() {
  const data = await api("/api/finance/months?months=6");
  const totals = data.totals || {};
  const bal = Number(totals.balance) || 0;
  const months = data.months || [];
  $("section-panel-inner").innerHTML = `
    <h2>Финансы</h2>
    <p class="sp-sub">Суммы из задач + ручные доп. по месяцам</p>
    <div class="sp-totals">
      <div class="sp-stat"><span class="label">Доход</span><span class="value pos">${escapeHtml(moneyPlain(totals.income))}</span></div>
      <div class="sp-stat"><span class="label">Расход</span><span class="value neg">${escapeHtml(moneyPlain(totals.expense))}</span></div>
      <div class="sp-stat"><span class="label">Баланс</span><span class="value ${bal >= 0 ? "pos" : "neg"}">${escapeHtml(moneyPlain(bal))}</span></div>
    </div>
    <p class="sp-sub">из задач: +${escapeHtml(moneyPlain(totals.task_income))} / −${escapeHtml(moneyPlain(totals.task_expense))}</p>
    ${months
      .map((m) => {
        const b = Number(m.balance) || 0;
        const hasManual =
          !!m.saved &&
          (Number(m.manual_income) || Number(m.manual_expense) || (m.notes || "").trim());
        return `
      <form class="finance-month" data-finance-month="${escapeAttr(m.year_month)}">
        <header>
          <div class="finance-month-head">
            <span class="ym">${escapeHtml(monthLabel(m.year_month))}</span>
            ${
              m.saved
                ? `<button type="button" class="btn ghost small btn-del" data-finance-delete title="Удалить ручные данные" aria-label="Удалить">×</button>`
                : ""
            }
          </div>
          <span class="hint">из задач: −${escapeHtml(moneyPlain(m.task_expense))} / +${escapeHtml(moneyPlain(m.task_income))}</span>
        </header>
        <div class="finance-sync-row">
          <span>Итого: <strong class="${b >= 0 ? "pos" : "neg"}">${escapeHtml(moneyPlain(b))}</strong></span>
          <button type="button" class="btn ghost small" data-finance-sync>Только из задач</button>
        </div>
        <div class="finance-fields">
          <label>Ещё доход <input type="number" name="income" min="0" step="0.01" value="${escapeAttr(String(m.manual_income ?? 0))}" /></label>
          <label>Ещё расход <input type="number" name="expense" min="0" step="0.01" value="${escapeAttr(String(m.manual_expense ?? 0))}" /></label>
        </div>
        <label>Заметки <textarea name="notes" rows="2">${escapeHtml(m.notes || "")}</textarea></label>
        <footer>
          <span class="hint">${hasManual ? "есть ручные правки" : "только задачи"}</span>
          <button class="btn" type="submit">Сохранить</button>
        </footer>
      </form>`;
      })
      .join("")}
  `;
}

async function renderWorkPanel() {
  const items = await api("/api/work-projects");
  $("section-panel-inner").innerHTML = `
    <h2>Проекты</h2>
    <p class="sp-sub">Рабочие проекты и статусы</p>
    ${
      items.length
        ? items
            .map(
              (p) => `
      <article class="work-item" data-work-id="${p.id}">
        <header>
          <div class="work-item-title">
            <strong>${escapeHtml(p.title)}</strong>
            <span class="status-pill ${escapeAttr(p.status)}">${escapeHtml(
                p.status === "active" ? "в работе" : p.status === "paused" ? "пауза" : "готово",
              )}</span>
          </div>
          <button type="button" class="btn ghost small btn-del" data-work-delete title="Удалить проект" aria-label="Удалить проект">×</button>
        </header>
        <div class="work-meta">
          ${p.client ? escapeHtml(p.client) : "без клиента"}
          ${p.budget != null ? ` · бюджет ${escapeHtml(moneyPlain(p.budget))}` : ""}
        </div>
        ${p.notes ? `<div class="work-meta">${escapeHtml(p.notes)}</div>` : ""}
        <div class="sp-actions">
          <button type="button" class="btn ghost" data-work-status="active">В работе</button>
          <button type="button" class="btn ghost" data-work-status="paused">Пауза</button>
          <button type="button" class="btn ghost" data-work-status="done">Готово</button>
        </div>
      </article>`,
            )
            .join("")
        : `<p class="empty" style="padding:0">Пока нет проектов — добавь ниже.</p>`
    }
    <form class="sp-form" id="work-form">
      <strong>Новый проект</strong>
      <label>Название <input name="title" required placeholder="Клиент / продукт" /></label>
      <div class="row">
        <label>Клиент <input name="client" placeholder="Компания" /></label>
        <label>Бюджет <input name="budget" type="number" min="0" step="0.01" placeholder="0" /></label>
      </div>
      <label>Заметки <textarea name="notes" rows="2" placeholder="Срок, контакт, суть"></textarea></label>
      <button class="btn" type="submit">Добавить</button>
    </form>
  `;
  applyListMotion($("section-panel-inner"), ".work-item");
}

function bodySvg(body) {
  const cls = (id) => {
    const st = (body[id] && body[id].status) || "ok";
    const active = state.healthSelected === id ? " active" : "";
    const tone = st === "warn" ? " warn" : st === "bad" ? " bad" : "";
    return `region${tone}${active}`;
  };
  return `
  <svg class="body-svg" viewBox="0 0 120 220" role="img" aria-label="Тело">
    <ellipse class="${cls("head")}" data-region="head" cx="60" cy="28" rx="22" ry="24"></ellipse>
    <rect class="${cls("chest")}" data-region="chest" x="38" y="54" width="44" height="42" rx="12"></rect>
    <rect class="${cls("arms")}" data-region="arms" x="12" y="58" width="18" height="58" rx="9"></rect>
    <rect class="${cls("arms")}" data-region="arms" x="90" y="58" width="18" height="58" rx="9"></rect>
    <rect class="${cls("stomach")}" data-region="stomach" x="40" y="98" width="40" height="34" rx="10"></rect>
    <rect class="${cls("back")}" data-region="back" x="48" y="88" width="24" height="16" rx="6" opacity="0.85"></rect>
    <rect class="${cls("legs")}" data-region="legs" x="40" y="134" width="16" height="70" rx="8"></rect>
    <rect class="${cls("legs")}" data-region="legs" x="64" y="134" width="16" height="70" rx="8"></rect>
  </svg>`;
}

async function renderHealthPanel(data) {
  const profile = data || (await api("/api/health-profile"));
  const metrics = profile.metrics || {};
  const body = profile.body || {};
  const selected = state.healthSelected;
  const region = body[selected] || { note: "", status: "ok" };
  const regionLabel = HEALTH_REGIONS.find((r) => r.id === selected)?.label || selected;
  $("section-panel-inner").innerHTML = `
    <h2>Здоровье</h2>
    <p class="sp-sub">Тело и характеристики — клик по зоне</p>
    <div class="health-layout">
      ${bodySvg(body)}
      <div class="health-region-edit" data-health-region="${escapeAttr(selected)}">
        <strong>${escapeHtml(regionLabel)}</strong>
        <label>Состояние
          <select name="status">
            <option value="ok"${region.status === "ok" ? " selected" : ""}>Норма</option>
            <option value="warn"${region.status === "warn" ? " selected" : ""}>Внимание</option>
            <option value="bad"${region.status === "bad" ? " selected" : ""}>Проблема</option>
          </select>
        </label>
        <label>Заметка <textarea name="note" rows="3">${escapeHtml(region.note || "")}</textarea></label>
        <button type="button" class="btn" id="health-save-region">Сохранить зону</button>
      </div>
    </div>
    <form class="sp-form" id="health-metrics-form">
      <strong>Характеристики</strong>
      <div class="health-metrics">
        ${HEALTH_METRIC_FIELDS.map(
          (f) => `
          <label>${escapeHtml(f.label)}
            <input name="${escapeAttr(f.key)}" value="${escapeAttr(metrics[f.key] || "")}" />
          </label>`,
        ).join("")}
      </div>
      <button class="btn" type="submit">Сохранить характеристики</button>
    </form>
  `;
}

async function renderWorkoutPanel() {
  const data = await api("/api/workout-panel");
  const stats = data.stats || {};
  const goals = data.goals || [];
  const recent = data.recent || [];
  $("section-panel-inner").innerHTML = `
    <h2>Тренировки</h2>
    <p class="sp-sub">Прогресс и цели</p>
    <div class="sp-totals">
      <div class="sp-stat"><span class="label">Сегодня</span><span class="value">${stats.workouts_today || 0}</span></div>
      <div class="sp-stat"><span class="label">30 дней</span><span class="value">${stats.workouts_30d || 0}</span></div>
      <div class="sp-stat"><span class="label">Целей</span><span class="value">${goals.length}</span></div>
    </div>
    ${
      goals.length
        ? goals
            .map((g) => {
              const target = Number(g.target) || 0;
              const current = Number(g.current) || 0;
              const pct = target > 0 ? Math.min(100, Math.round((current / target) * 100)) : 0;
              return `
      <article class="goal-item" data-goal-id="${g.id}">
        <header>
          <strong>${escapeHtml(g.title)}</strong>
          <span class="status-pill">${escapeHtml(g.period === "week" ? "неделя" : g.period === "year" ? "год" : "месяц")}</span>
        </header>
        <div class="work-meta">${escapeHtml(String(current))} / ${escapeHtml(String(target))} ${escapeHtml(g.unit || "")}</div>
        <div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div>
        <div class="sp-actions">
          <button type="button" class="btn ghost" data-goal-inc>＋1</button>
          <button type="button" class="btn ghost" data-goal-delete>Удалить</button>
        </div>
      </article>`;
            })
            .join("")
        : `<p class="empty" style="padding:0">Целей пока нет.</p>`
    }
    <form class="sp-form" id="goal-form">
      <strong>Новая цель</strong>
      <label>Название <input name="title" required placeholder="Тренировок в месяц" /></label>
      <div class="row">
        <label>Цель <input name="target" type="number" min="0" step="1" value="12" /></label>
        <label>Сейчас <input name="current" type="number" min="0" step="1" value="0" /></label>
      </div>
      <div class="row">
        <label>Ед. <input name="unit" placeholder="раз" /></label>
        <label>Период
          <select name="period">
            <option value="week">Неделя</option>
            <option value="month" selected>Месяц</option>
            <option value="year">Год</option>
          </select>
        </label>
      </div>
      <button class="btn" type="submit">Добавить цель</button>
    </form>
    <div>
      <strong>Недавние</strong>
      <div class="recent-list">
        ${
          recent.length
            ? recent
                .map(
                  (r) => `
          <div>
            <span>${escapeHtml(r.title || "Тренировка")}</span>
            <span>${escapeHtml((r.started_at || "").slice(0, 10))} · ${r.sets_count || 0} подх.</span>
          </div>`,
                )
                .join("")
            : `<div><span>Пока пусто</span></div>`
        }
      </div>
    </div>
  `;
  applyListMotion($("section-panel-inner"), ".goal-item");
}

function setView(view, opts = {}) {
  if (!opts.keepTaskForm) hideTaskForm();
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
    $("view-title").textContent = proj?.name === "Inbox" ? "Разобрать" : (proj?.name || titles.project);
    applySectionTheme(proj?.color || DEFAULT_THEME);
  } else {
    $("view-title").textContent = titles[view] || "";
    applySectionTheme(DEFAULT_THEME);
  }

  const taskViews = ["today", "project"];
  $("view-tasks").classList.toggle("hidden", !taskViews.includes(view));
  $("view-notes").classList.add("hidden");
  $("view-workouts").classList.add("hidden");
  $("view-history").classList.toggle("hidden", view !== "history");
  $("view-stats").classList.toggle("hidden", view !== "stats");

  if (!taskViews.includes(view) || !currentPanelKind()) hideSectionPanel();

  if (taskViews.includes(view)) $("task-kind").value = "task";

  const dueInput = $("task-due");
  if (view === "today") dueInput.value = todayIso();
  else if (view === "project") dueInput.value = "";

  updateTaskChips();
  syncWorkProjectChipVisibility();
  const main = document.querySelector(".main");
  if (main && !prefersReducedMotion()) {
    main.classList.remove("view-swap");
    void main.offsetWidth;
    main.classList.add("view-swap");
  }
  track("view_opened", "ui", null, { view, project_id: state.projectId });
  refresh();
}

async function refresh() {
  const v = state.view;
  if (["today", "project"].includes(v)) {
    await loadProjectsCache();
    if (leaveEmptyInboxIfNeeded()) return;
    await loadTasks(v);
    await loadSectionPanel();
  } else if (v === "history") await loadHistory();
  else if (v === "stats") await loadStats();
}

function priorityBadge(p) {
  if (p === 1) return '<span class="badge p1">P1</span>';
  if (p === 2) return '<span class="badge p2">P2</span>';
  return `<span class="badge">P${p}</span>`;
}

function truncateText(str, max) {
  const s = String(str || "").trim();
  if (s.length <= max) return s;
  return `${s.slice(0, max - 1)}…`;
}

function formatMoney(amount, type = "expense") {
  const n = Number(amount);
  if (!Number.isFinite(n) || n === 0) return "—";
  const formatted = n.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
  return type === "income" ? `+${formatted} ₽` : `−${formatted} ₽`;
}

function taskDueParts(task) {
  if (!task.due_at) return { date: "", time: "" };
  return {
    date: task.due_at.slice(0, 10),
    time: task.due_at.includes("T") ? task.due_at.slice(11, 16) : "",
  };
}

function mergeTaskDue(date, time) {
  if (!date) return null;
  if (time) {
    const d = new Date(`${date}T${time}:00`);
    return Number.isNaN(d.getTime()) ? date : d.toISOString();
  }
  return date;
}

async function patchTask(taskId, patch) {
  const item = findTaskItem(taskId);
  const leavesView =
    item &&
    state.view === "project" &&
    patch.project_id !== undefined &&
    Number(patch.project_id) !== Number(state.projectId);
  if (leavesView) await animateLeave(item, "move");
  else if (item && (patch.priority != null || patch.due_at !== undefined || patch.work_project_id !== undefined)) {
    state.motion.pulseId = taskId;
  }
  await api(`/api/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(patch) });
  await refresh();
}

function renderTaskAttrs(t, projectMap) {
  const due = taskDueParts(t);
  const projectName = t.project_id ? projectMap[t.project_id] || "Раздел" : "Раздел";
  const hasProject = !!t.project_id;
  const hasPriority = t.priority !== 4;
  const hasDue = !!due.date || !!due.time;
  const hasLocation = !!t.location;
  const hasCost = t.cost != null && Number(t.cost) !== 0;
  const costType = t.cost_type === "income" ? "income" : "expense";
  const dueLabel = due.date ? fmtShortDay(due.date) : "Срок";
  const showWork = isWorkSectionId(t.project_id) || t.work_project_id != null;
  const workTitle = workProjectTitle(t.work_project_id);
  const hasWork = !!t.work_project_id;

  const projects = [...state.projects].sort((a, b) => a.sort - b.sort || a.id - b.id);
  const projectOptions = [
    `<button type="button" class="chip-option${!t.project_id ? " selected" : ""}" data-task-patch='{"project_id":null,"work_project_id":null}'>Без раздела</button>`,
    ...projects.map(
      (p) =>
        `<button type="button" class="chip-option${t.project_id === p.id ? " selected" : ""}" data-task-patch='{"project_id":${p.id}${p.name === "Работа" ? "" : ',"work_project_id":null'}}'><span class="project-dot" style="background:${escapeAttr(p.color)}"></span>${escapeHtml(p.name)}</button>`,
    ),
  ].join("");

  const workOptions = [
    `<button type="button" class="chip-option${!t.work_project_id ? " selected" : ""}" data-task-patch='{"work_project_id":null}'>Без проекта</button>`,
    ...activeWorkProjects().map(
      (p) =>
        `<button type="button" class="chip-option${Number(t.work_project_id) === Number(p.id) ? " selected" : ""}" data-task-patch='{"work_project_id":${p.id}}'>${escapeHtml(p.title)}</button>`,
    ),
    // include current if done/deleted from active list
    ...(t.work_project_id && !activeWorkProjects().some((p) => Number(p.id) === Number(t.work_project_id)) && workTitle
      ? [`<button type="button" class="chip-option selected" data-task-patch='{"work_project_id":${t.work_project_id}}'>${escapeHtml(workTitle)}</button>`]
      : []),
  ].join("");

  return `
    <div class="task-attrs" data-task-id="${t.id}">
      <div class="chip-popover">
        <button type="button" class="chip-btn${hasProject ? " has-value" : ""}" aria-expanded="false">
          <span class="chip-icon">${CHIP_ICON.project}</span>
          <span class="chip-label">${escapeHtml(truncateText(projectName, 12))}</span>
        </button>
        <div class="chip-menu chip-menu-wide hidden" role="menu">${projectOptions}</div>
      </div>
      ${
        showWork
          ? `<div class="chip-popover">
        <button type="button" class="chip-btn${hasWork ? " has-value" : ""}" aria-expanded="false">
          <span class="chip-icon">${CHIP_ICON.work}</span>
          <span class="chip-label">${escapeHtml(truncateText(workTitle || "Проект", 12))}</span>
        </button>
        <div class="chip-menu chip-menu-wide hidden" role="menu">${workOptions}</div>
      </div>`
          : ""
      }
      <div class="chip-popover">
        <button type="button" class="chip-btn${hasPriority ? " has-value" : ""}" aria-expanded="false">
          <span class="chip-icon">${CHIP_ICON.priority}</span>
          <span class="chip-label">P${t.priority}</span>
        </button>
        <div class="chip-menu hidden" role="menu">
          <div class="priority-picker">
            ${[4, 3, 2, 1]
              .map(
                (p) =>
                  `<button type="button" class="chip-option p${p}${t.priority === p ? " selected" : ""}" data-task-patch='{"priority":${p}}'>P${p}</button>`,
              )
              .join("")}
          </div>
        </div>
      </div>
      <div class="chip-popover">
        <button type="button" class="chip-btn${hasDue ? " has-value" : ""}" aria-expanded="false">
          <span class="chip-icon">${CHIP_ICON.time}</span>
          <span class="chip-label">${due.time || dueLabel}</span>
        </button>
        <div class="chip-menu chip-menu-wide hidden" role="dialog" aria-label="Срок и время">
          <input type="date" data-task-field="due-date" value="${escapeAttr(due.date)}" />
          <input type="time" data-task-field="due-time" value="${escapeAttr(due.time)}" />
          ${quickDueButtonsHtml()}
          <button type="button" class="chip-clear" data-task-clear-due>Без срока</button>
        </div>
      </div>
      <div class="chip-popover">
        <button type="button" class="chip-btn${hasLocation ? " has-value" : ""}" aria-expanded="false">
          <span class="chip-icon">${CHIP_ICON.location}</span>
          <span class="chip-label">${escapeHtml(truncateText(t.location, 12) || "Место")}</span>
        </button>
        <div class="chip-menu chip-menu-wide hidden" role="dialog" aria-label="Место">
          <input type="text" data-task-field="location" value="${escapeAttr(t.location || "")}" placeholder="Адрес, зал…" autocomplete="off" />
          <button type="button" class="chip-clear" data-task-clear-location>Без места</button>
        </div>
      </div>
      <div class="chip-popover">
        <button type="button" class="chip-btn ${costType}${hasCost ? " has-value" : ""}" aria-expanded="false">
          <span class="chip-icon">${CHIP_ICON.cost}</span>
          <span class="chip-label">${hasCost ? formatMoney(t.cost, costType) : "Сумма"}</span>
        </button>
        <div class="chip-menu chip-menu-wide hidden" role="dialog" aria-label="Сумма">
          <div class="cost-type-toggle">
            <button type="button" class="chip-option cost-expense${costType === "expense" ? " selected" : ""}" data-task-cost-type="expense">Расход</button>
            <button type="button" class="chip-option cost-income${costType === "income" ? " selected" : ""}" data-task-cost-type="income">Доход</button>
          </div>
          <input type="number" data-task-field="cost" min="0" step="0.01" value="${t.cost != null ? escapeAttr(String(t.cost)) : ""}" placeholder="0" inputmode="decimal" />
          <button type="button" class="chip-clear" data-task-clear-cost>Без суммы</button>
        </div>
      </div>
    </div>`;
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
  applyListMotion(root, ".item");
}

function renderTaskItem(t, view, projectMap) {
  const done = t.status === "done";
  const kind =
    t.kind === "idea"
      ? '<span class="badge idea">идея</span>'
      : t.kind === "plan"
        ? '<span class="badge idea">план</span>'
        : "";
  const promote =
    t.kind !== "task" && !done
      ? `<button class="btn ghost small" data-promote="${t.id}">В задачу</button>`
      : "";
  return `
      <div class="item${done ? " is-done" : ""}" data-id="${t.id}">
        <button class="check${done ? " done" : ""}" data-complete="${t.id}" aria-label="${done ? "Выполнено" : "Отметить выполненным"}"></button>
        <div class="item-body">
          <div class="item-title-row">
            <div class="item-title${done ? " done-title" : ""}">${escapeHtml(t.title)}</div>
            ${kind}
          </div>
          ${renderTaskAttrs(t, projectMap)}
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

    const playTone = (type, start, stop, freqStart, freqEnd, peak, attack) => {
      const osc = ctx.createOscillator();
      osc.type = type;
      osc.frequency.setValueAtTime(freqStart, start);
      osc.frequency.exponentialRampToValueAtTime(Math.max(20, freqEnd), Math.max(start + 0.01, stop - 0.01));
      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.linearRampToValueAtTime(peak, start + attack);
      gain.gain.exponentialRampToValueAtTime(0.0001, stop);
      osc.connect(gain);
      gain.connect(master);
      osc.start(start);
      osc.stop(stop + 0.01);
    };

    playTone("sine", t0, t0 + 0.18, 110, 55, 0.7, 0.004);
    playTone("triangle", t0, t0 + 0.1, 80, 40, 0.35, 0.003);

    const dur = 0.04;
    const buffer = ctx.createBuffer(1, Math.ceil(ctx.sampleRate * dur), ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i += 1) {
      const env = 1 - i / data.length;
      data[i] = (Math.random() * 2 - 1) * env * env;
    }
    const noise = ctx.createBufferSource();
    noise.buffer = buffer;
    const filter = ctx.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.value = 180;
    filter.Q.value = 0.5;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0.25, t0);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    noise.connect(filter);
    filter.connect(gain);
    gain.connect(master);
    noise.start(t0);
    noise.stop(t0 + dur + 0.01);
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
  if (item) item.classList.add("item-completing");

  try {
    await api(`/api/tasks/${id}/complete`, { method: "POST" });
  } catch {
    completeBtn.classList.remove("done");
    item?.classList.remove("item-completing");
    return;
  }

  state.motion.completeId = id;
  if (item) await animateLeave(item, "complete");
  await loadTasks(state.view);
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
  root.querySelectorAll(".note-card").forEach((el, i) => {
    const btn = el.querySelector("[data-del-note]");
    if (btn) el.dataset.noteId = btn.dataset.delNote;
  });
  applyListMotion(root, ".note-card");
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
  applyListMotion(root, ".item");
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

  const fin = s.finance || { expense_30d: 0, income_30d: 0, balance_30d: 0, entries: [] };
  $("finance-cards").innerHTML = `
    <div class="stat"><div class="n">${Number(fin.expense_30d || 0).toLocaleString("ru-RU")} ₽</div><div class="l">Расходы 30д</div></div>
    <div class="stat"><div class="n">${Number(fin.income_30d || 0).toLocaleString("ru-RU")} ₽</div><div class="l">Доходы 30д</div></div>
    <div class="stat"><div class="n">${formatMoney(Math.abs(fin.balance_30d || 0), fin.balance_30d >= 0 ? "income" : "expense")}</div><div class="l">Баланс 30д</div></div>`;

  const projectMap = Object.fromEntries(state.projects.map((p) => [p.id, p.name]));
  $("finance-list").innerHTML = fin.entries?.length
    ? fin.entries
        .map((e) => {
          const type = e.cost_type === "income" ? "income" : "expense";
          const meta = [
            e.due_at ? fmtShortDay(e.due_at.slice(0, 10)) : "",
            e.location ? truncateText(e.location, 24) : "",
            e.project_id ? projectMap[e.project_id] : "",
          ]
            .filter(Boolean)
            .join(" · ");
          return `<div class="finance-item">
            <div class="finance-item-title">${escapeHtml(e.title)}</div>
            <div class="finance-amount ${type}">${formatMoney(e.cost, type)}</div>
            ${meta ? `<div class="finance-item-meta">${escapeHtml(meta)}</div>` : ""}
          </div>`;
        })
        .join("")
    : '<div class="empty">Нет сумм в задачах. Укажи «Сумма» в плашке под задачей.</div>';
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
  setView("today", { keepTaskForm: true });
  showTaskForm();
  const panel = $("view-tasks");
  panel.classList.add("capture-focus");
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
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

$("task-add-trigger").addEventListener("click", () => {
  if (!["today", "project"].includes(state.view)) setView("today", { keepTaskForm: true });
  showTaskForm();
});

$("task-title").addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !e.target.value.trim()) hideTaskForm();
});

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
  const location = $("task-location").value.trim() || null;
  const costVal = $("task-cost").value ? Number($("task-cost").value) : null;
  const costType = costVal ? $("task-cost-type-value").value || "expense" : null;
  const created = await api("/api/tasks", {
    method: "POST",
    body: JSON.stringify({
      title,
      notes: labelsNote,
      kind,
      priority,
      due_at: due,
      remind_at: remind,
      project_id: parsed.meta.projectId || (state.view === "project" ? state.projectId : null) || null,
      location,
      cost: costVal,
      cost_type: costType,
      work_project_id: (() => {
        const pid = parsed.meta.projectId || (state.view === "project" ? state.projectId : null) || null;
        if (!isWorkSectionId(pid)) return null;
        const raw = $("task-work-project").value;
        return raw ? Number(raw) : null;
      })(),
    }),
  });
  if (created?.id) state.motion.enterId = created.id;

  $("task-title").value = "";
  $("task-location").value = "";
  $("task-cost").value = "";
  $("task-cost-type-value").value = "expense";
  $("task-work-project").value = "";
  syncTaskTitleHighlight();
  updateTaskChips();
  hideTaskForm();
  if (kind === "idea" || kind === "plan") {
    const ideas = state.projects.find((p) => p.name === "Идеи");
    if (ideas) setView("project", { projectId: ideas.id });
    else await refresh();
  } else {
    await refresh();
  }
});

$("task-list").addEventListener("mousedown", (e) => {
  if (e.target.closest(".chip-menu, .chip-popover")) e.stopPropagation();
});

$("task-list").addEventListener("click", async (e) => {
  const attrsRoot = e.target.closest(".task-attrs");
  if (attrsRoot) {
    const patchBtn = e.target.closest("[data-task-patch]");
    if (patchBtn) {
      e.stopPropagation();
      await patchTask(Number(attrsRoot.dataset.taskId), JSON.parse(patchBtn.dataset.taskPatch));
      closeTaskPopovers();
      return;
    }
    const costTypeBtn = e.target.closest("[data-task-cost-type]");
    if (costTypeBtn) {
      e.stopPropagation();
      attrsRoot.querySelectorAll("[data-task-cost-type]").forEach((b) => {
        b.classList.toggle("selected", b === costTypeBtn);
      });
      const costInput = attrsRoot.querySelector('[data-task-field="cost"]');
      const cost = costInput?.value ? Number(costInput.value) : null;
      if (cost) {
        await patchTask(Number(attrsRoot.dataset.taskId), {
          cost_type: costTypeBtn.dataset.taskCostType,
          cost,
        });
      }
      return;
    }
    const quickDue = e.target.closest("[data-quick-due]");
    if (quickDue) {
      e.stopPropagation();
      const date = quickDueDate(quickDue.dataset.quickDue);
      if (!date) return;
      const timeInput = attrsRoot.querySelector('[data-task-field="due-time"]');
      await patchTask(Number(attrsRoot.dataset.taskId), {
        due_at: mergeTaskDue(date, timeInput?.value || ""),
      });
      closeTaskPopovers();
      return;
    }
    if (e.target.closest("[data-task-clear-due]")) {
      e.stopPropagation();
      await patchTask(Number(attrsRoot.dataset.taskId), { due_at: null });
      closeTaskPopovers();
      return;
    }
    if (e.target.closest("[data-task-clear-location]")) {
      e.stopPropagation();
      await patchTask(Number(attrsRoot.dataset.taskId), { location: null });
      closeTaskPopovers();
      return;
    }
    if (e.target.closest("[data-task-clear-cost]")) {
      e.stopPropagation();
      await patchTask(Number(attrsRoot.dataset.taskId), { cost: null, cost_type: null });
      closeTaskPopovers();
      return;
    }
    const chipBtn = e.target.closest(".chip-btn");
    if (chipBtn) {
      e.stopPropagation();
      const menu = chipBtn.parentElement.querySelector(".chip-menu");
      toggleChipPopover(chipBtn, menu);
      return;
    }
    if (e.target.closest(".chip-menu, .chip-popover")) {
      e.stopPropagation();
      return;
    }
  }

  const complete = e.target.closest("[data-complete]");
  const del = e.target.closest("[data-del-task]");
  const promote = e.target.closest("[data-promote]");
  if (complete) {
    await completeTaskItem(complete);
  } else if (del) {
    const item = del.closest(".item");
    await animateLeave(item, "out");
    await api(`/api/tasks/${del.dataset.delTask}`, { method: "DELETE" });
    await refresh();
  } else if (promote) {
    const item = promote.closest(".item");
    state.motion.pulseId = promote.dataset.promote;
    if (item) item.classList.add("anim-pulse");
    await api(`/api/tasks/${promote.dataset.promote}/promote`, { method: "POST" });
    await refresh();
  }
});

$("task-list").addEventListener("change", async (e) => {
  const attrsRoot = e.target.closest(".task-attrs");
  if (!attrsRoot) return;
  const taskId = Number(attrsRoot.dataset.taskId);
  const field = e.target.dataset.taskField;
  if (field === "due-date" || field === "due-time") {
    const dateInput = attrsRoot.querySelector('[data-task-field="due-date"]');
    const timeInput = attrsRoot.querySelector('[data-task-field="due-time"]');
    await patchTask(taskId, { due_at: mergeTaskDue(dateInput.value, timeInput.value) });
    closeTaskPopovers();
    return;
  }
  if (field === "location") {
    await patchTask(taskId, { location: e.target.value.trim() || null });
    return;
  }
  if (field === "cost") {
    const typeBtn = attrsRoot.querySelector("[data-task-cost-type].selected");
    const costType = typeBtn?.dataset.taskCostType || "expense";
    const val = e.target.value ? Number(e.target.value) : null;
    await patchTask(taskId, { cost: val, cost_type: val ? costType : null });
    return;
  }
});

$("note-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const createdNote = await api("/api/notes", {
    method: "POST",
    body: JSON.stringify({
      title: $("note-title").value.trim(),
      body: $("note-body").value,
    }),
  });
  if (createdNote?.id) state.motion.enterId = createdNote.id;
  $("note-title").value = "";
  $("note-body").value = "";
  await refresh();
});

$("note-list").addEventListener("click", async (e) => {
  const del = e.target.closest("[data-del-note]");
  if (del) {
    const card = del.closest(".note-card");
    await animateLeave(card, "out");
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
    const item = del.closest(".item");
    await animateLeave(item, "out");
    await api(`/api/workouts/${del.dataset.delWo}`, { method: "DELETE" });
    await refresh();
  }
});

$("section-panel").addEventListener("submit", async (e) => {
  const financeForm = e.target.closest("[data-finance-month]");
  if (financeForm) {
    e.preventDefault();
    const ym = financeForm.dataset.financeMonth;
    const fd = new FormData(financeForm);
    await api(`/api/finance/months/${ym}`, {
      method: "PUT",
      body: JSON.stringify({
        income: Number(fd.get("income") || 0),
        expense: Number(fd.get("expense") || 0),
        notes: String(fd.get("notes") || ""),
      }),
    });
    await renderFinancePanel();
    return;
  }
  if (e.target.id === "work-form") {
    e.preventDefault();
    const fd = new FormData(e.target);
    const budgetRaw = fd.get("budget");
    const createdWp = await api("/api/work-projects", {
      method: "POST",
      body: JSON.stringify({
        title: String(fd.get("title") || "").trim(),
        client: String(fd.get("client") || "").trim(),
        budget: budgetRaw === "" || budgetRaw == null ? null : Number(budgetRaw),
        notes: String(fd.get("notes") || ""),
        status: "active",
      }),
    });
    if (createdWp?.id) state.motion.enterId = createdWp.id;
    await loadWorkProjectsCache();
    await renderWorkPanel();
    return;
  }
  if (e.target.id === "health-metrics-form") {
    e.preventDefault();
    const fd = new FormData(e.target);
    const metrics = {};
    for (const f of HEALTH_METRIC_FIELDS) metrics[f.key] = String(fd.get(f.key) || "");
    await api("/api/health-profile", { method: "PUT", body: JSON.stringify({ metrics, body: {} }) });
    await renderHealthPanel();
    return;
  }
  if (e.target.id === "goal-form") {
    e.preventDefault();
    const fd = new FormData(e.target);
    const createdGoal = await api("/api/workout-goals", {
      method: "POST",
      body: JSON.stringify({
        title: String(fd.get("title") || "").trim(),
        target: Number(fd.get("target") || 0),
        current: Number(fd.get("current") || 0),
        unit: String(fd.get("unit") || ""),
        period: String(fd.get("period") || "month"),
      }),
    });
    if (createdGoal?.id) state.motion.enterId = createdGoal.id;
    await renderWorkoutPanel();
  }
});

$("section-panel").addEventListener("click", async (e) => {
  const financeMonth = e.target.closest("[data-finance-month]");
  if (financeMonth) {
    const ym = financeMonth.dataset.financeMonth;
    if (e.target.closest("[data-finance-delete]")) {
      e.preventDefault();
      e.stopPropagation();
      if (!confirm(`Удалить ручные данные за ${monthLabel(ym)}? Суммы из задач останутся.`)) return;
      await animateLeave(financeMonth, "out");
      try {
        await api(`/api/finance/months/${ym}`, { method: "DELETE" });
      } catch (err) {
        const msg = String(err.message || "");
        if (!/404|not found/i.test(msg)) {
          alert(msg || "Не удалось удалить");
          await renderFinancePanel();
          return;
        }
      }
      await renderFinancePanel();
      return;
    }
    if (e.target.closest("[data-finance-sync]")) {
      e.preventDefault();
      e.stopPropagation();
      const fd = new FormData(financeMonth);
      await api(`/api/finance/months/${ym}`, {
        method: "PUT",
        body: JSON.stringify({
          income: 0,
          expense: 0,
          notes: String(fd.get("notes") || ""),
        }),
      });
      await renderFinancePanel();
      return;
    }
  }

  const regionEl = e.target.closest("[data-region]");
  if (regionEl) {
    state.healthSelected = regionEl.dataset.region;
    await renderHealthPanel();
    return;
  }
  if (e.target.id === "health-save-region") {
    const box = e.target.closest("[data-health-region]");
    if (!box) return;
    const region = box.dataset.healthRegion;
    const status = box.querySelector('[name="status"]')?.value || "ok";
    const note = box.querySelector('[name="note"]')?.value || "";
    await api("/api/health-profile", {
      method: "PUT",
      body: JSON.stringify({ metrics: {}, body: { [region]: { status, note } } }),
    });
    await renderHealthPanel();
    return;
  }
  const workItem = e.target.closest("[data-work-id]");
  if (workItem) {
    const id = Number(workItem.dataset.workId);
    if (e.target.closest("[data-work-delete]")) {
      e.preventDefault();
      e.stopPropagation();
      const title = workItem.querySelector("strong")?.textContent?.trim() || "проект";
      if (!confirm(`Удалить проект «${title}»?`)) return;
      await animateLeave(workItem, "out");
      try {
        await api(`/api/work-projects/${id}`, { method: "DELETE" });
      } catch (err) {
        alert(err.message || "Не удалось удалить");
        await renderWorkPanel();
        return;
      }
      await loadWorkProjectsCache();
      await renderWorkPanel();
      if (state.view === "project" && isWorkSectionId(state.projectId)) {
        await loadTasks(state.view);
      }
      return;
    }
    const statusBtn = e.target.closest("[data-work-status]");
    if (statusBtn) {
      const items = await api("/api/work-projects");
      const cur = items.find((x) => x.id === id);
      if (!cur) return;
      await api(`/api/work-projects/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: cur.title,
          status: statusBtn.dataset.workStatus,
          client: cur.client || "",
          budget: cur.budget,
          notes: cur.notes || "",
        }),
      });
      await loadWorkProjectsCache();
      await renderWorkPanel();
      return;
    }
  }
  const goalItem = e.target.closest("[data-goal-id]");
  if (goalItem) {
    const id = Number(goalItem.dataset.goalId);
    if (e.target.closest("[data-goal-delete]")) {
      await animateLeave(goalItem, "out");
      await api(`/api/workout-goals/${id}`, { method: "DELETE" });
      await renderWorkoutPanel();
      return;
    }
    if (e.target.closest("[data-goal-inc]")) {
      const panel = await api("/api/workout-panel");
      const g = (panel.goals || []).find((x) => x.id === id);
      if (!g) return;
      await api(`/api/workout-goals/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: g.title,
          target: g.target,
          unit: g.unit || "",
          current: Number(g.current || 0) + 1,
          period: g.period || "month",
        }),
      });
      await renderWorkoutPanel();
    }
  }
});

async function boot() {
  addWorkoutSetRow();
  $("wo-started").value = localInputValue();
  initTaskMetaChips();
  initTaskTitleHighlight();
  initSidebarToggle();
  hideTaskForm();
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

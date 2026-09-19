const TOKEN_KEY = "notetask_token";
const SIDEBAR_KEY = "notetask_sidebar_collapsed";
const SIDEBAR_WIDTH_KEY = "notetask_sidebar_width";
const SIDEBAR_WIDTH_MIN = 180;
const SIDEBAR_WIDTH_MAX = 400;
const SIDEBAR_WIDTH_DEFAULT = 240;
const SORT_KEY = "notetask_task_sort";
const LAN_ORIGIN = "http://192.168.0.6";
const BASE = window.NOTETASK_BASE ?? (() => {
  const path = window.location.pathname;
  if (path === "/todo" || path.startsWith("/todo/")) return "/todo";
  return "";
})();

function isDesktopClient() {
  try {
    if (sessionStorage.getItem("notetask_client") === "desktop") return true;
  } catch {
    /* ignore */
  }
  try {
    if (new URLSearchParams(location.search).get("client") === "desktop") return true;
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

/** Home Wi‑Fi hairpin bypass: public DNS + no NAT loopback → use LAN HTTP. */
function lanFallbackUrl() {
  const params = new URLSearchParams(location.search);
  if (isDesktopClient()) params.set("client", "desktop");
  const token = localStorage.getItem(TOKEN_KEY) || "";
  const q = params.toString();
  const hash = token ? `#restore=${encodeURIComponent(token)}` : location.hash || "";
  return `${LAN_ORIGIN}/${q ? `?${q}` : ""}${hash}`;
}

function consumeTokenRestore() {
  const m = /^#restore=(.+)$/.exec(location.hash || "");
  if (!m) return;
  try {
    localStorage.setItem(TOKEN_KEY, decodeURIComponent(m[1]));
  } catch {
    /* ignore */
  }
  history.replaceState(null, "", location.pathname + location.search);
}

function goLanFallback() {
  if (isLanHost()) return false;
  location.replace(lanFallbackUrl());
  return true;
}

const SORT_FIELDS = [
  { id: "due", label: "Срок" },
  { id: "priority", label: "Приоритет" },
  { id: "project", label: "Раздел" },
  { id: "amount", label: "Сумма" },
];

function loadTaskSort() {
  try {
    const raw = JSON.parse(localStorage.getItem(SORT_KEY) || "null");
    if (raw && SORT_FIELDS.some((f) => f.id === raw.field)) {
      return { field: raw.field, dir: raw.dir === "desc" ? "desc" : "asc" };
    }
  } catch {
    /* ignore */
  }
  return { field: "due", dir: "asc" };
}

function saveTaskSort() {
  try {
    localStorage.setItem(SORT_KEY, JSON.stringify(state.taskSort));
  } catch {
    /* ignore */
  }
}

const state = {
  view: "today",
  token: localStorage.getItem(TOKEN_KEY) || "",
  projects: [],
  projectId: null,
  workProjects: [],
  panelKind: null,
  healthSelected: "chest",
  motion: { enterId: null, completeId: null, pulseId: null },
  financeYm: null,
  financeSheet: null,
  financeLedger: null,
  financeLedgerFilters: {},
  financeDrafts: [],
  financeFilterOpenCol: null,
  financeSelectedRowKey: null,
  taskSort: loadTaskSort(),
  expandedTaskAttrs: new Set(),
};

const SECTION_PANELS = {
  "Личные дела": "finance",
  Работа: "work",
  Здоровье: "health",
  Тренировки: "workout",
};

const HEALTH_REGIONS = [
  { id: "head", label: "Голова" },
  { id: "hair", label: "Волосы" },
  { id: "eyes", label: "Глаза" },
  { id: "nose", label: "Нос" },
  { id: "ears", label: "Уши" },
  { id: "jaw", label: "Челюсть" },
  { id: "teeth", label: "Зубы" },
  { id: "neck", label: "Шея" },
  { id: "shoulders", label: "Плечи" },
  { id: "chest", label: "Грудь" },
  { id: "back", label: "Спина" },
  { id: "stomach", label: "Живот" },
  { id: "arms", label: "Руки" },
  { id: "elbows", label: "Локти" },
  { id: "wrists", label: "Запястья" },
  { id: "hands", label: "Кисти" },
  { id: "hips", label: "Таз" },
  { id: "legs", label: "Ноги" },
  { id: "thighs", label: "Бёдра" },
  { id: "knees", label: "Колени" },
  { id: "calves", label: "Голени" },
  { id: "feet", label: "Стопы" },
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
  goals: "Цели",
  finance: "Финансы",
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

const API_TIMEOUT_MS = 12000;

function isAuthError(err) {
  const msg = String(err?.message || err || "");
  return msg === "auth" || msg === "Auth required" || msg === "Invalid token";
}

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const url = path.startsWith("http") ? path : `${BASE}${path}`;
  let signal = opts.signal;
  let timer = null;
  if (!signal && typeof AbortController !== "undefined") {
    const ctrl = new AbortController();
    signal = ctrl.signal;
    timer = setTimeout(() => ctrl.abort(), API_TIMEOUT_MS);
  }
  let res;
  try {
    res = await fetch(url, { ...opts, headers, signal });
  } catch (ex) {
    if (ex?.name === "AbortError" || /Failed to fetch|NetworkError|Load failed/i.test(String(ex?.message || ""))) {
      throw new Error("network");
    }
    throw ex;
  } finally {
    if (timer) clearTimeout(timer);
  }
  if (res.status === 401) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail || "auth";
    // login 401 = wrong password; do not wipe UI mid-submit
    if (!String(path).includes("/api/login")) logout(false);
    throw new Error(typeof detail === "string" ? detail : "auth");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    if (res.status === 503 || err.detail === "offline") {
      throw new Error("network");
    }
    throw new Error(err.detail || res.statusText);
  }
  if (res.status === 204) return null;
  return res.json();
}

window.notetaskApi = api;

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
  $("login").removeAttribute("aria-hidden");
  $("app").classList.add("hidden");
  $("app").setAttribute("aria-hidden", "true");
}

function showApp() {
  $("login").classList.add("hidden");
  $("login").setAttribute("aria-hidden", "true");
  $("app").classList.remove("hidden");
  $("app").removeAttribute("aria-hidden");
}

const CLIENT_KEY = "notetask_client";

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

function hideDesktopDownloads() {
  if (!isDesktopClient()) return;
  ["login-download", "download-apps-btn"].forEach((id) => {
    const el = $(id);
    if (!el) return;
    el.hidden = true;
    el.style.display = "none";
  });
}

window.__notetaskAfterLogin = async (token) => {
  state.token = token;
  localStorage.setItem(TOKEN_KEY, state.token);
  showApp();
  hideDesktopDownloads();
  await loadProjectsCache();
  setView("today");
  await refresh();
  track("app_opened", "ui", null, { path: location.pathname, client: "login" });
};

const kindLabels = { task: "Задача", idea: "Идея", plan: "План" };

const CHIP_ICON = {
  project: '<svg viewBox="0 0 16 16" width="13" height="13"><path fill="currentColor" d="M2 4.5h5v7H2v-7zm7 0h5v7H9v-7z"/></svg>',
  priority: '<svg viewBox="0 0 16 16" width="13" height="13"><path fill="currentColor" d="M3 2.5l5 2.8 5-2.8v11L8 10.7 3 13.5V2.5z"/></svg>',
  time: '<svg viewBox="0 0 16 16" width="13" height="13"><path fill="currentColor" d="M8 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13zm0 1.2a5.3 5.3 0 1 1 0 10.6 5.3 5.3 0 0 1 0-10.6zm.6 2.5v3.2l2.4 1.4-.6 1-3-1.8V5.2h1.2z"/></svg>',
  location: '<svg viewBox="0 0 16 16" width="13" height="13"><path fill="currentColor" d="M8 1.2a4.8 4.8 0 0 0-4.8 4.8c0 3.6 4.8 8.8 4.8 8.8s4.8-5.2 4.8-8.8A4.8 4.8 0 0 0 8 1.2zm0 6.5a1.7 1.7 0 1 1 0-3.4 1.7 1.7 0 0 1 0 3.4z"/></svg>',
  cost: '<svg viewBox="0 0 16 16" width="13" height="13"><path fill="currentColor" d="M2.5 4.5h11v7h-11v-7zm1.5 1.5v4h8V6h-8zm2 3.5H5V7h1v2.5zm3 0H8V7h1.5v2.5z"/></svg>',
  work: '<svg viewBox="0 0 16 16" width="13" height="13"><path fill="currentColor" d="M5 3.5h6l.8 1.5H14v8H2v-8h2.2L5 3.5zm1.2 1.5-.5 1H10.3l-.5-1H6.2zM3.5 7v4.5h9V7h-9z"/></svg>',
  remind: '<svg viewBox="0 0 16 16" width="13" height="13"><path fill="currentColor" d="M8 1.5a4.5 4.5 0 0 0-4.5 4.5v2.1L2 10.5h12l-1.5-2.4V6A4.5 4.5 0 0 0 8 1.5zm-2.2 11h4.4a1.6 1.6 0 0 1-4.4 0z"/></svg>',
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
    case "today":
      return toIsoDate(now);
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

const REPEAT_OPTIONS = [
  { id: "", label: "Без повтора" },
  { id: "daily", label: "Каждый день" },
  { id: "every_2_days", label: "Каждые 2 дня" },
  { id: "every_3_days", label: "Каждые 3 дня" },
  { id: "weekdays", label: "По будням" },
  { id: "weekly", label: "Каждую неделю" },
  { id: "monthly", label: "Каждый месяц" },
];

function repeatLabel(rule) {
  const hit = REPEAT_OPTIONS.find((o) => o.id === (rule || ""));
  return hit ? hit.label : "Без повтора";
}

function quickDueButtonsHtml() {
  return `
    <div class="due-quick">
      <button type="button" class="chip-option" data-quick-due="today">Сегодня</button>
      <button type="button" class="chip-option" data-quick-due="tomorrow">Завтра</button>
      <button type="button" class="chip-option" data-quick-due="weekend">На выходных</button>
      <button type="button" class="chip-option" data-quick-due="next_week">На след. неделе</button>
      <button type="button" class="chip-option" data-quick-due="next_month">Через месяц</button>
    </div>`;
}

function taskRemindInputValue(task) {
  if (!task?.remind_at) return "";
  try {
    const d = new Date(task.remind_at);
    if (Number.isNaN(d.getTime())) return "";
    return localInputValue(d);
  } catch {
    return "";
  }
}

function nextHourBoundaryLocal(from = new Date()) {
  const d = new Date(from);
  d.setMinutes(0, 0, 0);
  if (from.getTime() > d.getTime()) d.setHours(d.getHours() + 1);
  return d;
}

function formatRemindChipLabel(task) {
  if (task?.remind_rule === "hourly") {
    if (task.remind_at) {
      try {
        const d = new Date(task.remind_at);
        if (!Number.isNaN(d.getTime())) {
          const pad = (n) => String(n).padStart(2, "0");
          return `Каждый час · ${pad(d.getHours())}:${pad(d.getMinutes())}`;
        }
      } catch (_) {}
    }
    return "Каждый час";
  }
  if (!task?.remind_at) return "";
  try {
    const d = new Date(task.remind_at);
    if (Number.isNaN(d.getTime())) return "";
    return fmtShortDateTime(task.remind_at);
  } catch (_) {
    return "";
  }
}

function remindAtIso(localValue) {
  if (!localValue) return null;
  const d = new Date(localValue);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

function dueAtForRemindPreset(dueAt) {
  if (!dueAt) return null;
  if (dueAt.includes("T")) return dueAt;
  const parts = taskDueParts({ due_at: dueAt });
  return mergeTaskDue(parts.date, parts.time || "09:00");
}

function computeRemindPreset(preset, dueAt) {
  const now = new Date();
  if (preset === "hourly") return nextHourBoundaryLocal(now).toISOString();
  if (preset === "15m") return new Date(now.getTime() + 15 * 60_000).toISOString();
  if (preset === "1h") return new Date(now.getTime() + 3600_000).toISOString();
  const dueIso = dueAtForRemindPreset(dueAt);
  if (!dueIso) return null;
  const dueDt = new Date(dueIso);
  if (Number.isNaN(dueDt.getTime())) return null;
  if (preset === "at_due") return dueDt.toISOString();
  if (preset === "before_1h") {
    dueDt.setMinutes(dueDt.getMinutes() - 60);
    return dueDt.toISOString();
  }
  return null;
}

function remindPresetButtonsHtml(attrName, selectedRule = "") {
  const hourlySel = selectedRule === "hourly" ? " selected" : "";
  return `
    <div class="due-quick">
      <button type="button" class="chip-option${hourlySel}" ${attrName}="hourly">Каждый час</button>
      <button type="button" class="chip-option" ${attrName}="15m">Через 15 мин</button>
      <button type="button" class="chip-option" ${attrName}="1h">Через 1 час</button>
      <button type="button" class="chip-option" ${attrName}="before_1h">За 1 час до срока</button>
      <button type="button" class="chip-option" ${attrName}="at_due">В момент срока</button>
    </div>`;
}

function repeatButtonsHtml(selected) {
  const cur = selected || "";
  return `
    <div class="due-repeat">
      <div class="due-section-label">Расписание</div>
      ${REPEAT_OPTIONS.map(
        (o) =>
          `<button type="button" class="chip-option${o.id === cur ? " selected" : ""}" data-task-repeat="${escapeAttr(o.id)}">${escapeHtml(o.label)}</button>`,
      ).join("")}
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
    if (month < 0 || month > 11 || day < 1 || day > 31) return null;
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

function parseRepeatToken(text) {
  const lower = text.toLowerCase().trim().replace(/\s+/g, " ");
  if (/^(?:каждый\s+день|ежедневно|daily)$/.test(lower)) return "daily";
  if (/^(?:каждые\s+2\s+дня|every\s*2\s*days?)$/.test(lower)) return "every_2_days";
  if (/^(?:каждые\s+3\s+дня|every\s*3\s*days?)$/.test(lower)) return "every_3_days";
  if (/^(?:каждую\s+неделю|еженедельно|weekly)$/.test(lower)) return "weekly";
  if (/^(?:по\s+будням|будни|weekdays)$/.test(lower)) return "weekdays";
  if (/^(?:каждый\s+месяц|ежемесячно|monthly)$/.test(lower)) return "monthly";
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

function parseTimeToken(text) {
  const m = String(text || "")
    .toLowerCase()
    .trim()
    .replace(/\s+/g, " ")
    .match(/^(?:в\s+)?(\d{1,2})[:.](\d{2})$/);
  if (!m) return null;
  const hour = Number(m[1]);
  const minute = Number(m[2]);
  if (hour > 23 || minute > 59) return null;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

/** Parse money token: -25млн / +5000 / 25000₽ / trailing 25000000 → { cost, costType }. */
function parseCostToken(raw, opts = {}) {
  const requireMarker = !!opts.requireMarker; // sign / currency / млн|тыс
  let text = String(raw || "")
    .trim()
    .replace(/^[−–—]/, "-")
    .replace(/\s+/g, " ");
  if (!text) return {};

  let costType = null;
  if (/^\+/.test(text)) {
    costType = "income";
    text = text.slice(1).trim();
  } else if (/^-/.test(text)) {
    costType = "expense";
    text = text.slice(1).trim();
  }

  const currencyRe = /(?:₽|руб\.?|р\.?|rub)$/i;
  const hasCurrency = currencyRe.test(text);
  text = text.replace(currencyRe, "").trim();

  let mul = 1;
  if (/(?:млн|m)$/i.test(text)) {
    mul = 1_000_000;
    text = text.replace(/(?:млн|m)$/i, "").trim();
  } else if (/(?:тыс|k)$/i.test(text)) {
    mul = 1_000;
    text = text.replace(/(?:тыс|k)$/i, "").trim();
  }

  const numMatch = text.match(/^(\d+(?:\s+\d+)*)(?:[.,](\d{1,2}))?$/);
  if (!numMatch) return {};
  const digits = numMatch[1].replace(/\s+/g, "");
  if (!digits) return {};
  const frac = numMatch[2] || "0";
  const amount = Number(`${digits}.${frac}`) * mul;
  if (!Number.isFinite(amount) || amount <= 0) return {};

  const hasMarker = costType != null || hasCurrency || mul > 1;
  if (requireMarker && !hasMarker) return {};
  if (!hasMarker) {
    // bare trailing number: only «large» amounts (≥ 1000, ≥ 4 digits)
    if (digits.length < 4 || amount < 1000) return {};
  }
  if (!costType) costType = "expense";
  return { cost: amount, costType };
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
      type: "remind",
      re: ruTokenRe(
        "(?:напоминай|напомни|долби)\\s+каждый\\s+час|каждый\\s+час|hourly",
      ),
      meta: () => ({ remindHourly: true }),
    },
    {
      type: "remind",
      re: ruTokenRe("через\\s+\\d+\\s*(?:мин(?:ут[уы]?)?|м|час(?:а|ов)?|ч)"),
      meta: (m) => parseRemindToken(m[0]),
    },
    {
      type: "remind",
      re: ruTokenRe("за\\s+\\d+\\s*(?:мин(?:ут[уы]?)?|м|час(?:а|ов)?|ч)"),
      meta: (m) => parseRemindToken(m[0]),
    },
    {
      type: "remind",
      re: ruTokenRe("напомни\\s+завтра\\s+в\\s+\\d{1,2}(?:[:.]\\d{2})?"),
      meta: (m) => parseRemindToken(m[0]),
    },
    {
      type: "remind",
      re: ruTokenRe("напомни\\s+в\\s+\\d{1,2}(?:[:.]\\d{2})?"),
      meta: (m) => parseRemindToken(m[0]),
    },
    {
      type: "remind",
      re: ruTokenRe("напомни\\s+\\d{1,2}[:.]\\d{2}"),
      meta: (m) => parseRemindToken(m[0]),
    },
    {
      type: "remind",
      re: /(?<![\p{L}\p{N}_])(?:напомнить|напомни|remind)(?=\s*$)/giu,
      meta: (m) => parseRemindToken(m[0]),
    },
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
      // "в 15:30" / "в 15.30" / "в 9:00" — before bare HH.MM so "в" sticks to time
      re: ruTokenRe("в\\s+\\d{1,2}[:.]\\d{2}"),
      meta: (m) => ({ dueTime: parseTimeToken(m[0]) }),
    },
    {
      type: "date",
      // bare "15:30" / "9:00" (colon = always time)
      re: ruTokenRe("\\d{1,2}:\\d{2}"),
      meta: (m) => ({ dueTime: parseTimeToken(m[0]) }),
    },
    {
      type: "date",
      // bare "15.30" / "9.45" — only when .MM cannot be a month (MM > 12)
      re: ruTokenRe("\\d{1,2}\\.\\d{2}"),
      meta: (m) => {
        const dueTime = parseTimeToken(m[0]);
        if (!dueTime) return {};
        if (Number(dueTime.slice(3, 5)) <= 12) return {};
        return { dueTime };
      },
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
      type: "repeat",
      re: ruTokenRe("каждый\\s+день|ежедневно|каждые\\s+[23]\\s+дня|каждую\\s+неделю|еженедельно|по\\s+будням|будни|каждый\\s+месяц|ежемесячно|daily|weekly|monthly|weekdays|every\\s*[23]\\s*days?"),
      meta: (m) => ({ repeat: parseRepeatToken(m[0]) }),
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
    {
      type: "cost",
      // signed: -25000000 / +25 млн / −25тыс₽
      re: ruTokenRe("[+\\-−–—]\\s*\\d+(?:\\s+\\d+)*(?:[.,]\\d{1,2})?\\s*(?:млн|тыс|[mk])?\\s*(?:₽|руб\\.?|р\\.?|rub)?"),
      meta: (m) => parseCostToken(m[0], { requireMarker: true }),
    },
    {
      type: "cost",
      // currency or млн/тыс without sign: 25 000 000 ₽ / 25млн
      re: ruTokenRe("\\d+(?:\\s+\\d+)*(?:[.,]\\d{1,2})?\\s*(?:млн|тыс|[mk])\\s*(?:₽|руб\\.?|р\\.?|rub)?"),
      meta: (m) => parseCostToken(m[0], { requireMarker: true }),
    },
    {
      type: "cost",
      re: ruTokenRe("\\d+(?:\\s+\\d+)*(?:[.,]\\d{1,2})?\\s*(?:₽|руб\\.?|р\\.?|rub)"),
      meta: (m) => parseCostToken(m[0], { requireMarker: true }),
    },
    {
      type: "cost",
      // bare large number only at end of title: «… 25000000»
      re: /(?<![\p{L}\p{N}_])\d+(?:\s+\d+)*(?=\s*$)/gu,
      meta: (m) => parseCostToken(m[0], { requireMarker: false }),
    },
  ];

  const found = [];
  for (const rule of patterns) {
    for (const match of text.matchAll(rule.re)) {
      const meta = rule.meta(match);
      if (rule.type === "date" && !meta.due && !meta.dueTime) continue;
      if (rule.type === "remind" && !meta.remindAt && meta.remindBeforeMinutes == null && !meta.remindAtDue && !meta.remindHourly) continue;
      if (rule.type === "cost" && (meta.cost == null || !meta.costType)) continue;
      found.push({
        type: rule.type,
        start: match.index,
        end: match.index + match[0].length,
        text: match[0],
        meta,
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
    if (m.dueTime) meta.dueTime = m.dueTime;
    if (m.priority) meta.priority = m.priority;
    if (m.kind) meta.kind = m.kind;
    if (m.projectName) {
      meta.projectName = m.projectName;
      if (m.projectId) meta.projectId = m.projectId;
    }
    if (m.label) meta.labels.push(m.label);
    if (m.repeat) meta.repeat = m.repeat;
    if (m.remindHourly) {
      meta.remindHourly = true;
      delete meta.remindAt;
      delete meta.remindBeforeMinutes;
      delete meta.remindAtDue;
    }
    if (m.remindAt) meta.remindAt = m.remindAt;
    if (m.remindBeforeMinutes != null) meta.remindBeforeMinutes = m.remindBeforeMinutes;
    if (m.remindAtDue) meta.remindAtDue = true;
    if (m.cost != null) {
      meta.cost = m.cost;
      meta.costType = m.costType || "expense";
    }
  }
  return meta;
}

function resolveParsedDue(meta, fallbackDate = "", fallbackTime = "") {
  const datePart =
    (meta.due && String(meta.due).slice(0, 10)) || fallbackDate || "";
  const timePart = meta.dueTime || fallbackTime || "";
  if (timePart) return mergeTaskDue(datePart || todayIso(), timePart);
  return meta.due || fallbackDate || null;
}

function defaultRemindLocal() {
  const dt = new Date();
  dt.setHours(9, 0, 0, 0);
  if (dt <= new Date()) dt.setDate(dt.getDate() + 1);
  return localInputValue(dt);
}

function resolveRemindLocal(meta, fallbackDate = "", fallbackTime = "") {
  if (meta.remindHourly) return localInputValue(nextHourBoundaryLocal());
  if (meta.remindAt) return meta.remindAt;
  if (meta.remindBeforeMinutes != null) {
    const dueIso = resolveParsedDue(meta, fallbackDate, fallbackTime);
    if (!dueIso) return null;
    const dueDt = new Date(dueIso);
    if (Number.isNaN(dueDt.getTime())) return null;
    dueDt.setMinutes(dueDt.getMinutes() - Number(meta.remindBeforeMinutes));
    return localInputValue(dueDt);
  }
  if (meta.remindAtDue) {
    const dueIso = resolveParsedDue(meta, fallbackDate, fallbackTime);
    const normalized = dueAtForRemindPreset(dueIso);
    if (normalized) {
      const dueDt = new Date(normalized);
      if (!Number.isNaN(dueDt.getTime())) return localInputValue(dueDt);
    }
    return defaultRemindLocal();
  }
  return null;
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
        return !!m.due || !!m.dueTime;
      case "time":
        return !!m.dueTime;
      case "priority":
        return m.priority != null;
      case "project":
        return !!m.projectName;
      case "label":
        return !!m.label;
      case "kind":
        return !!m.kind;
      case "repeat":
        return !!m.repeat;
      case "remind":
        return !!m.remindAt || m.remindBeforeMinutes != null || !!m.remindAtDue || !!m.remindHourly;
      case "cost":
        return m.cost != null && !!m.costType;
      default: {
        const _exhaustive = token.type;
        void _exhaustive;
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
  const dueInput = $("task-due");
  const timeInput = $("task-due-time");
  if (meta.due) dueInput.value = String(meta.due).slice(0, 10);
  if (meta.dueTime) {
    if (timeInput) timeInput.value = meta.dueTime;
    if (!dueInput.value) dueInput.value = todayIso();
  }
  if (meta.priority) $("task-priority").value = String(meta.priority);
  if (meta.kind) $("task-kind").value = meta.kind;
  if (meta.cost != null) {
    $("task-cost").value = String(meta.cost);
    $("task-cost-type-value").value = meta.costType || "expense";
  }
  if (meta.repeat !== undefined && $("task-repeat")) {
    $("task-repeat").value = meta.repeat || "";
    if (meta.repeat && !$("task-due").value) $("task-due").value = todayIso();
  }
  const remindInput = $("task-remind");
  if (remindInput) {
    const remindLocal = resolveRemindLocal(meta, dueInput.value, timeInput?.value || "");
    if (remindLocal) remindInput.value = remindLocal;
    const ruleInput = $("task-remind-rule");
    if (ruleInput) ruleInput.value = meta.remindHourly ? "hourly" : "";
  }
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

function dueStartDay(task) {
  const raw = task?.due_start;
  if (!raw) return "";
  return String(raw).slice(0, 10);
}

function isOpenTaskOverdue(task) {
  if (!task || task.status === "done" || !task.due_at) return false;
  return task.due_at.slice(0, 10) < todayIso();
}

function formatDueChipLabel(task) {
  const due = taskDueParts(task);
  const start = dueStartDay(task);
  const end = due.date;
  const overdue = isOpenTaskOverdue(task);
  const repeatRule = task.repeat_rule || "";
  const today = todayIso();
  let base = "Срок";
  if (start && end && start !== end) {
    base = `${fmtShortDay(start)}–${fmtShortDay(end)}`;
  } else if (end === today && !overdue) {
    base = due.time ? `Сегодня ${due.time}` : "Сегодня";
  } else if (end) {
    base = due.time || fmtShortDay(end);
  } else if (due.time) {
    base = due.time;
  }
  if (repeatRule) {
    base = end || start ? `${base} · ${repeatLabel(repeatRule)}` : repeatLabel(repeatRule);
  }
  if (overdue && (end || start)) return `Просрочено · ${base}`;
  return base;
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

function chipPopoverRoot(el) {
  const node = el instanceof Element ? el : el?.parentElement;
  if (!node || !(node instanceof Element)) return null;
  return node.closest(".chip-popover, .chip-menu");
}

function isChipPopoverInteraction(target) {
  return !!chipPopoverRoot(target);
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
  $("chip-priority").classList.remove("prio-1", "prio-2", "prio-3", "prio-4");
  $("chip-priority").classList.add(`prio-${priority}`);
  document.querySelectorAll("[data-set-priority]").forEach((btn) => {
    btn.classList.toggle("selected", btn.dataset.setPriority === priority);
  });

  const due = $("task-due").value;
  const dueStart = $("task-due-start")?.value || "";
  const dueTime = $("task-due-time")?.value || "";
  const repeat = $("task-repeat")?.value || "";
  let dueLabel = "Срок";
  if (dueStart && due && dueStart !== due) dueLabel = `${fmtShortDay(dueStart)}–${fmtShortDay(due)}`;
  else if (due) dueLabel = dueTime ? `${fmtShortDay(due)} ${dueTime}` : fmtShortDay(due);
  else if (dueTime) dueLabel = dueTime;
  if (repeat) {
    $("chip-due-label").textContent = due || dueStart ? `${dueLabel} · ${repeatLabel(repeat)}` : repeatLabel(repeat);
  } else {
    $("chip-due-label").textContent = dueLabel;
  }
  $("chip-due").classList.toggle("has-value", !!due || !!dueStart || !!dueTime || !!repeat);
  document.querySelectorAll("#composer-repeat [data-set-repeat]").forEach((btn) => {
    btn.classList.toggle("selected", (btn.dataset.setRepeat || "") === repeat);
  });

  const remind = $("task-remind").value;
  const remindRule = $("task-remind-rule")?.value || "";
  if (remindRule === "hourly") {
    $("chip-remind-label").textContent = remind
      ? `Каждый час · ${String(new Date(remind).getHours()).padStart(2, "0")}:${String(new Date(remind).getMinutes()).padStart(2, "0")}`
      : "Каждый час";
  } else {
    $("chip-remind-label").textContent = remind ? fmtShortDateTime(remind) : "Напомн.";
  }
  $("chip-remind").classList.toggle("has-value", !!remind || remindRule === "hourly");
  document.querySelectorAll("#pop-remind [data-composer-remind-preset]").forEach((btn) => {
    btn.classList.toggle("selected", remindRule === "hourly" && btn.dataset.composerRemindPreset === "hourly");
  });

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
      if ($("task-due-start")) $("task-due-start").value = "";
      updateTaskChips();
      closeTaskPopovers();
    });
  });
  $("task-due-start")?.addEventListener("change", updateTaskChips);
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
      if (btn.dataset.clear === "task-due") {
        if (el) delete el.dataset.dueTime;
        if ($("task-due-time")) $("task-due-time").value = "";
        if ($("task-due-start")) $("task-due-start").value = "";
        if ($("task-repeat")) $("task-repeat").value = "";
      }
      if (btn.dataset.clear === "task-remind" && $("task-remind-rule")) {
        $("task-remind-rule").value = "";
      }
      updateTaskChips();
      closeTaskPopovers();
    });
  });

  $("task-due-time")?.addEventListener("change", updateTaskChips);

  $("composer-repeat")?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-set-repeat]");
    if (!btn) return;
    $("task-repeat").value = btn.dataset.setRepeat || "";
    if ($("task-repeat").value && !$("task-due").value) $("task-due").value = todayIso();
    updateTaskChips();
  });

  $("pop-work")?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-set-work-project]");
    if (!btn) return;
    $("task-work-project").value = btn.dataset.setWorkProject || "";
    updateTaskChips();
    closeTaskPopovers();
  });

  $("pop-remind")?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-composer-remind-preset]");
    if (!btn) return;
    const preset = btn.dataset.composerRemindPreset;
    const due = mergeTaskDue($("task-due")?.value || "", $("task-due-time")?.value || "") || $("task-due")?.value || null;
    const iso = computeRemindPreset(preset, due);
    if (!iso) return;
    $("task-remind").value = localInputValue(new Date(iso));
    if ($("task-remind-rule")) $("task-remind-rule").value = preset === "hourly" ? "hourly" : "";
    updateTaskChips();
  });

  document.addEventListener("click", (e) => {
    if (isChipPopoverInteraction(e.target)) return;
    window.setTimeout(() => {
      const active = document.activeElement;
      if (active instanceof HTMLElement && chipPopoverRoot(active)) return;
      closeTaskPopovers();
    }, 0);
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

function clampSidebarWidth(width) {
  return Math.round(Math.min(SIDEBAR_WIDTH_MAX, Math.max(SIDEBAR_WIDTH_MIN, width)));
}

function readSidebarWidth() {
  const raw = parseInt(localStorage.getItem(SIDEBAR_WIDTH_KEY), 10);
  return clampSidebarWidth(Number.isFinite(raw) ? raw : SIDEBAR_WIDTH_DEFAULT);
}

function applySidebarWidth(width, persist) {
  const w = clampSidebarWidth(width);
  const app = $("app");
  if (app) app.style.setProperty("--sidebar-width", `${w}px`);
  if (persist) localStorage.setItem(SIDEBAR_WIDTH_KEY, String(w));
  return w;
}

function currentSidebarWidth() {
  const app = $("app");
  if (!app) return SIDEBAR_WIDTH_DEFAULT;
  const raw = parseInt(getComputedStyle(app).getPropertyValue("--sidebar-width"), 10);
  return clampSidebarWidth(Number.isFinite(raw) ? raw : SIDEBAR_WIDTH_DEFAULT);
}

function isNarrowNav() {
  return window.matchMedia("(max-width: 860px)").matches;
}

function syncMobileNavChrome() {
  const collapsed = $("app")?.classList.contains("sidebar-collapsed");
  const open = isNarrowNav() && !collapsed;
  const scrim = $("sidebar-scrim");
  if (scrim) {
    scrim.classList.toggle("hidden", !open);
    scrim.setAttribute("aria-hidden", open ? "false" : "true");
  }
  document.body.classList.toggle("nav-open", open);
}

function setSidebarCollapsed(collapsed) {
  $("app").classList.toggle("sidebar-collapsed", collapsed);
  if (!isNarrowNav()) localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
  const btn = $("sidebar-toggle");
  if (btn) {
    btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
    const phone = isNarrowNav();
    btn.setAttribute("aria-label", collapsed ? "Показать меню" : phone ? "Закрыть меню" : "Скрыть меню");
    btn.title = collapsed ? "Показать меню" : phone ? "Закрыть меню" : "Скрыть меню";
  }
  syncMobileNavChrome();
}

function closeMobileNav() {
  if (isNarrowNav()) setSidebarCollapsed(true);
}

function initSidebarResize() {
  const handle = $("sidebar-resize");
  const app = $("app");
  if (!handle || !app) return;

  let dragging = false;
  let startX = 0;
  let startW = 0;

  function onPointerMove(clientX) {
    applySidebarWidth(startW + (clientX - startX), false);
  }

  function stopDrag() {
    if (!dragging) return;
    dragging = false;
    app.classList.remove("sidebar-resizing");
    document.body.style.removeProperty("user-select");
    document.body.style.removeProperty("cursor");
    applySidebarWidth(currentSidebarWidth(), true);
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mouseup", onMouseUp);
    window.removeEventListener("touchmove", onTouchMove);
    window.removeEventListener("touchend", onTouchEnd);
    window.removeEventListener("touchcancel", onTouchEnd);
  }

  function startDrag(clientX) {
    if (app.classList.contains("sidebar-collapsed")) return;
    dragging = true;
    startX = clientX;
    startW = currentSidebarWidth();
    app.classList.add("sidebar-resizing");
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
  }

  function onMouseMove(e) {
    if (!dragging) return;
    e.preventDefault();
    onPointerMove(e.clientX);
  }

  function onMouseUp() {
    stopDrag();
  }

  function onTouchMove(e) {
    if (!dragging) return;
    e.preventDefault();
    const touch = e.touches[0];
    if (touch) onPointerMove(touch.clientX);
  }

  function onTouchEnd() {
    stopDrag();
  }

  handle.addEventListener("mousedown", (e) => {
    e.preventDefault();
    startDrag(e.clientX);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  });

  handle.addEventListener(
    "touchstart",
    (e) => {
      if (app.classList.contains("sidebar-collapsed")) return;
      const touch = e.touches[0];
      if (!touch) return;
      startDrag(touch.clientX);
      window.addEventListener("touchmove", onTouchMove, { passive: false });
      window.addEventListener("touchend", onTouchEnd);
      window.addEventListener("touchcancel", onTouchEnd);
    },
    { passive: true },
  );

  handle.addEventListener("dblclick", () => {
    applySidebarWidth(SIDEBAR_WIDTH_DEFAULT, true);
    track("sidebar_resize_reset", "ui", null, { width: SIDEBAR_WIDTH_DEFAULT });
  });

  handle.addEventListener("keydown", (e) => {
    if (app.classList.contains("sidebar-collapsed")) return;
    let next = null;
    if (e.key === "ArrowLeft") next = currentSidebarWidth() - 16;
    else if (e.key === "ArrowRight") next = currentSidebarWidth() + 16;
    else if (e.key === "Home") next = SIDEBAR_WIDTH_MIN;
    else if (e.key === "End") next = SIDEBAR_WIDTH_MAX;
    else return;
    e.preventDefault();
    const w = applySidebarWidth(next, true);
    track("sidebar_resize_key", "ui", null, { width: w });
  });
}

function initSidebarToggle() {
  applySidebarWidth(readSidebarWidth(), false);
  initSidebarResize();
  const mq = window.matchMedia("(max-width: 860px)");
  const applyForViewport = () => {
    if (mq.matches) setSidebarCollapsed(true);
    else setSidebarCollapsed(localStorage.getItem(SIDEBAR_KEY) === "1");
  };
  applyForViewport();
  mq.addEventListener("change", applyForViewport);
  $("sidebar-toggle")?.addEventListener("click", () => {
    const collapsed = !$("app").classList.contains("sidebar-collapsed");
    setSidebarCollapsed(collapsed);
    track("sidebar_toggle", "ui", null, { collapsed, narrow: isNarrowNav() });
  });
  $("sidebar-scrim")?.addEventListener("click", () => closeMobileNav());
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeMobileNav();
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

function currentYearMonth(from = new Date()) {
  const d = new Date(from);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function shiftYearMonth(ym, delta) {
  const [y, m] = ym.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function moneySigned(amount, type = "expense") {
  const n = Number(amount) || 0;
  const formatted = Math.abs(n).toLocaleString("ru-RU", { maximumFractionDigits: 2 });
  if (type === "income") return `+${formatted} ₽`;
  return `−${formatted} ₽`;
}

function financeBarPct(income, expense) {
  const inc = Number(income) || 0;
  const exp = Number(expense) || 0;
  if (inc <= 0 && exp <= 0) return 0;
  if (inc <= 0) return 100;
  return Math.min(100, Math.round((exp / inc) * 100));
}

function moneyPlain(amount) {
  const n = Number(amount) || 0;
  return `${n.toLocaleString("ru-RU", { maximumFractionDigits: 2 })} ₽`;
}

function ledgerStatusLabel(status) {
  return status === "confirmed" ? "Подтверждено" : "План";
}

function ledgerDayKey(day) {
  if (!day) return "(пусто)";
  return String(day).slice(0, 10);
}

function ledgerRowFilterVals(row) {
  return {
    project: row.project_name || "Без раздела",
    title: row.title || "",
    amount: String(row.amount ?? ""),
    day: ledgerDayKey(row.day),
    status: ledgerStatusLabel(row.status),
  };
}

function ledgerVisibleRows() {
  const rows = [...(state.financeLedger?.rows || []), ...(state.financeDrafts || [])];
  const filters = state.financeLedgerFilters || {};
  return rows.filter((row) => {
    const vals = ledgerRowFilterVals(row);
    for (const [col, allowed] of Object.entries(filters)) {
      if (!allowed) continue;
      if (!allowed.has(vals[col])) return false;
    }
    return true;
  });
}

function ledgerHeroTotals(rows) {
  let income = 0;
  let expense = 0;
  for (const row of rows) {
    const n = Number(row.amount) || 0;
    if (n > 0) income += n;
    else expense += -n;
  }
  return { income, expense, balance: income - expense };
}

function ledgerRowAttr(row) {
  if (row.source === "draft") return `draft:${row.id}`;
  return `${row.source}:${row.id}`;
}

function ledgerAllFilterRows() {
  return [...(state.financeLedger?.rows || []), ...(state.financeDrafts || [])];
}

function ledgerUniqueFilterValues(col) {
  const seen = new Set();
  for (const row of ledgerAllFilterRows()) {
    seen.add(ledgerRowFilterVals(row)[col]);
  }
  return [...seen].sort((a, b) => String(a).localeCompare(String(b), "ru"));
}

function positionLedgerFilterMenu(menu, btn) {
  const rect = btn.getBoundingClientRect();
  menu.style.top = `${rect.bottom}px`;
  menu.style.left = `${Math.max(8, rect.right - 180)}px`;
}

function closeLedgerFilterMenus() {
  document.querySelectorAll("#finance-page .fin-filter-menu").forEach((menu) => {
    menu.classList.add("hidden");
    menu.style.top = "";
    menu.style.left = "";
  });
  state.financeFilterOpenCol = null;
}

function ledgerFilterMenuHtml(col) {
  const values = ledgerUniqueFilterValues(col);
  const allowed = state.financeLedgerFilters?.[col];
  const hiddenClass = state.financeFilterOpenCol === col ? "" : " hidden";
  const items = values
    .map((value) => {
      const checked = !allowed || allowed.has(value);
      return `<label><input type="checkbox" data-fin-filter-val="${escapeAttr(value)}"${checked ? " checked" : ""}>${escapeHtml(value)}</label>`;
    })
    .join("");
  return `<div class="fin-filter-menu${hiddenClass}" data-fin-filter-menu="${escapeAttr(col)}">${items}</div>`;
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
  if (kind === "finance" && !state.financeYm) state.financeYm = currentYearMonth();
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
  if (!state.financeYm) state.financeYm = currentYearMonth();
  const ym = state.financeYm;
  const data = await api(`/api/finance/months/${ym}`);
  const income = Number(data.income) || 0;
  const expense = Number(data.expense) || 0;
  const bal = Number(data.balance) || 0;
  const pct = financeBarPct(income, expense);
  const entries = data.entries || [];
  const balClass = bal > 0 ? "pos" : bal < 0 ? "neg" : "";

  $("section-panel-inner").innerHTML = `
    <div class="fin-panel">
      <div class="fin-top">
        <h2>Финансы</h2>
        <div class="fin-month-nav" role="group" aria-label="Месяц">
          <button type="button" class="btn ghost small fin-nav-btn" data-finance-shift="-1" aria-label="Предыдущий месяц">‹</button>
          <span class="fin-month-label">${escapeHtml(monthLabel(ym))}</span>
          <button type="button" class="btn ghost small fin-nav-btn" data-finance-shift="1" aria-label="Следующий месяц">›</button>
        </div>
      </div>

      <div class="fin-hero">
        <span class="fin-hero-label">Баланс</span>
        <div class="fin-hero-value ${balClass}">${escapeHtml(moneyPlain(bal))}</div>
      </div>

      <div class="fin-split">
        <div class="fin-split-card income">
          <span class="label">Доход</span>
          <span class="value">${escapeHtml(moneySigned(income, "income"))}</span>
        </div>
        <div class="fin-split-card expense">
          <span class="label">Расход</span>
          <span class="value">${escapeHtml(moneySigned(expense, "expense"))}</span>
        </div>
      </div>

      <div class="fin-bar" title="Расход относительно дохода">
        <div class="fin-bar-track">
          <div class="fin-bar-fill" style="width:${pct}%"></div>
        </div>
        <div class="fin-bar-meta">${pct}% расхода от дохода</div>
      </div>

      <div class="fin-ops-head">
        <h3>Операции</h3>
        <span class="hint">${entries.length}</span>
      </div>
      <div class="fin-ops">
        ${
          entries.length
            ? entries
                .map((e) => {
                  const type = e.cost_type === "income" ? "income" : "expense";
                  const day = e.day ? fmtShortDay(e.day) : "";
                  const taskAttr =
                    e.entry_type === "work_payment" ? "" : ` data-finance-task="${e.id}"`;
                  return `
            <button type="button" class="fin-op"${taskAttr}>
              <div class="fin-op-main">
                <span class="fin-op-title">${escapeHtml(e.title || "Без названия")}</span>
                <span class="fin-op-day">${escapeHtml(day)}</span>
              </div>
              <span class="fin-op-amount ${type}">${escapeHtml(moneySigned(e.cost, type))}</span>
            </button>`;
                })
                .join("")
            : `<p class="fin-empty">Нет операций с суммой в этом месяце. Добавь сумму в задаче.</p>`
        }
      </div>
    </div>
  `;
}

function ledgerAmountInputValue(amount) {
  const n = Number(amount) || 0;
  const body = Math.abs(n).toLocaleString("ru-RU", { maximumFractionDigits: 2 });
  return n < 0 ? `−${body}` : String(body);
}

function liveLedgerProjects() {
  return (state.projects || []).filter((p) => !p.deleted_at);
}

function ledgerProjectCell(row) {
  if (row.source === "work") {
    return `<select class="fin-cell-select" data-fin-field="project_id" data-fin-col="project" disabled><option value="${escapeAttr(row.project_id || "")}" selected>Работа</option></select>`;
  }
  const options = liveLedgerProjects()
    .map((p) => {
      const sel = String(p.id) === String(row.project_id) ? " selected" : "";
      return `<option value="${escapeAttr(p.id)}"${sel}>${escapeHtml(p.name)}</option>`;
    })
    .join("");
  return `<select class="fin-cell-select" data-fin-field="project_id" data-fin-col="project">${options}</select>`;
}

function ledgerTitleCell(row) {
  if (row.source === "work") {
    const wps = state.financeLedger?.work_projects || [];
    const options = wps
      .map((w) => {
        const sel = String(w.id) === String(row.work_project_id) ? " selected" : "";
        return `<option value="${escapeAttr(w.id)}"${sel}>${escapeHtml(w.title || "")}</option>`;
      })
      .join("");
    return `<select class="fin-cell-select" data-fin-field="work_project_id" data-fin-col="title">${options}</select>`;
  }
  return `<input class="fin-cell-input" data-fin-field="title" data-fin-col="title" value="${escapeAttr(row.title || "")}">`;
}

function ledgerAmountCell(row) {
  return `<input class="fin-cell-input" type="text" inputmode="decimal" data-fin-field="amount" data-fin-col="amount" value="${escapeAttr(ledgerAmountInputValue(row.amount))}">`;
}

function ledgerDayCell(row) {
  const v = row.day ? String(row.day).slice(0, 10) : "";
  return `<input class="fin-cell-input" type="date" data-fin-field="day" data-fin-col="day" value="${escapeAttr(v)}">`;
}

function ledgerStatusCell(row) {
  const planSel = row.status === "plan" ? " selected" : "";
  const confSel = row.status === "confirmed" ? " selected" : "";
  return `<select class="fin-cell-select" data-fin-field="status" data-fin-col="status"><option value="plan"${planSel}>План</option><option value="confirmed"${confSel}>Подтверждено</option></select>`;
}

function findLedgerRowByKey(key) {
  if (!key) return null;
  return ledgerAllFilterRows().find((r) => ledgerRowAttr(r) === key) || null;
}

function findLedgerRowFromEl(el) {
  const tr = el?.closest?.("tr[data-fin-row]");
  if (!tr) return null;
  return findLedgerRowByKey(tr.dataset.finRow);
}

function financeLedgerRowEls() {
  return [...document.querySelectorAll("#finance-page tr[data-fin-row]")];
}

function selectLedgerRow(row) {
  state.financeSelectedRowKey = row ? ledgerRowAttr(row) : null;
  financeLedgerRowEls().forEach((tr) => {
    tr.classList.toggle("is-selected", tr.dataset.finRow === state.financeSelectedRowKey);
  });
}

function ledgerFieldsInRow(tr) {
  return [...(tr?.querySelectorAll("[data-fin-field]") || [])].filter((el) => !el.disabled);
}

function focusLedgerField(tr, col) {
  if (!tr) return;
  const el = tr.querySelector(`[data-fin-col="${col}"]`);
  if (!el || el.disabled) {
    ledgerFieldsInRow(tr)[0]?.focus();
    return;
  }
  el.focus();
  if (typeof el.select === "function") el.select();
}

function cycleLedgerField(back) {
  const rows = financeLedgerRowEls();
  if (!rows.length) return;
  let rowIdx = rows.findIndex((r) => r.classList.contains("is-selected"));
  if (rowIdx < 0) rowIdx = 0;
  const fields = ledgerFieldsInRow(rows[rowIdx]);
  const fieldIdx = fields.indexOf(document.activeElement);
  if (back) {
    if (fieldIdx > 0) {
      fields[fieldIdx - 1].focus();
      return;
    }
    const prev = rows[rowIdx - 1] || rows[rows.length - 1];
    selectLedgerRow(findLedgerRowFromEl(prev));
    const prevFields = ledgerFieldsInRow(prev);
    prevFields[prevFields.length - 1]?.focus();
    return;
  }
  if (fieldIdx >= 0 && fieldIdx < fields.length - 1) {
    fields[fieldIdx + 1].focus();
    return;
  }
  const next = rows[rowIdx + 1] || rows[0];
  selectLedgerRow(findLedgerRowFromEl(next));
  ledgerFieldsInRow(next)[0]?.focus();
}

function moveLedgerFieldDown() {
  const rows = financeLedgerRowEls();
  if (!rows.length) return;
  let rowIdx = rows.findIndex((r) => r.classList.contains("is-selected"));
  if (rowIdx < 0) rowIdx = 0;
  const col = document.activeElement?.dataset?.finCol || "title";
  const next = rows[rowIdx + 1] || rows[0];
  selectLedgerRow(findLedgerRowFromEl(next));
  focusLedgerField(next, col);
}

function moveLedgerSelection(delta) {
  const rows = financeLedgerRowEls();
  if (!rows.length) return;
  let idx = rows.findIndex((r) => r.classList.contains("is-selected"));
  if (idx < 0) idx = delta > 0 ? -1 : 0;
  const nextIdx = Math.min(rows.length - 1, Math.max(0, idx + delta));
  selectLedgerRow(findLedgerRowFromEl(rows[nextIdx]));
}

function parseLedgerAmount(raw) {
  const t = String(raw || "").replace(/\s/g, "").replace(",", ".").replace("−", "-").replace("–", "-");
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

function uniqueLedgerDraftTitle() {
  const used = new Set(
    [...(state.financeLedger?.rows || []), ...(state.financeDrafts || [])].map((r) => r.title)
  );
  const base = "Новая строка";
  if (!used.has(base)) return base;
  let i = 2;
  while (used.has(`${base} ${i}`)) i += 1;
  return `${base} ${i}`;
}

async function commitLedgerDraft(row) {
  const n = Number(row.amount) || 0;
  if (n === 0) return;
  const personal = (state.projects || []).find((p) => p.name === "Личные дела");
  const title = (row.title || "").trim() || uniqueLedgerDraftTitle();
  await api("/api/tasks", {
    method: "POST",
    body: JSON.stringify({
      title,
      project_id: row.project_id || personal?.id || null,
      cost: Math.abs(n),
      cost_type: n >= 0 ? "income" : "expense",
      due_at: row.day || null,
    }),
  });
  state.financeDrafts = (state.financeDrafts || []).filter((d) => d.id !== row.id);
  await loadFinancePage();
}

async function saveLedgerField(row, field, value) {
  try {
    if (row.source === "draft") {
      row[field] = value;
      if (field === "project_id") {
        const p = (state.projects || []).find((x) => String(x.id) === String(value));
        row.project_name = p ? p.name : row.project_name;
      }
      if (field === "amount" && Number(row.amount) !== 0) {
        await commitLedgerDraft(row);
      }
      return;
    }
    if (row.source === "task") {
      if (field === "title") {
        await api(`/api/tasks/${row.id}`, { method: "PATCH", body: JSON.stringify({ title: value }) });
      } else if (field === "project_id") {
        await api(`/api/tasks/${row.id}`, { method: "PATCH", body: JSON.stringify({ project_id: Number(value) || null }) });
      } else if (field === "amount") {
        const n = Number(value);
        await api(`/api/tasks/${row.id}`, {
          method: "PATCH",
          body: JSON.stringify({ cost: Math.abs(n), cost_type: n >= 0 ? "income" : "expense" }),
        });
      } else if (field === "day") {
        await api(`/api/tasks/${row.id}`, { method: "PATCH", body: JSON.stringify({ due_at: value || null }) });
      } else if (field === "status") {
        if (value === "confirmed") await api(`/api/tasks/${row.id}/complete`, { method: "POST" });
        else await api(`/api/tasks/${row.id}`, { method: "PATCH", body: JSON.stringify({ status: "open" }) });
      }
      await loadFinancePage();
      return;
    }
    if (row.source === "work") {
      const wid = row.work_project_id;
      if (field === "amount") {
        const n = Number(value);
        if (!(n > 0)) {
          alert("Сумма платежа работы должна быть больше 0");
          renderFinancePage();
          return;
        }
        await api(`/api/work-projects/${wid}/payments/${row.id}`, {
          method: "PATCH",
          body: JSON.stringify({ amount: n }),
        });
      } else if (field === "day") {
        await api(`/api/work-projects/${wid}/payments/${row.id}`, {
          method: "PATCH",
          body: JSON.stringify({ paid_at: value }),
        });
      } else if (field === "status") {
        await api(`/api/work-projects/${wid}/payments/${row.id}`, {
          method: "PATCH",
          body: JSON.stringify({ status: value === "plan" ? "planned" : "received" }),
        });
      } else if (field === "work_project_id") {
        const nextId = Number(value);
        if (nextId === wid) return;
        await api(`/api/work-projects/${wid}/payments/${row.id}`, {
          method: "PATCH",
          body: JSON.stringify({ work_project_id: nextId }),
        });
      }
      await loadFinancePage();
    }
  } catch (err) {
    alert(err.message || "Ошибка");
    await loadFinancePage();
  }
}

async function deleteLedgerRow(row) {
  if (!row) return;
  if (!confirm("Удалить строку?")) return;
  try {
    if (row.source === "draft") {
      state.financeDrafts = (state.financeDrafts || []).filter((d) => d.id !== row.id);
      if (state.financeSelectedRowKey === ledgerRowAttr(row)) state.financeSelectedRowKey = null;
      renderFinancePage();
      return;
    }
    if (row.source === "task") {
      await api(`/api/tasks/${row.id}`, { method: "DELETE" });
    } else if (row.source === "work") {
      await api(`/api/work-projects/${row.work_project_id}/payments/${row.id}`, { method: "DELETE" });
    } else {
      return;
    }
    if (state.financeSelectedRowKey === ledgerRowAttr(row)) state.financeSelectedRowKey = null;
    await loadFinancePage();
  } catch (err) {
    alert(err.message || "Ошибка");
    await loadFinancePage();
  }
}

function addLedgerDraft() {
  const personal = (state.projects || []).find((p) => p.name === "Личные дела");
  const draft = {
    source: "draft",
    id: -Date.now(),
    project_id: personal?.id || null,
    project_name: "Личные дела",
    title: uniqueLedgerDraftTitle(),
    amount: 0,
    day: todayIso(),
    status: "plan",
  };
  state.financeDrafts = [...(state.financeDrafts || []), draft];
  state.financeSelectedRowKey = ledgerRowAttr(draft);
  renderFinancePage();
  const tr = financeLedgerRowEls().find((el) => el.dataset.finRow === ledgerRowAttr(draft));
  tr?.querySelector('[data-fin-field="title"]')?.focus();
}

async function loadFinancePage() {
  $("finance-page").innerHTML = `<p class="sp-sub">Загрузка…</p>`;
  try {
    const ym = currentYearMonth();
    const [ledger, sheet] = await Promise.all([
      api("/api/finance/ledger"),
      api(`/api/finance/sheet?year_month=${encodeURIComponent(ym)}`),
    ]);
    state.financeLedger = ledger;
    state.financeSheet = sheet;
    renderFinancePage();
  } catch (err) {
    $("finance-page").innerHTML = `<p class="error">${escapeHtml(err.message || "Ошибка")}</p>`;
  }
}

function renderFinancePage() {
  if (!Array.isArray(state.financeDrafts)) state.financeDrafts = [];
  if (!state.financeLedgerFilters) state.financeLedgerFilters = {};
  const visible = ledgerVisibleRows();
  const { income, expense, balance: bal } = ledgerHeroTotals(visible);
  const pct = financeBarPct(income, expense);
  const balClass = bal > 0 ? "pos" : bal < 0 ? "neg" : "";
  const accounts = state.financeSheet?.accounts || [];

  const accountHtml = accounts.length
    ? accounts
        .map(
          (a) => `
      <div class="fin-account-chip">
        <span class="name">${escapeHtml(a.name)}</span>
        <span class="bal">${escapeHtml(moneyPlain(a.balance))}</span>
      </div>`,
        )
        .join("")
    : `<p class="fin-empty">Нет счетов</p>`;

  const cols = [
    { col: "project", label: "Проект" },
    { col: "title", label: "Направление" },
    { col: "amount", label: "Цена" },
    { col: "day", label: "Месяц" },
    { col: "status", label: "Статус" },
  ];
  const headHtml = cols
    .map(
      (c) => `
              <th>${escapeHtml(c.label)}<button type="button" class="fin-col-filter" data-fin-filter-col="${c.col}">▾</button>${ledgerFilterMenuHtml(c.col)}</th>`,
    )
    .join("");

  const bodyHtml = visible
    .map((row) => {
      const selectedClass = state.financeSelectedRowKey === ledgerRowAttr(row) ? ` class="is-selected"` : "";
      return `
              <tr${selectedClass} data-fin-row="${escapeAttr(ledgerRowAttr(row))}" tabindex="-1">
                <td>${ledgerProjectCell(row)}</td>
                <td>${ledgerTitleCell(row)}</td>
                <td>${ledgerAmountCell(row)}</td>
                <td>${ledgerDayCell(row)}</td>
                <td>${ledgerStatusCell(row)}</td>
              </tr>`;
    })
    .join("");

  $("finance-page").innerHTML = `
    <div class="fin-page">
      <div class="fin-page-summary">
        <div class="fin-hero">
          <span class="fin-hero-label">Баланс</span>
          <div class="fin-hero-value ${balClass}">${escapeHtml(moneyPlain(bal))}</div>
        </div>

        <div class="fin-split">
          <div class="fin-split-card income">
            <span class="label">Доход</span>
            <span class="value">${escapeHtml(moneySigned(income, "income"))}</span>
          </div>
          <div class="fin-split-card expense">
            <span class="label">Расход</span>
            <span class="value">${escapeHtml(moneySigned(expense, "expense"))}</span>
          </div>
        </div>

        <div class="fin-bar" title="Расход относительно дохода">
          <div class="fin-bar-track">
            <div class="fin-bar-fill" style="width:${pct}%"></div>
          </div>
          <div class="fin-bar-meta">${pct}% расхода от дохода</div>
        </div>

        <section class="fin-section fin-accounts-section">
          <h3>Счета</h3>
          <div class="fin-accounts">${accountHtml}</div>
        </section>
      </div>

      <section class="fin-section">
        <div class="fin-ledger-sheet">
          <div class="fin-ledger-scroll">
            <table class="fin-ledger-table">
              <thead>
                <tr>
                  ${headHtml}
                </tr>
              </thead>
              <tbody>
                ${bodyHtml}
              </tbody>
            </table>
          </div>
          <button type="button" class="btn ghost small fin-row-add" data-fin-add-ledger>+ строка</button>
        </div>
      </section>
    </div>
  `;
  const openCol = state.financeFilterOpenCol;
  if (openCol) {
    const btn = document.querySelector(`#finance-page [data-fin-filter-col="${openCol}"]`);
    const menu = document.querySelector(`#finance-page [data-fin-filter-menu="${openCol}"]`);
    if (btn && menu) positionLedgerFilterMenu(menu, btn);
  }
}

function workPayBlock(p) {
  const budget = p.budget != null ? Number(p.budget) : null;
  const paid = Number(p.paid_sum || 0);
  const planned = Number(p.planned_sum || 0);
  const pct = budget && budget > 0 ? Math.min(100, Math.round((paid / budget) * 100)) : null;
  const payments = Array.isArray(p.payments) ? p.payments : [];
  let summary =
    budget != null
      ? `Получено ${escapeHtml(moneyPlain(paid))} из ${escapeHtml(moneyPlain(budget))}${pct != null ? ` (${pct}%)` : ""}`
      : `Получено ${escapeHtml(moneyPlain(paid))}`;
  if (planned > 0) summary += ` · план ${escapeHtml(moneyPlain(planned))}`;
  const rows = payments.length
    ? `<ul class="work-pay-list">${payments
        .map((pay) => {
          const isPlanned = pay.status === "planned";
          return `
      <li class="work-pay-row${isPlanned ? " planned" : ""}">
        <span>${escapeHtml((pay.paid_at || "").slice(0, 10))}${isPlanned ? `<span class="work-pay-badge">План</span>` : ""}</span>
        <span>${escapeHtml(pay.note || "")}</span>
        <span class="amt">${escapeHtml(moneyPlain(pay.amount))}</span>
        ${
          isPlanned
            ? `<button type="button" class="btn ghost small" data-work-pay-recv="${pay.id}" title="Отметить полученным" aria-label="Отметить полученным">✓</button>`
            : ""
        }
        <button type="button" class="btn ghost small btn-del" data-work-pay-del="${pay.id}" title="Удалить платёж" aria-label="Удалить платёж">×</button>
      </li>`;
        })
        .join("")}</ul>`
    : `<p class="work-meta">Пока нет платежей</p>`;
  return `
    <div class="work-pay">
      <div class="work-pay-summary">${summary}</div>
      ${
        pct != null
          ? `<div class="work-pay-bar" aria-hidden="true"><span style="width:${pct}%"></span></div>`
          : ""
      }
      ${rows}
      <form class="work-pay-form" data-work-pay-form>
        <label>Сумма <input name="amount" type="number" min="0.01" step="0.01" required placeholder="0" /></label>
        <label>Дата <input name="paid_at" type="date" value="${escapeAttr(todayIso())}" data-work-pay-date /></label>
        <label class="work-pay-plan"><input name="planned" type="checkbox" data-work-pay-planned /> План</label>
        <button class="btn small" type="submit">+</button>
        <label class="full">Комментарий <input name="note" type="text" placeholder="Аванс, этап…" /></label>
      </form>
    </div>`;
}

async function renderWorkPanel() {
  const items = await api("/api/work-projects");
  $("section-panel-inner").innerHTML = `
    <h2>Проекты</h2>
    <p class="sp-sub">Рабочие проекты, оплаты и статусы</p>
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
        ${workPayBlock(p)}
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
    let tone = "";
    switch (st) {
      case "warn":
        tone = " warn";
        break;
      case "bad":
        tone = " bad";
        break;
      case "unknown":
        tone = " unknown";
        break;
      case "ok":
        tone = "";
        break;
      default: {
        const _exhaustive = st;
        void _exhaustive;
        tone = "";
        break;
      }
    }
    return `region${tone}${active}`;
  };
  return `
  <svg class="body-svg" viewBox="0 0 140 280" role="img" aria-label="Тело">
    <ellipse class="${cls("head")}" data-region="head" cx="70" cy="28" rx="20" ry="22"></ellipse>
    <ellipse class="${cls("hair")}" data-region="hair" cx="70" cy="12" rx="18" ry="8"></ellipse>
    <ellipse class="${cls("eyes")}" data-region="eyes" cx="62" cy="26" rx="4" ry="3"></ellipse>
    <ellipse class="${cls("eyes")}" data-region="eyes" cx="78" cy="26" rx="4" ry="3"></ellipse>
    <ellipse class="${cls("nose")}" data-region="nose" cx="70" cy="32" rx="3" ry="4"></ellipse>
    <ellipse class="${cls("ears")}" data-region="ears" cx="48" cy="28" rx="4" ry="6"></ellipse>
    <ellipse class="${cls("ears")}" data-region="ears" cx="92" cy="28" rx="4" ry="6"></ellipse>
    <ellipse class="${cls("jaw")}" data-region="jaw" cx="70" cy="40" rx="12" ry="6"></ellipse>
    <rect class="${cls("teeth")}" data-region="teeth" x="64" y="36" width="12" height="5" rx="2"></rect>
    <rect class="${cls("neck")}" data-region="neck" x="62" y="46" width="16" height="14" rx="5"></rect>
    <rect class="${cls("shoulders")}" data-region="shoulders" x="28" y="58" width="84" height="14" rx="7"></rect>
    <rect class="${cls("chest")}" data-region="chest" x="46" y="70" width="48" height="36" rx="10"></rect>
    <rect class="${cls("back")}" data-region="back" x="56" y="78" width="28" height="18" rx="6" opacity="0.9"></rect>
    <rect class="${cls("stomach")}" data-region="stomach" x="48" y="106" width="44" height="30" rx="10"></rect>
    <rect class="${cls("arms")}" data-region="arms" x="18" y="70" width="14" height="36" rx="7"></rect>
    <rect class="${cls("arms")}" data-region="arms" x="108" y="70" width="14" height="36" rx="7"></rect>
    <ellipse class="${cls("elbows")}" data-region="elbows" cx="25" cy="108" rx="7" ry="6"></ellipse>
    <ellipse class="${cls("elbows")}" data-region="elbows" cx="115" cy="108" rx="7" ry="6"></ellipse>
    <rect class="${cls("wrists")}" data-region="wrists" x="18" y="118" width="14" height="10" rx="4"></rect>
    <rect class="${cls("wrists")}" data-region="wrists" x="108" y="118" width="14" height="10" rx="4"></rect>
    <ellipse class="${cls("hands")}" data-region="hands" cx="25" cy="134" rx="8" ry="7"></ellipse>
    <ellipse class="${cls("hands")}" data-region="hands" cx="115" cy="134" rx="8" ry="7"></ellipse>
    <rect class="${cls("hips")}" data-region="hips" x="48" y="134" width="44" height="16" rx="7"></rect>
    <rect class="${cls("legs")}" data-region="legs" x="50" y="148" width="16" height="18" rx="6"></rect>
    <rect class="${cls("legs")}" data-region="legs" x="74" y="148" width="16" height="18" rx="6"></rect>
    <rect class="${cls("thighs")}" data-region="thighs" x="50" y="164" width="16" height="28" rx="7"></rect>
    <rect class="${cls("thighs")}" data-region="thighs" x="74" y="164" width="16" height="28" rx="7"></rect>
    <ellipse class="${cls("knees")}" data-region="knees" cx="58" cy="196" rx="8" ry="7"></ellipse>
    <ellipse class="${cls("knees")}" data-region="knees" cx="82" cy="196" rx="8" ry="7"></ellipse>
    <rect class="${cls("calves")}" data-region="calves" x="50" y="202" width="16" height="36" rx="7"></rect>
    <rect class="${cls("calves")}" data-region="calves" x="74" y="202" width="16" height="36" rx="7"></rect>
    <ellipse class="${cls("feet")}" data-region="feet" cx="56" cy="246" rx="12" ry="7"></ellipse>
    <ellipse class="${cls("feet")}" data-region="feet" cx="84" cy="246" rx="12" ry="7"></ellipse>
  </svg>`;
}

async function renderHealthPanel(data) {
  const profile = data || (await api("/api/health-profile"));
  const metrics = profile.metrics || {};
  const body = profile.body || {};
  const selected = state.healthSelected;
  const region = body[selected] || { note: "", status: "ok", notes: [] };
  const regionLabel = HEALTH_REGIONS.find((r) => r.id === selected)?.label || selected;
  const notes = Array.isArray(region.notes) ? region.notes : [];
  const status = region.status || "ok";
  $("section-panel-inner").innerHTML = `
    <h2>Здоровье</h2>
    <p class="sp-sub">Тело и характеристики — клик по зоне</p>
    <div class="health-layout">
      ${bodySvg(body)}
      <div class="health-region-edit" data-health-region="${escapeAttr(selected)}">
        <strong>${escapeHtml(regionLabel)}</strong>
        <label>Состояние
          <select name="status" data-health-status>
            <option value="ok"${status === "ok" ? " selected" : ""}>Норма</option>
            <option value="warn"${status === "warn" ? " selected" : ""}>Внимание</option>
            <option value="bad"${status === "bad" ? " selected" : ""}>Проблема</option>
            <option value="unknown"${status === "unknown" ? " selected" : ""}>Неизвестно</option>
          </select>
        </label>
        <div class="health-notes">
          <span class="health-notes-label">Заметки</span>
          ${
            notes.length
              ? `<ul class="health-note-list">${notes
                  .map(
                    (n) => `
            <li class="health-note-item" data-health-note-id="${n.id}">
              <div class="health-note-meta">${escapeHtml(fmtShortDateTime(n.created_at))}</div>
              <p class="health-note-text">${escapeHtml(n.text)}</p>
              <button type="button" class="chip-clear" data-health-note-del="${n.id}">Удалить</button>
            </li>`,
                  )
                  .join("")}</ul>`
              : `<p class="empty" style="padding:0">Пока нет заметок</p>`
          }
          <textarea name="note" rows="3" placeholder="Новая заметка по зоне"></textarea>
          <button type="button" class="btn" data-health-note-add>Добавить заметку</button>
        </div>
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
    applySectionTheme(view === "finance" ? "#2a7a4b" : view === "goals" ? "#c9a227" : DEFAULT_THEME);
  }

  const taskViews = ["today", "project"];
  $("view-tasks").classList.toggle("hidden", !taskViews.includes(view));
  $("view-notes").classList.add("hidden");
  $("view-workouts").classList.add("hidden");
  $("view-history").classList.toggle("hidden", view !== "history");
  $("view-stats").classList.toggle("hidden", view !== "stats");
  $("view-finance").classList.toggle("hidden", view !== "finance");
  $("view-goals")?.classList.toggle("hidden", view !== "goals");

  if (!taskViews.includes(view) || !currentPanelKind()) hideSectionPanel();

  if (taskViews.includes(view)) $("task-kind").value = "task";

  const dueInput = $("task-due");
  if (view === "today") dueInput.value = todayIso();
  else if (view === "project") dueInput.value = "";

  updateTaskChips();
  syncWorkProjectChipVisibility();
  const main = document.querySelector(".main");
  if (main) {
    main.classList.add("content-wide");
    main.classList.toggle("finance-wide", view === "finance" || view === "goals");
    if (!prefersReducedMotion()) {
      main.classList.remove("view-swap");
      void main.offsetWidth;
      main.classList.add("view-swap");
    }
  }
  track("view_opened", "ui", null, { view, project_id: state.projectId });
  closeMobileNav();
  return refresh().catch(showListError);
}

function showListError() {
  const v = state.view;
  const taskViews = ["today", "project"];
  let root;
  if (taskViews.includes(v)) root = $("task-list");
  else if (v === "history") root = $("history-list");
  else if (v === "stats") root = $("stats-cards");
  else if (v === "finance") root = $("finance-page");
  else if (v === "goals") root = $("goals-stage");
  else return;
  if (!root) return;
  root.innerHTML =
    '<div class="empty">Не удалось загрузить. <button type="button" class="btn ghost small list-retry">Повторить</button></div>';
  root.querySelector(".list-retry")?.addEventListener("click", () => {
    refresh().catch(showListError);
  });
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
  else if (v === "finance") await loadFinancePage();
  else if (v === "goals") await window.notetaskGoals?.load?.();
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
    const hm = String(time).trim();
    if (!/^\d{1,2}:\d{2}$/.test(hm)) return date;
    const [h, m] = hm.split(":");
    const hh = String(Number(h)).padStart(2, "0");
    if (Number(h) > 23 || Number(m) > 59) return date;
    return `${date}T${hh}:${m}:00`;
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
  else if (item && (patch.priority != null || patch.due_at !== undefined || patch.due_start !== undefined || patch.remind_at !== undefined || patch.remind_rule !== undefined || patch.work_project_id !== undefined)) {
    state.motion.pulseId = taskId;
  }
  await api(`/api/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(patch) });
  await refresh();
}

function renderTaskAttrs(t, projectMap) {
  const due = taskDueParts(t);
  const dueStart = dueStartDay(t);
  const projectName = t.project_id ? projectMap[t.project_id] || "Раздел" : "Раздел";
  const hasProject = !!t.project_id;
  const hasPriority = t.priority !== 4;
  const hasDue = !!due.date || !!due.time || !!dueStart;
  const repeatRule = t.repeat_rule || "";
  const hasRepeat = !!repeatRule;
  const overdue = isOpenTaskOverdue(t);
  const dueChipLabel = formatDueChipLabel(t);
  const hasLocation = !!t.location;
  const hasCost = t.cost != null && Number(t.cost) !== 0;
  const hasRemind = !!t.remind_at || t.remind_rule === "hourly";
  const remindInput = taskRemindInputValue(t);
  const remindLabel = formatRemindChipLabel(t) || "Напомн.";
  const remindRule = t.remind_rule || "";
  const costType = t.cost_type === "income" ? "income" : "expense";
  const showWork = isWorkSectionId(t.project_id) || t.work_project_id != null;
  const workTitle = workProjectTitle(t.work_project_id);
  const hasWork = !!t.work_project_id;
  const hasHiddenChips =
    !hasProject ||
    (showWork && !hasWork) ||
    !hasPriority ||
    !(hasDue || hasRepeat) ||
    !hasRemind ||
    !hasLocation ||
    !hasCost;
  const expanded = state.expandedTaskAttrs.has(t.id);

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
    <div class="task-attrs${expanded ? " is-expanded" : ""}" data-task-id="${t.id}">
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
        <button type="button" class="chip-btn prio-${t.priority}${hasPriority ? " has-value" : ""}" aria-expanded="false">
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
        <button type="button" class="chip-btn${hasDue || hasRepeat ? " has-value" : ""}${overdue ? " is-overdue" : ""}" aria-expanded="false">
          <span class="chip-icon">${CHIP_ICON.time}</span>
          <span class="chip-label">${escapeHtml(dueChipLabel)}</span>
        </button>
        <div class="chip-menu chip-menu-wide hidden" role="dialog" aria-label="Срок и время">
          <label class="due-field-label">С <input type="date" data-task-field="due-start" value="${escapeAttr(dueStart)}" title="Начало периода" /></label>
          <label class="due-field-label">По <input type="date" data-task-field="due-date" value="${escapeAttr(due.date)}" title="Конец / срок" /></label>
          <input type="time" data-task-field="due-time" value="${escapeAttr(due.time)}" />
          ${
            hasDue || hasRepeat
              ? `<button type="button" class="chip-clear chip-clear-due" data-task-clear-due>Без срока</button>`
              : ""
          }
          ${quickDueButtonsHtml()}
          ${repeatButtonsHtml(repeatRule)}
        </div>
      </div>
      <div class="chip-popover">
        <button type="button" class="chip-btn${hasRemind ? " has-value" : ""}" aria-expanded="false">
          <span class="chip-icon">${CHIP_ICON.remind}</span>
          <span class="chip-label">${escapeHtml(truncateText(remindLabel, 14))}</span>
        </button>
        <div class="chip-menu chip-menu-wide hidden" role="dialog" aria-label="Напоминание" data-task-due-at="${escapeAttr(t.due_at || "")}">
          <input type="datetime-local" data-task-field="remind" value="${escapeAttr(remindInput)}" title="Напоминание" />
          ${remindPresetButtonsHtml("data-task-remind-preset", remindRule)}
          ${hasRemind ? `<button type="button" class="chip-clear" data-task-clear-remind>Без напоминания</button>` : ""}
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
      ${
        hasHiddenChips || expanded
          ? `<button type="button" class="chip-more" data-task-more aria-label="Ещё поля" aria-expanded="${expanded ? "true" : "false"}">⋯</button>`
          : ""
      }
    </div>`;
}

function taskDayKey(task) {
  if (!task.due_at) return "none";
  const day = task.due_at.slice(0, 10);
  const today = todayIso();
  if (task.status !== "done") {
    if (day < today) return today;
    const start = dueStartDay(task);
    if (start && start <= today && today <= day) return today;
  }
  return day;
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
      year: "numeric",
    });
  } catch {
    return dayKey;
  }
}

function sortTasksInDayGroup(tasks) {
  const { field, dir } = state.taskSort || { field: "due", dir: "asc" };
  const mul = dir === "desc" ? -1 : 1;
  const projectName = (t) => {
    const p = state.projects.find((x) => x.id === t.project_id);
    return (p?.name || "").toLowerCase();
  };
  return [...tasks].sort((a, b) => {
    let cmp = 0;
    switch (field) {
      case "priority":
        cmp = (a.priority || 4) - (b.priority || 4);
        break;
      case "project":
        cmp = projectName(a).localeCompare(projectName(b), "ru");
        break;
      case "amount": {
        const ca = a.cost == null ? -Infinity : Number(a.cost);
        const cb = b.cost == null ? -Infinity : Number(b.cost);
        cmp = ca - cb;
        break;
      }
      case "due":
      default: {
        const ta = taskTimeSortKey(a);
        const tb = taskTimeSortKey(b);
        cmp = ta - tb;
        break;
      }
    }
    if (cmp !== 0) return cmp * mul;
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


function syncTaskSortBar() {
  const bar = $("task-sort-bar");
  if (!bar) return;
  const { field, dir } = state.taskSort || { field: "due", dir: "asc" };
  bar.querySelectorAll("[data-sort-field]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.sortField === field);
  });
  const dirBtn = $("task-sort-dir");
  if (dirBtn) {
    dirBtn.textContent = dir === "desc" ? "↓" : "↑";
    dirBtn.setAttribute("aria-label", dir === "desc" ? "По убыванию" : "По возрастанию");
  }
}

function initTaskSortBar() {
  const bar = $("task-sort-bar");
  if (!bar || bar.dataset.bound) return;
  bar.dataset.bound = "1";
  bar.addEventListener("click", async (e) => {
    const fieldBtn = e.target.closest("[data-sort-field]");
    if (fieldBtn) {
      const field = fieldBtn.dataset.sortField;
      if (state.taskSort.field === field) {
        state.taskSort.dir = state.taskSort.dir === "asc" ? "desc" : "asc";
      } else {
        state.taskSort.field = field;
        state.taskSort.dir = field === "priority" ? "asc" : "asc";
      }
      saveTaskSort();
      syncTaskSortBar();
      if (["today", "project"].includes(state.view)) await loadTasks(state.view);
      return;
    }
    if (e.target.closest("[data-sort-dir]")) {
      state.taskSort.dir = state.taskSort.dir === "asc" ? "desc" : "asc";
      saveTaskSort();
      syncTaskSortBar();
      if (["today", "project"].includes(state.view)) await loadTasks(state.view);
    }
  });
  syncTaskSortBar();
}

function startInlineTitleEdit(titleEl) {
  const item = titleEl.closest(".item");
  if (!item || item.querySelector(".item-title-input")) return;
  const taskId = Number(item.dataset.id);
  const original = titleEl.textContent;
  const input = document.createElement("input");
  input.type = "text";
  input.className = "item-title-input";
  input.value = original;
  titleEl.replaceWith(input);
  input.focus();
  input.select();
  let saved = false;
  const restore = (text) => {
    const div = document.createElement("div");
    div.className = titleEl.className;
    div.textContent = text;
    input.replaceWith(div);
  };
  const cancel = () => {
    if (saved) return;
    saved = true;
    restore(original);
  };
  const save = async () => {
    if (saved) return;
    const raw = input.value.trim();
    if (!raw) {
      cancel();
      return;
    }
    const parsed = parseTaskInput(raw);
    const nextTitle = parsed.cleanTitle || raw;
    const patch = { title: nextTitle };
    if (parsed.meta.cost != null) {
      patch.cost = Number(parsed.meta.cost);
      patch.cost_type = parsed.meta.costType || "expense";
    }
    if (parsed.meta.priority) patch.priority = Number(parsed.meta.priority);
    const attrs = item.querySelector(".task-attrs");
    const fbDate = attrs?.querySelector('[data-task-field="due-date"]')?.value || "";
    const fbTime = attrs?.querySelector('[data-task-field="due-time"]')?.value || "";
    const due = resolveParsedDue(parsed.meta, fbDate, fbTime);
    if (due) patch.due_at = due;
    if (parsed.meta.repeat) patch.repeat_rule = parsed.meta.repeat;
    const remindLocal = resolveRemindLocal(parsed.meta, fbDate, fbTime);
    if (parsed.meta.remindHourly) {
      patch.remind_rule = "hourly";
      patch.remind_at = new Date(remindLocal || nextHourBoundaryLocal()).toISOString();
    } else if (remindLocal) {
      patch.remind_at = new Date(remindLocal).toISOString();
      patch.remind_rule = null;
    }
    if (parsed.meta.projectId) patch.project_id = parsed.meta.projectId;

    const onlyTitle = Object.keys(patch).length === 1;
    if (onlyTitle && nextTitle === original) {
      cancel();
      return;
    }
    saved = true;
    restore(nextTitle);
    try {
      await patchTask(taskId, patch);
    } catch (err) {
      alert(err.message || "Не удалось сохранить");
      await refresh();
    }
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      input.blur();
    } else if (e.key === "Escape") {
      e.preventDefault();
      saved = true;
      restore(original);
    }
  });
  input.addEventListener("blur", () => {
    void save();
  });
}

async function loadTasks(view) {
  let url = `/api/tasks?view=${view === "project" ? "all" : view}`;
  if (view === "project" && state.projectId) url += `&project_id=${state.projectId}`;
  const tasks = await api(url);
  const root = $("task-list");
  const sortBar = $("task-sort-bar");
  const projectMap = Object.fromEntries(state.projects.map((p) => [p.id, p.name]));
  if (sortBar) {
    const show = ["today", "project"].includes(view);
    sortBar.hidden = !show;
    if (show) syncTaskSortBar();
  }
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
    const result = await api(`/api/tasks/${id}/complete`, { method: "POST" });
    if (result?.rescheduled || result?.repeat_rule) {
      completeBtn.classList.remove("done");
      item?.classList.remove("item-completing");
      state.motion.pulseId = id;
      await loadTasks(state.view);
      return;
    }
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

function handleCaptureHash() {
  if (location.hash === "#capture") {
    openTaskCapture();
    // clear hash without reload so repeat hotkeys still fire
    history.replaceState(null, "", location.pathname + location.search);
  }
}

window.addEventListener("hashchange", handleCaptureHash);

function isTypingTarget(el) {
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}

function localInputValue(dt = new Date()) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
}

function parseRemindToken(raw) {
  const lower = String(raw || "").toLowerCase().replace(/\s+/g, " ").trim();
  const now = new Date();

  let m = lower.match(/^через\s+(\d+)\s*(?:мин(?:ут[уы]?)?|м)$/);
  if (m) {
    const dt = new Date(now.getTime() + Number(m[1]) * 60_000);
    return { remindAt: localInputValue(dt) };
  }
  m = lower.match(/^через\s+(\d+)\s*(?:час(?:а|ов)?|ч)$/);
  if (m) {
    const dt = new Date(now.getTime() + Number(m[1]) * 3_600_000);
    return { remindAt: localInputValue(dt) };
  }
  m = lower.match(/^за\s+(\d+)\s*(?:мин(?:ут[уы]?)?|м)$/);
  if (m) return { remindBeforeMinutes: Number(m[1]) };
  m = lower.match(/^за\s+(\d+)\s*(?:час(?:а|ов)?|ч)$/);
  if (m) return { remindBeforeMinutes: Number(m[1]) * 60 };

  m = lower.match(/^напомни\s+завтра\s+в\s+(\d{1,2})(?:[:.](\d{2}))?$/);
  if (m) {
    const dt = addDays(now, 1);
    dt.setHours(Number(m[1]), Number(m[2] || 0), 0, 0);
    return { remindAt: localInputValue(dt) };
  }
  m = lower.match(/^напомни\s+в\s+(\d{1,2})(?:[:.](\d{2}))?$/);
  if (m) {
    const dt = new Date(now);
    dt.setHours(Number(m[1]), Number(m[2] || 0), 0, 0);
    if (dt <= now) dt.setDate(dt.getDate() + 1);
    return { remindAt: localInputValue(dt) };
  }
  m = lower.match(/^напомни\s+(\d{1,2})(?:[:.](\d{2}))$/);
  if (m) {
    const dt = new Date(now);
    dt.setHours(Number(m[1]), Number(m[2] || 0), 0, 0);
    if (dt <= now) dt.setDate(dt.getDate() + 1);
    return { remindAt: localInputValue(dt) };
  }
  if (/^(?:напомнить|напомни|remind)$/.test(lower)) return { remindAtDue: true };
  return {};
}

document.addEventListener("keydown", (e) => {
  if (!e.ctrlKey || e.code !== "Space") return;
  if (isTypingTarget(document.activeElement) && document.activeElement?.id !== "task-title") return;
  e.preventDefault();
  openTaskCapture();
});

// events
if (!window.__notetaskLoginBound) {
  $("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errEl = $("login-error");
    const btn = e.submitter || $("login-btn") || $("login-form").querySelector('button[type="submit"]');
    errEl.classList.add("hidden");
    errEl.textContent = "Неверный пароль";
    if (btn) btn.disabled = true;
    try {
      const password = String($("password").value || "");
      if (!password) throw new Error("empty");
      const data = await api("/api/login", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      state.token = data.token;
      localStorage.setItem(TOKEN_KEY, state.token);
      showApp();
      await loadProjectsCache();
      setView("today");
      await refresh();
    } catch (ex) {
      showLogin();
      const msg = String(ex?.message || "");
      errEl.textContent = /empty/i.test(msg)
        ? "Введи пароль (кликни в поле, если браузер подставил сам)"
        : /wrong password|auth/i.test(msg)
          ? "Неверный пароль"
          : /network|AbortError|Failed to fetch/i.test(msg)
            ? "Сеть не отвечает. С домашнего Wi‑Fi: DNS 192.168.0.6 или hosts → todo.baski.pro, сайт только https://todo.baski.pro/"
            : "Не удалось войти. Обнови страницу (Ctrl+F5).";
      errEl.classList.remove("hidden");
    } finally {
      if (btn) btn.disabled = false;
    }
  });
}

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
  let due = resolveParsedDue(
    parsed.meta,
    $("task-due").value || "",
    $("task-due-time")?.value || "",
  );
  if (kind === "task" && !due && state.view === "today") due = todayIso();
  const remindRule =
    $("task-remind-rule")?.value || (parsed.meta.remindHourly ? "hourly" : "") || null;
  const remind = $("task-remind").value
    ? new Date($("task-remind").value).toISOString()
    : remindRule === "hourly"
      ? nextHourBoundaryLocal().toISOString()
      : null;
  const priority = parsed.meta.priority || Number($("task-priority").value);
  const title = parsed.cleanTitle || $("task-title").value.trim();
  const labelsNote = parsed.meta.labels?.length ? `Метки: ${parsed.meta.labels.join(", ")}` : "";
  const location = $("task-location").value.trim() || null;
  const costVal = $("task-cost").value
    ? Number($("task-cost").value)
    : parsed.meta.cost != null
      ? Number(parsed.meta.cost)
      : null;
  const costType = costVal
    ? $("task-cost-type-value").value || parsed.meta.costType || "expense"
    : null;
  const created = await api("/api/tasks", {
    method: "POST",
    body: JSON.stringify({
      title,
      notes: labelsNote,
      kind,
      priority,
      due_at: due,
      due_start: $("task-due-start")?.value || null,
      remind_at: remind,
      remind_rule: remindRule || null,
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
      repeat_rule: $("task-repeat")?.value || parsed.meta.repeat || null,
    }),
  });
  if (created?.id) state.motion.enterId = created.id;

  $("task-title").value = "";
  if ($("task-due-time")) $("task-due-time").value = "";
  if ($("task-remind-rule")) $("task-remind-rule").value = "";
  if ($("task-remind")) $("task-remind").value = "";
  if ($("task-due-start")) $("task-due-start").value = "";
  if ($("task-due")) delete $("task-due").dataset.dueTime;
  $("task-location").value = "";
  $("task-cost").value = "";
  $("task-cost-type-value").value = "expense";
  $("task-work-project").value = "";
  if ($("task-repeat")) $("task-repeat").value = "";
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
  if (isChipPopoverInteraction(e.target)) e.stopPropagation();
});

$("task-list").addEventListener("click", async (e) => {
  const titleEl = e.target.closest(".item-title");
  if (titleEl && !titleEl.classList.contains("done-title") && !e.target.closest(".task-attrs, .item-actions, .check")) {
    e.preventDefault();
    startInlineTitleEdit(titleEl);
    return;
  }
  const attrsRoot = e.target.closest(".task-attrs");
  if (attrsRoot) {
    const moreBtn = e.target.closest("[data-task-more]");
    if (moreBtn) {
      e.stopPropagation();
      const taskId = Number(attrsRoot.dataset.taskId);
      const next = !attrsRoot.classList.contains("is-expanded");
      attrsRoot.classList.toggle("is-expanded", next);
      moreBtn.setAttribute("aria-expanded", next ? "true" : "false");
      if (next) state.expandedTaskAttrs.add(taskId);
      else state.expandedTaskAttrs.delete(taskId);
      return;
    }
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
        due_start: null,
      });
      closeTaskPopovers();
      return;
    }
    if (e.target.closest("[data-task-clear-due]")) {
      e.stopPropagation();
      await patchTask(Number(attrsRoot.dataset.taskId), {
        due_at: null,
        due_start: null,
        repeat_rule: null,
      });
      closeTaskPopovers();
      return;
    }
    const remindPreset = e.target.closest("[data-task-remind-preset]");
    if (remindPreset) {
      e.stopPropagation();
      const menu = remindPreset.closest(".chip-menu");
      const dueAt = menu?.dataset.taskDueAt || attrsRoot.querySelector('[data-task-field="due-date"]')?.value || "";
      const dueTime = attrsRoot.querySelector('[data-task-field="due-time"]')?.value || "";
      const mergedDue = mergeTaskDue(dueAt, dueTime) || dueAt || null;
      const preset = remindPreset.dataset.taskRemindPreset;
      const iso = computeRemindPreset(preset, mergedDue);
      if (!iso) return;
      const patch =
        preset === "hourly"
          ? { remind_rule: "hourly", remind_at: iso }
          : { remind_rule: null, remind_at: iso };
      await patchTask(Number(attrsRoot.dataset.taskId), patch);
      closeTaskPopovers();
      return;
    }
    if (e.target.closest("[data-task-clear-remind]")) {
      e.stopPropagation();
      await patchTask(Number(attrsRoot.dataset.taskId), { remind_at: null, remind_rule: null });
      closeTaskPopovers();
      return;
    }
    const repeatBtn = e.target.closest("[data-task-repeat]");
    if (repeatBtn) {
      e.stopPropagation();
      const rule = repeatBtn.dataset.taskRepeat || null;
      const patch = { repeat_rule: rule || null };
      if (rule) {
        const dateInput = attrsRoot.querySelector('[data-task-field="due-date"]');
        const timeInput = attrsRoot.querySelector('[data-task-field="due-time"]');
        if (!dateInput?.value) {
          patch.due_at = mergeTaskDue(todayIso(), timeInput?.value || "");
        }
      }
      await patchTask(Number(attrsRoot.dataset.taskId), patch);
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
    if (isChipPopoverInteraction(e.target)) {
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
  if (field === "due-date" || field === "due-time" || field === "due-start") {
    const dateInput = attrsRoot.querySelector('[data-task-field="due-date"]');
    const startInput = attrsRoot.querySelector('[data-task-field="due-start"]');
    const timeInput = attrsRoot.querySelector('[data-task-field="due-time"]');
    let end = dateInput?.value || "";
    const start = startInput?.value || "";
    if (start && !end) {
      end = start;
      if (dateInput) dateInput.value = start;
    }
    await patchTask(taskId, {
      due_at: mergeTaskDue(end, timeInput?.value || "") || end || null,
      due_start: start || null,
    });
    closeTaskPopovers();
    return;
  }
  if (field === "remind") {
    await patchTask(taskId, { remind_at: remindAtIso(e.target.value), remind_rule: null });
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
  const payForm = e.target.closest("[data-work-pay-form]");
  if (payForm) {
    e.preventDefault();
    const workItem = payForm.closest("[data-work-id]");
    if (!workItem) return;
    const id = Number(workItem.dataset.workId);
    const fd = new FormData(payForm);
    const amount = Number(fd.get("amount"));
    if (!amount || amount <= 0) return;
    await api(`/api/work-projects/${id}/payments`, {
      method: "POST",
      body: JSON.stringify({
        amount,
        paid_at: String(fd.get("paid_at") || todayIso()),
        note: String(fd.get("note") || "").trim(),
        status: fd.get("planned") ? "planned" : "received",
      }),
    });
    await loadWorkProjectsCache();
    await renderWorkPanel();
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

$("section-panel").addEventListener("change", async (e) => {
  const payDate = e.target.closest("[data-work-pay-date]");
  if (payDate) {
    const form = payDate.closest("[data-work-pay-form]");
    const planned = form?.querySelector("[data-work-pay-planned]");
    if (planned) planned.checked = String(payDate.value || "") > todayIso();
    return;
  }
  const statusSel = e.target.closest("[data-health-status]");
  if (!statusSel) return;
  const box = statusSel.closest("[data-health-region]");
  if (!box) return;
  const region = box.dataset.healthRegion;
  const status = statusSel.value || "ok";
  await api("/api/health-profile", {
    method: "PUT",
    body: JSON.stringify({ metrics: {}, body: { [region]: { status } } }),
  });
  await renderHealthPanel();
});

$("section-panel").addEventListener("click", async (e) => {
  const shiftBtn = e.target.closest("[data-finance-shift]");
  if (shiftBtn) {
    e.preventDefault();
    const delta = Number(shiftBtn.dataset.financeShift) || 0;
    state.financeYm = shiftYearMonth(state.financeYm || currentYearMonth(), delta);
    await renderFinancePanel();
    return;
  }
  const finTask = e.target.closest("[data-finance-task]");
  if (finTask) {
    e.preventDefault();
    const taskId = Number(finTask.dataset.financeTask);
    const item = document.querySelector(`.item[data-id="${taskId}"]`);
    if (item) {
      item.classList.add("anim-pulse");
      item.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "center" });
    }
    return;
  }

  const regionEl = e.target.closest("[data-region]");
  if (regionEl) {
    state.healthSelected = regionEl.dataset.region;
    await renderHealthPanel();
    return;
  }
  if (e.target.id === "health-save-region") {
    return;
  }
  const noteAdd = e.target.closest("[data-health-note-add]");
  if (noteAdd) {
    const box = e.target.closest("[data-health-region]");
    if (!box) return;
    const region = box.dataset.healthRegion;
    const textarea = box.querySelector('[name="note"]');
    const text = textarea?.value.trim() || "";
    if (!text) return;
    await api(`/api/health-body/${encodeURIComponent(region)}/notes`, {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    await renderHealthPanel();
    return;
  }
  const noteDel = e.target.closest("[data-health-note-del]");
  if (noteDel) {
    const box = e.target.closest("[data-health-region]");
    if (!box) return;
    const region = box.dataset.healthRegion;
    const noteId = Number(noteDel.dataset.healthNoteDel);
    await api(`/api/health-body/${encodeURIComponent(region)}/notes/${noteId}`, { method: "DELETE" });
    await renderHealthPanel();
    return;
  }
  const workItem = e.target.closest("[data-work-id]");
  if (workItem) {
    const id = Number(workItem.dataset.workId);
    const payDel = e.target.closest("[data-work-pay-del]");
    if (payDel) {
      e.preventDefault();
      e.stopPropagation();
      const payId = Number(payDel.dataset.workPayDel);
      await api(`/api/work-projects/${id}/payments/${payId}`, { method: "DELETE" });
      await loadWorkProjectsCache();
      await renderWorkPanel();
      return;
    }
    const payRecv = e.target.closest("[data-work-pay-recv]");
    if (payRecv) {
      e.preventDefault();
      e.stopPropagation();
      const payId = Number(payRecv.dataset.workPayRecv);
      await api(`/api/work-projects/${id}/payments/${payId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: "received" }),
      });
      await loadWorkProjectsCache();
      await renderWorkPanel();
      return;
    }
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

function showBootError() {
  document.getElementById("boot-error")?.remove();
  const el = document.createElement("div");
  el.id = "boot-error";
  el.className = "boot-error";
  el.style.cssText =
    "position:fixed;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;padding:24px;text-align:center;z-index:9999;";
  el.innerHTML =
    '<p style="font-size:1.15rem;font-weight:600;margin:0">Нет связи с сервером</p>' +
    '<p style="color:var(--muted);max-width:320px;margin:0;font-size:0.9rem">В домашней сети Wi‑Fi роутер блокирует внешний адрес.</p>' +
    '<div style="display:flex;flex-direction:column;gap:10px;width:100%;max-width:300px;margin-top:8px">' +
    `<a class="btn" href="${lanFallbackUrl()}" style="text-decoration:none">Открыть через Wi‑Fi (192.168.0.6)</a>` +
    '<button type="button" class="btn ghost" data-boot-retry>Повторить</button>' +
    '</div>';
  el.querySelector("[data-boot-retry]")?.addEventListener("click", () => {
    if (!isLanHost() && goLanFallback()) return;
    location.reload();
  });
  el.querySelector("a")?.addEventListener("click", (e) => {
    e.preventDefault();
    goLanFallback();
  });
  document.body.appendChild(el);
}

const seenNotificationIds = new Set();

function showBrowserNotification(title, body) {
  if (!("Notification" in window)) return;
  if (Notification.permission === "granted") {
    try {
      new Notification(title, { body, icon: "/assets/icons/icon-192.png" });
    } catch {
      /* ignore */
    }
  }
}

async function pollNotifications() {
  if (!state.token) return;
  try {
    const rows = await api("/api/notifications?unread=1");
    for (const row of rows || []) {
      if (seenNotificationIds.has(row.id)) continue;
      seenNotificationIds.add(row.id);
      showBrowserNotification(row.title || "NoteTask", row.body || "");
    }
  } catch {
    /* ignore transient */
  }
}

function initNotificationPoll() {
  if (!("Notification" in window)) {
    window.setInterval(pollNotifications, 45_000);
    pollNotifications();
    return;
  }
  if (Notification.permission === "default") {
    Notification.requestPermission().catch(() => {});
  }
  window.setInterval(pollNotifications, 45_000);
  pollNotifications();
}

$("finance-page").addEventListener("click", (e) => {
  const filterBtn = e.target.closest("[data-fin-filter-col]");
  if (filterBtn) {
    e.preventDefault();
    e.stopPropagation();
    const col = filterBtn.dataset.finFilterCol;
    const menu = filterBtn.closest("th")?.querySelector(".fin-filter-menu");
    if (!menu) return;
    const willOpen = menu.classList.contains("hidden");
    document.querySelectorAll("#finance-page .fin-filter-menu").forEach((el) => {
      el.classList.add("hidden");
    });
    if (willOpen) {
      menu.classList.remove("hidden");
      positionLedgerFilterMenu(menu, filterBtn);
      state.financeFilterOpenCol = col;
    } else {
      state.financeFilterOpenCol = null;
    }
    return;
  }
  if (e.target.closest(".fin-filter-menu")) {
    e.stopPropagation();
    return;
  }
  const addLedger = e.target.closest("[data-fin-add-ledger]");
  if (addLedger) {
    e.preventDefault();
    addLedgerDraft();
    return;
  }
  const row = findLedgerRowFromEl(e.target);
  if (row) selectLedgerRow(row);
});

document.addEventListener("click", (e) => {
  if (e.target.closest(".fin-filter-menu, [data-fin-filter-col]")) return;
  closeLedgerFilterMenus();
});

$("finance-page").addEventListener("change", async (e) => {
  const filterMenu = e.target.closest(".fin-filter-menu");
  if (filterMenu) {
    const col = filterMenu.dataset.finFilterMenu;
    const boxes = [...filterMenu.querySelectorAll("input[type=checkbox]")];
    const checked = boxes.filter((box) => box.checked).map((box) => box.dataset.finFilterVal ?? "");
    if (!state.financeLedgerFilters) state.financeLedgerFilters = {};
    state.financeLedgerFilters[col] = checked.length === boxes.length ? null : new Set(checked);
    renderFinancePage();
    return;
  }
  const fieldEl = e.target.closest("[data-fin-field]");
  if (!fieldEl) return;
  const row = findLedgerRowFromEl(fieldEl);
  if (!row) return;
  const field = fieldEl.dataset.finField;
  let value = fieldEl.value;
  if (field === "amount") {
    const parsed = parseLedgerAmount(value);
    if (parsed === null) {
      alert("Ошибка");
      await loadFinancePage();
      return;
    }
    value = parsed;
  }
  await saveLedgerField(row, field, value);
});

$("finance-page").addEventListener("focusin", (e) => {
  const row = findLedgerRowFromEl(e.target);
  if (row) selectLedgerRow(row);
});

$("finance-page").addEventListener("keydown", async (e) => {
  const inTable = Boolean(e.target.closest(".fin-ledger-table"));
  const menuOpen = Boolean(state.financeFilterOpenCol);
  const inField = Boolean(e.target.closest("input, textarea, select"));

  if (menuOpen && e.key !== "Escape") return;

  if (e.key === "Escape") {
    if (menuOpen) {
      e.preventDefault();
      closeLedgerFilterMenus();
      return;
    }
    if (inTable) {
      e.preventDefault();
      const tr = e.target.closest("tr[data-fin-row]") || document.querySelector("#finance-page tr[data-fin-row].is-selected");
      e.target.blur?.();
      tr?.focus();
    }
    return;
  }

  if (!inTable) return;

  if (e.key === "Tab") {
    e.preventDefault();
    cycleLedgerField(e.shiftKey);
    return;
  }

  if (e.key === "Enter" && inField) {
    e.preventDefault();
    moveLedgerFieldDown();
    return;
  }

  if (!inField && (e.key === "ArrowUp" || e.key === "ArrowDown" || e.key === "ArrowLeft" || e.key === "ArrowRight")) {
    e.preventDefault();
    moveLedgerSelection(e.key === "ArrowDown" || e.key === "ArrowRight" ? 1 : -1);
    return;
  }

  if (!inField && (e.key === "Delete" || e.key === "Backspace")) {
    const row = findLedgerRowFromEl(document.querySelector("#finance-page tr[data-fin-row].is-selected"))
      || findLedgerRowByKey(state.financeSelectedRowKey);
    if (!row) return;
    e.preventDefault();
    await deleteLedgerRow(row);
  }
});

async function boot() {
  consumeTokenRestore();
  state.token = localStorage.getItem(TOKEN_KEY) || "";
  addWorkoutSetRow();
  $("wo-started").value = localInputValue();
  initTaskMetaChips();
  initTaskTitleHighlight();
  initTaskSortBar();
  initSidebarToggle();
  hideTaskForm();
  hideDesktopDownloads();
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
    hideDesktopDownloads();
    track("app_opened", "ui", null, { path: location.pathname });
    setView("today");
    handleCaptureHash();
    initNotificationPoll();
  } catch (err) {
    if (isAuthError(err)) showLogin();
    else if (!isLanHost() && goLanFallback()) return;
    else showBootError();
  }
}

boot();

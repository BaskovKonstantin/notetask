# NoteTask Desktop + Android Implementation Plan

> **For agentic workers:** implement task-by-task; checkboxes below.

**Goal:** Tauri Windows/Linux shell with global Ctrl+Space + Flutter Android Today widget.

**Architecture:** Desktop = thin Tauri WebView to production URL. Mobile = Flutter API client + `home_widget`.

**Tech Stack:** Tauri 2, Rust plugins, Flutter 3.x, `home_widget`, existing FastAPI.

## Global Constraints

- API base: `https://todo.baski.pro` (LAN may need hosts → `192.168.0.6`)
- Do not commit `.env` / secrets
- Conventional commits

---

### Task 1: Tauri scaffold `desktop/`

- [ ] Create Tauri 2 app (npm + Rust)
- [ ] Config: window title NoteTask, load `https://todo.baski.pro/`
- [ ] Build smoke on Linux

### Task 2: Tray + close-to-tray + autostart + Ctrl+Space

- [ ] System tray menu
- [ ] Global shortcut Ctrl+Space → show + `#capture`
- [ ] Autostart plugin enabled by default on first run (or settings)

### Task 3: Web capture hook

- [ ] `app.js`: on `#capture` / `notetask-capture` event → `openTaskCapture()`
- [ ] Bump asset version

### Task 4: Flutter Android

- [ ] Scaffold `mobile/`
- [ ] Login + Today screen
- [ ] `home_widget` Android widget

### Task 5: Docs + commit

- [ ] Update `context/context.md`
- [ ] README build notes (Windows MSI / Android APK)

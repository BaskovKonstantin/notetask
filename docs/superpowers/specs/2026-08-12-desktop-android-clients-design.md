# NoteTask Desktop + Android Clients — Design

Approved: 2026-08-12

## Goals

1. **Windows desktop (Tauri 2):** tray app wrapping `https://todo.baski.pro/`, global **Ctrl+Space**, autostart, minimize-to-tray.
2. **Android (Flutter):** Today list + home-screen widget «Сегодня», same API/password auth.

## Desktop

- WebView loads live site (always fresh UI).
- Plugins: `global-shortcut`, `autostart`, `shell` (open URL if needed).
- Ctrl+Space → show + focus window → navigate/emit `#capture` so web opens task capture.
- Close button → hide to tray (not quit); tray Quit exits.
- Updater: defer to v1.1 (shell rarely changes); document release folder `/desktop/`.

## Android

- Flutter app: login → JWT in secure storage → Today tasks (list, complete, add).
- Widget via `home_widget`: open today tasks; tap opens app.
- Full web parity out of scope for v1.

## Order

1. Tauri desktop
2. Web `#capture` hook
3. Flutter Today + widget

# NoteTask Desktop (Tauri)

Thin Windows/Linux shell around https://todo.baski.pro/

## Features

- Global **Ctrl+Space** → show window + task capture (`#capture`)
- System tray: Показать / Новая задача / Выход
- Close → hide to tray (Quit only from tray)
- Autostart enabled on first run

## Dev (Linux)

```bash
cd desktop
npm install
npm run tauri dev
```

Needs: Rust, WebKitGTK (see Tauri Linux prerequisites).

## Build Windows

On a Windows machine with Rust + WebView2:

```powershell
cd desktop
npm install
npm run tauri build
```

Installer under `src-tauri/target/release/bundle/`.

## LAN note

If the site does not load, add hosts: `192.168.0.6 todo.baski.pro`

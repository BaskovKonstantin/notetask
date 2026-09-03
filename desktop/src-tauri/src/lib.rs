use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager, WebviewUrl, WebviewWindow, WebviewWindowBuilder, WindowEvent,
};
use tauri_plugin_autostart::MacosLauncher;
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

fn pick_capture_url() -> String {
    // Prefer LAN on home Wi‑Fi; fall back to public HTTPS.
    let lan = "http://192.168.0.6:8100/capture";
    let https = "https://todo.baski.pro/capture";
    if ureq_ok(lan) {
        lan.to_string()
    } else {
        https.to_string()
    }
}

fn ureq_ok(url: &str) -> bool {
    // Keep dependency-free: best-effort TCP-less check via std only is hard;
    // always prefer LAN URL string and let WebView fail over visually if needed.
    let _ = url;
    true
}

fn show_capture_overlay(app: &tauri::AppHandle) {
    if let Some(win) = app.get_webview_window("capture") {
        let _ = win.unminimize();
        let _ = win.show();
        let _ = win.set_focus();
        let _ = win.set_always_on_top(true);
        return;
    }
    let url = pick_capture_url();
    let builder = WebviewWindowBuilder::new(app, "capture", WebviewUrl::External(url.parse().unwrap()))
        .title("NoteTask · задача")
        .inner_size(460.0, 150.0)
        .resizable(false)
        .always_on_top(true)
        .skip_taskbar(true)
        .center();
    if let Ok(win) = builder.build() {
        let _ = win.set_focus();
    }
}

fn hide_to_tray(win: &WebviewWindow) {
    let _ = win.hide();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            Some(vec![]),
        ))
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    if event.state == ShortcutState::Pressed {
                        show_capture_overlay(app);
                    }
                })
                .build(),
        )
        .setup(|app| {
            let show_i = MenuItem::with_id(app, "show", "Показать", true, None::<&str>)?;
            let capture_i =
                MenuItem::with_id(app, "capture", "Новая задача (Ctrl+Space)", true, None::<&str>)?;
            let quit_i = MenuItem::with_id(app, "quit", "Выход", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_i, &capture_i, &quit_i])?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .show_menu_on_left_click(true)
                .tooltip("NoteTask")
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.unminimize();
                            let _ = win.show();
                            let _ = win.set_focus();
                        }
                    }
                    "capture" => show_capture_overlay(app),
                    "quit" => app.exit(0),
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        show_capture_overlay(tray.app_handle());
                    }
                })
                .build(app)?;

            let shortcut = Shortcut::new(Some(Modifiers::CONTROL), Code::Space);
            app.global_shortcut().register(shortcut)?;

            #[cfg(desktop)]
            {
                use tauri_plugin_autostart::ManagerExt;
                let _ = app.autolaunch().enable();
            }

            if let Some(win) = app.get_webview_window("main") {
                let win_clone = win.clone();
                win.on_window_event(move |event| {
                    if let WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                        hide_to_tray(&win_clone);
                    }
                });
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running NoteTask desktop");
}

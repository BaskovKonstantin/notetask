# NoteTask Mobile (Flutter / Android)

Today list + home-screen widget «Сегодня».

## Setup

```bash
export PATH="$HOME/flutter/bin:$PATH"   # if Flutter installed via clone
cd mobile
flutter pub get
flutter run
```

API URL (default production):

```bash
flutter run --dart-define=API_BASE=https://todo.baski.pro
# LAN:
flutter run --dart-define=API_BASE=http://192.168.0.6:8100
```

## Widget

After install: long-press home screen → widgets → **NoteTask · Сегодня**.  
Data refreshes when you open the app / pull-to-refresh.

## Build APK

```bash
flutter build apk --release --dart-define=API_BASE=https://todo.baski.pro
```

Output: `build/app/outputs/flutter-apk/app-release.apk`

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

## Build APK (WebView of todo.baski.pro + widget)

Flutter SDK is not required. From repo root:

```bash
cd mobile-android
./gradlew assembleRelease
../scripts/publish-downloads.sh
```

Output: `mobile-android/app/build/outputs/apk/release/app-release.apk` → `data/downloads/NoteTask.apk`.

Same `applicationId` as the old Flutter APK (`pro.baski.notetask_mobile`) so Android can upgrade in place.

In-app updates: on launch the app calls `GET /api/android-update` and, if `versionCode` is newer, shows **Обновить**. First install of 0.3.0+ still comes from `/download`; later APKs install from inside the app. `publish-downloads.sh` writes `data/downloads/android-version.json`.

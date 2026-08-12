#!/usr/bin/env bash
# Publish installers into data/downloads (served at /download and /downloads/*)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/data/downloads"
mkdir -p "$OUT"

APK_SRC="$ROOT/mobile/build/app/outputs/flutter-apk/app-release.apk"
WIN_PUBLISH="$ROOT/desktop-win/NoteTaskWin/publish/NoteTask.exe"
EXTRA_WIN="${1:-}"

if [[ -f "$APK_SRC" ]]; then
  cp -f "$APK_SRC" "$OUT/NoteTask.apk"
  echo "OK Android -> $OUT/NoteTask.apk ($(du -h "$OUT/NoteTask.apk" | cut -f1))"
else
  echo "SKIP Android: build with: cd mobile && flutter build apk --release --dart-define=API_BASE=https://todo.baski.pro"
fi

if [[ -n "$EXTRA_WIN" && -f "$EXTRA_WIN" ]]; then
  cp -f "$EXTRA_WIN" "$OUT/NoteTask-Setup.exe"
  echo "OK Windows (arg) -> $OUT/NoteTask-Setup.exe"
elif [[ -f "$WIN_PUBLISH" ]]; then
  cp -f "$WIN_PUBLISH" "$OUT/NoteTask-Setup.exe"
  echo "OK Windows -> $OUT/NoteTask-Setup.exe ($(du -h "$OUT/NoteTask-Setup.exe" | cut -f1))"
else
  echo "SKIP Windows: cd desktop-win/NoteTaskWin && dotnet publish -c Release -r win-x64 --self-contained -p:PublishSingleFile=true -o ./publish"
fi

curl -sS "http://127.0.0.1:8100/api/downloads" | python3 -m json.tool || true

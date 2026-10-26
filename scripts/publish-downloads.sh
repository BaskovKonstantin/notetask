#!/usr/bin/env bash
# Publish installers into data/downloads (served at /download and /downloads/*)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/data/downloads"
mkdir -p "$OUT"

APK_SRC="$ROOT/mobile-android/app/build/outputs/apk/release/app-release.apk"
FLUTTER_APK="$ROOT/mobile/build/app/outputs/flutter-apk/app-release.apk"
if [[ ! -f "$APK_SRC" && -f "$FLUTTER_APK" ]]; then
  APK_SRC="$FLUTTER_APK"
fi
WIN_PUBLISH="$ROOT/desktop-win/NoteTaskWin/publish/NoteTask.exe"
EXTRA_WIN="${1:-}"

if [[ -f "$APK_SRC" ]]; then
  cp -f "$APK_SRC" "$OUT/NoteTask.apk"
  echo "OK Android -> $OUT/NoteTask.apk ($(du -h "$OUT/NoteTask.apk" | cut -f1))"
  AAPT=""
  if [[ -n "${ANDROID_HOME:-}${ANDROID_SDK_ROOT:-}" ]]; then
    AAPT=$(ls -1 "${ANDROID_HOME:-$ANDROID_SDK_ROOT}"/build-tools/*/aapt 2>/dev/null | tail -n 1 || true)
  fi
  if [[ -n "$AAPT" && -x "$AAPT" ]]; then
    BADGING=$("$AAPT" dump badging "$OUT/NoteTask.apk")
    VC=$(printf '%s\n' "$BADGING" | sed -n "s/.*versionCode='\\([0-9]*\\)'.*/\\1/p" | head -n 1)
    VN=$(printf '%s\n' "$BADGING" | sed -n "s/.*versionName='\\([^']*\\)'.*/\\1/p" | head -n 1)
    if [[ -n "$VC" ]]; then
      python3 - <<PY
import json
from pathlib import Path
Path("$OUT/android-version.json").write_text(
    json.dumps({"versionCode": int("$VC"), "versionName": "$VN"}, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
print("OK android-version.json versionCode=$VC versionName=$VN")
PY
    fi
  else
    echo "WARN aapt not found; write android-version.json by hand for in-app updates"
  fi
else
  echo "SKIP Android: cd mobile-android && ./gradlew assembleRelease"
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

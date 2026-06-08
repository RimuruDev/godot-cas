#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Пересборка Godot CAS AAR (godot4) и установка его в addon игры.
#
# Когда нужно: вышла новая версия CAS SDK / поправил GodotCas.java.
# Запуск: двойной клик в Finder, либо `bash rebuild_aar.command`.
#
# Куда кладёт готовый aar:
#   1) <форк>/release/godot4/GodotCas.<ver>.release.aar
#   2) если задан GODOT_CAS_ADDON_DIR — туда (для любого проекта);
#      иначе — в addon проекта MurderDronesCatClicker по умолчанию.
#
# Требования: Android SDK (ANDROID_HOME / ~/Library/Android/sdk), JDK 17–22
# (Gradle 8.7 не дружит с JDK 25). NDK версия указана в godot4/build.gradle.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

FORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$FORK_DIR"

DEFAULT_ADDON_DIR="/Users/rimurutempest/RimuruDev/GodotProjects/MurderDronesCatClicker/addons/godot_cas/android"
ADDON_DIR="${GODOT_CAS_ADDON_DIR:-$DEFAULT_ADDON_DIR}"

export ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}"
if [[ -z "${JAVA_HOME:-}" ]] && command -v /usr/libexec/java_home >/dev/null 2>&1; then
  export JAVA_HOME="$(/usr/libexec/java_home -v 22 2>/dev/null || /usr/libexec/java_home -v 17 2>/dev/null || /usr/libexec/java_home 2>/dev/null || true)"
fi

echo "[CAS] FORK_DIR=$FORK_DIR"
echo "[CAS] ANDROID_HOME=$ANDROID_HOME"
echo "[CAS] JAVA_HOME=$JAVA_HOME"
echo "[CAS] ADDON_DIR=$ADDON_DIR"

echo "[CAS] Building godot4 release AAR..."
./gradlew :godot4:assembleRelease --no-daemon

AAR_PATH="$(ls -t godot4/build/outputs/aar/GodotCas.*.release.aar 2>/dev/null | head -1 || true)"
if [[ -z "$AAR_PATH" || ! -f "$AAR_PATH" ]]; then
  echo "[CAS] ERROR: собранный aar не найден в godot4/build/outputs/aar/"
  exit 1
fi
AAR_NAME="$(basename "$AAR_PATH")"
echo "[CAS] Built: $AAR_NAME"

mkdir -p release/godot4
cp -f "$AAR_PATH" "release/godot4/$AAR_NAME"

if [[ -d "$ADDON_DIR" ]]; then
  cp -f "$AAR_PATH" "$ADDON_DIR/$AAR_NAME"
  echo "[CAS] Installed into addon: $ADDON_DIR/$AAR_NAME"
else
  echo "[CAS] ADDON_DIR не найден ($ADDON_DIR) — пропускаю установку в проект."
  echo "[CAS] Скопируй вручную: $AAR_PATH"
fi

echo "[CAS] Готово."
echo "[CAS] ВНИМАНИЕ: если имя/версия aar изменились — обнови RELEASE_AAR в"
echo "      addons/godot_cas/godot_cas_export_plugin.gd и cas-sdk версию там же."

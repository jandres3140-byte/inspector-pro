[app]
title = jcamp029.pro
package.name = jcamp029pro
package.domain = pro.jcamp029

source.dir = .
source.include_exts = py
version = 0.1

requirements = python3,kivy

orientation = portrait
fullscreen = 0

# Si tu entrypoint no es main.py, ajusta esta línea (por defecto suele ser main.py)
# entrypoint = main.py


[buildozer]
log_level = 2
warn_on_root = 1


[android]
# --- CLAVE: forzar SDK estable (evita 37.0.0-rc1) ---
android.api = 33
android.minapi = 21
android.ndk_api = 21
android.build_tools_version = 33.0.2

# --- CLAVE: usar el SDK que instalas en GitHub Actions (no ~/.buildozer) ---
# En GitHub Actions el HOME del runner es /home/runner
android.sdk_path = /home/runner/android-sdk

# --- Recomendado: que acepte licencias automáticamente si tu versión de buildozer lo soporta ---
android.accept_sdk_license = True

# Arquitecturas típicas (puedes dejar solo una si quieres)
android.archs = arm64-v8a, armeabi-v7a

# Permite usar AndroidX (suele evitar dolores con dependencias)
android.enable_androidx = True

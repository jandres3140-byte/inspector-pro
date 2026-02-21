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

# --- ANDROID (debe ir aquí en [app]) ---
android.api = 33
android.minapi = 21
android.ndk_api = 21
android.build_tools_version = 33.0.2

# Forzar a usar el SDK instalado por el workflow
android.sdk_path = /home/runner/android-sdk

# Aceptar licencias (si tu versión lo soporta)
android.accept_sdk_license = True

# Arquitecturas típicas
android.archs = arm64-v8a, armeabi-v7a

# AndroidX (útil para compatibilidad)
android.enable_androidx = True


[buildozer]
log_level = 2
warn_on_root = 1

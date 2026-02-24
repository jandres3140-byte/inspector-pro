[app]
title = jcamp029.pro
package.name = jcamp029pro
package.domain = pro.jcamp029

# Compila SOLO la app Android (no Streamlit del root)
source.dir = android
source.include_exts = py,png,jpg,jpeg,kv,ttf

version = 0.1

# Dependencias
requirements = python3,kivy,reportlab,Pillow,plyer,androidstorage4kivy

# Archivo principal Kivy
entrypoint = main.py

orientation = portrait
fullscreen = 0

# ANDROID (estable para p4a/CI)
android.minapi = 21
android.api = 33
android.build_tools_version = 33.0.2

# SOLO una arquitectura mientras depuramos (evita duplicar errores y logs gigantes)
android.archs = arm64-v8a

# AndroidX
android.enable_androidx = True

# Release artifact
android.release_artifact = apk

# Permisos (Android 13+ usa READ_MEDIA_IMAGES; los legacy se mantienen por compatibilidad)
android.permissions = READ_MEDIA_IMAGES,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# RELEASE SIGNING (para producción real: mover a Secrets)
android.release_keystore = keystore.jks
android.release_keyalias = jcamp029
android.release_keystore_passwd = jcamp029pro
android.release_keyalias_passwd = jcamp029pro


[buildozer]
log_level = 2
warn_on_root = 1

[app]
title = jcamp029.pro
package.name = jcamp029pro
package.domain = pro.jcamp029

# ✅ Compila SOLO la app Android (no el Streamlit del root)
source.dir = android
source.include_exts = py,png,jpg,jpeg,kv,ttf

version = 0.1

# ✅ Dependencias reales (PDF + imágenes + selector + compartir + storage)
# 🔥 Fix: forzar Python 3.10 para evitar fallo de compilación reportlab (_rl_accel.c) en p4a/NDK
requirements = python3==3.10.12,kivy,reportlab,Pillow,plyer,androidstorage4kivy

# ✅ Archivo principal Kivy
entrypoint = main.py

orientation = portrait
fullscreen = 0

# ANDROID
android.api = 34
android.minapi = 21
android.ndk_api = 21
android.build_tools_version = 34.0.0

# ✅ NO fijar SDK hardcodeado (en Actions se define ANDROID_SDK_ROOT)
# android.sdk_path = /home/runner/android-sdk

# Arquitecturas
android.archs = arm64-v8a, armeabi-v7a

# AndroidX
android.enable_androidx = True

# ✅ Release
android.release_artifact = apk

# ✅ Permisos (fotos + storage)
android.permissions = READ_MEDIA_IMAGES,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# RELEASE SIGNING (⚠️ para venta real después lo movemos a secrets)
android.release_keystore = keystore.jks
android.release_keyalias = jcamp029
android.release_keystore_passwd = jcamp029pro
android.release_keyalias_passwd = jcamp029pro


[buildozer]
log_level = 2
warn_on_root = 1

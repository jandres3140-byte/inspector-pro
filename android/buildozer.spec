[app]
title = jcamp029.pro
package.name = jcamp029pro
package.domain = pro.jcamp029

# ✅ Como el workflow hace "cd android", la raíz del proyecto es "."
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,ttf

version = 0.1

# ✅ PDF con fpdf2 (sin ReportLab)
requirements = python3,kivy,fpdf2,Pillow,plyer,androidstorage4kivy

entrypoint = main.py

orientation = portrait
fullscreen = 0

# ANDROID
android.minapi = 21
android.api = 34
android.ndk_api = 21
android.build_tools_version = 34.0.0

# ✅ Incluye 64 y 32 bits (evita crashes por libs/arquitectura)
android.archs = arm64-v8a, armeabi-v7a

# ✅ Bootstrap explícito (Kivy)
p4a.bootstrap = sdl2

# AndroidX
android.enable_androidx = True

# Artifact
android.release_artifact = apk

# Permisos (fotos + storage)
android.permissions = READ_MEDIA_IMAGES,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# RELEASE SIGNING (después lo movemos a secrets)
android.release_keystore = keystore.jks
android.release_keyalias = jcamp029
android.release_keystore_passwd = jcamp029pro
android.release_keyalias_passwd = jcamp029pro

[buildozer]
log_level = 2
warn_on_root = 1

[app]
title = jcamp029.pro
package.name = jcamp029pro
package.domain = pro.jcamp029

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,ttf

version = 0.1.9

requirements = python3,kivy,Pillow,plyer,androidstorage4kivy

entrypoint = main.py

orientation = portrait
fullscreen = 0

android.minapi = 23
android.api = 33
android.ndk_api = 23


android.archs = arm64-v8a

p4a.bootstrap = sdl2
android.enable_androidx = True

# ✅ Para diagnóstico: sin permisos (evita bloqueos raros al inicio)
android.permissions = READ_MEDIA_IMAGES,READ_MEDIA_VIDEO,READ_MEDIA_AUDIO

# ✅ Para diagnóstico: NO firmar release aquí (debug no lo necesita)
# android.release_keystore = keystore.jks
# android.release_keyalias = jcamp029
# android.release_keystore_passwd = jcamp029pro
# android.release_keyalias_passwd = jcamp029pro

[buildozer]
log_level = 2
warn_on_root = 1

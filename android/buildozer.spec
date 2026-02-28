[app]
title = jcamp029.pro
package.name = jcamp029pro
package.domain = pro.jcamp029

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,ttf

version = 0.1.9

requirements = python3,kivy,fpdf2,Pillow,plyer,androidstorage4kivy

entrypoint = main.py

orientation = portrait
fullscreen = 0

android.minapi = 23
android.api = 34
android.ndk_api = 23
android.build_tools_version = 34.0.0

android.archs = arm64-v8a, armeabi-v7a

p4a.bootstrap = sdl2
android.enable_androidx = True

# ✅ Para diagnóstico: sin permisos (evita bloqueos raros al inicio)
android.permissions =

# ✅ Para diagnóstico: NO firmar release aquí (debug no lo necesita)
# android.release_keystore = keystore.jks
# android.release_keyalias = jcamp029
# android.release_keystore_passwd = jcamp029pro
# android.release_keyalias_passwd = jcamp029pro

[buildozer]
log_level = 2
warn_on_root = 1

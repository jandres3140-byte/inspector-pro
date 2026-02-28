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

# ANDROID (más estable para Kivy en equipos reales)
android.minapi = 21
android.api = 33
android.ndk_api = 23
# android.build_tools_version = 34.0.0  # (déjalo comentado; que use el del SDK)

# ✅ SOLO 64-bit (evita varios crashes sdl2)
android.archs = arm64-v8a

# ✅ Bootstrap explícito (Kivy)
p4a.bootstrap = sdl2

# AndroidX
android.enable_androidx = True

# Artifact
android.release_artifact = apk

# Permisos (Android 13/14)
# READ_EXTERNAL_STORAGE y WRITE_EXTERNAL_STORAGE ya no aplican bien en API 33+
# Con picker/SAF + androidstorage4kivy normalmente basta esto:
android.permissions = READ_MEDIA_IMAGES

# RELEASE SIGNING (ideal mover a secrets; por ahora lo dejo igual que tú)
android.release_keystore = keystore.jks
android.release_keyalias = jcamp029
android.release_keystore_passwd = jcamp029pro
android.release_keyalias_passwd = jcamp029pro

[buildozer]
log_level = 2
warn_on_root = 1

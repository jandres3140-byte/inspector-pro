[app]
title = jcamp029.pro
package.name = jcamp029pro
package.domain = pro.jcamp029

source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,ttf

version = 0.1

requirements = python3,kivy,fpdf2,Pillow,plyer,androidstorage4kivy

entrypoint = main.py

orientation = portrait
fullscreen = 0

android.minapi = 21
android.api = 33
android.build_tools_version = 33.0.2
android.archs = arm64-v8a

android.enable_androidx = True
android.release_artifact = apk

android.permissions = READ_MEDIA_IMAGES,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

android.release_keystore = keystore.jks
android.release_keyalias = jcamp029
android.release_keystore_passwd = jcamp029pro
android.release_keyalias_passwd = jcamp029pro

[buildozer]
log_level = 2
warn_on_root = 1

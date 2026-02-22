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

# ANDROID
android.api = 34
android.minapi = 21
android.ndk_api = 21
android.build_tools_version = 34.0.0

# Forzar SDK del workflow (runner)
android.sdk_path = /home/runner/android-sdk

# Arquitecturas
android.archs = arm64-v8a, armeabi-v7a

# AndroidX
android.enable_androidx = True

# RELEASE SIGNING (la keystore la genera el workflow)
android.release_keystore = keystore.jks
android.release_keyalias = jcamp029
android.release_keystore_passwd = jcamp029pro
android.release_keyalias_passwd = jcamp029pro


[buildozer]
log_level = 2
warn_on_root = 1

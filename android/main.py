from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label

class Root(BoxLayout):
    pass

class MainApp(App):
    def build(self):
        box = BoxLayout(orientation="vertical", padding=20, spacing=20)
        box.add_widget(Label(text="OK ✅ App de diagnóstico", font_size=24))
        box.add_widget(Label(text="Si ves esto, Kivy corre bien.\nEl cierre venía de imports/código.", font_size=16))
        return box

if __name__ == "__main__":
    MainApp().run()

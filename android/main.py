import os
from datetime import datetime

from kivy.app import App
from kivy.clock import mainthread
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from plyer import filechooser, share

self.shared_storage = SharedStorage()
self.chooser = Chooser(self.shared_storage)
import core


def _now_str():
    return datetime.now().strftime("%d-%m-%Y")


def _safe_text(x: str) -> str:
    return (x or "").strip()


class FieldRow(BoxLayout):
    def __init__(self, title: str, widget, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(4), size_hint_y=None, height=dp(86), **kwargs)
        self.add_widget(Label(text=title, size_hint_y=None, height=dp(22)))
        self.add_widget(widget)


class InspectorRoot(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(10), padding=dp(12), **kwargs)

        self.fotos = []  # List[Tuple[name, bytes]]
        self.firma = None  # Optional[Tuple[name, bytes]]
        self.last_pdf_path = ""

        self.scroll = ScrollView()
        self.form = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        self.form.bind(minimum_height=self.form.setter("height"))
        self.scroll.add_widget(self.form)
        self.add_widget(self.scroll)

        # Campos
        self.titulo = TextInput(text="Informe Técnico de Inspección", multiline=False)
        self.fecha = TextInput(text=_now_str(), multiline=False)
        self.disciplina = Spinner(text="Eléctrica", values=["Eléctrica", "Mecánica", "Instrumental", "Civil", "Otra"])
        self.riesgo = Spinner(text="Medio", values=["Bajo", "Medio", "Alto"])
        self.equipo = TextInput(text="", multiline=False)
        self.ubicacion = TextInput(text="", multiline=False)
        self.inspector = TextInput(text="JORGE CAMPOS AGUIRRE", multiline=False)
        self.cargo = TextInput(text="Especialista eléctrico", multiline=False)
        self.ot = TextInput(text="", multiline=False)

        self.hallazgos = TextInput(text="", hint_text="Ej: LOTO, Tableros, Orden y limpieza", multiline=False)
        self.observaciones = TextInput(text="", multiline=True, height=dp(120), size_hint_y=None)
        self.conclusion = TextInput(text="", multiline=True, height=dp(120), size_hint_y=None)

        self.form.add_widget(FieldRow("Título", self.titulo))
        self.form.add_widget(FieldRow("Fecha", self.fecha))
        self.form.add_widget(FieldRow("Disciplina", self.disciplina))
        self.form.add_widget(FieldRow("Riesgo", self.riesgo))
        self.form.add_widget(FieldRow("Equipo/Área", self.equipo))
        self.form.add_widget(FieldRow("Ubicación", self.ubicacion))
        self.form.add_widget(FieldRow("Inspector", self.inspector))
        self.form.add_widget(FieldRow("Cargo", self.cargo))
        self.form.add_widget(FieldRow("N° Registro/OT", self.ot))
        self.form.add_widget(FieldRow("Hallazgos (coma)", self.hallazgos))
        self.form.add_widget(FieldRow("Observaciones", self.observaciones))
        self.form.add_widget(FieldRow("Conclusión", self.conclusion))

        # Botonera
        bar = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None, height=dp(240))
        self.add_widget(bar)

        btn_fix = Button(text="🔧 Sugerir correcciones (Observaciones)", size_hint_y=None, height=dp(46))
        btn_fix.bind(on_release=lambda *_: self.do_fix_obs())
        bar.add_widget(btn_fix)

        btn_auto = Button(text="🔁 Auto-conclusión", size_hint_y=None, height=dp(46))
        btn_auto.bind(on_release=lambda *_: self.do_auto_conclusion())
        bar.add_widget(btn_auto)

        btn_photos = Button(text="🖼️ Cargar Fotos (máx 3)", size_hint_y=None, height=dp(46))
        btn_photos.bind(on_release=lambda *_: self.pick_photos())
        bar.add_widget(btn_photos)

        btn_sign = Button(text="✍️ Cargar Firma", size_hint_y=None, height=dp(46))
        btn_sign.bind(on_release=lambda *_: self.pick_signature())
        bar.add_widget(btn_sign)

        btn_pdf = Button(text="✅ Generar PDF (offline)", size_hint_y=None, height=dp(52))
        btn_pdf.bind(on_release=lambda *_: self.generate_pdf())
        bar.add_widget(btn_pdf)

        bottom = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(52))
        bar.add_widget(bottom)

        btn_share = Button(text="📤 Compartir PDF", disabled=True)
        btn_share.bind(on_release=lambda *_: self.share_pdf())
        self.btn_share = btn_share
        bottom.add_widget(btn_share)

        btn_copy = Button(text="📋 Copiar ruta PDF", disabled=True)
        btn_copy.bind(on_release=lambda *_: self.copy_pdf_path())
        self.btn_copy = btn_copy
        bottom.add_widget(btn_copy)

        self.status = Label(text="Listo.", size_hint_y=None, height=dp(28))
        bar.add_widget(self.status)

        # Storage helper
        self.shared_storage = SharedStorage()
        self.chooser = Chooser(self.shared_storage)


    def _set_status(self, text: str):
        self.status.text = text


    def _read_bytes(self, path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()


    def do_fix_obs(self):
        obs = self.observaciones.text or ""
        fixed, changes = core.technical_spanish_fixes(obs)
        self.observaciones.text = fixed
        if changes:
            self._set_status("Cambios: " + " | ".join(changes[:4]) + (" ..." if len(changes) > 4 else ""))
        else:
            self._set_status("Sin cambios detectados.")


    def do_auto_conclusion(self):
        hall = [h.strip() for h in (self.hallazgos.text or "").split(",") if h.strip()]
        conc = core.generate_conclusion_short(self.disciplina.text, self.riesgo.text, hall, self.observaciones.text)
        self.conclusion.text = conc
        self._set_status("Auto-conclusión generada.")


    def pick_photos(self):
        self._set_status("Selecciona hasta 3 fotos...")
        filechooser.open_file(on_selection=self._on_photos_selected, multiple=True)


    @mainthread
    def _on_photos_selected(self, selection):
        if not selection:
            self._set_status("Sin selección.")
            return

        picks = selection[:3]
        fotos = []
        for p in picks:
            try:
                fotos.append((os.path.basename(p), self._read_bytes(p)))
            except Exception:
                continue

        self.fotos = fotos
        self._set_status(f"Fotos cargadas: {len(self.fotos)} / 3")


    def pick_signature(self):
        self._set_status("Selecciona la firma...")
        filechooser.open_file(on_selection=self._on_signature_selected, multiple=False)


    @mainthread
    def _on_signature_selected(self, selection):
        if not selection:
            self._set_status("Sin selección.")
            return

        p = selection[0]
        try:
            self.firma = (os.path.basename(p), self._read_bytes(p))
            self._set_status("Firma cargada.")
        except Exception:
            self.firma = None
            self._set_status("No se pudo leer la firma.")


    def generate_pdf(self):
        try:
            hall = [h.strip() for h in (self.hallazgos.text or "").split(",") if h.strip()]

            data = core.ReportData(
                titulo=_safe_text(self.titulo.text),
                fecha=_safe_text(self.fecha.text),
                disciplina=_safe_text(self.disciplina.text),
                equipo=_safe_text(self.equipo.text),
                ubicacion=_safe_text(self.ubicacion.text),
                inspector=_safe_text(self.inspector.text),
                cargo=_safe_text(self.cargo.text),
                registro_ot=_safe_text(self.ot.text),
                nivel_riesgo=_safe_text(self.riesgo.text),
                hallazgos=hall,
                observaciones=_safe_text(self.observaciones.text),
                conclusion=_safe_text(self.conclusion.text),
            )

            pdf_bytes = core.build_pdf(data, self.fotos, self.firma)

            fname = f"informe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            # Guarda en carpeta de documentos compartidos (user-friendly)
            out_path = self.shared_storage.get_document_path(fname)

            with open(out_path, "wb") as f:
                f.write(pdf_bytes)

            self.last_pdf_path = out_path
            self.btn_share.disabled = False
            self.btn_copy.disabled = False
            self._set_status(f"PDF OK: {fname}")

        except Exception as e:
            self._set_status(f"Error PDF: {e}")


    def share_pdf(self):
        if not self.last_pdf_path or not os.path.exists(self.last_pdf_path):
            self._set_status("No hay PDF para compartir.")
            return
        try:
            share.share(filepath=self.last_pdf_path, mime_type="application/pdf")
            self._set_status("Compartir abierto.")
        except Exception as e:
            self._set_status(f"No se pudo compartir: {e}")


    def copy_pdf_path(self):
        if not self.last_pdf_path:
            self._set_status("No hay ruta.")
            return
        Clipboard.copy(self.last_pdf_path)
        self._set_status("Ruta copiada al portapapeles.")


class InspectorApp(App):
    def build(self):
        self.title = "jcamp029.pro"
        return InspectorRoot()


if __name__ == "__main__":
    InspectorApp().run()

import io
import re
import unicodedata
from collections import Counter
from datetime import datetime
from typing import List, Tuple, Optional

import streamlit as st
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage

from PIL import Image, ImageOps
from xml.sax.saxutils import escape


# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="jcamp029.pro", page_icon="🧾", layout="centered")
APP_TITLE = "jcamp029.pro"
APP_SUBTITLE = "Generador profesional de informes de inspección técnica (PDF)."
TZ_CL = ZoneInfo("America/Santiago")

UP_NONCE = "__uploader_nonce__"

# ✅ Reglas Multimedia
# - Bloque total de imágenes (1,2,3) NO supera 15x6 cm
TOTAL_IMG_W_MM = 150
TOTAL_IMG_H_MM = 60

# - Firma fija 3x3 cm
SIGN_W_MM = 30
SIGN_H_MM = 30


# -----------------------------
# Keys + Defaults
# -----------------------------
FIELD_KEYS = {
    "theme": "theme",
    "theme_initialized": "theme_initialized",  # fuerza claro SOLO 1 vez por sesión

    "include_signature": "include_signature",
    "include_photos": "include_photos",
    "show_correccion": "show_correccion",
    "auto_conclusion": "auto_conclusion",

    "fecha": "fecha",
    "titulo": "titulo",
    "disciplina": "disciplina",
    "equipo": "equipo",
    "ubicacion": "ubicacion",
    "inspector": "inspector",
    "cargo": "cargo",
    "registro_ot": "registro_ot",
    "nivel_riesgo": "nivel_riesgo",
    "hallazgos": "hallazgos",
    "observaciones_raw": "observaciones_raw",
    "obs_fixed_preview": "obs_fixed_preview",
    "conclusion": "conclusion",

    "conclusion_locked": "conclusion_locked",
    "last_auto_hash": "last_auto_hash",
}


def get_defaults() -> dict:
    return {
        FIELD_KEYS["theme"]: "Claro",
        FIELD_KEYS["theme_initialized"]: False,

        FIELD_KEYS["include_signature"]: True,
        FIELD_KEYS["include_photos"]: True,
        FIELD_KEYS["show_correccion"]: True,
        FIELD_KEYS["auto_conclusion"]: True,

        FIELD_KEYS["fecha"]: datetime.now(TZ_CL).strftime("%d-%m-%Y"),
        FIELD_KEYS["titulo"]: "Informe Técnico de Inspección",
        FIELD_KEYS["disciplina"]: "Eléctrica",
        FIELD_KEYS["equipo"]: "",
        FIELD_KEYS["ubicacion"]: "",
        FIELD_KEYS["inspector"]: "JORGE CAMPOS AGUIRRE",
        FIELD_KEYS["cargo"]: "Especialista eléctrico",
        FIELD_KEYS["registro_ot"]: "",
        FIELD_KEYS["nivel_riesgo"]: "Medio",
        FIELD_KEYS["hallazgos"]: [],
        FIELD_KEYS["observaciones_raw"]: "",
        FIELD_KEYS["obs_fixed_preview"]: "",
        FIELD_KEYS["conclusion"]: "",

        FIELD_KEYS["conclusion_locked"]: False,
        FIELD_KEYS["last_auto_hash"]: "",
    }


def init_state():
    if UP_NONCE not in st.session_state:
        st.session_state[UP_NONCE] = 0

    defaults = get_defaults()

    # ✅ abrir siempre en CLARO al inicio de la sesión,
    # pero permitir cambiar a Oscuro después (no se pisa en reruns).
    if not st.session_state.get(FIELD_KEYS["theme_initialized"], False):
        st.session_state[FIELD_KEYS["theme"]] = "Claro"
        st.session_state[FIELD_KEYS["theme_initialized"]] = True

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def hard_reset_now():
    """
    Reset definitivo del formulario preservando el tema actual.
    """
    current_theme = st.session_state.get(FIELD_KEYS["theme"], "Claro")

    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.session_state[UP_NONCE] = 1

    defaults = get_defaults()
    for k, v in defaults.items():
        st.session_state[k] = v

    st.session_state[FIELD_KEYS["theme"]] = current_theme
    st.session_state[FIELD_KEYS["theme_initialized"]] = True  # no volver a forzar
    st.rerun()


init_state()


# -----------------------------
# CSS Dinámico
# -----------------------------
def apply_theme_css(theme: str) -> None:
    if theme == "Oscuro":
        bg = "#070B14"
        fg = "#FFFFFF"
        muted = "#D6DEEA"
        card = "#0B1220"
        border = "#2A3A58"
        input_bg = "#0A1020"
        placeholder = "#9FB0C8"
        focus = "#5AA9FF"

        btn_bg = "#0B1220"
        btn_border = "#2A3A58"
        btn_text = "#FFFFFF"
        btn_hover = "#101A2E"
    else:
        bg = "#FFFFFF"
        fg = "#0F172A"
        muted = "#334155"
        card = "#F8FAFC"
        border = "#E2E8F0"
        input_bg = "#FFFFFF"
        placeholder = "#64748B"
        focus = "#2563EB"

        btn_bg = "#FFFFFF"
        btn_border = "#CBD5E1"
        btn_text = "#0F172A"
        btn_hover = "#F1F5F9"

    st.markdown(
        f"""
        <style>
        .stApp {{ background: {bg}; color: {fg}; }}
        div[data-testid="stMarkdownContainer"] * {{ color: {fg} !important; }}
        div[data-testid="stWidgetLabel"] > label {{ color: {fg} !important; font-weight: 800 !important; }}
        .muted {{ color: {muted} !important; }}

        .app-card {{
            border: 1px solid {border};
            background: {card};
            border-radius: 14px;
            padding: 16px;
            margin-bottom: 16px;
        }}
        .app-card:empty {{
            display: none !important;
            padding: 0 !important;
            margin: 0 !important;
            border: 0 !important;
        }}

        input, textarea {{
            background: {input_bg} !important;
            color: {fg} !important;
            border: 1px solid {border} !important;
        }}
        input::placeholder, textarea::placeholder {{
            color: {placeholder} !important;
            opacity: 1 !important;
        }}
        input:focus, textarea:focus {{
            border-color: {focus} !important;
            outline: none !important;
            box-shadow: 0 0 0 2px rgba(90,169,255,0.18) !important;
        }}

        div[data-baseweb="select"] > div {{
            background: {input_bg} !important;
            color: {fg} !important;
            border: 1px solid {border} !important;
        }}
        div[data-baseweb="select"] * {{ color: {fg} !important; }}

        div[data-baseweb="tag"] {{
            background: rgba(90,169,255,0.18) !important;
            border: 1px solid {border} !important;
        }}
        div[data-baseweb="tag"] * {{ color: {fg} !important; }}

        /* Botones */
        div[data-testid="stButton"] button,
        div[data-testid="stDownloadButton"] button,
        div[data-testid="stFormSubmitButton"] button {{
            background: {btn_bg} !important;
            border: 1px solid {btn_border} !important;
            color: {btn_text} !important;
            border-radius: 12px !important;
            font-weight: 800 !important;
        }}
        div[data-testid="stButton"] button:hover,
        div[data-testid="stDownloadButton"] button:hover,
        div[data-testid="stFormSubmitButton"] button:hover {{
            background: {btn_hover} !important;
            color: {btn_text} !important;
            border-color: {btn_border} !important;
        }}
        div[data-testid="stButton"] button *,
        div[data-testid="stDownloadButton"] button *,
        div[data-testid="stFormSubmitButton"] button * {{
            color: {btn_text} !important;
        }}

        /* File Uploader (Browse files visible en claro) */
        div[data-testid="stFileUploader"] {{ color: {fg} !important; }}
        div[data-testid="stFileUploader"] * {{ color: {fg} !important; }}
        div[data-testid="stFileUploader"] section {{
            background: {card} !important;
            border: 1px solid {border} !important;
            border-radius: 14px !important;
        }}
        div[data-testid="stFileUploader"] button {{
            background: {btn_bg} !important;
            border: 1px solid {btn_border} !important;
            color: {btn_text} !important;
            font-weight: 800 !important;
            border-radius: 12px !important;
        }}
        div[data-testid="stFileUploader"] button * {{ color: {btn_text} !important; }}

        div[role="radiogroup"] * {{ color: {fg} !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------
# Corrección técnica (A)
# -----------------------------
def normalize_spaces(text: str) -> str:
    text = text or ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_accents(s: str) -> str:
    # Quita diacríticos sin cambiar letras (á -> a, ü -> u, ñ se mantiene como ñ en NFD?).
    # Nota: ñ al descomponer queda n + ~, por lo que aquí queda "n".
    # Para corrección técnica es aceptable porque comparamos “sin acentos”.
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


def match_case(original: str, replacement: str) -> str:
    # Respeta el estilo del token original
    if original.isupper():
        return replacement.upper()
    if len(original) > 1 and original[0].isupper() and original[1:].islower():
        # Title case simple
        return replacement[:1].upper() + replacement[1:].lower()
    return replacement


# Diccionario técnico controlado (dominio inspección)
TECH_WORDS = {
    # núcleo
    "aseo": "aseo",
    "area": "área",
    "tecnico": "técnico",
    "tecnica": "técnica",
    "inspeccion": "inspección",
    "ubicacion": "ubicación",
    "conclusion": "conclusión",
    "observacion": "observación",
    "iluminacion": "iluminación",
    "condicion": "condición",
    "revision": "revisión",
    "operacion": "operación",
    "senalizacion": "señalización",
    "proteccion": "protección",
    "mantenimiento": "mantenimiento",

    # disciplina
    "electrico": "eléctrico",
    "electrica": "eléctrica",
    "mecanico": "mecánico",
    "mecanica": "mecánica",
    "instrumentacion": "instrumentación",

    # siglas comunes
    "epp": "EPP",
}

# Pre-cálculo: key sin acentos -> palabra correcta
TECH_MAP = {strip_accents(k).lower(): v for k, v in TECH_WORDS.items()}


def technical_spanish_fixes(text: str):
    """
    Corrector técnico:
    - Normaliza espacios
    - Corrige SOLO un set controlado de palabras (con y sin tildes mal puestas)
    - Respeta estilo (mayúsculas / título / minúsculas)
    - Entrega logs con conteo
    """
    t = normalize_spaces(text or "")
    changes_counter = Counter()

    # Tokenizador: solo palabras (no números), incluyendo letras con tildes
    word_re = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")

    def repl(m: re.Match) -> str:
        w = m.group(0)

        # Protecciones: si contiene dígitos, no tocar (aunque no debería entrar)
        if any(ch.isdigit() for ch in w):
            return w

        key = strip_accents(w).lower()

        if key in TECH_MAP:
            new_word = match_case(w, TECH_MAP[key])
            if new_word != w:
                changes_counter[f"{w} → {new_word}"] += 1
            return new_word

        return w

    t2 = word_re.sub(repl, t)

    # Capitalización inicial (sin tocar el resto)
    logs = []
    if t2 and t2[0].islower():
        t2 = t2[0].upper() + t2[1:]
        changes_counter["Capitalización inicial"] += 1

    for k, n in changes_counter.most_common():
        logs.append(f"{k} ({n})")

    return t2, logs


def apply_obs_fix():
    st.session_state[FIELD_KEYS["observaciones_raw"]] = st.session_state.get(FIELD_KEYS["obs_fixed_preview"], "")
    st.rerun()


# -----------------------------
# Auto-conclusión (corta)
# -----------------------------
def generate_conclusion_short(disciplina: str, nivel_riesgo: str, hallazgos: List[str]) -> str:
    riesgo = f"Riesgo {nivel_riesgo.lower()}"
    prioridad = "inmediata" if nivel_riesgo == "Alto" else "programada" if nivel_riesgo == "Medio" else "rutinaria"
    hall = ", ".join(hallazgos) if hallazgos else "General"
    return f"{disciplina}: {riesgo}. Prioridad {prioridad}. Hallazgos: {hall}. Acción: corregir según prioridad."


def compute_auto_hash() -> str:
    d = st.session_state.get(FIELD_KEYS["disciplina"], "")
    r = st.session_state.get(FIELD_KEYS["nivel_riesgo"], "")
    h = ",".join(st.session_state.get(FIELD_KEYS["hallazgos"], []) or [])
    return f"{d}|{r}|{h}"


def sync_auto_conclusion_if_needed():
    if not st.session_state.get(FIELD_KEYS["auto_conclusion"], True):
        return
    if st.session_state.get(FIELD_KEYS["conclusion_locked"], False):
        return

    current_hash = compute_auto_hash()
    last_hash = st.session_state.get(FIELD_KEYS["last_auto_hash"], "")

    if current_hash != last_hash or not (st.session_state.get(FIELD_KEYS["conclusion"], "").strip()):
        st.session_state[FIELD_KEYS["conclusion"]] = generate_conclusion_short(
            st.session_state.get(FIELD_KEYS["disciplina"], "Otra"),
            st.session_state.get(FIELD_KEYS["nivel_riesgo"], "Medio"),
            st.session_state.get(FIELD_KEYS["hallazgos"], []),
        )
        st.session_state[FIELD_KEYS["last_auto_hash"]] = current_hash


# -----------------------------
# Imágenes (COVER)
# -----------------------------
def _img_cover(file_bytes: bytes, w_mm: float, h_mm: float) -> io.BytesIO:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(file_bytes)).convert("RGB"))
    box_px_w = 1500
    box_px_h = max(1, int(box_px_w * (h_mm / w_mm)))

    scale = max(box_px_w / img.width, box_px_h / img.height)
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)

    left = (img.width - box_px_w) // 2
    top = (img.height - box_px_h) // 2
    img = img.crop((left, top, left + box_px_w, top + box_px_h))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return buf


# -----------------------------
# PDF
# -----------------------------
def build_pdf(
    data_dict: dict,
    fotos: List[Tuple[str, bytes]],
    firma_img: Optional[Tuple[str, bytes]],
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, margin=15 * mm)
    styles = getSampleStyleSheet()

    story = [
        Paragraph("INFORME TÉCNICO DE INSPECCIÓN", styles["Heading1"]),
        Spacer(1, 8),
    ]

    table_data = [
        ["Fecha", data_dict["fecha"]],
        ["Título", data_dict["titulo"]],
        ["Disciplina", data_dict["disciplina"]],
        ["Riesgo", data_dict["nivel_riesgo"]],
        ["Equipo/Área", data_dict["equipo"] or "—"],
        ["Ubicación", data_dict["ubicacion"] or "—"],
        ["Inspector", data_dict["inspector"]],
        ["Cargo", data_dict["cargo"]],
        ["OT/Registro", data_dict["registro_ot"] or "—"],
    ]

    t = Table(table_data, colWidths=[42 * mm, 138 * mm])
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.extend([t, Spacer(1, 10)])

    story.append(Paragraph("Observaciones", styles["Heading2"]))
    story.append(Paragraph(escape(data_dict["observaciones"]).replace("\n", "<br/>"), styles["BodyText"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Conclusión", styles["Heading2"]))
    story.append(Paragraph(escape(data_dict["conclusion"]).replace("\n", "<br/>"), styles["BodyText"]))
    story.append(Spacer(1, 8))

    # Imágenes: 1 fila horizontal (máx 15x6 cm)
    if fotos:
        story.append(Paragraph("Imágenes", styles["Heading2"]))
        use = fotos[:3]
        n = len(use)

        img_w_mm = TOTAL_IMG_W_MM / n
        img_h_mm = TOTAL_IMG_H_MM

        imgs = [
            RLImage(_img_cover(b, img_w_mm, img_h_mm), width=img_w_mm * mm, height=img_h_mm * mm)
            for _, b in use
        ]

        img_table = Table([imgs], colWidths=[img_w_mm * mm] * n)
        img_table.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(img_table)

    # Firma: 3x3 cm (al final)
    if firma_img:
        story.append(Spacer(1, 8))
        sig = RLImage(_img_cover(firma_img[1], SIGN_W_MM, SIGN_H_MM), width=SIGN_W_MM * mm, height=SIGN_H_MM * mm)
        story.append(sig)

    doc.build(story)
    return buffer.getvalue()


# -----------------------------
# UI
# -----------------------------
apply_theme_css(st.session_state[FIELD_KEYS["theme"]])

st.markdown(f"<h1><i>{APP_TITLE}</i></h1><p class='muted'>{APP_SUBTITLE}</p>", unsafe_allow_html=True)

st.radio("Tema", ["Claro", "Oscuro"], horizontal=True, key=FIELD_KEYS["theme"])
apply_theme_css(st.session_state[FIELD_KEYS["theme"]])

# Configuración + Limpieza
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
with c1:
    st.checkbox("Firma", key=FIELD_KEYS["include_signature"])
with c2:
    st.checkbox("Fotos", key=FIELD_KEYS["include_photos"])
with c3:
    st.checkbox("Corrección", key=FIELD_KEYS["show_correccion"])
with c4:
    if st.button("Limpiar formulario", use_container_width=True):
        hard_reset_now()
st.markdown("</div>", unsafe_allow_html=True)

# Formulario
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
cL, cR = st.columns(2)
with cL:
    st.text_input("Fecha", key=FIELD_KEYS["fecha"])
with cR:
    st.text_input("Título", key=FIELD_KEYS["titulo"])

cA, cB = st.columns(2)
with cA:
    st.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Instrumental", "Civil", "Otra"], key=FIELD_KEYS["disciplina"])
    st.text_input("Equipo/Área", key=FIELD_KEYS["equipo"])
    st.text_input("Inspector", key=FIELD_KEYS["inspector"])
with cB:
    st.selectbox("Riesgo", ["Bajo", "Medio", "Alto"], key=FIELD_KEYS["nivel_riesgo"])
    st.text_input("Ubicación", key=FIELD_KEYS["ubicacion"])
    st.text_input("Cargo", key=FIELD_KEYS["cargo"])

st.text_input("N° Registro/OT", key=FIELD_KEYS["registro_ot"])
st.multiselect(
    "Hallazgos",
    ["Condición insegura", "Orden y limpieza", "LOTO", "Tableros", "Otros"],
    key=FIELD_KEYS["hallazgos"],
)

st.text_area("Observaciones", height=120, key=FIELD_KEYS["observaciones_raw"])

# Corrección (técnica A)
if st.session_state[FIELD_KEYS["show_correccion"]]:
    if st.button("Sugerir correcciones"):
        fixed, changes = technical_spanish_fixes(st.session_state[FIELD_KEYS["observaciones_raw"]])
        st.session_state[FIELD_KEYS["obs_fixed_preview"]] = fixed
        if changes:
            st.info("Cambios: " + " | ".join(changes))
        else:
            st.info("Sin cambios detectados.")
    if st.session_state.get(FIELD_KEYS["obs_fixed_preview"], "").strip():
        st.text_area("Sugerencia", key=FIELD_KEYS["obs_fixed_preview"], height=90)
        st.button("Aplicar sugerencias", on_click=apply_obs_fix)

# Auto / Manual
st.checkbox("Auto", key=FIELD_KEYS["auto_conclusion"])
sync_auto_conclusion_if_needed()

cX, cY = st.columns(2)
with cX:
    if st.button("🔁 Auto", use_container_width=True):
        st.session_state[FIELD_KEYS["conclusion_locked"]] = False
        st.session_state[FIELD_KEYS["last_auto_hash"]] = ""
        sync_auto_conclusion_if_needed()
        st.rerun()
with cY:
    if st.button("✍️ Manual", use_container_width=True):
        st.session_state[FIELD_KEYS["conclusion_locked"]] = True
        st.rerun()

st.text_area("Conclusión", height=120, key=FIELD_KEYS["conclusion"])
st.markdown("</div>", unsafe_allow_html=True)

# Multimedia
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
st.subheader("Multimedia")
nonce = st.session_state[UP_NONCE]

fotos_files = (
    st.file_uploader("Fotos (Máx 3)", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key=f"f_{nonce}")
    if st.session_state[FIELD_KEYS["include_photos"]]
    else None
)
firma_file = (
    st.file_uploader("Firma", type=["jpg", "png", "jpeg"], key=f"s_{nonce}")
    if st.session_state[FIELD_KEYS["include_signature"]]
    else None
)
st.markdown("</div>", unsafe_allow_html=True)

# Generación
if st.button("Generar PDF Profesional ✅", use_container_width=True):
    fotos = [(f.name, f.read()) for f in (fotos_files or [])[:3]]
    firma = (firma_file.name, firma_file.read()) if firma_file else None

    datos = {
        "titulo": st.session_state[FIELD_KEYS["titulo"]],
        "fecha": st.session_state[FIELD_KEYS["fecha"]],
        "disciplina": st.session_state[FIELD_KEYS["disciplina"]],
        "equipo": st.session_state[FIELD_KEYS["equipo"]],
        "ubicacion": st.session_state[FIELD_KEYS["ubicacion"]],
        "inspector": st.session_state[FIELD_KEYS["inspector"]],
        "cargo": st.session_state[FIELD_KEYS["cargo"]],
        "registro_ot": st.session_state[FIELD_KEYS["registro_ot"]],
        "nivel_riesgo": st.session_state[FIELD_KEYS["nivel_riesgo"]],
        "observaciones": st.session_state[FIELD_KEYS["observaciones_raw"]],
        "conclusion": st.session_state[FIELD_KEYS["conclusion"]],
    }

    pdf_output = build_pdf(datos, fotos, firma)

    st.download_button(
        "Descargar Informe",
        data=pdf_output,
        file_name=f"informe_{datetime.now(TZ_CL).strftime('%H%M%S')}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

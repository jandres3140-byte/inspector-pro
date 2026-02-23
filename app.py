import io
import re
import unicodedata
import base64
from collections import Counter
from datetime import datetime
from typing import List, Tuple, Optional

import streamlit as st
import streamlit.components.v1 as components
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

    # PDF generado (para descargar/compartir sin perderlo en reruns)
    "last_pdf_bytes": "last_pdf_bytes",
    "last_pdf_name": "last_pdf_name",
    "last_pdf_token": "last_pdf_token",
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

        FIELD_KEYS["last_pdf_bytes"]: None,
        FIELD_KEYS["last_pdf_name"]: "",
        FIELD_KEYS["last_pdf_token"]: "",
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

        /* File Uploader */
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
# Recomendación NO bloqueante para Nombres (Inspector)
# -----------------------------
def _recommended_title_name(name: str) -> str:
    s = (name or "").strip()
    s = re.sub(r"\s+", " ", s)
    parts = re.split(r"([ \-’'`])", s)
    out = []
    for p in parts:
        if p in {" ", "-", "’", "'", "`"} or p == "":
            out.append(p)
            continue
        out.append(p[:1].upper() + p[1:].lower() if p.isalpha() else p)
    return "".join(out).strip()


def _has_obvious_caps_issue(name: str) -> bool:
    s = (name or "").strip()
    if not s:
        return False

    letters = [ch for ch in s if ch.isalpha()]
    if not letters:
        return False

    if all(ch.islower() for ch in letters):
        return True
    if all(ch.isupper() for ch in letters):
        return True

    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", s)
    for w in words:
        if len(w) >= 2 and w[0].isupper():
            if any(ch.isupper() for ch in w[1:]) and not w.isupper():
                return True
    return False


# -----------------------------
# Corrección técnica (A) - solo Observaciones
# -----------------------------
def normalize_spaces(text: str) -> str:
    text = text or ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


def match_case(original: str, replacement: str) -> str:
    if original.isupper():
        return replacement.upper()
    if len(original) > 1 and original[0].isupper() and original[1:].islower():
        return replacement[:1].upper() + replacement[1:].lower()
    return replacement


TECH_WORDS = {
    "aseo": "aseo",
    "area": "área",
    "medicion": "medición",
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
    "electrico": "eléctrico",
    "electrica": "eléctrica",
    "electricos": "eléctricos",
    "electricas": "eléctricas",
    "mecanico": "mecánico",
    "mecanica": "mecánica",
    "instrumentacion": "instrumentación",
    "epp": "EPP",
}

TECH_MAP = {strip_accents(k).lower(): v for k, v in TECH_WORDS.items()}


def technical_spanish_fixes(text: str):
    t = normalize_spaces(text or "")
    changes_counter = Counter()
    word_re = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")

    def repl(m: re.Match) -> str:
        w = m.group(0)
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
# Auto-conclusión (compacta, sin repetir riesgo)
# -----------------------------
def generate_conclusion_compact(disciplina: str, nivel_riesgo: str, hallazgos: List[str]) -> str:
    prioridad = "inmediata" if nivel_riesgo == "Alto" else "programada" if nivel_riesgo == "Medio" else "rutinaria"
    hall = ", ".join(hallazgos) if hallazgos else "General"
    # ✅ sin "Acción:" para que no quede colgando
    return f"{disciplina}. Prioridad {prioridad}. Hallazgos: {hall}. Corregir según prioridad."


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
        st.session_state[FIELD_KEYS["conclusion"]] = generate_conclusion_compact(
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

    if fotos:
        story.append(Paragraph("Imágenes", styles["Heading2"]))
        use = fotos[:3]
        n = len(use)

        img_w_mm = TOTAL_IMG_W_MM / n
        img_h_mm = TOTAL_IMG_H_MM

        imgs = [
            # RLImage(_img_cover(b, img_w_mm, img_h_mm), width=img_w_mm * mm, height=img_h_mm * mm]

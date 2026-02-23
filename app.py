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
    "theme_initialized": "theme_initialized",

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

    # abrir siempre en CLARO al inicio de la sesión, permitir cambiar luego
    if not st.session_state.get(FIELD_KEYS["theme_initialized"], False):
        st.session_state[FIELD_KEYS["theme"]] = "Claro"
        st.session_state[FIELD_KEYS["theme_initialized"]] = True

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def hard_reset_now():
    """Reset definitivo del formulario preservando el tema actual."""
    current_theme = st.session_state.get(FIELD_KEYS["theme"], "Claro")

    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.session_state[UP_NONCE] = 1

    defaults = get_defaults()
    for k, v in defaults.items():
        st.session_state[k] = v

    st.session_state[FIELD_KEYS["theme"]] = current_theme
    st.session_state[FIELD_KEYS["theme_initialized"]] = True
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
    "medicion": "medición",   # ✅ tu caso
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
# Auto-conclusión (compacta)
# -----------------------------
def compute_auto_hash() -> str:
    d = st.session_state.get(FIELD_KEYS["disciplina"], "")
    r = st.session_state.get(FIELD_KEYS["nivel_riesgo"], "")
    h = ",".join(st.session_state.get(FIELD_KEYS["hallazgos"], []) or [])
    o = st.session_state.get(FIELD_KEYS["observaciones_raw"], "")
    return f"{d}|{r}|{h}|{o}"


def _contains_any(text: str, words: List[str]) -> bool:
    t = strip_accents((text or "").lower())
    return any(strip_accents(w.lower()) in t for w in words)


def generate_conclusion_compact(disciplina: str, nivel_riesgo: str, hallazgos: List[str], observaciones: str) -> str:
    # NOTA: por decisión tuya, NO repetimos el nivel de riesgo aquí (ya está en tabla).
    disc = (disciplina or "Otra").strip()
    obs = observaciones or ""
    hall = hallazgos or []

    # Causa (1 frase)
    causas = []

    # Electricidad
    if disc.lower().startswith("eléctr"):
        if _contains_any(obs, ["tablero", "tableros", "gabinete", "panel"]):
            causas.append("condición deficiente en tableros/gabinetes")
        if _contains_any(obs, ["loto", "bloqueo", "etiquetado"]):
            causas.append("ausencia o debilidad de control LOTO")
        if _contains_any(obs, ["polvo conductor", "polvo", "suciedad"]):
            causas.append("acumulación de polvo")
        if not causas and hall:
            causas.append("condiciones observadas en terreno")

        accion = "Corregir según prioridad"
        if _contains_any(obs, ["polvo conductor", "polvo", "suciedad", "aseo", "limpieza"]) or ("Orden y limpieza" in hall):
            accion = "Realizar limpieza y control de polvo conductor"
        if _contains_any(obs, ["loto", "bloqueo", "etiquetado"]) or ("LOTO" in hall):
            accion = accion + " y asegurar aplicación LOTO"
        if _contains_any(obs, ["tablero", "tableros", "gabinete", "panel"]) or ("Tableros" in hall):
            accion = accion + " en tableros/gabinetes"

    # Mecánica
    elif disc.lower().startswith("mec"):
        if _contains_any(obs, ["guardas", "proteccion", "protección"]):
            causas.append("protecciones/guardas deficientes")
        if _contains_any(obs, ["fuga", "aceite", "lubric"]):
            causas.append("fugas o lubricación deficiente")
        if not causas and hall:
            causas.append("condiciones mecánicas observadas")
        accion = "Corregir según prioridad"

    # Instrumental / Instrumentación
    elif disc.lower().startswith("instr"):
        if _contains_any(obs, ["medicion", "medición", "calibr", "señal", "sensor"]):
            causas.append("condición de medición/control a verificar")
        if not causas and hall:
            causas.append("condiciones de instrumentación observadas")
        accion = "Verificar y corregir según prioridad"

    # Civil / Otra
    else:
        if not causas and hall:
            causas.append("condiciones observadas")
        accion = "Corregir según prioridad"

    causa_txt = " y ".join(causas) if causas else "condiciones observadas"
    frase1 = f"Se identifican {causa_txt}."
    frase2 = f"{accion}."

    # Compactar por si se va largo (para evitar segunda hoja)
    out = f"{frase1} {frase2}"
    out = re.sub(r"\s+", " ", out).strip()
    if len(out) > 260:
        out = out[:257].rstrip() + "..."
    return out


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
            st.session_state.get(FIELD_KEYS["observaciones_raw"], ""),
        )
        st.session_state[FIELD_KEYS["last_auto_hash"]] = current_hash


# -----------------------------
# Imágenes (COVER)
# -----------------------------
def _img_cover(file_bytes: bytes, w_mm: float, h_mm: float

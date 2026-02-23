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

        /* File Uploader (Browse files visible) */
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
    "medicion": "medición",  # ✅ caso real tuyo
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
# Auto-conclusión 2.0 (compacta, contextual, 2 frases)
# - NO repite nivel de riesgo (ya va en tabla)
# - Usa Disciplina + Hallazgos + palabras clave en Observaciones
# -----------------------------
def _tokenize(text: str) -> set:
    s = strip_accents((text or "").lower())
    s = re.sub(r"[^a-z0-9áéíóúüñ\s\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return set()
    return set(s.split(" "))


def _compact_join(items: List[str], max_items: int = 2) -> str:
    items = [x for x in items if x]
    if not items:
        return ""
    items = items[:max_items]
    return " y ".join(items) if len(items) == 2 else items[0]


def _limit_len(text: str, max_len: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    t = t[: max_len - 1].rstrip()
    return t + "…"


def generate_conclusion_auto_v2(disciplina: str, hallazgos: List[str], observaciones: str) -> str:
    disc = (disciplina or "Otra").strip()
    hall = hallazgos or []
    obs = observaciones or ""
    tokens = _tokenize(obs)

    # Señales comunes
    has_loto = "loto" in tokens
    has_tablero = any(t in tokens for t in ["tablero", "tableros", "gabinete", "gabinetes"])
    has_polvo = any(t in tokens for t in ["polvo", "conductor", "conductivo", "conductora", "conductores"])
    has_abierto = any(t in tokens for t in ["abierto", "abiertos", "abierta", "abiertas"])
    has_aseo = any(t in tokens for t in ["aseo", "limpieza", "sucio", "sucia", "orden"])
    has_senal = any(t in tokens for t in ["senalizacion", "señalizacion", "senal", "señal"])
    has_epp = "epp" in tokens

    # Causas / acciones por disciplina
    causa = ""
    accion = ""
    prevencion = ""

    if disc == "Eléctrica":
        causas = []
        acciones = []

        if has_tablero:
            causas.append("condiciones deficientes en tableros/gabinetes")
        if has_abierto and has_tablero:
            causas.append("tableros abiertos")
        if has_loto or ("LOTO" in hall) or ("Loto" in hall):
            causas.append("ausencia de control LOTO")
        if has_polvo:
            causas.append("presencia de polvo conductor")
        if ("Orden y limpieza" in hall) or has_aseo:
            causas.append("orden y limpieza deficientes")
        if not causas and hall:
            causas.append("condiciones observadas en la inspección")

        # Acciones recomendadas (compactas)
        if has_loto or ("LOTO" in hall) or ("Loto" in hall):
            acciones.append("implementar y verificar LOTO")
        if has_tablero:

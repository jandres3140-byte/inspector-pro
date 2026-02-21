import io
import re
import uuid
from datetime import datetime
from typing import List, Tuple, Optional

import streamlit as st

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
)
from reportlab.pdfgen import canvas

from PIL import Image, ImageOps
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="jcamp029.pro", page_icon="🧾", layout="centered")
APP_TITLE = "jcamp029.pro"
APP_SUBTITLE = "Generador profesional de informes de inspección técnica (PDF)."
TZ_CL = ZoneInfo("America/Santiago")

UP_NONCE = "__uploader_nonce__"

# -----------------------------
# Keys + Defaults
# -----------------------------
FIELD_KEYS = {
    "theme": "theme",
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
}

def get_defaults() -> dict:
    return {
        FIELD_KEYS["theme"]: "Claro",  # ✅ Corregido: Ahora inicia en Claro por defecto
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
        FIELD_KEYS["conclusion"]: "",
    }

def hard_reset_now():
    current_theme = st.session_state.get(FIELD_KEYS["theme"], "Claro")
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state[UP_NONCE] = st.session_state.get(UP_NONCE, 0) + 1
    defaults = get_defaults()
    for k, v in defaults.items():
        st.session_state[k] = v
    st.session_state[FIELD_KEYS["theme"]] = current_theme
    st.rerun()

def init_state():
    if UP_NONCE not in st.session_state:
        st.session_state[UP_NONCE] = 0
    defaults = get_defaults()
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# -----------------------------
# Helpers UI / CSS (Mejorado para Modo Oscuro)
# -----------------------------
def apply_theme_css(theme: str) -> None:
    if theme == "Oscuro":
        # Colores optimizados para legibilidad en negro
        bg, fg, muted, card, border, input_bg = "#070B14", "#E0E6ED", "#A0AEC0", "#0B1220", "#2D3748", "#1A202C"
        sel_txt = "#FFFFFF"
    else:
        bg, fg, muted, card, border, input_bg = "#FFFFFF", "#1A202C", "#4A5568", "#F7FAFC", "#E2E8F0", "#FFFFFF"
        sel_txt = "#1A202C"

    st.markdown(f"""
        <style>
        .stApp {{ background: {bg}; color: {fg}; }}
        /* Forzar color de texto en todos los contenedores de markdown y labels */
        div[data-testid="stMarkdownContainer"] p {{ color: {fg} !important; }}
        div[data-testid="stWidgetLabel"] > label {{ color: {fg} !important; font-weight: 700 !important; }}
        
        /* Inputs, Textareas y Selects corregidos para modo oscuro */
        input, textarea, div[data-baseweb="select"] > div {{ 
            background-color: {input_bg} !important; 
            color: {sel_txt} !important; 
            border: 1px solid {border} !important; 
        }}
        
        /* Corregir visibilidad de texto dentro de los selectores (dropdowns) */
        div[data-baseweb="select"] * {{ color: {sel_txt} !important; }}
        
        .app-card {{ border: 1px solid {border}; background: {card}; border-radius: 14px; padding: 16px; margin-bottom: 16px; }}
        .muted {{ color: {muted} !important; }}
        </style>
        """, unsafe_allow_html=True)

# -----------------------------
# Lógica de PDF con Tamaños Duplicados
# -----------------------------
def _thumb_jpeg_fixed_box(file_bytes, box_w_mm, box_h_mm):
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(file_bytes)).convert("RGB"))
    # Aumentamos resolución interna para mantener nitidez al ser más grandes
    box_px_w, box_px_h = 1200, int(1200 * (box_h_mm / box_w_mm))
    canvas_img = Image.new("RGB", (box_px_w, box_px_h), (255, 255, 255))
    img.thumbnail((box_px_w, box_px_h), Image.Resampling.LANCZOS)
    canvas_img.paste(img, ((box_px_w - img.size[0]) // 2, (box_px_h - img.size[1]) // 2))
    buf = io.BytesIO()
    canvas_img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf

def build_pdf(titulo, fecha, equipo, ubicacion, inspector, cargo, registro_ot, disciplina, nivel_riesgo, observaciones, conclusion, fotos, firma_img, include_firma, include_fotos):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    
    story = [Paragraph(f"<b>{titulo}</b>", styles["Heading1"]), Spacer(1, 10)]
    
    # Tabla de datos
    data = [["Fecha", fecha], ["Disciplina", disciplina], ["Área/Equipo", equipo], ["Ubicación", ubicacion], ["Inspector", inspector], ["Cargo", cargo]]
    t =

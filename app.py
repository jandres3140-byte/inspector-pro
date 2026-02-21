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
# Configuración Inicial
# -----------------------------
st.set_page_config(page_title="jcamp029.pro", page_icon="🧾", layout="centered")
APP_TITLE = "jcamp029.pro"
APP_SUBTITLE = "Generador profesional de informes de inspección técnica (PDF)."
TZ_CL = ZoneInfo("America/Santiago")

UP_NONCE = "__uploader_nonce__"

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
        FIELD_KEYS["theme"]: "Claro",  # ✅ Cambio 1: Modo Claro por defecto
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
# CSS Dinámico (✅ Cambio 2: Legibilidad mejorada en Oscuro)
# -----------------------------
def apply_theme_css(theme: str) -> None:
    if theme == "Oscuro":
        bg, fg, card, border, input_bg = "#070B14", "#FFFFFF", "#0B1220", "#2D3748", "#1A202C"
    else:
        bg, fg, card, border, input_bg = "#FFFFFF", "#0f172a", "#f8fafc", "#e2e8f0", "#FFFFFF"

    st.markdown(f"""
        <style>
        .stApp {{ background: {bg}; color: {fg}; }}
        div[data-testid="stMarkdownContainer"] p {{ color: {fg} !important; }}
        div[data-testid="stWidgetLabel"] > label {{ color: {fg} !important; font-weight: 700 !important; }}
        input, textarea, div[data-baseweb="select"] > div {{ 
            background-color: {input_bg} !important; 
            color: {fg} !important; 
            border: 1px solid {border} !important; 
        }}
        .app-card {{ border: 1px solid {border}; background: {card}; border-radius: 12px; padding: 20px; margin-bottom: 20px; }}
        </style>
        """, unsafe_allow_html=True)

# -----------------------------
# PDF y Procesamiento de Imágenes (✅ Cambio 3: Tamaño al Doble)
# -----------------------------
def _thumb_jpeg(file_bytes, w_mm, h_mm):
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(file_bytes)).convert("RGB"))
    # Alta resolución para que no se vea pixelado al agrandar
    box_px_w, box_px_h = 1600, int(1600 * (h_mm / w_mm))
    canvas_img = Image.new("RGB", (box_px_w, box_px_h), (255, 255, 255))
    img.thumbnail((box_px_w, box_px_h), Image.Resampling.LANCZOS)
    canvas_img.paste(img, ((box_px_w - img.size[0]) // 2, (box_px_h - img.size[1]) // 2))
    buf = io.BytesIO()
    canvas_img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf

def build_pdf(data_dict, fotos, firma_img):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, margin=15*mm)
    styles = getSampleStyleSheet()
    
    # Encabezado
    story = [Paragraph(f"<b>{data_dict['titulo']}</b>", styles["Heading1"]), Spacer(1, 10)]
    
    # Tabla Principal
    table_data = [
        ["Fecha", data_dict['fecha']],
        ["Disciplina", data_dict['disciplina']],
        ["Equipo/Área", data_dict['equipo']],
        ["Ubicación", data_dict['ubicacion']],
        ["Inspector", data_dict['inspector']],
        ["OT/Registro", data_dict['registro_ot']]
    ]
    t = Table(table_data, colWidths=[40*mm, 140*mm])
    t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke)]))
    story.extend([t, Spacer(1, 15)])

    # Observaciones y Conclusión
    story.append(Paragraph("<b>Observaciones:</b>", styles["Heading2"]))
    story.append(Paragraph(data_dict['observaciones'].replace('\n', '<br/>'), styles["BodyText"]))
    story.append(Spacer(1, 15))
    story.append(Paragraph("<b>Conclusión:</b>", styles["Heading2"]))
    story.append(Paragraph(data_dict['conclusion'].replace('\n', '<br/>'), styles["BodyText"]))

    # Imágenes al DOBLE (80mm x 55mm aprox)
    if fotos:
        story.append(Spacer(1, 15))
        story.append(Paragraph("<b>Imágenes de Respaldo:</b>", styles["Heading2"]))
        for f_name, f_bytes in fotos:
            img_data = _thumb_jpeg(f_bytes, 90, 60)
            img_obj = RLImage(img_data, width=90*mm, height=60*mm)
            img_obj.hAlign = 'LEFT'
            story.extend([img_obj, Spacer(1, 5)])

    # Firma al DOBLE (80mm de ancho)
    if firma_img:
        story.append(Spacer(1, 20))
        story.append(Paragraph("<b>Firma:</b>", styles["Heading2"]))
        sig_data = _thumb_jpeg(firma_img[1], 80, 30)
        sig_obj = RLImage(sig_data, width=80*mm, height=30*mm)
        sig_obj.hAlign = 'LEFT'
        story.append(sig_obj)

    doc.build(story)
    return buffer.getvalue()

# -----------------------------
# Interfaz de Usuario
# -----------------------------
apply_theme_css(st.session_state[FIELD_KEYS["theme"]])

st.title(APP_TITLE)
st.radio("Seleccionar Tema", ["Claro", "Oscuro"], horizontal=True, key=FIELD_KEYS["theme"])

# Botón Limpiar
if st.button("🧹 Limpiar Formulario"):
    hard_reset_now()

# Sección de Datos
with st.container():
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.text_input("Título", key=FIELD_KEYS["titulo"])
    st.text_input("Inspector", key=FIELD_KEYS["inspector"])
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Fecha", key=FIELD_KEYS["fecha"])
        st.text_input("Equipo", key=FIELD_KEYS["equipo"])
    with col2:
        st.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Civil"], key=FIELD_KEYS["disciplina"])
        st.text_input("Ubicación", key=FIELD_KEYS["ubicacion"])
    st.text_input("OT", key=FIELD_KEYS["registro_ot"])
    st.text_area("Observaciones", height=120, key=FIELD_KEYS["observaciones_raw"])
    st.text_area("Conclusión", height=120, key=FIELD_KEYS["conclusion"])
    st.markdown("</div>", unsafe_allow_html=True)

# Imágenes y Archivos
with st.container():
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    nonce = st.session_state[UP_NONCE]
    up_fotos = st.file_uploader("Fotos (Máx 3)", type=["jpg", "png"], accept_multiple_files=True, key=f"f_{nonce}")
    up_firma = st.file_uploader("Firma", type=["jpg", "png"], key=f"s_{nonce}")
    st.markdown("</div>", unsafe_allow_html=True)

# Generación
if st.button("✅ Generar PDF", use_container_width=True):
    datos = {
        "titulo": st.session_state[FIELD_KEYS["titulo"]],
        "fecha": st.session_state[FIELD_KEYS["fecha"]],
        "disciplina": st.session_state[FIELD_KEYS["disciplina"]],
        "equipo": st.session_state[FIELD_KEYS["equipo"]],
        "ubicacion": st.session_state[FIELD_KEYS["ubicacion"]],
        "inspector": st.session_state[FIELD_KEYS["inspector"]],
        "registro_ot": st.session_state[FIELD_KEYS["registro_ot"]],
        "observaciones": st.session_state[FIELD_KEYS["observaciones_raw"]],
        "conclusion": st.session_state[FIELD_KEYS["conclusion"]],
    }
    fotos = [(f.name, f.read()) for f in up_fotos[:3]] if up_fotos else []
    firma = (up_firma.name, up_firma.read()) if up_firma else None
    
    pdf_output = build_pdf(datos, fotos, firma)
    st.download_button("📩 Descargar Informe", data=pdf_output, file_name="informe.pdf", mime="application/pdf")

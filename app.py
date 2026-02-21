import io
import re
from datetime import datetime
from typing import List, Tuple, Optional

import streamlit as st
from zoneinfo import ZoneInfo

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

from PIL import Image, ImageOps
from xml.sax.saxutils import escape

# -----------------------------
# Config & Medidas Reales
# -----------------------------
st.set_page_config(page_title="jcamp029.pro", page_icon="🧾", layout="centered")
APP_TITLE = "jcamp029.pro"
APP_SUBTITLE = "Generador profesional de informes de inspección técnica (PDF)."
TZ_CL = ZoneInfo("America/Santiago")

UP_NONCE = "__uploader_nonce__"

# ✅ TAMAÑOS MAXIMIZADOS PARA IMPACTO VISUAL
PHOTO_W_MM = 175  # Ancho casi total de la página
PHOTO_H_MM = 90   # Altura proporcional para gran detalle
SIGN_W_MM, SIGN_H_MM = 70, 40 # Firma profesional alargada

FIELD_KEYS = {
    "theme": "theme", "include_signature": "include_signature", "include_photos": "include_photos",
    "show_correccion": "show_correccion", "auto_conclusion": "auto_conclusion",
    "fecha": "fecha", "titulo": "titulo", "disciplina": "disciplina",
    "equipo": "equipo", "ubicacion": "ubicacion", "inspector": "inspector",
    "cargo": "cargo", "registro_ot": "registro_ot", "nivel_riesgo": "nivel_riesgo",
    "hallazgos": "hallazgos", "observaciones_raw": "observaciones_raw",
    "obs_fixed_preview": "obs_fixed_preview", "conclusion": "conclusion",
    "conclusion_locked": "conclusion_locked", "last_auto_hash": "last_auto_hash",
}

def get_defaults() -> dict:
    return {
        FIELD_KEYS["theme"]: "Oscuro", FIELD_KEYS["include_signature"]: True,
        FIELD_KEYS["include_photos"]: True, FIELD_KEYS["show_correccion"]: True,
        FIELD_KEYS["auto_conclusion"]: True,
        FIELD_KEYS["fecha"]: datetime.now(TZ_CL).strftime("%d-%m-%Y"),
        FIELD_KEYS["titulo"]: "Informe Técnico de Inspección",
        FIELD_KEYS["disciplina"]: "Eléctrica", FIELD_KEYS["equipo"]: "",
        FIELD_KEYS["ubicacion"]: "", FIELD_KEYS["inspector"]: "JORGE CAMPOS AGUIRRE",
        FIELD_KEYS["cargo"]: "Especialista eléctrico", FIELD_KEYS["registro_ot"]: "",
        FIELD_KEYS["nivel_riesgo"]: "Medio", FIELD_KEYS["hallazgos"]: [],
        FIELD_KEYS["observaciones_raw"]: "", FIELD_KEYS["obs_fixed_preview"]: "",
        FIELD_KEYS["conclusion"]: "", FIELD_KEYS["conclusion_locked"]: False,
        FIELD_KEYS["last_auto_hash"]: "",
    }

def init_state():
    if UP_NONCE not in st.session_state: st.session_state[UP_NONCE] = 0
    defaults = get_defaults()
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

def hard_reset_now():
    current_theme = st.session_state.get(FIELD_KEYS["theme"], "Oscuro")
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.session_state[UP_NONCE] = st.session_state.get(UP_NONCE, 0) + 1
    defaults = get_defaults()
    for k, v in defaults.items(): st.session_state[k] = v
    st.session_state[FIELD_KEYS["theme"]] = current_theme
    st.rerun()

init_state()

# -----------------------------
# Estilos CSS
# -----------------------------
def apply_theme_css(theme: str) -> None:
    if theme == "Oscuro":
        bg, fg, card, border = "#070B14", "#FFFFFF", "#0B1220", "#2A3A58"
        input_bg, placeholder = "#0A1020", "#9FB0C8"
    else:
        bg, fg, card, border = "#FFFFFF", "#0F172A", "#F8FAFC", "#E2E8F0"
        input_bg, placeholder = "#FFFFFF", "#64748B"

    st.markdown(f"""
        <style>
        .stApp {{ background: {bg}; color: {fg}; }}
        div[data-testid="stMarkdownContainer"] * {{ color: {fg} !important; }}
        .app-card {{ border: 1px solid {border}; background: {card}; border-radius: 14px; padding: 20px; margin-bottom: 16px; }}
        input, textarea {{ background: {input_bg} !important; color: {fg} !important; border: 1px solid {border} !important; }}
        div[data-baseweb="select"] > div {{ background: {input_bg} !important; border: 1px solid {border} !important; }}
        div[data-baseweb="select"] * {{ color: {fg} !important; }}
        </style>
        """, unsafe_allow_html=True)

# -----------------------------
# Procesamiento de Imágenes
# -----------------------------
def _thumb_jpeg_fixed_box(file_bytes: bytes, box_w_mm: float, box_h_mm: float) -> io.BytesIO:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(file_bytes)).convert("RGB"))
    # Alta resolución para impresión
    box_px_w = 1800 
    box_px_h = max(1, int(box_px_w * (box_h_mm / box_w_mm)))
    canvas_img = Image.new("RGB", (box_px_w, box_px_h), (255, 255, 255))
    img.thumbnail((box_px_w, box_px_h), Image.Resampling.LANCZOS)
    canvas_img.paste(img, ((box_px_w - img.size[0]) // 2, (box_px_h - img.size[1]) // 2))
    buf = io.BytesIO()
    canvas_img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf

# -----------------------------
# Motor PDF (Corregido para 1 Hoja)
# -----------------------------
def build_pdf(data_dict, fotos, firma_img, include_firma, include_fotos) -> bytes:
    buffer = io.BytesIO()
    # Márgenes reducidos para ganar espacio
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=12*mm, bottomMargin=12*mm)
    styles = getSampleStyleSheet()
    
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18, alignment=1, spaceAfter=14)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=4, textColor=colors.hexColor("#1A365D"))
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=13)

    story = [Paragraph(data_dict['titulo'].upper(), h1)]

    # Tabla de datos técnica
    tabla_info = [
        ["FECHA", data_dict['fecha'], "RIESGO", data_dict['nivel_riesgo']],
        ["DISCIPLINA", data_dict['disciplina'], "OT / REGISTRO", data_dict['registro_ot']],
        ["EQUIPO", data_dict['equipo'], "UBICACIÓN", data_dict['ubicacion']],
        ["INSPECTOR", data_dict['inspector'], "CARGO", data_dict['cargo']]
    ]
    t = Table(tabla_info, colWidths=[35*mm, 55*mm, 35*mm, 55*mm])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke),
        ('BACKGROUND', (2,0), (2,-1), colors.whitesmoke),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t)

    story.append(Paragraph("OBSERVACIONES TÉCNICAS", h2))
    story.append(Paragraph(data_dict['obs'].replace('\n', '<br/>') or "Sin observaciones.", body))

    story.append(Paragraph("CONCLUSIÓN", h2))
    story.append(Paragraph(data_dict['concl'].replace('\n', '<br/>') or "Sin conclusión.", body))

    # ✅ IMÁGENES GRANDES (Una debajo de otra para máximo detalle)
    if include_fotos and fotos:
        story.append(Paragraph("EVIDENCIA FOTOGRÁFICA", h2))
        for _, b in fotos[:3]:
            img_data = _thumb_jpeg_fixed_box(b, PHOTO_W_MM, PHOTO_H_MM)
            img_obj = RLImage(img_data, width=PHOTO_W_MM*mm, height=PHOTO_H_MM*mm)
            img_obj.hAlign = 'CENTER'
            story.append(Spacer(1, 2*mm))
            story.append(img_obj)

    # ✅ FIRMA GRANDE AL FINAL
    if include_firma and firma_img:
        story.append(Spacer(1, 10*mm))
        story.append(Paragraph("FIRMA RESPONSABLE", h2))
        sig_data = _thumb_jpeg_fixed_box(firma_img[1], SIGN_W_MM, SIGN_H_MM)
        sig_obj = RLImage(sig_data, width=SIGN_W_MM*mm, height=SIGN_H_MM*mm)
        sig_obj.hAlign = 'LEFT'
        story.append(sig_obj)

    doc.build(story)
    return buffer.getvalue()

# -----------------------------
# Interfaz de Usuario
# -----------------------------
apply_theme_css(st.session_state[FIELD_KEYS["theme"]])
st.markdown(f"<h1>{APP_TITLE}</h1>", unsafe_allow_html=True)
st.radio("Tema", ["Claro", "Oscuro"], horizontal=True, key=FIELD_KEYS["theme"])

# Panel de controles
with st.container():
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1.2])
    c1.checkbox("Firma", key=FIELD_KEYS["include_signature"])
    c2.checkbox("Fotos", key=FIELD_KEYS["include_photos"])
    c3.checkbox("Corrección", key=FIELD_KEYS["show_correccion"])
    if c4.button("🧹 Limpiar Formulario", use_container_width=True): hard_reset_now()
    st.markdown("</div>", unsafe_allow_html=True)

# Formulario
with st.container():
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.text_input("Título del Informe", key=FIELD_KEYS["titulo"])
    st.text_input("Fecha", key=FIELD_KEYS["fecha"])
    
    colA, colB = st.columns(2)
    with colA:
        st.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Civil", "Otra"], key=FIELD_KEYS["disciplina"])
        st.text_input("Equipo / Área", key=FIELD_KEYS["equipo"])
    with colB:
        st.selectbox("Riesgo", ["Bajo", "Medio", "Alto"], key=FIELD_KEYS["nivel_riesgo"])
        st.text_input("Ubicación", key=FIELD_KEYS["ubicacion"])
    
    st.text_area("Observaciones", height=120, key=FIELD_KEYS["observaciones_raw"])
    st.text_area("Conclusión", height=120, key=FIELD_KEYS["conclusion"])
    st.markdown("</div>", unsafe_allow_html=True)

# Archivos
with st.container():
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    nonce = st.session_state[UP_NONCE]
    f_files = st.file_uploader("Fotos (Máx 3)", type=["jpg", "png"], accept_multiple_files=True, key=f"f_{nonce}")
    s_file = st.file_uploader("Subir Firma", type=["jpg", "png"], key=f"s_{nonce}")
    st.markdown("</div>", unsafe_allow_html=True)

# Generación
if st.button("GENERAR PDF PROFESIONAL ✅", use_container_width=True):
    fotos_list = [(f.name, f.read()) for f in (f_files or [])[:3]]
    firma_data = (s_file.name, s_file.read()) if s_file else None
    
    pdf = build_pdf({
        'titulo': st.session_state[FIELD_KEYS["titulo"]],
        'fecha': st.session_state[FIELD_KEYS["fecha"]],
        'disciplina': st.session_state[FIELD_KEYS["disciplina"]],
        'nivel_riesgo': st.session_state[FIELD_KEYS["nivel_riesgo"]],
        'equipo': st.session_state[FIELD_KEYS["equipo"]],
        'ubicacion': st.session_state[FIELD_KEYS["ubicacion"]],
        'inspector': st.session_state[FIELD_KEYS["inspector"]],
        'cargo': st.session_state[FIELD_KEYS["cargo"]],
        'registro_ot': st.session_state[FIELD_KEYS["registro_ot"]],
        'obs': st.session_state[FIELD_KEYS["observaciones_raw"]],
        'concl': st.session_state[FIELD_KEYS["conclusion"]]
    }, fotos_list, firma_data, st.session_state[FIELD_KEYS["include_signature"]], st.session_state[FIELD_KEYS["include_photos"]])
    
    st.download_button("Descargar Informe PDF", data=pdf, file_name=f"informe_{datetime.now().strftime('%H%M%S')}.pdf", mime="application/pdf", use_container_width=True)

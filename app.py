import io
import re
from datetime import datetime
from typing import Optional, List, Tuple

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

from PIL import Image, ImageOps
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

# -----------------------------
# Configuración
# -----------------------------
st.set_page_config(page_title="jcamp029.pro", page_icon="🧾", layout="centered")
APP_TITLE = "jcamp029.pro"
APP_SUBTITLE = "Generador profesional de informes de inspección técnica (PDF)."
TZ_CL = ZoneInfo("America/Santiago")

UP_NONCE = "__uploader_nonce__"

# ✅ TAMAÑOS DUPLICADOS (Ajustados para máximo impacto visual en A4)
PHOTO_W_MM, PHOTO_H_MM = 110, 75  # Mucho más grandes
SIGN_W_MM, SIGN_H_MM = 80, 40    # Firma más legible

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
    "conclusion_locked": "conclusion_locked",
    "last_auto_hash": "last_auto_hash",
}

def get_defaults() -> dict:
    return {
        FIELD_KEYS["theme"]: "Claro",  # ✅ Cambio: Claro por defecto
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
        FIELD_KEYS["conclusion_locked"]: False,
        FIELD_KEYS["last_auto_hash"]: "",
    }

def init_state():
    if UP_NONCE not in st.session_state:
        st.session_state[UP_NONCE] = 0
    defaults = get_defaults()
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

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

init_state()

# -----------------------------
# Helpers UI / CSS (Legibilidad Mejorada)
# -----------------------------
def apply_theme_css(theme: str) -> None:
    if theme == "Oscuro":
        bg, fg, card, border, input_bg, input_fg = "#070B14", "#FFFFFF", "#0B1220", "#2D3748", "#1A202C", "#FFFFFF"
    else:
        bg, fg, card, border, input_bg, input_fg = "#FFFFFF", "#0F172A", "#F8FAFC", "#E2E8F0", "#FFFFFF", "#0F172A"

    st.markdown(f"""
        <style>
        .stApp {{ background: {bg}; color: {fg}; }}
        div[data-testid="stMarkdownContainer"] * {{ color: {fg} !important; }}
        div[data-testid="stWidgetLabel"] > label {{ color: {fg} !important; font-weight: 800 !important; }}
        .app-card {{ border: 1px solid {border}; background: {card}; border-radius: 14px; padding: 20px; margin-bottom: 16px; }}
        
        /* ✅ Solución a letras que no se distinguen en modo oscuro */
        input, textarea, div[data-baseweb="select"] > div {{ 
            background-color: {input_bg} !important; 
            color: {input_fg} !important; 
            border: 1px solid {border} !important; 
        }}
        div[data-baseweb="select"] * {{ color: {input_fg} !important; }}
        </style>
        """, unsafe_allow_html=True)

# -----------------------------
# Lógica de PDF y Procesamiento
# -----------------------------
def _thumb_jpeg_fixed_box(file_bytes: bytes, box_w_mm: float, box_h_mm: float) -> io.BytesIO:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(file_bytes)).convert("RGB"))
    box_px_w = 1600 # Mayor resolución para impresión
    box_px_h = max(1, int(box_px_w * (box_h_mm / box_w_mm)))
    canvas_img = Image.new("RGB", (box_px_w, box_px_h), (255, 255, 255))
    img.thumbnail((box_px_w, box_px_h), Image.Resampling.LANCZOS)
    canvas_img.paste(img, ((box_px_w - img.size[0]) // 2, (box_px_h - img.size[1]) // 2))
    buf = io.BytesIO()
    canvas_img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf

def build_pdf(data: dict, fotos: list, firma: Optional[tuple]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, margin=15*mm)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18, spaceAfter=12)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13, spaceBefore=12, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14)

    story = [Paragraph(data['titulo'].upper(), h1), Spacer(1, 5)]
    
    # Tabla de Datos
    tbl_data = [
        ["Fecha", data['fecha']], ["Disciplina", data['disciplina']],
        ["Riesgo", data['nivel_riesgo']], ["Equipo", data['equipo']],
        ["Ubicación", data['ubicacion']], ["Inspector", data['inspector']],
        ["OT", data['registro_ot']]
    ]
    t = Table(tbl_data, colWidths=[40*mm, 140*mm])
    t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
    story.extend([t, Paragraph("Observaciones", h2), Paragraph(data['obs'].replace('\n', '<br/>'), body)])
    story.extend([Paragraph("Conclusión", h2), Paragraph(data['concl'].replace('\n', '<br/>'), body)])

    # ✅ Imágenes Grandes
    if data['inc_fotos'] and fotos:
        story.append(Paragraph("Evidencia Fotográfica", h2))
        for f in fotos[:3]:
            img_data = _thumb_jpeg_fixed_box(f[1], PHOTO_W_MM, PHOTO_H_MM)
            img_obj = RLImage(img_data, width=PHOTO_W_MM*mm, height=PHOTO_H_MM*mm)
            img_obj.hAlign = 'CENTER'
            story.extend([Spacer(1, 5), img_obj, Spacer(1, 5)])

    # ✅ Firma Grande
    if data['inc_firma'] and firma:
        story.append(Spacer(1, 15))
        story.append(Paragraph("Firma Responsable", h2))
        sig_data = _thumb_jpeg_fixed_box(firma[1], SIGN_W_MM, SIGN_H_MM)
        sig_obj = RLImage(sig_data, width=SIGN_W_MM*mm, height=SIGN_H_MM*mm)
        sig_obj.hAlign = 'LEFT'
        story.append(sig_obj)

    doc.build(story)
    return buffer.getvalue()

# -----------------------------
# Lógica de Conclusión y Corrección
# -----------------------------
def sync_auto_conclusion():
    if not st.session_state[FIELD_KEYS["auto_conclusion"]] or st.session_state[FIELD_KEYS["conclusion_locked"]]:
        return
    d = st.session_state[FIELD_KEYS["disciplina"]]
    r = st.session_state[FIELD_KEYS["nivel_riesgo"]]
    h = st.session_state[FIELD_KEYS["hallazgos"]]
    current_hash = f"{d}|{r}|{h}"
    if current_hash != st.session_state[FIELD_KEYS["last_auto_hash"]]:
        prioridad = "inmediata" if r == "Alto" else "programada" if r == "Medio" else "rutinaria"
        hall = f" Hallazgos: {', '.join(h)}." if h else ""
        st.session_state[FIELD_KEYS["conclusion"]] = f"Inspección {d}: Riesgo {r.lower()}. Prioridad {prioridad}.{hall} Acción: Corregir desviaciones y registrar en sistema."
        st.session_state[FIELD_KEYS["last_auto_hash"]] = current_hash

# -----------------------------
# UI RENDERING
# -----------------------------
apply_theme_css(st.session_state[FIELD_KEYS["theme"]])
st.markdown(f"<h1>{APP_TITLE}</h1>", unsafe_allow_html=True)
st.radio("Visualización", ["Claro", "Oscuro"], horizontal=True, key=FIELD_KEYS["theme"])

# Panel de Control
with st.container():
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([1,1,1,1.5])
    c1.checkbox("Firma", key=FIELD_KEYS["include_signature"])
    c2.checkbox("Fotos", key=FIELD_KEYS["include_photos"])
    c3.checkbox("Corrección", key=FIELD_KEYS["show_correccion"])
    if c4.button("🧹 Limpiar Formulario", use_container_width=True): hard_reset_now()
    st.markdown("</div>", unsafe_allow_html=True)

# Formulario Principal
with st.container():
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.text_input("Título", key=FIELD_KEYS["titulo"])
    st.text_input("Fecha", key=FIELD_KEYS["fecha"])
    colA, colB = st.columns(2)
    colA.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Instrumentación", "Otra"], key=FIELD_KEYS["disciplina"])
    colB.selectbox("Riesgo", ["Bajo", "Medio", "Alto"], key=FIELD_KEYS["nivel_riesgo"])
    st.multiselect("Hallazgos", ["Condición insegura", "EPP", "LOTO", "Orden/Limpieza", "Tableros"], key=FIELD_KEYS["hallazgos"])
    st.text_input("Equipo / Área", key=FIELD_KEYS["equipo"])
    st.text_input("Ubicación", key=FIELD_KEYS["ubicacion"])
    st.text_area("Observaciones Técnicas", height=120, key=FIELD_KEYS["observaciones_raw"])
    
    sync_auto_conclusion()
    st.checkbox("Auto-conclusión", key=FIELD_KEYS["auto_conclusion"])
    st.text_area("Conclusión Final", height=120, key=FIELD_KEYS["conclusion"])
    st.markdown("</div>", unsafe_allow_html=True)

# Archivos
with st.container():
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    nonce = st.session_state[UP_NONCE]
    f_files = st.file_uploader("Subir Fotos (Máx 3)", type=["jpg","png"], accept_multiple_files=True, key=f"f_{nonce}")
    s_file = st.file_uploader("Subir Firma", type=["jpg","png"], key=f"s_{nonce}")
    st.markdown("</div>", unsafe_allow_html=True)

# Acción
if st.button("🚀 GENERAR INFORME PDF", use_container_width=True):
    pdf_data = {
        'titulo': st.session_state[FIELD_KEYS["titulo"]],
        'fecha': st.session_state[FIELD_KEYS["fecha"]],
        'disciplina': st.session_state[FIELD_KEYS["disciplina"]],
        'nivel_riesgo': st.session_state[FIELD_KEYS["nivel_riesgo"]],
        'equipo': st.session_state[FIELD_KEYS["equipo"]],
        'ubicacion': st.session_state[FIELD_KEYS["ubicacion"]],
        'inspector': st.session_state[FIELD_KEYS["inspector"]],
        'registro_ot': st.session_state[FIELD_KEYS["registro_ot"]],
        'obs': st.session_state[FIELD_KEYS["observaciones_raw"]],
        'concl': st.session_state[FIELD_KEYS["conclusion"]],
        'inc_fotos': st.session_state[FIELD_KEYS["include_photos"]],
        'inc_firma': st.session_state[FIELD_KEYS["include_signature"]]
    }
    
    fotos_list = [(f.name, f.read()) for f in (f_files or [])[:3]]
    firma_tuple = (s_file.name, s_file.read()) if s_file else None
    
    pdf = build_pdf(pdf_data, fotos_list, firma_tuple)
    st.download_button("📩 Descargar PDF Corregido", data=pdf, file_name=f"informe_{datetime.now().strftime('%H%M%S')}.pdf", mime="application/pdf", use_container_width=True)

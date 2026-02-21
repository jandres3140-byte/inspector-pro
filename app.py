import io
import re
from datetime import datetime
from typing import Optional, List, Tuple

import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from PIL import Image, ImageOps
from zoneinfo import ZoneInfo

# -----------------------------
# Configuración y Estilo
# -----------------------------
st.set_page_config(page_title="jcamp029.pro", page_icon="🧾", layout="centered")
TZ_CL = ZoneInfo("America/Santiago")

# ✅ TAMAÑOS MAXIMIZADOS PARA UNA HOJA
PHOTO_W_MM = 160  # Casi el ancho total de la página (A4 es 210mm)
PHOTO_H_MM = 85   # Altura generosa para detalle
SIGN_W_MM = 70    # Firma clara y visible

FIELD_KEYS = {
    "theme": "theme", "fecha": "fecha", "titulo": "titulo", "disciplina": "disciplina",
    "equipo": "equipo", "ubicacion": "ubicacion", "inspector": "inspector",
    "registro_ot": "registro_ot", "nivel_riesgo": "nivel_riesgo", "hallazgos": "hallazgos",
    "observaciones_raw": "observaciones_raw", "conclusion": "conclusion"
}

def get_defaults():
    return {
        FIELD_KEYS["theme"]: "Claro", FIELD_KEYS["fecha"]: datetime.now(TZ_CL).strftime("%d-%m-%Y"),
        FIELD_KEYS["titulo"]: "Informe Técnico de Inspección", FIELD_KEYS["disciplina"]: "Eléctrica",
        FIELD_KEYS["equipo"]: "", FIELD_KEYS["ubicacion"]: "", FIELD_KEYS["inspector"]: "JORGE CAMPOS AGUIRRE",
        FIELD_KEYS["registro_ot"]: "", FIELD_KEYS["nivel_riesgo"]: "Bajo", FIELD_KEYS["hallazgos"]: [],
        FIELD_KEYS["observaciones_raw"]: "", FIELD_KEYS["conclusion"]: ""
    }

if "initialized" not in st.session_state:
    for k, v in get_defaults().items(): st.session_state[k] = v
    st.session_state["initialized"] = True

# -----------------------------
# Motor de PDF (Optimizado para 1 Hoja)
# -----------------------------
def _process_image(file_bytes, w_mm, h_mm):
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(file_bytes)).convert("RGB"))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf

def build_pdf(data, fotos, firma):
    buffer = io.BytesIO()
    # Márgenes estrechos para maximizar espacio
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=10*mm, bottomMargin=10*mm)
    styles = getSampleStyleSheet()
    
    # Estilos compactos
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=16, alignment=1, spaceAfter=10)
    sub_style = ParagraphStyle("Sub", parent=styles["Heading2"], fontSize=11, spaceBefore=5, spaceAfter=2, textColor=colors.navy)
    body_style = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10, leading=12)

    story = [Paragraph(data['titulo'].upper(), title_style)]
    
    # Tabla de cabecera compacta
    tbl_data = [
        ["FECHA:", data['fecha'], "DISCIPLINA:", data['disciplina']],
        ["EQUIPO:", data['equipo'], "RIESGO:", data['nivel_riesgo']],
        ["UBICACIÓN:", data['ubicacion'], "OT:", data['registro_ot']],
        ["INSPECTOR:", data['inspector'], "", ""]
    ]
    t = Table(tbl_data, colWidths=[30*mm, 60*mm, 30*mm, 60*mm])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke),
        ('BACKGROUND', (2,0), (2,-1), colors.whitesmoke),
    ]))
    story.append(t)

    # Observaciones y Conclusión
    story.append(Paragraph("OBSERVACIONES", sub_style))
    story.append(Paragraph(data['obs'] or "Sin observaciones.", body_style))
    
    story.append(Paragraph("CONCLUSIÓN", sub_style))
    story.append(Paragraph(data['concl'] or "Sin conclusión.", body_style))

    # Imágenes GRANDES
    if fotos:
        story.append(Paragraph("EVIDENCIA FOTOGRÁFICA", sub_style))
        for f in fotos[:3]:
            img_processed = _process_image(f[1], PHOTO_W_MM, PHOTO_H_MM)
            img_obj = RLImage(img_processed, width=PHOTO_W_MM*mm, height=PHOTO_H_MM*mm)
            img_obj.hAlign = 'CENTER'
            story.append(img_obj)
            story.append(Spacer(1, 2*mm))

    # Firma
    if firma:
        story.append(Spacer(1, 5*mm))
        sig_processed = _process_image(firma[1], SIGN_W_MM, 30)
        sig_obj = RLImage(sig_processed, width=SIGN_W_MM*mm, height=35*mm)
        sig_obj.hAlign = 'LEFT'
        story.append(Paragraph("FIRMA RESPONSABLE:", sub_style))
        story.append(sig_obj)

    doc.build(story)
    return buffer.getvalue()

# -----------------------------
# Interfaz Streamlit
# -----------------------------
st.title("jcamp029.pro")
st.radio("Tema", ["Claro", "Oscuro"], key=FIELD_KEYS["theme"], horizontal=True)

with st.expander("DATOS DEL INFORME", expanded=True):
    col1, col2 = st.columns(2)
    st.text_input("Título del Informe", key=FIELD_KEYS["titulo"])
    with col1:
        st.text_input("Fecha", key=FIELD_KEYS["fecha"])
        st.text_input("Equipo / Área", key=FIELD_KEYS["equipo"])
        st.selectbox("Nivel de Riesgo", ["Bajo", "Medio", "Alto"], key=FIELD_KEYS["nivel_riesgo"])
    with col2:
        st.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Civil"], key=FIELD_KEYS["disciplina"])
        st.text_input("Ubicación", key=FIELD_KEYS["ubicacion"])
        st.text_input("N° Registro / OT", key=FIELD_KEYS["registro_ot"])
    
    st.text_area("Observaciones Técnicas", key=FIELD_KEYS["observaciones_raw"], height=100)
    st.text_area("Conclusión (Editable)", key=FIELD_KEYS["conclusion"], height=100)

col_img, col_sig = st.columns(2)
with col_img:
    up_fotos = st.file_uploader("Fotos (Máx 3)", type=["jpg", "png"], accept_multiple_files=True)
with col_sig:
    up_firma = st.file_uploader("Firma (Imagen)", type=["jpg", "png"])

if st.button("GENERAR PDF PROFESIONAL ✅", use_container_width=True):
    fotos_list = [(f.name, f.read()) for f in up_fotos] if up_fotos else []
    firma_data = (up_firma.name, up_firma.read()) if up_firma else None
    
    pdf_bytes = build_pdf({
        'titulo': st.session_state[FIELD_KEYS["titulo"]],
        'fecha': st.session_state[FIELD_KEYS["fecha"]],
        'disciplina': st.session_state[FIELD_KEYS["disciplina"]],
        'equipo': st.session_state[FIELD_KEYS["equipo"]],
        'ubicacion': st.session_state[FIELD_KEYS["ubicacion"]],
        'nivel_riesgo': st.session_state[FIELD_KEYS["nivel_riesgo"]],
        'registro_ot': st.session_state[FIELD_KEYS["registro_ot"]],
        'inspector': st.session_state[FIELD_KEYS["inspector"]],
        'obs': st.session_state[FIELD_KEYS["observaciones_raw"]],
        'concl': st.session_state[FIELD_KEYS["conclusion"]]
    }, fotos_list, firma_data)
    
    st.download_button("📥 Descargar Informe", data=pdf_bytes, file_name="informe_tecnico.pdf", mime="application/pdf", use_container_width=True)

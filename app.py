import streamlit as st
from datetime import datetime
from io import BytesIO
from typing import List, Tuple, Optional
import re

# PDF (ReportLab)
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# Imágenes
from PIL import Image as PILImage

# Corrector (LanguageTool)
LANGUAGETOOL_OK = True
try:
    import language_tool_python
except Exception:
    LANGUAGETOOL_OK = False


# =========================
# CONFIG APP
# =========================
st.set_page_config(page_title="jcamp029.pro", layout="centered")

APP_BRAND = "jcamp029.pro"
APP_TAGLINE = "Technical Inspection System"

RISK_LEVELS = ["Bajo", "Medio", "Alto"]

RISK_COLOR_HEX = {
    "Bajo": "#1E7F2D",
    "Medio": "#B7791F",
    "Alto": "#B91C1C",
}

RISK_COLOR_RL = {
    "Bajo": colors.HexColor(RISK_COLOR_HEX["Bajo"]),
    "Medio": colors.HexColor(RISK_COLOR_HEX["Medio"]),
    "Alto": colors.HexColor(RISK_COLOR_HEX["Alto"]),
}


# =========================
# CSS
# =========================
def inject_css(theme: str):
    if theme == "Oscuro":
        bg = "#0B1220"
        panel = "#0F1A2E"
        text = "#EAF0FF"
        muted = "#AAB7D1"
        input_bg = "#0F1A2E"
        border = "#2A3A5F"
        accent = "#FFFFFF"
        button_bg = "#111827"
        button_border = "#C9A227"
        button_text = "#F9FAFB"
        shadow = "0 10px 30px rgba(0,0,0,.35)"
    else:
        bg = "#FFFFFF"
        panel = "#FFFFFF"
        text = "#0F172A"
        muted = "#475569"
        input_bg = "#FFFFFF"
        border = "#CBD5E1"
        accent = "#0F172A"
        button_bg = "#0F172A"
        button_border = "#0F172A"
        button_text = "#FFFFFF"
        shadow = "0 10px 30px rgba(2,6,23,.08)"

    st.markdown(
        f"""
        <style>
        html, body, [data-testid="stAppViewContainer"] {{
            background: {bg} !important;
            color: {text} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================
# UTILIDADES TEXTO
# =========================
def normalize_text_basic(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\.(\S)", r". \1", t)
    if t and t[0].isalpha():
        t = t[0].upper() + t[1:]
    return t


# =========================
# UI
# =========================
theme = st.radio("Tema", ["Claro", "Oscuro"], horizontal=True)
inject_css(theme)

st.title("jcamp029.pro")
st.write("Generador profesional de informes de inspección técnica (PDF).")

titulo = st.text_input("Título del informe", "Informe Técnico de Inspección")
equipo = st.text_input("Equipo inspeccionado")
ubicacion = st.text_input("Ubicación")
inspector = st.text_input("Inspector")
cargo = st.text_input("Cargo")
registro_ot = st.text_input("N° Registro/OT")
riesgo = st.selectbox("Nivel de riesgo", RISK_LEVELS)
observaciones = st.text_area("Observaciones técnicas")

# =========================
# PDF
# =========================
def generar_pdf():
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("INFORME TÉCNICO DE INSPECCIÓN", styles["Heading1"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(f"Fecha: {datetime.now().strftime('%d-%m-%Y')}", styles["Normal"]))
    elements.append(Paragraph(f"Equipo: {equipo}", styles["Normal"]))
    elements.append(Paragraph(f"Ubicación: {ubicacion}", styles["Normal"]))
    elements.append(Paragraph(f"Inspector: {inspector}", styles["Normal"]))
    elements.append(Paragraph(f"Cargo: {cargo}", styles["Normal"]))
    elements.append(Paragraph(f"N° Registro/OT: {registro_ot}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Observaciones:", styles["Heading2"]))
    elements.append(Paragraph(normalize_text_basic(observaciones), styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


if st.button("Generar PDF Profesional"):
    pdf = generar_pdf()
    st.success("PDF generado ✅")
    st.download_button(
        label="Descargar Informe PDF",
        data=pdf,
        file_name="Informe_jcamp029pro.pdf",
        mime="application/pdf"
    )

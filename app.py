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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from PIL import Image, ImageOps

# -----------------------------
# Config & Inteligencia
# -----------------------------
st.set_page_config(page_title="jcamp029.pro", page_icon="🧾", layout="centered")
TZ_CL = ZoneInfo("America/Santiago")

def generar_resumen_tecnico(disciplina, riesgo, hallazgos):
    """La magia: Genera un párrafo profesional basado en la selección."""
    prioridad = "INMEDIATA" if riesgo == "Alto" else "PROGRAMADA" if riesgo == "Medio" else "RUTINARIA"
    
    dict_especifico = {
        "Eléctrica": "Se recomienda inspección de torque en conexiones y validación de parámetros de aislamiento.",
        "Mecánica": "Verificar niveles de lubricación y estado de anclajes estructurales.",
        "Instrumental": "Validar calibración de lazos y limpieza de elementos primarios.",
        "Civil": "Evaluar integridad de bases y estado de recubrimientos superficiales."
    }
    
    concl = f"Evaluación de especialidad {disciplina} concluida con nivel de riesgo {riesgo.upper()}. "
    concl += f"Se establece una prioridad de atención {prioridad}. "
    
    if hallazgos:
        concl += f"Los hallazgos en {', '.join(hallazgos)} requieren corrección según norma vigente. "
    
    concl += dict_especifico.get(disciplina, "Seguir pautas de mantenimiento preventivo estándar.")
    return concl

# -----------------------------
# Funciones PDF
# -----------------------------
def build_pdf(data, fotos, firma_img):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, margin=15*mm)
    styles = getSampleStyleSheet()
    
    # Estilos
    h1 = ParagraphStyle("h1", fontSize=16, spaceAfter=10, fontName="Helvetica-Bold", alignment=1)
    h2 = ParagraphStyle("h2", fontSize=11, spaceBefore=8, spaceAfter=4, textColor=colors.navy, fontName="Helvetica-Bold")
    body = ParagraphStyle("body", fontSize=10, leading=13)

    story = [Paragraph("INFORME TÉCNICO DE INSPECCIÓN", h1)]

    # Tabla de Datos
    tbl_data = [
        ["FECHA", data['fecha'], "RIESGO", data['riesgo']],
        ["DISCIPLINA", data['disciplina'], "OT", data['ot']],
        ["EQUIPO", data['equipo'], "UBICACIÓN", data['ubicacion']],
        ["INSPECTOR", data['inspector'], "CARGO", data['cargo']]
    ]
    t = Table(tbl_data, colWidths=[30*mm, 60*mm, 30*mm, 60*mm])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke),
        ('BACKGROUND', (2,0), (2,-1), colors.whitesmoke),
        ('FONTSIZE', (0,0), (-1,-1), 9),
    ]))
    story.append(t)

    story.append(Paragraph("OBSERVACIONES DE CAMPO", h2))
    story.append(Paragraph(data['obs'] or "Sin observaciones adicionales.", body))

    story.append(Paragraph("RESUMEN TÉCNICO (GENERADO POR SISTEMA)", h2))
    story.append(Paragraph(data['resumen'], body))

    if fotos:
        story.append(Paragraph("EVIDENCIA FOTOGRÁFICA", h2))
        for _, b in fotos[:2]: # Limitado a 2 para asegurar 1 sola hoja
            img = RLImage(io.BytesIO(b), width=140*mm, height=80*mm)
            img.hAlign = 'CENTER'
            story.append(Spacer(1, 4*mm))
            story.append(img)

    if firma_img:
        story.append(Spacer(1, 10*mm))
        story.append(Paragraph("FIRMA RESPONSABLE:", h2))
        sig = RLImage(io.BytesIO(firma_img[1]), width=60*mm, height=30*mm)
        sig.hAlign = 'LEFT'
        story.append(sig)

    doc.build(story)
    return buffer.getvalue()

# -----------------------------
# Interfaz Streamlit
# -----------------------------
st.title("jcamp029.pro")

# Botón de Limpieza al inicio
if st.button("🧹 Limpiar Formulario"):
    st.rerun()

with st.container(border=True):
    col1, col2 = st.columns(2)
    with col1:
        fecha = st.text_input("Fecha", datetime.now(TZ_CL).strftime("%d-%m-%Y"))
        disciplina = st.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Instrumental", "Civil"])
        equipo = st.text_input("Equipo / TAG")
    with col2:
        riesgo = st.selectbox("Riesgo", ["Bajo", "Medio", "Alto"])
        ubicacion = st.text_input("Ubicación") # Limpio: solo Ubicación
        ot = st.text_input("N° OT")

    inspector = st.text_input("Inspector", "JORGE CAMPOS AGUIRRE")
    cargo = st.text_input("Cargo", "Especialista Eléctrico")
    
    hallazgos = st.multiselect("Hallazgos Detectados", ["Condición Insegura", "Falta Rotulación", "Falla Aislamiento", "Corrosión", "LOTO"])
    obs = st.text_area("Observaciones Adicionales")

# Generación automática de la conclusión técnica
resumen_auto = generar_resumen_tecnico(disciplina, riesgo, hallazgos)
st.markdown("### 🤖 Resumen Técnico Automático")
st.info(resumen_auto)

# Carga de archivos
c_img, c_sig = st.columns(2)
up_fotos = c_img.file_uploader("Evidencia (Fotos)", type=["jpg", "png"], accept_multiple_files=True)
up_firma = c_sig.file_uploader("Firma", type=["jpg", "png"])

if st.button("Generar PDF Profesional ✅", use_container_width=True):
    if not up_firma:
        st.error("Se requiere la firma para validar el informe.")
    else:
        fotos_list = [(f.name, f.read()) for f in up_fotos] if up_fotos else []
        pdf_data = {
            'fecha': fecha, 'disciplina': disciplina, 'equipo': equipo,
            'riesgo': riesgo, 'ubicacion': ubicacion, 'ot': ot,
            'inspector': inspector, 'cargo': cargo, 'obs': obs,
            'resumen': resumen_auto
        }
        
        pdf = build_pdf(pdf_data, fotos_list, (up_firma.name, up_firma.read()))
        st.download_button("📥 Descargar Informe", pdf, f"Informe_{equipo}.pdf", "application/pdf", use_container_width=True)

import io
from datetime import datetime
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from PIL import Image, ImageOps

# --- LÓGICA DE INTELIGENCIA TÉCNICA ---
def generar_resumen_tecnico(disciplina, riesgo, hallazgos):
    # Diccionario de recomendaciones según disciplina
    recomendaciones = {
        "Eléctrica": "Asegurar integridad de tableros, reapriete de conexiones y validación de termografía.",
        "Mecánica": "Verificar niveles de lubricación, alineación de componentes y estado de fijaciones.",
        "Instrumentación": "Calibrar lazos de control, limpiar sensores y verificar comunicación con DCS/PLC."
    }
    
    prioridad = "INMEDIATA" if riesgo == "Alto" else "PROGRAMADA" if riesgo == "Medio" else "RUTINARIA"
    base = recomendaciones.get(disciplina, "Seguir pautas de mantenimiento preventivo.")
    
    texto = (f"Tras la inspección de especialidad {disciplina.upper()}, se determina un nivel de riesgo {riesgo.upper()}. "
             f"Se requiere intervención de carácter {prioridad}. "
             f"Acción recomendada: {base}")
    
    if hallazgos:
        texto += f" Se debe prestar especial atención a: {', '.join(hallazgos)}."
        
    return texto

# --- GENERADOR DE PDF ---
def build_pdf(data, fotos, firma):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    
    # Estilos Personalizados
    estilo_t = ParagraphStyle("T", fontSize=16, alignment=1, spaceAfter=12, fontName="Helvetica-Bold")
    estilo_h = ParagraphStyle("H", fontSize=11, fontName="Helvetica-Bold", textColor=colors.navy, spaceBefore=10)
    estilo_b = ParagraphStyle("B", fontSize=10, leading=12)

    story = [Paragraph("INFORME TÉCNICO DE INSPECCIÓN", estilo_t)]

    # Tabla de Datos (Estilizada)
    tbl_data = [
        ["FECHA:", data['fecha'], "RIESGO:", data['riesgo']],
        ["DISCIPLINA:", data['disciplina'], "OT:", data['ot']],
        ["EQUIPO:", data['equipo'], "UBICACIÓN:", data['ubicacion']],
        ["INSPECTOR:", data['inspector'], "CARGO:", data['cargo']]
    ]
    t = Table(tbl_data, colWidths=[25*mm, 65*mm, 25*mm, 65*mm])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke),
        ('BACKGROUND', (2,0), (2,-1), colors.whitesmoke),
    ]))
    story.append(t)

    # Cuerpo del Informe
    story.append(Paragraph("OBSERVACIONES DE TERRENO", estilo_h))
    story.append(Paragraph(data['obs'] or "Sin observaciones adicionales.", estilo_b))
    
    story.append(Paragraph("RESUMEN TÉCNICO Y CONCLUSIÓN (SISTEMA)", estilo_h))
    story.append(Paragraph(data['resumen'], estilo_b))

    # Imágenes (Tamaño Ajustado a 12cm de ancho)
    if fotos:
        story.append(Paragraph("EVIDENCIA FOTOGRÁFICA", estilo_h))
        for f_name, f_bytes in fotos:
            img = RLImage(io.BytesIO(f_bytes), width=120*mm, height=70*mm)
            img.hAlign = 'CENTER'
            story.append(Spacer(1, 5*mm))
            story.append(img)

    # Firma
    if firma:
        story.append(Spacer(1, 10*mm))
        story.append(Paragraph("FIRMA DEL RESPONSABLE:", estilo_h))
        sig = RLImage(io.BytesIO(firma[1]), width=60*mm, height=30*mm)
        sig.hAlign = 'LEFT'
        story.append(sig)

    doc.build(story)
    return buffer.getvalue()

# --- INTERFAZ STREAMLIT ---
st.title("jcamp029.pro")

# Botón de Limpieza
if st.button("🧹 Limpiar Formulario"):
    st.cache_data.clear()
    st.rerun()

with st.container(border=True):
    col1, col2 = st.columns(2)
    with col1:
        fecha = st.text_input("Fecha", datetime.now().strftime("%d-%m-%Y"))
        disciplina = st.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Instrumentación"])
        equipo = st.text_input("Equipo")
    with col2:
        riesgo = st.selectbox("Nivel de Riesgo", ["Bajo", "Medio", "Alto"])
        ubicacion = st.text_input("Ubicación") # Solo Ubicación, sin 'Nodo'
        ot = st.text_input("N° OT")

    inspector = st.text_input("Inspector", "JORGE CAMPOS AGUIRRE")
    cargo = st.text_input("Cargo", "Especialista Eléctrico")
    
    hallazgos = st.multiselect("Hallazgos Específicos", ["Desgaste", "Fuga", "Falta Rotulación", "Conexión Suelta", "Corrosión"])
    obs = st.text_area("Observaciones Técnicas (Opcional)")

# ✅ CONCLUSIÓN GENERADA POR LA APP
resumen_final = generar_resumen_tecnico(disciplina, riesgo, hallazgos)
st.subheader("🤖 Conclusión del Sistema")
st.info(resumen_final)

# Archivos
c_img, c_sig = st.columns(2)
up_fotos = c_img.file_uploader("Fotos de Evidencia (Máx 2)", type=["jpg", "png"], accept_multiple_

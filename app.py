import io
from datetime import datetime
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from PIL import Image, ImageOps
from zoneinfo import ZoneInfo

# Configuración Base
st.set_page_config(page_title="jcamp029.pro", layout="centered")
TZ_CL = ZoneInfo("America/Santiago")

# ✅ MEDIDAS PARA CONTROL TOTAL
ANCHO_PAGINA = 180 * mm
ALTO_FOTO = 85 * mm
ANCHO_FIRMA = 70 * mm

def procesar_img(file_bytes, is_firma=False):
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    img = ImageOps.exif_transpose(img)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf

# ✅ LA APP GENERA LA CONCLUSIÓN (No el inspector)
def generar_conclusion_automatica(disciplina, riesgo, hallazgos):
    prioridad = "INMEDIATA" if riesgo == "Alto" else "PROGRAMADA" if riesgo == "Medio" else "RUTINARIA"
    texto_hallazgos = f" con hallazgos en: {', '.join(hallazgos)}" if hallazgos else " sin hallazgos críticos detectados"
    
    return (f"Inspección de especialidad {disciplina} finalizada con nivel de riesgo {riesgo.upper()}. "
            f"Se requiere intervención de carácter {prioridad}{texto_hallazgos}. "
            f"Se recomienda normalizar desviaciones y registrar cierre en sistema SAP/OT.")

def build_pdf(data, fotos, firma):
    buffer = io.BytesIO()
    # Márgenes optimizados para una sola hoja
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=12*mm, bottomMargin=12*mm, leftMargin=15*mm, rightMargin=15*mm)
    styles = getSampleStyleSheet()
    
    # Estilos
    style_title = ParagraphStyle("T", fontSize=18, alignment=1, spaceAfter=15, fontName="Helvetica-Bold")
    style_h = ParagraphStyle("H", fontSize=11, fontName="Helvetica-Bold", textColor=colors.navy, spaceBefore=6)
    style_b = ParagraphStyle("B", fontSize=10, leading=12)

    story = [Paragraph("INFORME TÉCNICO DE INSPECCIÓN", style_title)]

    # Tabla de Datos
    info = [
        ["FECHA:", data['fecha'], "RIESGO:", data['riesgo']],
        ["DISCIPLINA:", data['disciplina'], "OT:", data['ot']],
        ["EQUIPO:", data['equipo'], "UBICACIÓN:", data['ubicacion']],
        ["INSPECTOR:", data['inspector'], "CARGO:", data['cargo']]
    ]
    t = Table(info, colWidths=[30*mm, 60*mm, 30*mm, 60*mm])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke),
        ('BACKGROUND', (2,0), (2,-1), colors.whitesmoke),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t)

    # Contenido Generado
    story.append(Paragraph("OBSERVACIONES TÉCNICAS", style_h))
    story.append(Paragraph(data['obs'] or "Operación normal según inspección visual.", style_b))
    
    story.append(Paragraph("CONCLUSIÓN TÉCNICA (SISTEMA)", style_h))
    story.append(Paragraph(data['concl'], style_b))

    # ✅ IMÁGENES GRANDES
    if fotos:
        story.append(Paragraph("EVIDENCIA FOTOGRÁFICA", style_h))
        for f in fotos[:3]:
            img_buf = procesar_img(f[1])
            img_obj = RLImage(img_buf, width=ANCHO_PAGINA, height=ALTO_FOTO)
            img_obj.hAlign = 'CENTER'
            story.append(Spacer(1, 3*mm))
            story.append(img_obj)

    # ✅ FIRMA
    if firma:
        story.append(Spacer(1, 8*mm))
        story.append(Paragraph("FIRMA RESPONSABLE:", style_h))
        f_buf = procesar_img(firma[1])
        f_obj = RLImage(f_buf, width=ANCHO_FIRMA, height=35*mm)
        f_obj.hAlign = 'LEFT'
        story.append(f_obj)

    doc.build(story)
    return buffer.getvalue()

# --- INTERFAZ STREAMLIT ---
st.title("jcamp029.pro")

with st.expander("📝 DATOS DE LA INSPECCIÓN", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        fecha = st.text_input("Fecha", datetime.now(TZ_CL).strftime("%d-%m-%Y"))
        disciplina = st.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Instrumentación"])
        equipo = st.text_input("Equipo / Sala")
    with c2:
        riesgo = st.selectbox("Nivel de Riesgo", ["Bajo", "Medio", "Alto"])
        ubicacion = st.text_input("Ubicación / Nodo")
        ot = st.text_input("N° OT / Registro")
    
    inspector = st.text_input("Inspector", "JORGE CAMPOS AGUIRRE")
    cargo = st.text_input("Cargo", "Especialista Eléctrico")
    
    hallazgos = st.multiselect("Hallazgos detectados", ["Condición insegura", "Orden y Limpieza", "Falta rotulación", "Estructura dañada", "LOTO"])
    obs = st.text_area("Observaciones de campo")

# Generación Automática de Conclusión
concl_auto = generar_conclusion_automatica(disciplina, riesgo, hallazgos)
st.info(f"**Conclusión sugerida por la App:**\n\n{concl_auto}")

# Archivos
col_f, col_s = st.columns(2)
up_fotos = col_f.file_uploader("Fotos (Máx 3)", type=["jpg", "png"], accept_multiple_files=True)
up_firma = col_s.file_uploader("Tu Firma", type=["jpg", "png"])

if st.button("GENERAR PDF PROFESIONAL ✅", use_container_width=True):
    if not up_firma:
        st.error("Por favor, carga la firma para continuar.")
    else:
        lista_fotos = [(f.name, f.read()) for f in up_fotos] if up_fotos else []
        data_pdf = {
            'fecha': fecha, 'disciplina': disciplina, 'equipo': equipo,
            'riesgo': riesgo, 'ubicacion': ubicacion, 'ot': ot,
            'inspector': inspector, 'cargo': cargo, 'obs': obs,
            'concl': concl_auto
        }
        
        pdf_bytes = build_pdf(data_pdf, lista_fotos, (up_firma.name, up_firma.read()))
        st.download_button("📥 Descargar Informe", pdf_bytes, f"Informe_{equipo}.pdf", "application/pdf", use_container_width=True)

import io
from datetime import datetime
import streamlit as st
from zoneinfo import ZoneInfo
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
from reportlab.pdfgen import canvas
from PIL import Image, ImageOps
from xml.sax.saxutils import escape

# -----------------------------
# Configuración e Interfaz
# -----------------------------
st.set_page_config(page_title="jcamp029.pro", page_icon="🧾", layout="centered")
TZ_CL = ZoneInfo("America/Santiago")

# Sidebar para control de Licencia (Simulado)
st.sidebar.title("🔐 Licencia")
is_pro = st.sidebar.toggle("Activar Modo PRO (Comprado)", value=False)
if is_pro:
    st.sidebar.success("Modo Profesional Activo")
    user_logo = st.sidebar.file_uploader("Subir tu Logo (Empresa)", type=["jpg", "png", "jpeg"])
else:
    st.sidebar.warning("Versión Gratuita (Con Marca de Agua)")
    user_logo = None

# -----------------------------
# Lógica del PDF con Marca de Agua y Logo
# -----------------------------
def process_image(uploaded_file, target_w_mm, target_h_mm):
    img = Image.open(uploaded_file)
    img = ImageOps.exif_transpose(img)
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG', quality=85)
    return RLImage(img_byte_arr, width=target_w_mm*mm, height=target_h_mm*mm)

def header_footer(canvas, doc, is_pro, logo_file):
    canvas.saveState()
    # Marca de agua para usuarios NO PRO
    if not is_pro:
        canvas.setFont('Helvetica-Bold', 40)
        canvas.setStrokeColor(colors.lightgrey)
        canvas.setFillColor(colors.lightgrey, alpha=0.3)
        canvas.drawCentredString(105*mm, 148*mm, "GENERADO POR JCAMP029.PRO")
    
    # Logo para usuarios PRO
    if is_pro and logo_file:
        img = Image.open(logo_file)
        # Dibujar logo en la esquina superior derecha
        canvas.drawImage(logo_file.name, 160*mm, 265*mm, width=30*mm, height=20*mm, preserveAspectRatio=True, mask='auto')
    canvas.restoreState()

def generate_pdf(data, photos, signature, is_pro, logo_file):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, margin=(15*mm, 15*mm, 15*mm, 15*mm))
    styles = getSampleStyleSheet()
    
    style_title = ParagraphStyle(name='HTitle', fontSize=18, fontName='Helvetica-Bold', alignment=0, spaceAfter=12)
    style_label = ParagraphStyle(name='Label', fontSize=8, fontName='Helvetica-Bold', textColor=colors.grey)
    style_val = ParagraphStyle(name='Val', fontSize=10, fontName='Helvetica')
    
    elements = []
    
    # Título
    elements.append(Paragraph("Informe Técnico de Inspección", style_title))
    elements.append(Spacer(1, 5*mm))
    
    # Tabla de Datos
    table_data = [
        [Paragraph("FECHA", style_label), Paragraph("DISCIPLINA", style_label), Paragraph("RIESGO", style_label)],
        [data.get("fecha"), data.get("disciplina"), data.get("riesgo")],
        [Paragraph("EQUIPO", style_label), Paragraph("UBICACIÓN", style_label), Paragraph("OT", style_label)],
        [data.get("equipo") or "—", data.get("ubicacion") or "—", data.get("ot") or "—"]
    ]
    t = Table(table_data, colWidths=[60*mm]*3)
    t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey), ('VALIGN',(0,0),(-1,-1),'TOP')]))
    elements.append(t)
    elements.append(Spacer(1, 10*mm))
    
    # Hallazgos
    elements.append(Paragraph("OBSERVACIONES TÉCNICAS", style_label))
    elements.append(Paragraph(escape(data.get("obs") or "Sin registrar."), style_val))
    elements.append(Spacer(1, 10*mm))

    # Fotos
    if photos:
        elements.append(Paragraph("REGISTRO FOTOGRÁFICO", style_label))
        photo_objs = [process_image(p, 86, 65) for p in photos]
        rows = [photo_objs[i:i+2] for i in range(0, len(photo_objs), 2)]
        pt = Table(rows, colWidths=[90*mm, 90*mm])
        elements.append(pt)

    # Firma
    if signature:
        elements.append(Spacer(1, 15*mm))
        sign_img = process_image(signature, 45, 30)
        stb = Table([[sign_img], [Paragraph(f"<b>{data.get('inspector')}</b>", style_val)]], colWidths=[180*mm])
        stb.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        elements.append(KeepTogether(stb))

    # Build con Header (Logo y Marca de Agua)
    doc.build(elements, onFirstPage=lambda c, d: header_footer(c, d, is_pro, logo_file))
    return buffer.getvalue()

# -----------------------------
# UI Principal
# -----------------------------
st.title("jcamp029.pro")

with st.expander("📝 Datos del Informe", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        disciplina = st.text_input("Disciplina", "Eléctrica")
        equipo = st.text_input("Equipo / Sistema")
        riesgo = st.selectbox("Nivel de Riesgo", ["Bajo", "Medio", "Alto", "Crítico"])
    with col2:
        ubicacion = st.text_input("Ubicación")
        ot = st.text_input("Orden de Trabajo (OT)")
        fecha = st.text_input("Fecha", datetime.now(TZ_CL).strftime("%d-%m-%Y"))

    obs = st.text_area("Descripción de Hallazgos")
    inspector = st.text_input("Nombre del Inspector", "JORGE CAMPOS AGUIRRE")

col_p, col_s = st.columns(2)
with col_p:
    u_photos = st.file_uploader("Fotos de Evidencia", type=["jpg","jpeg","png"], accept_multiple_files=True)
with col_s:
    u_sign = st.file_uploader("Firma Digital", type=["png","jpg"])

if st.button("🚀 Generar y Descargar Informe"):
    data = {"disciplina": disciplina, "equipo": equipo, "riesgo": riesgo, "ubicacion": ubicacion, "ot": ot, "fecha": fecha, "obs": obs, "inspector": inspector}
    pdf_bytes = generate_pdf(data, u_photos, u_sign, is_pro, user_logo)
    
    st.download_button(
        label="📥 Descargar PDF",
        data=pdf_bytes,
        file_name=f"Informe_{ot or 'inspeccion'}.pdf",
        mime="application/pdf"
    )

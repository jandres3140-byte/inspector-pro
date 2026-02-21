import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io
from datetime import datetime

# --- CONFIGURACIÓN Y ESTILOS ---
FIELD_KEYS = {
    "titulo": "tit_inf",
    "disciplina": "disc_inf",
    "riesgo": "ries_inf",
    "hallazgos": "hal_inf",
    "observaciones_raw": "obs_raw",
    "conclusion": "concl_fin",
    "auto_conclusion": "auto_concl_check"
}

def init_state():
    """Inicializa el estado para evitar KeyErrors vistos en las capturas """
    if "initialized" not in st.session_state:
        st.session_state.initialized = True
        defaults = {
            FIELD_KEYS["titulo"]: "Informe Técnico de Inspección",
            FIELD_KEYS["disciplina"]: "Eléctrica",
            FIELD_KEYS["riesgo"]: "Bajo",
            FIELD_KEYS["auto_conclusion"]: True,
            "obs_fixed": None
        }
        for k, v in defaults.items():
            if k not in st.session_state:
                st.session_state[k] = v

# --- LÓGICA DEL GENERADOR DE CONCLUSIONES PRO ---
def generate_conclusion_pro(disciplina, riesgo, hallazgos, observaciones):
    """
    Generador mejorado que analiza el contexto técnico.
    Resuelve la falta del generador automático mencionada.
    """
    prioridad = "ROTATIVA/RUTINARIA" if riesgo == "Bajo" else "PROGRAMADA" if riesgo == "Medio" else "INMEDIATA"
    
    # Base de la conclusión
    conclusion = f"Inspección de especialidad {disciplina} finalizada con nivel de riesgo {riesgo.upper()}. "
    conclusion += f"Se establece una prioridad de atención {prioridad}. \n"

    # Análisis de hallazgos (basado en la lógica de 'image_40d4dd.png') [cite: 1]
    if not hallazgos:
        conclusion += "- Sin hallazgos críticos detectados mediante inspección visual directa. "
    else:
        hallazgos_str = ", ".join(hallazgos)
        conclusion += f"- Hallazgos detectados: {hallazgos_str}. Requieren normalización según estándar. "

    # Análisis de palabras clave en observaciones
    obs_lower = observaciones.lower()
    if "polvo" in obs_lower or "sucio" in obs_lower:
        conclusion += "\n- Foco técnico: Limpieza y condiciones ambientales (control de agentes contaminantes)."
    if "tablero" in obs_lower or "abierto" in obs_lower:
        conclusion += "\n- Acción recomendada: Asegurar integridad de envolventes y reapriete de conexiones."
    
    return conclusion

# --- CONSTRUCTOR DE PDF PROFESIONAL ---
def build_pdf(datos, fotos=None, firma=None):
    """
    Versión corregida del constructor para evitar el AttributeError 
    visto en 'image_422d9e.png' 
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    
    # Estilo personalizado para evitar errores de diccionario
    style_h2 = ParagraphStyle('h2_custom', parent=styles['Heading2'], fontSize=12, textColor=colors.navy, spaceBefore=10)
    style_body = styles["BodyText"]

    story = []

    # Encabezado (Tabla de datos)
    tabla_data = [
        [Paragraph(f"<b>FECHA:</b> {datos.get('fecha', 'N/A')}", style_body), Paragraph(f"<b>RIESGO:</b> {datos.get('riesgo', 'N/A')}", style_body)],
        [Paragraph(f"<b>DISCIPLINA:</b> {datos.get('disciplina', 'N/A')}", style_body), Paragraph(f"<b>OT:</b> {datos.get('ot', 'N/A')}", style_body)],
        [Paragraph(f"<b>EQUIPO:</b> {datos.get('equipo', 'N/A')}", style_body), Paragraph(f"<b>UBICACIÓN:</b> {datos.get('ubicacion', 'N/A')}", style_body)]
    ]
    t = Table(tabla_data, colWidths=[250, 250])
    t.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 1, colors.black), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
    story.append(t)
    story.append(Spacer(1, 15))

    # Secciones de Texto
    story.append(Paragraph("OBSERVACIONES TÉCNICAS", style_h2))
    story.append(Paragraph(datos.get('obs', 'Sin observaciones.'), style_body))
    
    story.append(Paragraph("CONCLUSIÓN TÉCNICA (SISTEMA)", style_h2))
    story.append(Paragraph(datos.get('concl', 'Sin conclusión.'), style_body))

    # Imágenes y Firma con manejo de escala (Mejora visual para image_42351a.png) 
    if fotos:
        story.append(Paragraph("EVIDENCIA FOTOGRÁFICA", style_h2))
        # Lógica de escalado para evitar saltos de página innecesarios
        for foto in fotos[:3]:
            img = Image(foto, width=400, height=200, kind='proportional')
            story.append(img)
            story.append(Spacer(1, 10))

    if firma:
        story.append(Spacer(1, 20))
        story.append(Paragraph("FIRMA RESPONSABLE:", style_h2))
        img_firma = Image(firma, width=150, height=80)
        story.append(img_firma)

    doc.build(story)
    buffer.seek(0)
    return buffer

# --- INTERFAZ DE USUARIO (STREAMLIT) ---
def main():
    st.set_page_config(page_title="Inspector Pro", layout="wide")
    init_state()

    st.title("Generador Profesional de Informes (PDF)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fecha = st.date_input("Fecha", datetime.now())
        equipo = st.text_input("Equipo / Área", placeholder="Ej: Sala 31000")
        riesgo = st.selectbox("Nivel de Riesgo", ["Bajo", "Medio", "Alto"])
        hallazgos = st.multiselect("Hallazgos comunes", ["Polvo conductor", "Conexiones sueltas", "Falta rotulación", "Estructura dañada"])

    with col2:
        disciplina = st.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Instrumentación"])
        ot = st.text_input("N° Registro / OT")
        ubicacion = st.text_input("Ubicación / Nodo")

    obs = st.text_area("Observaciones técnicas", height=100, key=FIELD_KEYS["observaciones_raw"])

    # Lógica del Generador Automático (Lo que solicitaste mejorar)
    st.checkbox("Auto-actualizar conclusión", key=FIELD_KEYS["auto_conclusion"])
    
    if st.session_state[FIELD_KEYS["auto_conclusion"]]:
        auto_concl = generate_conclusion_pro(disciplina, riesgo, hallazgos, obs)
        st.session_state[FIELD_KEYS["conclusion"]] = auto_concl

    concl_final = st.text_area("Conclusión (Editable)", value=st.session_state.get(FIELD_KEYS["conclusion"], ""), height=150)

    # Subida de archivos
    foto_file = st.file_uploader("Subir Imagen (Máx 1)", type=["png", "jpg", "jpeg"])
    firma_file = st.file_uploader("Subir Firma", type=["png", "jpg"])

    if st.button("GENERAR PDF PROFESIONAL"):
        try:
            datos_pdf = {
                "fecha": str(fecha),
                "riesgo": riesgo,
                "disciplina": disciplina,
                "ot": ot,
                "equipo": equipo,
                "ubicacion": ubicacion,
                "obs": obs,
                "concl": concl_final
            }
            
            pdf_result = build_pdf(datos_pdf, 
                                   fotos=[foto_file] if foto_file else None, 
                                   firma=firma_file)
            
            st.download_button("Descargar Informe", pdf_result, file_name=f"Informe_{equipo}.pdf", mime="application/pdf")
            st.success("PDF generado exitosamente.")
        except Exception as e:
            st.error(f"Error al generar PDF: {str(e)}")

if __name__ == "__main__":
    main()

import io
import re
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
    PageBreak,
)
from reportlab.pdfgen import canvas

from PIL import Image
from xml.sax.saxutils import escape


# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="jcamp029.pro", page_icon="🧾", layout="centered")

APP_TITLE = "jcamp029.pro"
APP_SUBTITLE = "Generador profesional de informes de inspección técnica (PDF)."


# -----------------------------
# Helpers UI / CSS
# -----------------------------
def apply_theme_css(theme: str) -> None:
    """
    Fix label visibility and overall style for light/dark.
    Streamlit's widgets sometimes hide label color on dark backgrounds.
    """
    if theme == "Oscuro":
        bg = "#0b1220"
        fg = "#f8fafc"
        muted = "#cbd5e1"
        card = "#0f172a"
        border = "#1e293b"
        input_bg = "#0b1220"
    else:
        bg = "#ffffff"
        fg = "#0f172a"
        muted = "#334155"
        card = "#ffffff"
        border = "#e2e8f0"
        input_bg = "#ffffff"

    st.markdown(
        f"""
        <style>
        .stApp {{
            background: {bg};
            color: {fg};
        }}
        h1, h2, h3, h4, h5, h6, p, div, span, label {{
            color: {fg} !important;
        }}

        /* Make widget labels visible */
        div[data-testid="stWidgetLabel"] > label {{
            color: {fg} !important;
            font-weight: 600 !important;
        }}

        /* Inputs background / border */
        input, textarea {{
            background: {input_bg} !important;
            color: {fg} !important;
            border: 1px solid {border} !important;
        }}

        /* Selectbox */
        div[data-baseweb="select"] > div {{
            background: {input_bg} !important;
            color: {fg} !important;
            border: 1px solid {border} !important;
        }}

        /* Card feel */
        .block-container {{
            padding-top: 28px;
        }}
        .app-card {{
            border: 1px solid {border};
            background: {card};
            border-radius: 14px;
            padding: 16px 16px 10px 16px;
            margin-bottom: 16px;
        }}
        .muted {{
            color: {muted} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def normalize_spaces(text: str) -> str:
    text = text or ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def text_to_paragraph_html(text: str) -> str:
    """
    ReportLab Paragraph understands a small HTML subset.
    We escape special chars and convert newlines into <br/>.
    """
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = escape(t)
    t = t.replace("\n", "<br/>")
    return t.strip() if t.strip() else "—"


def basic_spanish_fixes(text: str) -> Tuple[str, List[str]]:
    """
    Corrección básica (no perfecta):
    - Espacios dobles
    - Mayúscula al inicio de oración (simple)
    - Algunas palabras comunes mal escritas (diccionario mínimo)
    Retorna: texto_corregido, lista_de_cambios
    """
    changes = []
    original = text or ""
    t = normalize_spaces(original)

    replacements = {
        "demasciado": "demasiado",
        "ubucacion": "ubicación",
        "ubicacion": "ubicación",
        "observacion": "observación",
        "conclucion": "conclusión",
        "electrico": "eléctrico",
        "mecanico": "mecánico",
        "tableros electricos": "tableros eléctricos",
        "inspeccion": "inspección",
    }

    for wrong, right in replacements.items():
        pattern = re.compile(rf"\b{re.escape(wrong)}\b", re.IGNORECASE)
        if pattern.search(t):
            t2 = pattern.sub(right, t)
            if t2 != t:
                changes.append(f"'{wrong}' → '{right}'")
                t = t2

    if t and t[0].islower():
        t = t[0].upper() + t[1:]
        changes.append("Capitalización: primera letra en mayúscula")

    return t, changes


def generate_conclusion(
    disciplina: str,
    nivel_riesgo: str,
    hallazgos: List[str],
    observaciones: str,
) -> str:
    """
    Conclusión técnica genérica y útil, ajustada por disciplina/riesgo/hallazgos.
    Devuelve texto con saltos de línea (para render tipo lista en PDF).
    """
    obs = normalize_spaces(observaciones)
    hall = ", ".join(hallazgos) if hallazgos else "sin hallazgos críticos declarados"

    if nivel_riesgo == "Bajo":
        riesgo_text = (
            "Condición general aceptable. No se identifican riesgos inmediatos que impidan la continuidad operativa."
        )
        accion = "Se recomienda mantener monitoreo rutinario y registrar control en próxima ronda."
        plazo = "Plazo sugerido: próximo ciclo de inspección."
    elif nivel_riesgo == "Medio":
        riesgo_text = (
            "Se identifican desviaciones que requieren corrección planificada para evitar deterioro de condición y exposición a incidentes."
        )
        accion = "Se recomienda generar OT y ejecutar medidas correctivas/ajustes con prioridad media."
        plazo = "Plazo sugerido: 7–14 días o según criticidad del área."
    else:
        riesgo_text = (
            "Se identifican condiciones de riesgo alto que pueden derivar en incidente o falla. Requiere acción prioritaria."
        )
        accion = (
            "Se recomienda aislar/asegurar el área/equipo si corresponde, informar a supervisión y ejecutar corrección inmediata."
        )
        plazo = "Plazo sugerido: inmediato / dentro de 24 horas."

    if disciplina == "Eléctrica":
        foco = (
            "Verificar integridad de protecciones, estado de tableros/cajas, señalización y control de energías (bloqueo/etiquetado), "
            "orden y limpieza, cierre de puertas/tapas, y cumplimiento de resguardos."
        )
        medidas = (
            "Acciones típicas: cierre y aseguramiento de tableros, reposición de tapas, torque/ajuste, ordenamiento de cables, "
            "revisión de protecciones, pruebas funcionales según procedimiento."
        )
    elif disciplina == "Mecánica":
        foco = (
            "Verificar resguardos mecánicos, condición de transmisiones, fijaciones, holguras, lubricación, vibración/ruidos anómalos, "
            "fugas, y condiciones de seguridad en partes móviles."
        )
        medidas = (
            "Acciones típicas: ajuste de fijaciones, reposición de resguardos, corrección de fugas, lubricación, alineación básica, "
            "verificación de puntos críticos y prueba operativa controlada."
        )
    else:
        foco = (
            "Verificar condiciones de seguridad, integridad de componentes, orden y limpieza, señalización, y desviaciones respecto al estándar."
        )
        medidas = "Acciones típicas: asegurar condición segura, corregir desviaciones, registrar evidencias y coordinar mantenimiento."

    conclusion = (
        f"Conclusión técnica ({disciplina}):\n"
        f"- {riesgo_text}\n"
        f"- Hallazgos declarados: {hall}.\n"
        f"- En base a la inspección: {foco}\n"
        f"- {accion}\n"
        f"- {plazo}\n"
        f"- Referencia de observaciones: {obs if obs else 'No se ingresaron observaciones.'}\n"
        f"- {medidas}\n"
    )
    return conclusion


# -----------------------------
# PDF helpers
# -----------------------------
def pil_to_rl_image(file_bytes: bytes, max_w_mm: float = 170, max_h_mm: float = 100) -> RLImage:
    """
    Convert uploaded image bytes to ReportLab Image, preserving aspect ratio and fitting.
    """
    img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    w_px, h_px = img.size

    max_w = max_w_mm * mm
    max_h = max_h_mm * mm

    aspect = w_px / h_px
    if (max_w / max_h) > aspect:
        h = max_h
        w = h * aspect
    else:
        w = max_w
        h = w / aspect

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)

    return RLImage(buf, width=w, height=h)


def build_pdf(
    titulo: str,
    fecha: str,
    equipo: str,
    ubicacion: str,
    inspector: str,
    cargo: str,
    registro_ot: str,
    disciplina: str,
    nivel_riesgo: str,
    observaciones: str,
    conclusion: str,
    fotos: List[Tuple[str, bytes]],
    firma_img: Optional[Tuple[str, bytes]],
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=titulo,
        author=inspector,
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "h1_custom",
        parent=styles["Heading1"],
        fontSize=16,
        leading=18,
        spaceAfter=10,
    )
    h2 = ParagraphStyle(
        "h2_custom",
        parent=styles["Heading2"],
        fontSize=12,
        leading=14,
        spaceBefore=10,
        spaceAfter=6,
    )
    body = ParagraphStyle(
        "body_custom",
        parent=styles["BodyText"],
        fontSize=10,
        leading=13,
    )
    muted = ParagraphStyle(
        "muted_custom",
        parent=styles["BodyText"],
        fontSize=9,
        leading=12,
        textColor=colors.grey,
    )

    def header_footer(c: canvas.Canvas, d):
        c.saveState()
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.grey)
        c.drawString(
            18 * mm,
            10 * mm,
            f"{APP_TITLE} · Informe generado {datetime.now().strftime('%d-%m-%Y %H:%M')}",
        )
        c.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Página {c.getPageNumber()}")
        c.restoreState()

    story = []

    story.append(Paragraph("INFORME TÉCNICO DE INSPECCIÓN", h1))
    story.append(Paragraph("Documento generado desde aplicación de inspección (PDF).", muted))
    story.append(Spacer(1, 6))

    data = [
        ["Fecha", fecha],
        ["Título", titulo],
        ["Disciplina", disciplina],
        ["Nivel de riesgo", nivel_riesgo],
        ["Equipo / Área", equipo],
        ["Ubicación", ubicacion],
        ["Inspector", inspector],
        ["Cargo", cargo],
        ["N° Registro / OT", registro_ot],
    ]
    t = Table(data, colWidths=[40 * mm, 130 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Observaciones técnicas", h2))
    story.append(Paragraph(text_to_paragraph_html(observaciones), body))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Conclusión técnica", h2))
    story.append(Paragraph(text_to_paragraph_html(conclusion), body))
    story.append(Spacer(1, 10))

    if firma_img:
        story.append(Paragraph("Firma", h2))
        try:
            story.append(pil_to_rl_image(firma_img[1], max_w_mm=70, max_h_mm=25))
            story.append(Spacer(1, 6))
            story.append(Paragraph(f"<b>{escape(inspector)}</b> · {escape(cargo)}", body))
        except Exception:
            story.append(Paragraph("No fue posible procesar la imagen de firma.", muted))
        story.append(Spacer(1, 10))

    if fotos:
        story.append(PageBreak())
        story.append(Paragraph("Evidencias fotográficas", h2))
        story.append(Paragraph("Se adjuntan imágenes asociadas a la inspección.", muted))
        story.append(Spacer(1, 10))

        for idx, (fname, fbytes) in enumerate(fotos, start=1):
            story.append(Paragraph(f"Foto {idx}: {escape(fname)}", body))
            try:
                story.append(pil_to_rl_image(fbytes))
            except Exception:
                story.append(Paragraph("No fue posible procesar esta imagen.", muted))
            story.append(Spacer(1, 10))

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# -----------------------------
# UI
# -----------------------------
st.markdown(f"<h1 style='margin-bottom:4px'>{APP_TITLE}</h1>", unsafe_allow_html=True)
st.markdown(f"<p class='muted' style='margin-top:0'>{APP_SUBTITLE}</p>", unsafe_allow_html=True)

colA, colB = st.columns([1, 1])
with colA:
    theme = st.radio("Tema", ["Claro", "Oscuro"], index=1, horizontal=True)
apply_theme_css(theme)

# Estado inicial de Observaciones
if "observaciones_raw" not in st.session_state:
    st.session_state["observaciones_raw"] = "Se observa la sala con tableros eléctricos abiertos, los demás equipos funcionando ok."

st.markdown("<div class='app-card'>", unsafe_allow_html=True)

today_str = datetime.now().strftime("%d-%m-%Y")
fecha = st.text_input("Fecha", value=today_str)

titulo = st.text_input("Título del informe", value="Informe Técnico de Inspección")
disciplina = st.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Otra"])

equipo = st.text_input("Equipo / Área inspeccionada", value="sala 31000")
ubicacion = st.text_input("Ubicación", value="nodo 3500")
inspector = st.text_input("Inspector", value="jorge campos A.")
cargo = st.text_input("Cargo", value="Especialista eléctrico")
registro_ot = st.text_input("N° Registro / OT", value="33332222")

nivel_riesgo = st.selectbox("Nivel de riesgo", ["Bajo", "Medio", "Alto"], index=1)

hallazgos = st.multiselect(
    "Hallazgos (marca lo que aplique)",
    [
        "Condición insegura",
        "Resguardos / protecciones",
        "Orden y limpieza",
        "Energías peligrosas (LOTO)",
        "Tableros / cajas / tapas",
        "Señalización / demarcación",
        "Fugas / derrames",
        "Vibración / ruidos anómalos",
        "Temperatura / olor anómalo",
        "Instrumentación / control",
        "Otro",
    ],
)

observaciones_raw = st.text_area(
    "Observaciones técnicas",
    key="observaciones_raw",
    height=120,
)

st.markdown("<hr/>", unsafe_allow_html=True)
st.markdown(
    "<p class='muted'><b>Corrección básica:</b> sugiere cambios simples (tú decides aplicar).</p>",
    unsafe_allow_html=True,
)

fix_btn = st.button("Sugerir correcciones en Observaciones")
if fix_btn:
    fixed, changes = basic_spanish_fixes(st.session_state["observaciones_raw"])
    st.session_state["obs_fixed"] = fixed
    st.session_state["obs_changes"] = changes

if "obs_fixed" in st.session_state:
    st.text_area("Observaciones (sugerido)", value=st.session_state["obs_fixed"], height=120, key="obs_fixed_preview")
    if st.session_state.get("obs_changes"):
        st.write("Cambios sugeridos:")
        for c in st.session_state["obs_changes"]:
            st.write(f"- {c}")

    apply_fix = st.button("Aplicar sugerencias a Observaciones")
    if apply_fix:
        st.session_state["observaciones_raw"] = st.session_state.get("obs_fixed_preview", st.session_state["observaciones_raw"])

st.markdown("<hr/>", unsafe_allow_html=True)
auto_conc = generate_conclusion(disciplina, nivel_riesgo, hallazgos, st.session_state["observaciones_raw"])
conclusion = st.text_area("Conclusión técnica (editable)", value=auto_conc, height=180)

st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='app-card'>", unsafe_allow_html=True)
st.subheader("Evidencias y firma")

fotos_files = st.file_uploader(
    "Subir imágenes de evidencia (JPG/PNG) — puedes cargar varias",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
)

firma_file = st.file_uploader(
    "Firma (imagen JPG/PNG) — opcional",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=False,
)

st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='app-card'>", unsafe_allow_html=True)
st.subheader("Generación de PDF")

gen = st.button("Generar PDF Profesional ✅")
if gen:
    fotos: List[Tuple[str, bytes]] = []
    if fotos_files:
        for f in fotos_files:
            fotos.append((f.name, f.read()))

    firma_img: Optional[Tuple[str, bytes]] = None
    if firma_file:
        firma_img = (firma_file.name, firma_file.read())

    pdf_bytes = build_pdf(
        titulo=titulo,
        fecha=fecha,
        equipo=equipo,
        ubicacion=ubicacion,
        inspector=inspector,
        cargo=cargo,
        registro_ot=registro_ot,
        disciplina=disciplina,
        nivel_riesgo=nivel_riesgo,
        observaciones=st.session_state["observaciones_raw"],
        conclusion=conclusion,
        fotos=fotos,
        firma_img=firma_img,
    )

    filename = f"informe_inspeccion_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    st.success("PDF generado 🎉")
    st.download_button(
        "Descargar PDF",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
    )

st.markdown("</div>", unsafe_allow_html=True)

st.caption("Tip: si editas el código, Streamlit se recarga solo. Para detener: CTRL + C en la consola.")

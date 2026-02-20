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
# Keys + Defaults (para reset real)
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
    "fotos_files": "fotos_files",
    "firma_file": "firma_file",
}


def get_defaults() -> dict:
    # Ojo: fecha dinámica para que al limpiar vuelva a "hoy"
    return {
        FIELD_KEYS["theme"]: "Oscuro",
        FIELD_KEYS["include_signature"]: True,
        FIELD_KEYS["include_photos"]: True,
        FIELD_KEYS["show_correccion"]: True,
        FIELD_KEYS["auto_conclusion"]: True,
        FIELD_KEYS["fecha"]: datetime.now().strftime("%d-%m-%Y"),
        FIELD_KEYS["titulo"]: "Informe Técnico de Inspección",
        FIELD_KEYS["disciplina"]: "Eléctrica",
        FIELD_KEYS["equipo"]: "sala 31000",
        FIELD_KEYS["ubicacion"]: "Nodo 3500",
        FIELD_KEYS["inspector"]: "JORGE CAMPOS AGUIRRE",
        FIELD_KEYS["cargo"]: "Especialista eléctrico",
        FIELD_KEYS["registro_ot"]: "3333888",
        FIELD_KEYS["nivel_riesgo"]: "Medio",
        FIELD_KEYS["hallazgos"]: [],
        FIELD_KEYS["observaciones_raw"]: "Se observa la sala con tableros eléctricos abiertos, los demás equipos funcionando ok.",
        FIELD_KEYS["conclusion"]: "",
    }


def init_state():
    defaults = get_defaults()
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset_form():
    """
    Reset REAL:
    - Reasigna todos los keys de widgets
    - Limpia resultados de corrección
    - Limpia uploaders (pop)
    - Fuerza rerun para que la UI se actualice al tiro
    """
    defaults = get_defaults()
    for k, v in defaults.items():
        st.session_state[k] = v

    st.session_state.pop("obs_fixed", None)
    st.session_state.pop("obs_changes", None)

    # Uploaders: borrar key (es lo más confiable)
    st.session_state.pop(FIELD_KEYS["fotos_files"], None)
    st.session_state.pop(FIELD_KEYS["firma_file"], None)

    st.rerun()


init_state()


# -----------------------------
# Helpers UI / CSS
# -----------------------------
def apply_theme_css(theme: str) -> None:
    """
    Modo oscuro con alto contraste (más agresivo) para que se vea SIEMPRE.
    """
    if theme == "Oscuro":
        bg = "#070B14"
        fg = "#FFFFFF"
        muted = "#D0D7E2"
        card = "#0B1220"
        border = "#263247"
        input_bg = "#070B14"
        hint = "#EAEFFF"
    else:
        bg = "#ffffff"
        fg = "#0f172a"
        muted = "#334155"
        card = "#ffffff"
        border = "#e2e8f0"
        input_bg = "#ffffff"
        hint = "#0f172a"

    st.markdown(
        f"""
        <style>
        .stApp {{
            background: {bg};
            color: {fg};
        }}

        /* Markdown text + labels */
        .stMarkdown, .stMarkdown p, .stMarkdown span, .stMarkdown div {{
            color: {fg} !important;
        }}
        div[data-testid="stMarkdownContainer"] * {{
            color: {fg} !important;
        }}

        /* Widget labels */
        div[data-testid="stWidgetLabel"] > label {{
            color: {fg} !important;
            font-weight: 700 !important;
        }}

        /* Inputs */
        input, textarea {{
            background: {input_bg} !important;
            color: {fg} !important;
            border: 1px solid {border} !important;
            caret-color: {fg} !important;
        }}

        /* Selectbox */
        div[data-baseweb="select"] > div {{
            background: {input_bg} !important;
            color: {fg} !important;
            border: 1px solid {border} !important;
        }}

        /* Checkbox & radio text */
        [data-baseweb="checkbox"] span, [data-baseweb="radio"] span {{
            color: {fg} !important;
            font-weight: 600 !important;
        }}

        /* File uploader text */
        [data-testid="stFileUploader"] * {{
            color: {fg} !important;
        }}

        /* Buttons */
        .stButton>button {{
            border: 1px solid {border} !important;
        }}

        /* Card */
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
        .hint {{
            color: {hint} !important;
            opacity: 0.95;
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
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = escape(t)
    t = t.replace("\n", "<br/>")
    return t.strip() if t.strip() else "—"


def basic_spanish_fixes(text: str) -> Tuple[str, List[str]]:
    changes = []
    t = normalize_spaces(text or "")

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
        "epp": "EPP",
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


# -----------------------------
# Conclusión breve (SIN plazo)
# -----------------------------
def generate_conclusion_short(
    disciplina: str,
    nivel_riesgo: str,
    hallazgos: List[str],
    observaciones: str,
) -> str:
    hall = ", ".join(hallazgos) if hallazgos else "Sin hallazgos críticos"
    obs = normalize_spaces(observaciones)

    if nivel_riesgo == "Bajo":
        riesgo = "Riesgo bajo"
        accion = "Mantener control rutinario."
    elif nivel_riesgo == "Medio":
        riesgo = "Riesgo medio"
        accion = "Generar OT y corregir."
    else:
        riesgo = "Riesgo alto"
        accion = "Acción inmediata y notificar."

    # Breve, directo, sin “Plazo sugerido”
    out = (
        f"Conclusión ({disciplina}): {riesgo}.\n"
        f"- Hallazgos: {hall}.\n"
        f"- Acción: {accion}"
    )

    # Observación corta opcional (si hay)
    if obs:
        out += f"\n- Obs: {obs}"

    return out


# -----------------------------
# PDF helpers
# -----------------------------
def pil_to_rl_image(file_bytes: bytes, max_w_mm: float = 170, max_h_mm: float = 100) -> RLImage:
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
    include_firma: bool,
    include_fotos: bool,
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
            f"{APP_TITLE} · Generado {datetime.now().strftime('%d-%m-%Y %H:%M')}",
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

    story.append(Paragraph("Observaciones", h2))
    story.append(Paragraph(text_to_paragraph_html(observaciones), body))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Conclusión", h2))
    story.append(Paragraph(text_to_paragraph_html(conclusion), body))
    story.append(Spacer(1, 10))

    if include_firma:
        story.append(Paragraph("Firma", h2))
        if firma_img:
            try:
                story.append(pil_to_rl_image(firma_img[1], max_w_mm=70, max_h_mm=25))
                story.append(Spacer(1, 6))
                story.append(Paragraph(f"<b>{escape(inspector)}</b> · {escape(cargo)}", body))
            except Exception:
                story.append(Paragraph("No fue posible procesar la imagen de firma.", muted))
        else:
            story.append(Paragraph("No se adjuntó firma.", muted))
        story.append(Spacer(1, 10))

    if include_fotos and fotos:
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
# Callbacks seguros
# -----------------------------
def apply_obs_fix():
    st.session_state[FIELD_KEYS["observaciones_raw"]] = st.session_state.get(
        FIELD_KEYS["obs_fixed_preview"],
        st.session_state.get(FIELD_KEYS["observaciones_raw"], ""),
    )
    st.rerun()


# -----------------------------
# UI
# -----------------------------
st.markdown(f"<h1 style='margin-bottom:4px'>{APP_TITLE}</h1>", unsafe_allow_html=True)
st.markdown(f"<p class='muted' style='margin-top:0'>{APP_SUBTITLE}</p>", unsafe_allow_html=True)

# Tema
st.radio("Tema", ["Claro", "Oscuro"], horizontal=True, key=FIELD_KEYS["theme"])
apply_theme_css(st.session_state[FIELD_KEYS["theme"]])

# Config card
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
st.subheader("Configuración del informe")

c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
with c1:
    st.checkbox("Incluir firma", key=FIELD_KEYS["include_signature"])
with c2:
    st.checkbox("Incluir fotos", key=FIELD_KEYS["include_photos"])
with c3:
    st.checkbox("Mostrar corrección básica", key=FIELD_KEYS["show_correccion"])
with c4:
    st.button("🧹 Limpiar formulario", on_click=reset_form)

st.markdown("</div>", unsafe_allow_html=True)

# Main fields
st.markdown("<div class='app-card'>", unsafe_allow_html=True)

st.text_input("Fecha", key=FIELD_KEYS["fecha"])
st.text_input("Título del informe", key=FIELD_KEYS["titulo"])
st.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Otra"], key=FIELD_KEYS["disciplina"])

st.text_input("Equipo / Área inspeccionada", key=FIELD_KEYS["equipo"])
st.text_input("Ubicación", key=FIELD_KEYS["ubicacion"])
st.text_input("Inspector", key=FIELD_KEYS["inspector"])
st.text_input("Cargo", key=FIELD_KEYS["cargo"])
st.text_input("N° Registro / OT", key=FIELD_KEYS["registro_ot"])

st.selectbox("Nivel de riesgo", ["Bajo", "Medio", "Alto"], key=FIELD_KEYS["nivel_riesgo"])

st.multiselect(
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
    key=FIELD_KEYS["hallazgos"],
)

st.text_area("Observaciones técnicas", height=120, key=FIELD_KEYS["observaciones_raw"])

# Corrección básica
if st.session_state[FIELD_KEYS["show_correccion"]]:
    st.markdown("<hr/>", unsafe_allow_html=True)
    st.markdown("<p class='muted'><b>Corrección básica:</b> sugerencias simples (tú decides aplicar).</p>",
                unsafe_allow_html=True)

    if st.button("Sugerir correcciones en Observaciones"):
        fixed, changes = basic_spanish_fixes(st.session_state[FIELD_KEYS["observaciones_raw"]])
        st.session_state["obs_fixed"] = fixed
        st.session_state["obs_changes"] = changes
        st.session_state[FIELD_KEYS["obs_fixed_preview"]] = fixed

    if "obs_fixed" in st.session_state:
        st.text_area("Observaciones (sugerido)", height=120, key=FIELD_KEYS["obs_fixed_preview"])
        if st.session_state.get("obs_changes"):
            st.write("Cambios sugeridos:")
            for c in st.session_state["obs_changes"]:
                st.write(f"- {c}")

        st.button("Aplicar sugerencias a Observaciones", on_click=apply_obs_fix)

# Conclusión (breve)
st.markdown("<hr/>", unsafe_allow_html=True)
st.checkbox("Auto-actualizar conclusión", key=FIELD_KEYS["auto_conclusion"])

auto_conc = generate_conclusion_short(
    st.session_state[FIELD_KEYS["disciplina"]],
    st.session_state[FIELD_KEYS["nivel_riesgo"]],
    st.session_state[FIELD_KEYS["hallazgos"]],
    st.session_state[FIELD_KEYS["observaciones_raw"]],
)

# Si auto está activo, seteamos antes de crear el widget
if st.session_state[FIELD_KEYS["auto_conclusion"]]:
    st.session_state[FIELD_KEYS["conclusion"]] = auto_conc
elif not st.session_state.get(FIELD_KEYS["conclusion"]):
    st.session_state[FIELD_KEYS["conclusion"]] = auto_conc

st.text_area("Conclusión (breve y editable)", height=140, key=FIELD_KEYS["conclusion"])

st.markdown("</div>", unsafe_allow_html=True)

# Evidencias + firma
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
st.subheader("Evidencias y firma")

fotos_files = None
firma_file = None

if st.session_state[FIELD_KEYS["include_photos"]]:
    fotos_files = st.file_uploader(
        "Subir imágenes de evidencia (JPG/PNG) — puedes cargar varias",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key=FIELD_KEYS["fotos_files"],
    )

if st.session_state[FIELD_KEYS["include_signature"]]:
    firma_file = st.file_uploader(
        "Firma (imagen JPG/PNG) — opcional",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=False,
        key=FIELD_KEYS["firma_file"],
    )

st.markdown("</div>", unsafe_allow_html=True)

# Generación PDF
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
st.subheader("Generación de PDF")

if st.button("Generar PDF Profesional ✅"):
    fotos: List[Tuple[str, bytes]] = []
    if st.session_state[FIELD_KEYS["include_photos"]] and fotos_files:
        for f in fotos_files:
            fotos.append((f.name, f.read()))

    firma_img: Optional[Tuple[str, bytes]] = None
    if st.session_state[FIELD_KEYS["include_signature"]] and firma_file:
        firma_img = (firma_file.name, firma_file.read())

    pdf_bytes = build_pdf(
        titulo=st.session_state[FIELD_KEYS["titulo"]],
        fecha=st.session_state[FIELD_KEYS["fecha"]],
        equipo=st.session_state[FIELD_KEYS["equipo"]],
        ubicacion=st.session_state[FIELD_KEYS["ubicacion"]],
        inspector=st.session_state[FIELD_KEYS["inspector"]],
        cargo=st.session_state[FIELD_KEYS["cargo"]],
        registro_ot=st.session_state[FIELD_KEYS["registro_ot"]],
        disciplina=st.session_state[FIELD_KEYS["disciplina"]],
        nivel_riesgo=st.session_state[FIELD_KEYS["nivel_riesgo"]],
        observaciones=st.session_state[FIELD_KEYS["observaciones_raw"]],
        conclusion=st.session_state[FIELD_KEYS["conclusion"]],
        fotos=fotos,
        firma_img=firma_img,
        include_firma=st.session_state[FIELD_KEYS["include_signature"]],
        include_fotos=st.session_state[FIELD_KEYS["include_photos"]],
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

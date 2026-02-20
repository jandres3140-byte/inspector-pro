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
        div[data-testid="stWidgetLabel"] > label {{
            color: {fg} !important;
            font-weight: 600 !important;
        }}
        input, textarea {{
            background: {input_bg} !important;
            color: {fg} !important;
            border: 1px solid {border} !important;
        }}
        div[data-baseweb="select"] > div {{
            background: {input_bg} !important;
            color: {fg} !important;
            border: 1px solid {border} !important;
        }}
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
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = escape(t)
    t = t.replace("\n", "<br/>")
    return t.strip() if t.strip() else "—"


def basic_spanish_fixes(text: str):
    changes = []
    t = normalize_spaces(text)

    replacements = {
        "demasciado": "demasiado",
        "ubicacion": "ubicación",
        "observacion": "observación",
        "conclucion": "conclusión",
        "electrico": "eléctrico",
        "mecanico": "mecánico",
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
        changes.append("Capitalización inicial")

    return t, changes


def generate_conclusion(disciplina, nivel_riesgo, hallazgos, observaciones):
    hall = ", ".join(hallazgos) if hallazgos else "sin hallazgos críticos declarados"

    if nivel_riesgo == "Bajo":
        riesgo_text = "Condición general aceptable. No se identifican riesgos inmediatos."
        accion = "Mantener monitoreo rutinario."
        plazo = "Próximo ciclo de inspección."
    elif nivel_riesgo == "Medio":
        riesgo_text = "Desviaciones que requieren corrección planificada."
        accion = "Generar OT con prioridad media."
        plazo = "7–14 días."
    else:
        riesgo_text = "Condición de riesgo alto. Acción inmediata requerida."
        accion = "Aislar/asegurar equipo y notificar supervisión."
        plazo = "Inmediato / 24 horas."

    conclusion = (
        f"Conclusión técnica ({disciplina}):\n"
        f"- {riesgo_text}\n"
        f"- Hallazgos: {hall}\n"
        f"- Acción recomendada: {accion}\n"
        f"- Plazo: {plazo}\n"
        f"- Observaciones: {observaciones or 'No registradas.'}"
    )
    return conclusion


def pil_to_rl_image(file_bytes: bytes, max_w_mm: float = 170, max_h_mm: float = 100):
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
    titulo,
    fecha,
    equipo,
    ubicacion,
    inspector,
    cargo,
    registro_ot,
    disciplina,
    nivel_riesgo,
    observaciones,
    conclusion,
    fotos,
    firma_img,
):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]

    story = []

    story.append(Paragraph("INFORME TÉCNICO DE INSPECCIÓN", h1))
    story.append(Spacer(1, 10))

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

    table = Table(data, colWidths=[40 * mm, 130 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )

    story.append(table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Observaciones", h2))
    story.append(Paragraph(text_to_paragraph_html(observaciones), body))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Conclusión", h2))
    story.append(Paragraph(text_to_paragraph_html(conclusion), body))
    story.append(Spacer(1, 10))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# -----------------------------
# UI
# -----------------------------
st.title(APP_TITLE)
st.caption(APP_SUBTITLE)

theme = st.radio("Tema", ["Claro", "Oscuro"], index=1, horizontal=True)
apply_theme_css(theme)

if "observaciones_raw" not in st.session_state:
    st.session_state["observaciones_raw"] = "Se observa la sala con tableros eléctricos abiertos."

def apply_obs_fix():
    st.session_state["observaciones_raw"] = st.session_state.get(
        "obs_fixed_preview",
        st.session_state["observaciones_raw"]
    )

fecha = st.text_input("Fecha", value=datetime.now().strftime("%d-%m-%Y"))
titulo = st.text_input("Título", value="Informe Técnico")
disciplina = st.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Otra"])
equipo = st.text_input("Equipo")
ubicacion = st.text_input("Ubicación")
inspector = st.text_input("Inspector")
cargo = st.text_input("Cargo")
registro_ot = st.text_input("Registro / OT")
nivel_riesgo = st.selectbox("Nivel de riesgo", ["Bajo", "Medio", "Alto"])

hallazgos = st.multiselect(
    "Hallazgos",
    ["Condición insegura", "LOTO", "Protecciones", "Orden", "Otro"],
)

observaciones_raw = st.text_area(
    "Observaciones técnicas",
    key="observaciones_raw",
    height=120,
)

if st.button("Sugerir correcciones"):
    fixed, changes = basic_spanish_fixes(st.session_state["observaciones_raw"])
    st.session_state["obs_fixed"] = fixed
    st.session_state["obs_changes"] = changes

if "obs_fixed" in st.session_state:
    st.text_area(
        "Observaciones (sugerido)",
        value=st.session_state["obs_fixed"],
        height=120,
        key="obs_fixed_preview",
    )
    st.button("Aplicar sugerencias a Observaciones", on_click=apply_obs_fix)

conclusion = st.text_area(
    "Conclusión técnica",
    value=generate_conclusion(
        disciplina,
        nivel_riesgo,
        hallazgos,
        st.session_state["observaciones_raw"],
    ),
    height=150,
)

if st.button("Generar PDF"):
    pdf = build_pdf(
        titulo,
        fecha,
        equipo,
        ubicacion,
        inspector,
        cargo,
        registro_ot,
        disciplina,
        nivel_riesgo,
        st.session_state["observaciones_raw"],
        conclusion,
        [],
        None,
    )
    st.download_button(
        "Descargar PDF",
        data=pdf,
        file_name="informe.pdf",
        mime="application/pdf",
    )

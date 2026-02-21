import io
import re
import uuid
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
)
from reportlab.pdfgen import canvas

from PIL import Image, ImageOps
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo


# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="jcamp029.pro", page_icon="🧾", layout="centered")
APP_TITLE = "jcamp029.pro"
APP_SUBTITLE = "Generador profesional de informes de inspección técnica (PDF)."
TZ_CL = ZoneInfo("America/Santiago")

UP_NONCE = "__uploader_nonce__"

# -----------------------------
# Keys + Defaults
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
}

def get_defaults() -> dict:
    return {
        FIELD_KEYS["theme"]: "Oscuro",
        FIELD_KEYS["include_signature"]: True,
        FIELD_KEYS["include_photos"]: True,
        FIELD_KEYS["show_correccion"]: True,
        FIELD_KEYS["auto_conclusion"]: True,
        FIELD_KEYS["fecha"]: datetime.now(TZ_CL).strftime("%d-%m-%Y"),
        FIELD_KEYS["titulo"]: "Informe Técnico de Inspección",
        FIELD_KEYS["disciplina"]: "Eléctrica",
        FIELD_KEYS["equipo"]: "",
        FIELD_KEYS["ubicacion"]: "",
        FIELD_KEYS["inspector"]: "JORGE CAMPOS AGUIRRE",
        FIELD_KEYS["cargo"]: "Especialista eléctrico",
        FIELD_KEYS["registro_ot"]: "",
        FIELD_KEYS["nivel_riesgo"]: "Medio",
        FIELD_KEYS["hallazgos"]: [],
        FIELD_KEYS["observaciones_raw"]: "",
        FIELD_KEYS["conclusion"]: "",
    }

def hard_reset_now():
    """
    Reset definitivo del formulario preservando el tema visual.
    """
    # Guardar el tema actual antes de limpiar
    current_theme = st.session_state.get(FIELD_KEYS["theme"], "Oscuro")
    
    # Limpiar todo el estado de sesión de forma agresiva
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    # Incrementar nonce para limpiar uploaders de archivos
    st.session_state[UP_NONCE] = st.session_state.get(UP_NONCE, 0) + 1
    
    # Cargar valores por defecto
    defaults = get_defaults()
    for k, v in defaults.items():
        st.session_state[k] = v
    
    # Restaurar el tema para evitar el cambio visual indeseado
    st.session_state[FIELD_KEYS["theme"]] = current_theme
    
    st.rerun()

def init_state():
    if UP_NONCE not in st.session_state:
        st.session_state[UP_NONCE] = 0
    
    defaults = get_defaults()
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# -----------------------------
# Helpers UI / CSS
# -----------------------------
def apply_theme_css(theme: str) -> None:
    if theme == "Oscuro":
        bg, fg, muted, card, border, input_bg = "#070B14", "#FFFFFF", "#D0D7E2", "#0B1220", "#263247", "#070B14"
    else:
        bg, fg, muted, card, border, input_bg = "#ffffff", "#0f172a", "#334155", "#ffffff", "#e2e8f0", "#ffffff"

    st.markdown(f"""
        <style>
        .stApp {{ background: {bg}; color: {fg}; }}
        div[data-testid="stMarkdownContainer"] * {{ color: {fg} !important; }}
        div[data-testid="stWidgetLabel"] > label {{ color: {fg} !important; font-weight: 700 !important; }}
        input, textarea {{ background: {input_bg} !important; color: {fg} !important; border: 1px solid {border} !important; }}
        div[data-baseweb="select"] > div {{ background: {input_bg} !important; color: {fg} !important; border: 1px solid {border} !important; }}
        .app-card {{ border: 1px solid {border}; background: {card}; border-radius: 14px; padding: 16px; margin-bottom: 16px; }}
        .muted {{ color: {muted} !important; }}
        </style>
        """, unsafe_allow_html=True)

def normalize_spaces(text: str) -> str:
    text = text or ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def text_to_paragraph_html(text: str) -> str:
    t = escape((text or "").replace("\r\n", "\n").replace("\r", "\n"))
    return t.replace("\n", "<br/>").strip() if t.strip() else "—"

def basic_spanish_fixes(text: str):
    changes = []
    t = normalize_spaces(text or "")
    replacements = {
        "demasciado": "demasiado", "ubucacion": "ubicación", "ubicacion": "ubicación",
        "observacion": "observación", "conclucion": "conclusión", "electrico": "eléctrico",
        "mecanico": "mecánico", "inspeccion": "inspección", "epp": "EPP",
    }
    for wrong, right in replacements.items():
        pattern = re.compile(rf"\b{re.escape(wrong)}\b", re.IGNORECASE)
        if pattern.search(t):
            t = pattern.sub(right, t)
            changes.append(f"'{wrong}' → '{right}'")
    if t and t[0].islower():
        t = t[0].upper() + t[1:]; changes.append("Capitalización inicial")
    return t, changes

def generate_conclusion_pro(disciplina, nivel_riesgo, hallazgos, observaciones):
    hall = ", ".join(hallazgos) if hallazgos else "Sin hallazgos críticos"
    riesgo = f"Riesgo {nivel_riesgo.lower()}"
    prioridad = "inmediata" if nivel_riesgo == "Alto" else "programada" if nivel_riesgo == "Medio" else "rutinaria"
    
    soporte = "Foco: integridad de tableros y LOTO." if disciplina == "Eléctrica" else "Foco: resguardos y vibraciones." if disciplina == "Mecánica" else "Foco: condición segura."
    return f"Conclusión ({disciplina}): {riesgo}. Prioridad: {prioridad}.\n- Hallazgos: {hall}.\n- {soporte}\n- Acción: Corregir desviación y registrar OT."

def _thumb_jpeg_fixed_box(file_bytes, box_w_mm, box_h_mm):
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(file_bytes)).convert("RGB"))
    box_px_w, box_px_h = 900, int(900 * (box_h_mm / box_w_mm))
    canvas_img = Image.new("RGB", (box_px_w, box_px_h), (255, 255, 255))
    img.thumbnail((box_px_w, box_px_h))
    canvas_img.paste(img, ((box_px_w - img.size[0]) // 2, (box_px_h - img.size[1]) // 2))
    buf = io.BytesIO()
    canvas_img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return buf

def build_pdf(titulo, fecha, equipo, ubicacion, inspector, cargo, registro_ot, disciplina, nivel_riesgo, observaciones, conclusion, fotos, firma_img, include_firma, include_fotos):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, margin=18*mm)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=10)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10)

    def header_footer(c, d):
        c.saveState()
        c.setFont("Helvetica", 9); c.setFillColor(colors.grey)
        c.drawString(18*mm, 10*mm, f"{APP_TITLE} · {datetime.now(TZ_CL).strftime('%d-%m-%Y')}")
        c.drawRightString(A4[0]-18*mm, 10*mm, f"Página {c.getPageNumber()}")
        c.restoreState()

    story = [Paragraph("INFORME TÉCNICO DE INSPECCIÓN", h1), Spacer(1, 10)]
    data = [["Fecha", fecha], ["Título", titulo], ["Disciplina", disciplina], ["Riesgo", nivel_riesgo], ["Equipo", equipo], ["Ubicación", ubicacion], ["Inspector", inspector], ["Cargo", cargo], ["OT", registro_ot]]
    t = Table(data, colWidths=[40*mm, 130*mm])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (0,-1), colors.whitesmoke), ('GRID', (0,0), (-1,-1), 0.5, colors.grey)]))
    story.extend([t, Paragraph("Observaciones", h2), Paragraph(text_to_paragraph_html(observaciones), body), Paragraph("Conclusión", h2), Paragraph(text_to_paragraph_html(conclusion), body)])

    if include_fotos and fotos:
        story.append(Paragraph("Imágenes", h2))
        row = [RLImage(_thumb_jpeg_fixed_box(f[1], 55, 35), width=55*mm, height=35*mm) for f in fotos[:3]]
        it = Table([row]); it.hAlign = 'CENTER'; story.append(it)

    if include_firma and firma_img:
        story.append(Paragraph("Firma", h2))
        story.append(RLImage(_thumb_jpeg_fixed_box(firma_img[1], 55, 18), width=55*mm, height=18*mm))

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return buffer.getvalue()

def apply_obs_fix():
    st.session_state[FIELD_KEYS["observaciones_raw"]] = st.session_state.get(FIELD_KEYS["obs_fixed_preview"], "")
    st.rerun()

# -----------------------------
# UI RENDERING
# -----------------------------
st.markdown(f"<h1>{APP_TITLE}</h1><p class='muted'>{APP_SUBTITLE}</p>", unsafe_allow_html=True)
st.radio("Tema", ["Claro", "Oscuro"], horizontal=True, key=FIELD_KEYS["theme"])
apply_theme_css(st.session_state[FIELD_KEYS["theme"]])

# Configuración y Limpieza
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
with c1: st.checkbox("Firma", key=FIELD_KEYS["include_signature"])
with c2: st.checkbox("Fotos", key=FIELD_KEYS["include_photos"])
with c3: st.checkbox("Corrección", key=FIELD_KEYS["show_correccion"])
with c4: 
    if st.button("🧹 Limpiar formulario", use_container_width=True):
        hard_reset_now()
st.markdown("</div>", unsafe_allow_html=True)

# Formulario de Datos
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
st.text_input("Fecha", key=FIELD_KEYS["fecha"])
st.text_input("Título", key=FIELD_KEYS["titulo"])
st.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Otra"], key=FIELD_KEYS["disciplina"])
st.text_input("Equipo / Área", key=FIELD_KEYS["equipo"])
st.text_input("Ubicación", key=FIELD_KEYS["ubicacion"])
st.text_input("Inspector", key=FIELD_KEYS["inspector"])
st.text_input("Cargo", key=FIELD_KEYS["cargo"])
st.text_input("N° Registro / OT", key=FIELD_KEYS["registro_ot"])
st.selectbox("Nivel de riesgo", ["Bajo", "Medio", "Alto"], key=FIELD_KEYS["nivel_riesgo"])
st.multiselect("Hallazgos", ["Condición insegura", "Orden y limpieza", "LOTO", "Tableros", "Otros"], key=FIELD_KEYS["hallazgos"])
st.text_area("Observaciones", height=120, key=FIELD_KEYS["observaciones_raw"])

if st.session_state[FIELD_KEYS["show_correccion"]]:
    if st.button("Sugerir correcciones"):
        fixed, changes = basic_spanish_fixes(st.session_state[FIELD_KEYS["observaciones_raw"]])
        st.session_state["obs_fixed"] = fixed
        st.session_state[FIELD_KEYS["obs_fixed_preview"]] = fixed
        if changes: st.info(f"Sugerencias: {', '.join(changes)}")
    if "obs_fixed" in st.session_state:
        st.text_area("Sugerencia", key=FIELD_KEYS["obs_fixed_preview"])
        st.button("Aplicar sugerencias", on_click=apply_obs_fix)

st.checkbox("Auto-conclusión", key=FIELD_KEYS["auto_conclusion"])
if st.session_state[FIELD_KEYS["auto_conclusion"]]:
    st.session_state[FIELD_KEYS["conclusion"]] = generate_conclusion_pro(st.session_state[FIELD_KEYS["disciplina"]], st.session_state[FIELD_KEYS["nivel_riesgo"]], st.session_state[FIELD_KEYS["hallazgos"]], st.session_state[FIELD_KEYS["observaciones_raw"]])
st.text_area("Conclusión", height=150, key=FIELD_KEYS["conclusion"])
st.markdown("</div>", unsafe_allow_html=True)

# Archivos
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
nonce = st.session_state[UP_NONCE]
fotos_files = st.file_uploader("Fotos (Máx 3)", type=["jpg", "png"], accept_multiple_files=True, key=f"f_{nonce}") if st.session_state[FIELD_KEYS["include_photos"]] else None
firma_file = st.file_uploader("Firma", type=["jpg", "png"], key=f"s_{nonce}") if st.session_state[FIELD_KEYS["include_signature"]] else None
st.markdown("</div>", unsafe_allow_html=True)

# Generación
if st.button("Generar PDF Profesional ✅", use_container_width=True):
    fotos = [(f.name, f.read()) for f in fotos_files[:3]] if fotos_files else []
    firma = (firma_file.name, firma_file.read()) if firma_file else None
    
    pdf = build_pdf(st.session_state[FIELD_KEYS["titulo"]], st.session_state[FIELD_KEYS["fecha"]], st.session_state[FIELD_KEYS["equipo"]], st.session_state[FIELD_KEYS["ubicacion"]], st.session_state[FIELD_KEYS["inspector"]], st.session_state[FIELD_KEYS["cargo"]], st.session_state[FIELD_KEYS["registro_ot"]], st.session_state[FIELD_KEYS["disciplina"]], st.session_state[FIELD_KEYS["nivel_riesgo"]], st.session_state[FIELD_KEYS["observaciones_raw"]], st.session_state[FIELD_KEYS["conclusion"]], fotos, firma, st.session_state[FIELD_KEYS["include_signature"]], st.session_state[FIELD_KEYS["include_photos"]])
    
    st.download_button("Descargar Informe", data=pdf, file_name=f"informe_{datetime.now().strftime('%H%M%S')}.pdf", mime="application/pdf")

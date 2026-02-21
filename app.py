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
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
)

from PIL import Image, ImageOps, ImageChops
from xml.sax.saxutils import escape

# -----------------------------
# Configuración Global
# -----------------------------
st.set_page_config(page_title="jcamp029.pro", page_icon="🧾", layout="centered")
APP_TITLE = "jcamp029.pro"
APP_SUBTITLE = "Generador profesional de informes de inspección técnica (PDF)."
TZ_CL = ZoneInfo("America/Santiago")

UP_NONCE = "__uploader_nonce__"

# Dimensiones PDF (mm)
PHOTO_W_2COL_MM, PHOTO_H_2COL_MM = 86, 72
PHOTO_W_FULL_MM, PHOTO_H_FULL_MM = 172, 95
SIGN_W_MM, SIGN_H_MM = 90, 60

# Claves de Estado
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
    "conclusion_locked": "conclusion_locked",
    "last_auto_hash": "last_auto_hash",
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
        FIELD_KEYS["obs_fixed_preview"]: "",
        FIELD_KEYS["conclusion"]: "",
        FIELD_KEYS["conclusion_locked"]: False,
        FIELD_KEYS["last_auto_hash"]: "",
    }

def init_state():
    # Forzar modo claro siempre al abrir
    st.session_state[FIELD_KEYS["theme"]] = "Claro"

    if UP_NONCE not in st.session_state:
        st.session_state[UP_NONCE] = 0

    defaults = get_defaults()
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

def hard_reset_now():
    current_theme = st.session_state.get(FIELD_KEYS["theme"], "Oscuro")
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state[UP_NONCE] = 1
    defaults = get_defaults()
    for k, v in defaults.items():
        st.session_state[k] = v
    st.session_state[FIELD_KEYS["theme"]] = current_theme
    st.rerun()

init_state()

# -----------------------------
# Lógica de Interfaz y Temas
# -----------------------------
def apply_theme_css(theme: str) -> None:
    if theme == "Oscuro":
        bg, fg, muted, card, border = "#070B14", "#FFFFFF", "#D6DEEA", "#0B1220", "#2A3A58"
        input_bg, placeholder, focus = "#0A1020", "#9FB0C8", "#5AA9FF"
    else:
        bg, fg, muted, card, border = "#FFFFFF", "#0F172A", "#334155", "#F8FAFC", "#E2E8F0"
        input_bg, placeholder, focus = "#FFFFFF", "#64748B", "#2563EB"

    st.markdown(f"""
        <style>
        .stApp {{ background: {bg}; color: {fg}; }}
        div[data-testid="stMarkdownContainer"] * {{ color: {fg} !important; }}
        div[data-testid="stWidgetLabel"] > label {{ color: {fg} !important; font-weight: 800 !important; }}
        .app-card {{ border: 1px solid {border}; background: {card}; border-radius: 14px; padding: 16px; margin-bottom: 16px; }}
        input, textarea {{ background: {input_bg} !important; color: {fg} !important; border: 1px solid {border} !important; }}
        </style>
        """, unsafe_allow_html=True)

# -----------------------------
# Procesamiento de Texto e IA
# -----------------------------
def basic_spanish_fixes(text: str):
    changes = []
    t = (text or "").strip()
    replacements = {"demasciado": "demasiado", "ubucacion": "ubicación", "epp": "EPP"}
    for wrong, right in replacements.items():
        if re.search(rf"\b{wrong}\b", t, re.I):
            t = re.sub(rf"\b{wrong}\b", right, t, flags=re.I)
            changes.append(f"'{wrong}' → '{right}'")
    if t and t[0].islower():
        t = t[0].upper() + t[1:]; changes.append("Capitalización")
    return t, changes

def generate_conclusion_short(disciplina, riesgo, hallazgos):
    prioridad = "inmediata" if riesgo == "Alto" else "programada" if riesgo == "Medio" else "rutinaria"
    h_str = ", ".join(hallazgos[:4]) if hallazgos else "General"
    return f"{disciplina}: Riesgo {riesgo.lower()}. Prioridad {prioridad}. Hallazgos: {h_str}. Acción: Corregir según prioridad."

def sync_auto_conclusion_if_needed():
    if st.session_state[FIELD_KEYS["auto_conclusion"]] and not st.session_state[FIELD_KEYS["conclusion_locked"]]:
        st.session_state[FIELD_KEYS["conclusion"]] = generate_conclusion_short(
            st.session_state[FIELD_KEYS["disciplina"]],
            st.session_state[FIELD_KEYS["nivel_riesgo"]],
            st.session_state[FIELD_KEYS["hallazgos"]]
        )

# -----------------------------
# Procesamiento de Imágenes (Firma/Fotos)
# -----------------------------
def _trim_signature(img: Image.Image) -> Image.Image:
    if img.mode != 'RGBA': img = img.convert('RGBA')
    bg = Image.new('RGBA', img.size, (255, 255, 255, 0))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    return img.crop(bbox) if bbox else img

def _img_to_jpeg_signature_big(img_bytes: bytes, target_w_mm, target_h_mm) -> io.BytesIO:
    img = Image.open(io.BytesIO(img_bytes))
    img = _trim_signature(img)
    canvas = Image.new("RGB", (int(target_w_mm*10), int(target_h_mm*10)), (255,255,255))
    img.thumbnail(canvas.size, Image.Resampling.LANCZOS)
    offset = ((canvas.width - img.width)//2, (canvas.height - img.height)//2)
    canvas.paste(img, offset, img if img.mode == 'RGBA' else None)
    out = io.BytesIO()
    canvas.save(out, format="JPEG", quality=92)
    return out

def _img_to_jpeg_cover(img_bytes: bytes, w_mm, h_mm) -> io.BytesIO:
    img = Image.open(io.BytesIO(img_bytes))
    img = ImageOps.exif_transpose(img)
    img = ImageOps.fit(img, (int(w_mm*10), int(h_mm*10)), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out

# -----------------------------
# Generación del PDF
# -----------------------------
def build_pdf(titulo, fecha, equipo, ubicacion, inspector, cargo, registro_ot, disciplina, nivel_riesgo, hallazgos, observaciones, conclusion, fotos, firma_img, include_sign, include_photos):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, margin=(14*mm, 14*mm, 14*mm, 14*mm))
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', fontSize=15, fontName='Helvetica-Bold', alignment=1, spaceAfter=8)
    body = ParagraphStyle('body', fontSize=9.5, leading=11)
    
    story = [Paragraph("INFORME TÉCNICO DE INSPECCIÓN", h1)]
    
    # Tabla de Datos
    data = [
        ["Fecha", fecha], ["Título", titulo], ["Disciplina", disciplina], ["Riesgo", nivel_riesgo],
        ["Equipo/Área", equipo or "—"], ["Ubicación", ubicacion or "—"], ["Inspector", inspector],
        ["Cargo", cargo], ["Registro/OT", registro_ot or "—"], ["Hallazgos", ", ".join(hallazgos) or "—"]
    ]
    t = Table(data, colWidths=[42*mm, 130*mm])
    t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke), ('FONTSIZE', (0,0), (-1,-1), 9), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    story.append(t)
    story.append(Spacer(1, 4*mm))

    # Lógica de recorte para 1 página
    max_obs = 520 if (fotos or firma_img) else 2000
    max_con = 320 if (fotos or firma_img) else 1000
    
    story.append(Paragraph(f"<b>Observaciones:</b> {escape(observaciones[:max_obs])}", body))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(f"<b>Conclusión:</b> {escape(conclusion[:max_con])}", body))
    story.append(Spacer(1, 5*mm))

    # Multimedia Layout
    photo_objs = [RLImage(_img_to_jpeg_cover(f, PHOTO_W_2COL_MM, PHOTO_H_2COL_MM), width=PHOTO_W_2COL_MM*mm, height=PHOTO_H_2COL_MM*mm) for f in fotos[:3]]
    sign_obj = RLImage(_img_to_jpeg_signature_big(firma_img, SIGN_W_MM, SIGN_H_MM), width=SIGN_W_MM*mm, height=SIGN_H_MM*mm) if firma_img else None

    # Distribución Dinámica
    grid_data = []
    if len(photo_objs) == 1:
        if sign_obj: grid_data = [[photo_objs[0]], [sign_obj]]
        else: story.append(RLImage(_img_to_jpeg_cover(fotos[0], PHOTO_W_FULL_MM, PHOTO_H_FULL_MM), PHOTO_W_FULL_MM*mm, PHOTO_H_FULL_MM*mm))
    elif len(photo_objs) == 2:
        if sign_obj: grid_data = [[photo_objs[0], photo_objs[1]], [sign_obj, ""]]
        else: grid_data = [[photo_objs[0], photo_objs[1]]]
    elif len(photo_objs) == 3:
        if sign_obj: grid_data = [[photo_objs[0], photo_objs[1]], [photo_objs[2], sign_obj]]
        else: grid_data = [[photo_objs[0], photo_objs[1]], [photo_objs[2], ""]]

    if grid_data:
        gt = Table(grid_data, colWidths=[88*mm, 88*mm])
        if len(photo_objs) == 2 and sign_obj: gt.setStyle(TableStyle([('SPAN', (0,1), (1,1)), ('ALIGN', (0,1), (1,1), 'CENTER')]))
        story.append(gt)

    doc.build(story)
    return buffer.getvalue()

# -----------------------------
# Interfaz Streamlit (UI)
# -----------------------------
apply_theme_css(st.session_state[FIELD_KEYS["theme"]])
st.markdown(f"<h1>{APP_TITLE}</h1>", unsafe_allow_html=True)
st.radio("Tema", ["Claro", "Oscuro"], key=FIELD_KEYS["theme"], horizontal=True)

with st.container():
    c1, c2, c3, c4 = st.columns(4)
    c1.toggle("Firma", key=FIELD_KEYS["include_signature"])
    c2.toggle("Fotos", key=FIELD_KEYS["include_photos"])
    c3.toggle("Corrección", key=FIELD_KEYS["show_correccion"])
    if c4.button("Limpiar formulario"): hard_reset_now()

# Formulario
col_l, col_r = st.columns(2)
fecha = col_l.text_input("Fecha", key=FIELD_KEYS["fecha"])
titulo = col_r.text_input("Título", key=FIELD_KEYS["titulo"])
disciplina = col_l.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Instrumentación", "Seguridad"], key=FIELD_KEYS["disciplina"])
riesgo = col_r.selectbox("Riesgo", ["Bajo", "Medio", "Alto"], key=FIELD_KEYS["nivel_riesgo"])
equipo = col_l.text_input("Equipo/Área", key=FIELD_KEYS["equipo"])
ubicacion = col_r.text_input("Ubicación", key=FIELD_KEYS["ubicacion"])
inspector = col_l.text_input("Inspector", key=FIELD_KEYS["inspector"])
cargo = col_r.text_input("Cargo", key=FIELD_KEYS["cargo"])
ot = st.text_input("Nº Registro/OT", key=FIELD_KEYS["registro_ot"])
hallazgos = st.multiselect("Hallazgos", ["LOTO", "Tableros", "Cableado", "Protecciones", "EPP", "Orden y limpieza"], key=FIELD_KEYS["hallazgos"])

obs_raw = st.text_area("Observaciones", key=FIELD_KEYS["observaciones_raw"], height=130)

if st.session_state[FIELD_KEYS["show_correccion"]]:
    if st.button("Sugerir correcciones"):
        fixed, logs = basic_spanish_fixes(obs_raw)
        st.session_state[FIELD_KEYS["obs_fixed_preview"]] = fixed
        if logs: st.info(f"Sugerencia: {fixed}")
    if st.session_state[FIELD_KEYS["obs_fixed_preview"]]:
        if st.button("Aplicar sugerencia"):
            st.session_state[FIELD_KEYS["observaciones_raw"]] = st.session_state[FIELD_KEYS["obs_fixed_preview"]]
            st.rerun()

# Conclusión
st.divider()
sync_auto_conclusion_if_needed()
cb1, cb2 = st.columns(2)
if cb1.button("🤖 Auto", use_container_width=True): st.session_state[FIELD_KEYS["conclusion_locked"]] = False
if cb2.button("✍️ Manual", use_container_width=True): st.session_state[FIELD_KEYS["conclusion_locked"]] = True
st.text_area("Conclusión", key=FIELD_KEYS["conclusion"], height=140)

# Carga de Archivos
with st.container():
    st.write("### Multimedia")
    u_photos = st.file_uploader("Fotos (Máx 3)", type=["jpg", "png"], accept_multiple_files=True, key=f"f_{st.session_state[UP_NONCE]}") if st.session_state[FIELD_KEYS["include_photos"]] else []
    u_sign = st.file_uploader("Firma", type=["png", "jpg"], key=f"s_{st.session_state[UP_NONCE]}") if st.session_state[FIELD_KEYS["include_signature"]] else None

if st.button("Generar PDF Profesional ✅", use_container_width=True):
    f_bytes = [f.read() for f in u_photos]
    s_bytes = u_sign.read() if u_sign else None
    
    pdf = build_pdf(
        st.session_state[FIELD_KEYS["titulo"]], st.session_state[FIELD_KEYS["fecha"]],
        st.session_state[FIELD_KEYS["equipo"]], st.session_state[FIELD_KEYS["ubicacion"]],
        st.session_state[FIELD_KEYS["inspector"]], st.session_state[FIELD_KEYS["cargo"]],
        st.session_state[FIELD_KEYS["registro_ot"]], st.session_state[FIELD_KEYS["disciplina"]],
        st.session_state[FIELD_KEYS["nivel_riesgo"]], st.session_state[FIELD_KEYS["hallazgos"]],
        st.session_state[FIELD_KEYS["observaciones_raw"]], st.session_state[FIELD_KEYS["conclusion"]],
        f_bytes, s_bytes, st.session_state[FIELD_KEYS["include_signature"]], st.session_state[FIELD_KEYS["include_photos"]]
    )
    
    st.download_button("Descargar Informe", data=pdf, file_name=f"informe_{datetime.now(TZ_CL).strftime('%H%M%S')}.pdf", mime="application/pdf", use_container_width=True)

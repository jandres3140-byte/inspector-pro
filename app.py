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
# Config
# -----------------------------
st.set_page_config(page_title="jcamp029.pro", page_icon="🧾", layout="centered")
APP_TITLE = "jcamp029.pro"
APP_SUBTITLE = "Generador profesional de informes de inspección técnica (PDF)."
TZ_CL = ZoneInfo("America/Santiago")

UP_NONCE = "__uploader_nonce__"

# Tamaños (NO CAMBIO los tamaños de fotos como veníamos; solo ajusto layout para que quepa 1 página)
PHOTO_W_2COL_MM, PHOTO_H_2COL_MM = 86, 72
PHOTO_W_FULL_MM, PHOTO_H_FULL_MM = 172, 95

# Firma: mantener grande, pero ahora “se verá grande” porque recorto bordes blancos
SIGN_W_MM, SIGN_H_MM = 90, 60  # ✅ más presencia real en página sin forzar salto


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
    if UP_NONCE not in st.session_state:
        st.session_state[UP_NONCE] = 0
    defaults = get_defaults()
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def hard_reset_now():
    """Reset definitivo (incluye uploaders) preservando el tema actual."""
    current_theme = st.session_state.get(FIELD_KEYS["theme"], "Oscuro")

    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.session_state[UP_NONCE] = 1  # reset uploaders

    defaults = get_defaults()
    for k, v in defaults.items():
        st.session_state[k] = v

    st.session_state[FIELD_KEYS["theme"]] = current_theme
    st.rerun()


init_state()


# -----------------------------
# Theme CSS (oscuro legible)
# -----------------------------
def apply_theme_css(theme: str) -> None:
    if theme == "Oscuro":
        bg = "#070B14"
        fg = "#FFFFFF"
        muted = "#D6DEEA"
        card = "#0B1220"
        border = "#2A3A58"
        input_bg = "#0A1020"
        placeholder = "#9FB0C8"
        focus = "#5AA9FF"
    else:
        bg = "#FFFFFF"
        fg = "#0F172A"
        muted = "#334155"
        card = "#F8FAFC"
        border = "#E2E8F0"
        input_bg = "#FFFFFF"
        placeholder = "#64748B"
        focus = "#2563EB"

    st.markdown(
        f"""
        <style>
        .stApp {{ background: {bg}; color: {fg}; }}
        div[data-testid="stMarkdownContainer"] * {{ color: {fg} !important; }}
        div[data-testid="stWidgetLabel"] > label {{ color: {fg} !important; font-weight: 800 !important; }}
        .muted {{ color: {muted} !important; }}
        .app-card {{
            border: 1px solid {border};
            background: {card};
            border-radius: 14px;
            padding: 16px;
            margin-bottom: 16px;
        }}

        input, textarea {{
            background: {input_bg} !important;
            color: {fg} !important;
            border: 1px solid {border} !important;
        }}
        input::placeholder, textarea::placeholder {{
            color: {placeholder} !important;
            opacity: 1 !important;
        }}
        input:focus, textarea:focus {{
            border-color: {focus} !important;
            outline: none !important;
            box-shadow: 0 0 0 2px rgba(90,169,255,0.18) !important;
        }}

        div[data-baseweb="select"] > div {{
            background: {input_bg} !important;
            color: {fg} !important;
            border: 1px solid {border} !important;
        }}
        div[data-baseweb="select"] * {{ color: {fg} !important; }}

        div[data-baseweb="tag"] {{
            background: rgba(90,169,255,0.18) !important;
            border: 1px solid {border} !important;
        }}
        div[data-baseweb="tag"] * {{ color: {fg} !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------
# Text helpers
# -----------------------------
def normalize_spaces(text: str) -> str:
    text = text or ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def text_to_paragraph_html(text: str) -> str:
    t = escape((text or "").replace("\r\n", "\n").replace("\r", "\n"))
    return t.replace("\n", "<br/>").strip() if t.strip() else "—"


def trim_for_pdf(text: str, max_chars: int) -> str:
    """Recorta SOLO para PDF para ayudar a mantener 1 hoja cuando hay muchas fotos/firma."""
    t = normalize_spaces(text or "")
    if len(t) <= max_chars:
        return t
    return (t[: max_chars - 3].rstrip() + "...").strip()


def basic_spanish_fixes(text: str):
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
        "inspeccion": "inspección",
        "epp": "EPP",
    }
    for wrong, right in replacements.items():
        pattern = re.compile(rf"\b{re.escape(wrong)}\b", re.IGNORECASE)
        if pattern.search(t):
            t = pattern.sub(right, t)
            changes.append(f"'{wrong}' → '{right}'")
    if t and t[0].islower():
        t = t[0].upper() + t[1:]
        changes.append("Capitalización inicial")
    return t, changes


# -----------------------------
# Auto conclusión (corta)
# -----------------------------
def compute_auto_hash() -> str:
    d = st.session_state.get(FIELD_KEYS["disciplina"], "")
    r = st.session_state.get(FIELD_KEYS["nivel_riesgo"], "")
    h = ",".join(st.session_state.get(FIELD_KEYS["hallazgos"], []) or [])
    return f"{d}|{r}|{h}"


def generate_conclusion_short(disciplina: str, nivel_riesgo: str, hallazgos: List[str]) -> str:
    riesgo = f"Riesgo {nivel_riesgo.lower()}"
    prioridad = "inmediata" if nivel_riesgo == "Alto" else "programada" if nivel_riesgo == "Medio" else "rutinaria"
    if hallazgos:
        hall = ", ".join(hallazgos[:5])
        return f"{disciplina}: {riesgo}. Prioridad {prioridad}. Hallazgos: {hall}. Acción: corregir desviación y registrar OT."
    return f"{disciplina}: {riesgo}. Prioridad {prioridad}. Acción: mantener condición segura y registrar verificación."


def sync_auto_conclusion_if_needed():
    if not st.session_state.get(FIELD_KEYS["auto_conclusion"], True):
        return
    if st.session_state.get(FIELD_KEYS["conclusion_locked"], False):
        return

    current_hash = compute_auto_hash()
    last_hash = st.session_state.get(FIELD_KEYS["last_auto_hash"], "")

    if current_hash != last_hash or not (st.session_state.get(FIELD_KEYS["conclusion"], "").strip()):
        st.session_state[FIELD_KEYS["conclusion"]] = generate_conclusion_short(
            st.session_state.get(FIELD_KEYS["disciplina"], "Otra"),
            st.session_state.get(FIELD_KEYS["nivel_riesgo"], "Medio"),
            st.session_state.get(FIELD_KEYS["hallazgos"], []),
        )
        st.session_state[FIELD_KEYS["last_auto_hash"]] = current_hash


def apply_obs_fix():
    st.session_state[FIELD_KEYS["observaciones_raw"]] = st.session_state.get(FIELD_KEYS["obs_fixed_preview"], "")
    st.rerun()


# -----------------------------
# Image helpers
# -----------------------------
def _img_to_jpeg_cover(file_bytes: bytes, box_w_mm: float, box_h_mm: float) -> io.BytesIO:
    """COVER: rellena el cuadro recortando al centro (para fotos)."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(file_bytes)).convert("RGB"))

    box_px_w = 1800
    box_px_h = max(1, int(box_px_w * (box_h_mm / box_w_mm)))

    scale = max(box_px_w / img.width, box_px_h / img.height)
    new_w = int(img.width * scale)
    new_h = int(img.height * scale)
    img2 = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    left = (new_w - box_px_w) // 2
    top = (new_h - box_px_h) // 2
    img2 = img2.crop((left, top, left + box_px_w, top + box_px_h))

    buf = io.BytesIO()
    img2.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return buf


def _trim_signature(img: Image.Image) -> Image.Image:
    """
    ✅ Recorta márgenes blancos/transparencia de la firma para que “se vea grande”
    sin mandar todo a página 2.
    """
    if img.mode in ("RGBA", "LA"):
        bg = Image.new(img.mode, img.size, (255, 255, 255, 0))
        diff = ImageChops.difference(img, bg)
        bbox = diff.getbbox()
        return img.crop(bbox) if bbox else img

    # RGB: recorta por diferencia con blanco
    rgb = img.convert("RGB")
    bg = Image.new("RGB", rgb.size, (255, 255, 255))
    diff = ImageChops.difference(rgb, bg)
    bbox = diff.getbbox()
    return rgb.crop(bbox) if bbox else rgb


def _img_to_jpeg_signature_big(file_bytes: bytes, box_w_mm: float, box_h_mm: float) -> io.BytesIO:
    """
    Firma: recorta bordes y luego encaja (sin deformar).
    Resultado: firma MUCHO más grande visualmente.
    """
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(file_bytes)))
    img = _trim_signature(img)

    img = img.convert("RGB")
    box_px_w = 1800
    box_px_h = max(1, int(box_px_w * (box_h_mm / box_w_mm)))

    canvas_img = Image.new("RGB", (box_px_w, box_px_h), (255, 255, 255))
    img.thumbnail((box_px_w, box_px_h), Image.Resampling.LANCZOS)
    canvas_img.paste(img, ((box_px_w - img.size[0]) // 2, (box_px_h - img.size[1]) // 2))

    buf = io.BytesIO()
    canvas_img.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf


# -----------------------------
# PDF
# -----------------------------
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
    hallazgos: List[str],
    observaciones: str,
    conclusion: str,
    fotos: List[Tuple[str, bytes]],
    firma_img: Optional[Tuple[str, bytes]],
    include_firma: bool,
    include_fotos: bool,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, margin=14 * mm)

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=15, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, spaceBefore=6, spaceAfter=2)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=12)

    story: List = []
    story.append(Paragraph("INFORME TÉCNICO DE INSPECCIÓN", h1))

    data = [
        ["Fecha", fecha],
        ["Título", titulo],
        ["Disciplina", disciplina],
        ["Riesgo", nivel_riesgo],
        ["Equipo / Área", equipo],
        ["Ubicación", ubicacion],
        ["Inspector", inspector],
        ["Cargo", cargo],
        ["OT / Registro", registro_ot],
        ["Hallazgos", (", ".join(hallazgos) if hallazgos else "—")],
    ]
    t = Table(data, colWidths=[42 * mm, 130 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t)

    # Para mantener 1 página cuando hay media (fotos/firma)
    has_media = (include_fotos and bool(fotos)) or (include_firma and bool(firma_img))
    obs_pdf = trim_for_pdf(observaciones, 520 if has_media else 2000)
    con_pdf = trim_for_pdf(conclusion, 320 if has_media else 2000)

    story.append(Paragraph("Observaciones", h2))
    story.append(Paragraph(text_to_paragraph_html(obs_pdf), body))

    story.append(Paragraph("Conclusión", h2))
    story.append(Paragraph(text_to_paragraph_html(con_pdf), body))

    # ✅ Layout combinado para NO irse a página 2
    fotos_use = fotos[:3] if (include_fotos and fotos) else []
    sig_use = firma_img if (include_firma and firma_img) else None

    if fotos_use or sig_use:
        story.append(Paragraph("Imágenes", h2))

        n = len(fotos_use)

        # --- crear objetos imagen ---
        def photo_obj(b: bytes, w: float, h: float) -> RLImage:
            return RLImage(_img_to_jpeg_cover(b, w, h), width=w * mm, height=h * mm)

        def sign_obj(b: bytes) -> RLImage:
            return RLImage(_img_to_jpeg_signature_big(b, SIGN_W_MM, SIGN_H_MM),
                           width=SIGN_W_MM * mm, height=SIGN_H_MM * mm)

        # 1 foto
        if n == 1 and not sig_use:
            story.append(photo_obj(fotos_use[0][1], PHOTO_W_FULL_MM, PHOTO_H_FULL_MM))

        elif n == 1 and sig_use:
            p1 = photo_obj(fotos_use[0][1], PHOTO_W_FULL_MM, PHOTO_H_FULL_MM)
            s1 = sign_obj(sig_use[1])
            grid = Table(
                [[p1],
                 [s1]],
                colWidths=[PHOTO_W_FULL_MM * mm],
            )
            grid.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(grid)

        # 2 fotos
        elif n == 2 and not sig_use:
            p1 = photo_obj(fotos_use[0][1], PHOTO_W_2COL_MM, PHOTO_H_2COL_MM)
            p2 = photo_obj(fotos_use[1][1], PHOTO_W_2COL_MM, PHOTO_H_2COL_MM)
            grid = Table([[p1, p2]], colWidths=[PHOTO_W_2COL_MM * mm, PHOTO_W_2COL_MM * mm])
            grid.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(grid)

        elif n == 2 and sig_use:
            p1 = photo_obj(fotos_use[0][1], PHOTO_W_2COL_MM, PHOTO_H_2COL_MM)
            p2 = photo_obj(fotos_use[1][1], PHOTO_W_2COL_MM, PHOTO_H_2COL_MM)
            s1 = sign_obj(sig_use[1])
            grid = Table(
                [
                    [p1, p2],
                    [s1, ""],  # firma abajo ocupando “visual” sin empujar a página 2
                ],
                colWidths=[PHOTO_W_2COL_MM * mm, PHOTO_W_2COL_MM * mm],
            )
            grid.setStyle(TableStyle([
                ("SPAN", (0, 1), (1, 1)),  # ✅ firma ocupa las 2 columnas
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 1), (1, 1), "LEFT"),
            ]))
            story.append(grid)

        # 3 fotos
        elif n == 3 and not sig_use:
            p1 = photo_obj(fotos_use[0][1], PHOTO_W_2COL_MM, PHOTO_H_2COL_MM)
            p2 = photo_obj(fotos_use[1][1], PHOTO_W_2COL_MM, PHOTO_H_2COL_MM)
            p3 = photo_obj(fotos_use[2][1], PHOTO_W_2COL_MM, PHOTO_H_2COL_MM)
            grid = Table(
                [[p1, p2],
                 [p3, ""]],
                colWidths=[PHOTO_W_2COL_MM * mm, PHOTO_W_2COL_MM * mm],
            )
            grid.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(grid)

        else:  # n == 3 and sig_use
            p1 = photo_obj(fotos_use[0][1], PHOTO_W_2COL_MM, PHOTO_H_2COL_MM)
            p2 = photo_obj(fotos_use[1][1], PHOTO_W_2COL_MM, PHOTO_H_2COL_MM)
            p3 = photo_obj(fotos_use[2][1], PHOTO_W_2COL_MM, PHOTO_H_2COL_MM)
            s1 = sign_obj(sig_use[1])

            # ✅ 2x2: abajo va foto3 + firma lado a lado -> se queda en 1 página
            grid = Table(
                [[p1, p2],
                 [p3, s1]],
                colWidths=[PHOTO_W_2COL_MM * mm, PHOTO_W_2COL_MM * mm],
            )
            grid.setStyle(TableStyle([
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ]))
            story.append(grid)

    doc.build(story)
    return buffer.getvalue()


# -----------------------------
# UI
# -----------------------------
st.markdown(f"<h1>{APP_TITLE}</h1><p class='muted'>{APP_SUBTITLE}</p>", unsafe_allow_html=True)

st.radio("Tema", ["Claro", "Oscuro"], horizontal=True, key=FIELD_KEYS["theme"])
apply_theme_css(st.session_state[FIELD_KEYS["theme"]])

# Barra de controles + limpiar
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns([1, 1, 1, 1.2])
with c1:
    st.checkbox("Firma", key=FIELD_KEYS["include_signature"])
with c2:
    st.checkbox("Fotos", key=FIELD_KEYS["include_photos"])
with c3:
    st.checkbox("Corrección", key=FIELD_KEYS["show_correccion"])
with c4:
    if st.button("🧹 Limpiar formulario", use_container_width=True):
        hard_reset_now()
st.markdown("</div>", unsafe_allow_html=True)

# Datos
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
st.text_input("Fecha", key=FIELD_KEYS["fecha"])
st.text_input("Título", key=FIELD_KEYS["titulo"])

cA, cB = st.columns(2)
with cA:
    st.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Instrumental", "Civil", "Otra"], key=FIELD_KEYS["disciplina"])
    st.text_input("Equipo / Área", key=FIELD_KEYS["equipo"])
    st.text_input("Inspector", key=FIELD_KEYS["inspector"])
with cB:
    st.selectbox("Nivel de riesgo", ["Bajo", "Medio", "Alto"], key=FIELD_KEYS["nivel_riesgo"])
    st.text_input("Ubicación", key=FIELD_KEYS["ubicacion"])
    st.text_input("Cargo", key=FIELD_KEYS["cargo"])

st.text_input("N° Registro / OT", key=FIELD_KEYS["registro_ot"])
st.multiselect("Hallazgos", ["Condición insegura", "Orden y limpieza", "LOTO", "Tableros", "Otros"], key=FIELD_KEYS["hallazgos"])

st.text_area("Observaciones", height=130, key=FIELD_KEYS["observaciones_raw"])

# Corrección
if st.session_state[FIELD_KEYS["show_correccion"]]:
    if st.button("Sugerir correcciones"):
        fixed, changes = basic_spanish_fixes(st.session_state[FIELD_KEYS["observaciones_raw"]])
        st.session_state[FIELD_KEYS["obs_fixed_preview"]] = fixed
        if changes:
            st.info("Sugerencias: " + ", ".join(changes))
    if st.session_state.get(FIELD_KEYS["obs_fixed_preview"], "").strip():
        st.text_area("Sugerencia", key=FIELD_KEYS["obs_fixed_preview"], height=90)
        st.button("Aplicar sugerencias", on_click=apply_obs_fix)

# Auto-conclusión SIN pisar manual
st.checkbox("Auto-conclusión", key=FIELD_KEYS["auto_conclusion"])
sync_auto_conclusion_if_needed()

cX, cY = st.columns(2)
with cX:
    if st.button("🔁 Regenerar conclusión (auto)", use_container_width=True):
        st.session_state[FIELD_KEYS["conclusion_locked"]] = False
        st.session_state[FIELD_KEYS["last_auto_hash"]] = ""
        sync_auto_conclusion_if_needed()
        st.rerun()
with cY:
    if st.button("✍️ Dejar conclusión manual", use_container_width=True):
        st.session_state[FIELD_KEYS["conclusion_locked"]] = True
        st.rerun()

st.text_area("Conclusión", height=140, key=FIELD_KEYS["conclusion"])
st.markdown("</div>", unsafe_allow_html=True)

# Archivos
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
nonce = st.session_state[UP_NONCE]

fotos_files = (
    st.file_uploader("Fotos (Máx 3)", type=["jpg", "png"], accept_multiple_files=True, key=f"f_{nonce}")
    if st.session_state[FIELD_KEYS["include_photos"]]
    else None
)
firma_file = (
    st.file_uploader("Firma", type=["jpg", "png"], key=f"s_{nonce}")
    if st.session_state[FIELD_KEYS["include_signature"]]
    else None
)
st.markdown("</div>", unsafe_allow_html=True)

# Generación
if st.button("Generar PDF Profesional ✅", use_container_width=True):
    fotos: List[Tuple[str, bytes]] = [(f.name, f.read()) for f in (fotos_files or [])[:3]]
    firma: Optional[Tuple[str, bytes]] = (firma_file.name, firma_file.read()) if firma_file else None

    pdf = build_pdf(
        st.session_state[FIELD_KEYS["titulo"]],
        st.session_state[FIELD_KEYS["fecha"]],
        st.session_state[FIELD_KEYS["equipo"]],
        st.session_state[FIELD_KEYS["ubicacion"]],
        st.session_state[FIELD_KEYS["inspector"]],
        st.session_state[FIELD_KEYS["cargo"]],
        st.session_state[FIELD_KEYS["registro_ot"]],
        st.session_state[FIELD_KEYS["disciplina"]],
        st.session_state[FIELD_KEYS["nivel_riesgo"]],
        st.session_state[FIELD_KEYS["hallazgos"]],
        st.session_state[FIELD_KEYS["observaciones_raw"]],
        st.session_state[FIELD_KEYS["conclusion"]],
        fotos,
        firma,
        st.session_state[FIELD_KEYS["include_signature"]],
        st.session_state[FIELD_KEYS["include_photos"]],
    )

    st.download_button(
        "Descargar Informe",
        data=pdf,
        file_name=f"informe_{datetime.now(TZ_CL).strftime('%H%M%S')}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

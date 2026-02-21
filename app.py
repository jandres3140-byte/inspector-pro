import io
import re
from datetime import datetime
from typing import Optional, List, Tuple

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

# Tamaños solicitados
PHOTO_W_MM, PHOTO_H_MM = 80, 55
SIGN_W_MM, SIGN_H_MM = 60, 60


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
    "conclusion_locked": "conclusion_locked",  # NUEVO: evita que el auto mode pise lo manual
    "last_auto_hash": "last_auto_hash",        # NUEVO: para saber si cambió el input que genera conclusión
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
    """
    Reset definitivo del formulario preservando el tema visual.
    Limpia uploaders usando nonce.
    """
    current_theme = st.session_state.get(FIELD_KEYS["theme"], "Oscuro")

    # limpiar todo
    for key in list(st.session_state.keys()):
        del st.session_state[key]

    # nonce para resetear uploaders
    st.session_state[UP_NONCE] = 1

    # defaults
    defaults = get_defaults()
    for k, v in defaults.items():
        st.session_state[k] = v

    # restaurar tema
    st.session_state[FIELD_KEYS["theme"]] = current_theme

    st.rerun()


init_state()


# -----------------------------
# Helpers UI / CSS
# -----------------------------
def apply_theme_css(theme: str) -> None:
    if theme == "Oscuro":
        bg = "#070B14"
        fg = "#FFFFFF"
        muted = "#D6DEEA"
        card = "#0B1220"
        border = "#2A3A58"
        input_bg = "#0A1020"
        input_fg = "#FFFFFF"
        placeholder = "#9FB0C8"
        focus = "#5AA9FF"
    else:
        bg = "#FFFFFF"
        fg = "#0F172A"
        muted = "#334155"
        card = "#FFFFFF"
        border = "#E2E8F0"
        input_bg = "#FFFFFF"
        input_fg = "#0F172A"
        placeholder = "#64748B"
        focus = "#2563EB"

    st.markdown(
        f"""
        <style>
        .stApp {{
            background: {bg};
            color: {fg};
        }}

        /* texto general */
        div[data-testid="stMarkdownContainer"] * {{
            color: {fg} !important;
        }}

        /* labels */
        div[data-testid="stWidgetLabel"] > label {{
            color: {fg} !important;
            font-weight: 800 !important;
        }}

        /* cards */
        .app-card {{
            border: 1px solid {border};
            background: {card};
            border-radius: 14px;
            padding: 16px;
            margin-bottom: 16px;
        }}
        .muted {{ color: {muted} !important; }}

        /* inputs/textarea */
        input, textarea {{
            background: {input_bg} !important;
            color: {input_fg} !important;
            border: 1px solid {border} !important;
        }}
        input::placeholder, textarea::placeholder {{
            color: {placeholder} !important;
            opacity: 1 !important;
        }}
        input:focus, textarea:focus {{
            border-color: {focus} !important;
            outline: none !important;
            box-shadow: 0 0 0 2px rgba(90,169,255,0.20) !important;
        }}

        /* select (baseweb) - fuerza color del texto y fondo */
        div[data-baseweb="select"] > div {{
            background: {input_bg} !important;
            color: {input_fg} !important;
            border: 1px solid {border} !important;
        }}
        div[data-baseweb="select"] * {{
            color: {input_fg} !important;
        }}

        /* multiselect chips / tags */
        div[data-baseweb="tag"] {{
            background: rgba(90,169,255,0.18) !important;
            border: 1px solid {border} !important;
        }}
        div[data-baseweb="tag"] * {{
            color: {input_fg} !important;
        }}

        /* botones */
        button[kind="primary"] {{
            border-radius: 12px !important;
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
    t = escape((text or "").replace("\r\n", "\n").replace("\r", "\n"))
    return t.replace("\n", "<br/>").strip() if t.strip() else "—"


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


def generate_conclusion_short(disciplina: str, nivel_riesgo: str, hallazgos: List[str]) -> str:
    # Conclusión breve, técnica, sin “plazo sugerido”
    riesgo = f"Riesgo {nivel_riesgo.lower()}"
    prioridad = "inmediata" if nivel_riesgo == "Alto" else "programada" if nivel_riesgo == "Medio" else "rutinaria"

    if hallazgos:
        hall = ", ".join(hallazgos[:4])
        return f"{disciplina}: {riesgo}. Prioridad {prioridad}. Hallazgos: {hall}. Acción: corregir desviación y registrar OT."
    return f"{disciplina}: {riesgo}. Prioridad {prioridad}. Acción: mantener condición segura y registrar verificación."


def _thumb_jpeg_fixed_box(file_bytes: bytes, box_w_mm: float, box_h_mm: float) -> io.BytesIO:
    """
    Encaja la imagen dentro de un rectángulo (mm) sin deformar, centrada.
    Convierte a JPG.
    """
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(file_bytes)).convert("RGB"))

    # relación del box para crear un canvas en px consistente
    box_px_w = 1200
    box_px_h = max(1, int(box_px_w * (box_h_mm / box_w_mm)))

    canvas_img = Image.new("RGB", (box_px_w, box_px_h), (255, 255, 255))
    img.thumbnail((box_px_w, box_px_h))
    canvas_img.paste(img, ((box_px_w - img.size[0]) // 2, (box_px_h - img.size[1]) // 2))

    buf = io.BytesIO()
    canvas_img.save(buf, format="JPEG", quality=85)
    buf.seek(0)
    return buf


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
    doc = SimpleDocTemplate(buffer, pagesize=A4, margin=18 * mm)

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=13)

    def header_footer(c, d):
        c.saveState()
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.grey)
        c.drawString(18 * mm, 10 * mm, f"{APP_TITLE} · {datetime.now(TZ_CL).strftime('%d-%m-%Y')}")
        c.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Página {c.getPageNumber()}")
        c.restoreState()

    story = []
    story.append(Paragraph("INFORME TÉCNICO DE INSPECCIÓN", h1))
    story.append(Spacer(1, 8))

    data = [
        ["Fecha", fecha],
        ["Título", titulo],
        ["Disciplina", disciplina],
        ["Riesgo", nivel_riesgo],
        ["Equipo", equipo],
        ["Ubicación", ubicacion],
        ["Inspector", inspector],
        ["Cargo", cargo],
        ["OT", registro_ot],
    ]

    t = Table(data, colWidths=[40 * mm, 130 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTSIZE", (0, 0), (0, -1), 9),
            ]
        )
    )
    story.append(t)

    story.append(Paragraph("Observaciones", h2))
    story.append(Paragraph(text_to_paragraph_html(observaciones), body))

    story.append(Paragraph("Conclusión", h2))
    story.append(Paragraph(text_to_paragraph_html(conclusion), body))

    # Imágenes (máx 3) - 80x55 mm
    if include_fotos and fotos:
        story.append(Paragraph("Imágenes", h2))

        imgs = []
        for f in fotos[:3]:
            imgs.append(
                RLImage(
                    _thumb_jpeg_fixed_box(f[1], PHOTO_W_MM, PHOTO_H_MM),
                    width=PHOTO_W_MM * mm,
                    height=PHOTO_H_MM * mm,
                )
            )

        # si vienen 3, las ponemos en 2 filas: 2 arriba, 1 abajo centrada
        if len(imgs) == 1:
            it = Table([[imgs[0]]])
        elif len(imgs) == 2:
            it = Table([[imgs[0], imgs[1]]], colWidths=[PHOTO_W_MM * mm, PHOTO_W_MM * mm])
        else:
            it = Table(
                [
                    [imgs[0], imgs[1]],
                    [imgs[2], ""],
                ],
                colWidths=[PHOTO_W_MM * mm, PHOTO_W_MM * mm],
            )

        it.hAlign = "CENTER"
        it.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(it)

    # Firma al final - 60x60 mm (sin título para que quede limpio)
    if include_firma and firma_img:
        story.append(Spacer(1, 10))
        story.append(
            RLImage(
                _thumb_jpeg_fixed_box(firma_img[1], SIGN_W_MM, SIGN_H_MM),
                width=SIGN_W_MM * mm,
                height=SIGN_H_MM * mm,
            )
        )

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return buffer.getvalue()


def apply_obs_fix():
    st.session_state[FIELD_KEYS["observaciones_raw"]] = st.session_state.get(FIELD_KEYS["obs_fixed_preview"], "")
    st.rerun()


def compute_auto_hash() -> str:
    # si cambia disciplina/riesgo/hallazgos => cambia el hash
    d = st.session_state.get(FIELD_KEYS["disciplina"], "")
    r = st.session_state.get(FIELD_KEYS["nivel_riesgo"], "")
    h = ",".join(st.session_state.get(FIELD_KEYS["hallazgos"], []) or [])
    return f"{d}|{r}|{h}"


def sync_auto_conclusion_if_needed():
    """
    Auto-conclusión SIN pisar lo manual:
    - Si auto_conclusion está activo y no está locked, se actualiza cuando cambia el hash.
    - Si el usuario escribe manual (detectable porque desactivó auto o apretó botón), se lockea.
    """
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


# -----------------------------
# UI RENDERING
# -----------------------------
st.markdown(f"<h1>{APP_TITLE}</h1><p class='muted'>{APP_SUBTITLE}</p>", unsafe_allow_html=True)
st.radio("Tema", ["Claro", "Oscuro"], horizontal=True, key=FIELD_KEYS["theme"])
apply_theme_css(st.session_state[FIELD_KEYS["theme"]])

# Configuración y Limpieza
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
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
        st.session_state[FIELD_KEYS["obs_fixed_preview"]] = fixed
        if changes:
            st.info(f"Sugerencias: {', '.join(changes)}")
    if st.session_state.get(FIELD_KEYS["obs_fixed_preview"], "").strip():
        st.text_area("Sugerencia", key=FIELD_KEYS["obs_fixed_preview"])
        st.button("Aplicar sugerencias", on_click=apply_obs_fix)

# Auto conclusión + control
st.checkbox("Auto-conclusión", key=FIELD_KEYS["auto_conclusion"])

# sincroniza solo cuando corresponde y SIN pisar manual
sync_auto_conclusion_if_needed()

# Botón para volver a autogenerar (y desbloquear)
cA, cB = st.columns([1, 1])
with cA:
    if st.button("🔁 Regenerar conclusión (auto)", use_container_width=True):
        st.session_state[FIELD_KEYS["conclusion_locked"]] = False
        st.session_state[FIELD_KEYS["last_auto_hash"]] = ""  # fuerza regeneración
        sync_auto_conclusion_if_needed()
        st.rerun()
with cB:
    if st.button("✍️ Dejar conclusión manual", use_container_width=True):
        st.session_state[FIELD_KEYS["conclusion_locked"]] = True
        st.rerun()

st.text_area("Conclusión", height=150, key=FIELD_KEYS["conclusion"])
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

# ayuda visual
st.caption(f"📸 Fotos: {PHOTO_W_MM}×{PHOTO_H_MM} mm · ✒️ Firma: {SIGN_W_MM}×{SIGN_H_MM} mm")
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

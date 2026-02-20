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
    # ✅ Reset definitivo (incluye uploaders siempre)
    st.session_state.clear()
    # Reinyecta defaults
    defaults = get_defaults()
    for k, v in defaults.items():
        st.session_state[k] = v
    st.rerun()


init_state()


# -----------------------------
# Helpers UI / CSS
# -----------------------------
def apply_theme_css(theme: str) -> None:
    if theme == "Oscuro":
        bg = "#070B14"
        fg = "#FFFFFF"
        muted = "#D0D7E2"
        card = "#0B1220"
        border = "#263247"
        input_bg = "#070B14"
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
        div[data-testid="stMarkdownContainer"] * {{
            color: {fg} !important;
        }}
        div[data-testid="stWidgetLabel"] > label {{
            color: {fg} !important;
            font-weight: 700 !important;
        }}
        input, textarea {{
            background: {input_bg} !important;
            color: {fg} !important;
            border: 1px solid {border} !important;
            caret-color: {fg} !important;
        }}
        div[data-baseweb="select"] > div {{
            background: {input_bg} !important;
            color: {fg} !important;
            border: 1px solid {border} !important;
        }}
        [data-baseweb="checkbox"] span, [data-baseweb="radio"] span {{
            color: {fg} !important;
            font-weight: 600 !important;
        }}
        [data-testid="stFileUploader"] * {{
            color: {fg} !important;
        }}
        .stButton>button {{
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
# Conclusión PRO
# -----------------------------
def generate_conclusion_pro(
    disciplina: str,
    nivel_riesgo: str,
    hallazgos: List[str],
    observaciones: str,
) -> str:
    hall = ", ".join(hallazgos) if hallazgos else "Sin hallazgos críticos declarados"

    if nivel_riesgo == "Bajo":
        riesgo = "Riesgo bajo"
        prioridad = "Prioridad: rutinaria"
    elif nivel_riesgo == "Medio":
        riesgo = "Riesgo medio"
        prioridad = "Prioridad: programada"
    else:
        riesgo = "Riesgo alto"
        prioridad = "Prioridad: inmediata"

    if disciplina == "Eléctrica":
        soporte = (
            "Foco técnico: condición de canalizaciones, luminarias/enchufes, integridad de tableros, señalización y control de energías (LOTO)."
        )
        acciones = (
            "Acción recomendada: corregir condición insegura, asegurar fijaciones/cierres, normalizar orden/aseo del área y dejar registro OT."
        )
        verif = "Verificación: inspección visual final + control funcional básico según procedimiento."
    elif disciplina == "Mecánica":
        soporte = (
            "Foco técnico: resguardos, fijaciones, partes móviles, ruidos/vibración y condición de seguridad operacional."
        )
        acciones = "Acción recomendada: asegurar condición segura, corregir desviación y registrar OT."
        verif = "Verificación: prueba operativa controlada + checklist de seguridad."
    else:
        soporte = "Foco técnico: condición segura, integridad de componentes, orden/limpieza y cumplimiento del estándar."
        acciones = "Acción recomendada: corregir desviación y registrar OT."
        verif = "Verificación: revisión final y registro fotográfico."

    conclusion = (
        f"Conclusión ({disciplina}): {riesgo}. {prioridad}.\n"
        f"- Hallazgos: {hall}.\n"
        f"- {soporte}\n"
        f"- {acciones}\n"
        f"- {verif}"
    )
    return conclusion


# -----------------------------
# PDF helpers (miniaturas iguales SIN casilleros)
# -----------------------------
def _thumb_jpeg_fixed_box(file_bytes: bytes, box_w_mm: float, box_h_mm: float) -> io.BytesIO:
    """
    Miniatura con caja fija (letterbox blanco) para que TODAS queden iguales.
    Retorna buffer JPEG listo para RLImage.
    """
    img = Image.open(io.BytesIO(file_bytes))
    img = ImageOps.exif_transpose(img)

    # Aplanar transparencias
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1])
        img = bg
    else:
        img = img.convert("RGB")

    # Caja final en px (simple y estable)
    box_px_w = 900
    box_px_h = int(box_px_w * ((box_h_mm * mm) / (box_w_mm * mm)))

    canvas_img = Image.new("RGB", (box_px_w, box_px_h), (255, 255, 255))
    img.thumbnail((box_px_w, box_px_h))
    x = (box_px_w - img.size[0]) // 2
    y = (box_px_h - img.size[1]) // 2
    canvas_img.paste(img, (x, y))

    buf = io.BytesIO()
    canvas_img.save(buf, format="JPEG", quality=85, optimize=True)
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
    fotos: List[Tuple[str, bytes]],          # máx 3
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
    h1 = ParagraphStyle("h1_custom", parent=styles["Heading1"], fontSize=16, leading=18, spaceAfter=10)
    h2 = ParagraphStyle("h2_custom", parent=styles["Heading2"], fontSize=12, leading=14, spaceBefore=10, spaceAfter=6)
    body = ParagraphStyle("body_custom", parent=styles["BodyText"], fontSize=10, leading=13)
    muted = ParagraphStyle("muted_custom", parent=styles["BodyText"], fontSize=9, leading=12, textColor=colors.grey)

    def header_footer(c: canvas.Canvas, d):
        c.saveState()
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.grey)
        now_cl = datetime.now(TZ_CL).strftime("%d-%m-%Y %H:%M")
        c.drawString(18 * mm, 10 * mm, f"{APP_TITLE} · Generado {now_cl}")
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

    # ✅ Imágenes: 1–3, todas miniatura igual, SIN casilleros vacíos, centradas
    if include_fotos and fotos:
        story.append(Paragraph("Imágenes", h2))

        box_w_mm = 55
        box_h_mm = 35
        imgs: List[RLImage] = []

        for _, fbytes in fotos[:3]:
            try:
                buf = _thumb_jpeg_fixed_box(fbytes, box_w_mm, box_h_mm)
                im = RLImage(buf, width=box_w_mm * mm, height=box_h_mm * mm)
                im.hAlign = "CENTER"
                imgs.append(im)
            except Exception:
                story.append(Paragraph("Una imagen no pudo ser procesada.", muted))

        if imgs:
            # Tabla con EXACTAMENTE N columnas (no se dibujan bordes, no hay “casilleros”)
            img_table = Table([imgs], colWidths=[box_w_mm * mm] * len(imgs))
            img_table.hAlign = "CENTER"
            img_table.setStyle(
                TableStyle(
                    [
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        # ❌ sin BOX / sin INNERGRID
                    ]
                )
            )
            story.append(img_table)
            story.append(Spacer(1, 10))

    # ✅ Firma centrada (solo imagen, sin repetir nombre/cargo)
    if include_firma and firma_img:
        story.append(Paragraph("Firma", h2))
        try:
            buf = _thumb_jpeg_fixed_box(firma_img[1], 55, 18)
            sig = RLImage(buf, width=55 * mm, height=18 * mm)
            sig.hAlign = "CENTER"  # 🔥 esto la centra sí o sí
            story.append(sig)
            story.append(Spacer(1, 8))
        except Exception:
            story.append(Paragraph("No fue posible procesar la imagen de firma.", muted))
            story.append(Spacer(1, 8))

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# -----------------------------
# Callbacks
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

st.radio("Tema", ["Claro", "Oscuro"], horizontal=True, key=FIELD_KEYS["theme"])
apply_theme_css(st.session_state[FIELD_KEYS["theme"]])

# Config
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
st.subheader("Configuración del informe")

c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
with c1:
    st.checkbox("Incluir firma", key=FIELD_KEYS["include_signature"])
with c2:
    st.checkbox("Incluir imágenes", key=FIELD_KEYS["include_photos"])
with c3:
    st.checkbox("Mostrar corrección básica", key=FIELD_KEYS["show_correccion"])
with c4:
    st.button("🧹 Limpiar formulario", on_click=reset_form)

st.markdown("</div>", unsafe_allow_html=True)

# Datos
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

# Corrección
if st.session_state[FIELD_KEYS["show_correccion"]]:
    st.markdown("<hr/>", unsafe_allow_html=True)
    st.markdown("<p class='muted'><b>Corrección básica:</b> sugerencias simples (tú decides aplicar).</p>", unsafe_allow_html=True)

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

# Conclusión
st.markdown("<hr/>", unsafe_allow_html=True)
st.checkbox("Auto-actualizar conclusión", key=FIELD_KEYS["auto_conclusion"])

auto_conc = generate_conclusion_pro(
    st.session_state[FIELD_KEYS["disciplina"]],
    st.session_state[FIELD_KEYS["nivel_riesgo"]],
    st.session_state[FIELD_KEYS["hallazgos"]],
    st.session_state[FIELD_KEYS["observaciones_raw"]],
)

if st.session_state[FIELD_KEYS["auto_conclusion"]]:
    st.session_state[FIELD_KEYS["conclusion"]] = auto_conc
elif not st.session_state.get(FIELD_KEYS["conclusion"]):
    st.session_state[FIELD_KEYS["conclusion"]] = auto_conc

st.text_area("Conclusión (editable)", height=170, key=FIELD_KEYS["conclusion"])

st.markdown("</div>", unsafe_allow_html=True)

# Imágenes y firma
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
st.subheader("Imágenes y firma")

fotos_files = None
firma_file = None

if st.session_state[FIELD_KEYS["include_photos"]]:
    fotos_files = st.file_uploader(
        "Subir imágenes (máximo 3) — todas se verán como miniatura del mismo tamaño",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )

if st.session_state[FIELD_KEYS["include_signature"]]:
    firma_file = st.file_uploader(
        "Firma (imagen JPG/PNG) — opcional",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=False,
    )

st.markdown("</div>", unsafe_allow_html=True)

# PDF
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
st.subheader("Generación de PDF")

if st.button("Generar PDF Profesional ✅"):
    fotos: List[Tuple[str, bytes]] = []
    if st.session_state[FIELD_KEYS["include_photos"]] and fotos_files:
        if len(fotos_files) > 3:
            st.warning("Subiste más de 3 imágenes. Se usarán solo las primeras 3.")
        for f in fotos_files[:3]:
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

    filename = f"informe_inspeccion_{datetime.now(TZ_CL).strftime('%Y%m%d_%H%M')}.pdf"
    st.success("PDF generado 🎉")
    st.download_button(
        "Descargar PDF",
        data=pdf_bytes,
        file_name=filename,
        mime="application/pdf",
    )

st.markdown("</div>", unsafe_allow_html=True)

st.caption("Tip: si editas el código, Streamlit se recarga solo. Para detener: CTRL + C en la consola.")

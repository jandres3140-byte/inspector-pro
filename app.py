# app.py
import io
import re
from datetime import datetime, date
from typing import List, Optional, Tuple

import streamlit as st
from PIL import Image as PILImage

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
    KeepTogether,
)
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.utils import ImageReader


# -----------------------------
# UI Config
# -----------------------------
st.set_page_config(page_title="jcamp029.pro", page_icon="🧾", layout="centered")
st.markdown("""
<style>

/* Fondo general */
.stApp {
    background: radial-gradient(1200px 600px at 20% 0%, #0b1a33 0%, #05070d 55%, #000 100%);
}

/* ✅ Labels (ESTO ES LO IMPORTANTE) */
label {
    color: white !important;
    font-weight: 500;
}

/* Textos normales */
.stMarkdown, .stText, .stCaption {
    color: white !important;
}

/* Inputs */
div[data-baseweb="input"] input {
    background-color: #05070d !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
}

/* Textarea */
div[data-baseweb="textarea"] textarea {
    background-color: #05070d !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
}

/* Selectbox */
div[data-baseweb="select"] > div {
    background-color: #05070d !important;
    color: white !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
}

</style>
""", unsafe_allow_html=True)

# CSS oscuro (alto contraste)
st.markdown(
    """
    <style>
      .stApp { background: radial-gradient(1200px 600px at 20% 0%, #0b1a33 0%, #05070d 55%, #000 100%); }
      h1,h2,h3,h4 { color: #f5f5f5; }
      label, .stMarkdown, .stText, .stCaption { color: #eaeaea !important; }
      div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea {
        background-color: #05070d !important;
        color: #f5f5f5 !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
      }
      div[data-baseweb="select"] > div {
        background-color: #05070d !important;
        color: #f5f5f5 !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
      }
      .stCheckbox, .stRadio, .stSelectbox { color: #f5f5f5 !important; }
      .block-container { padding-top: 1.2rem; }
      .stButton button { border-radius: 12px; padding: 0.6rem 1.0rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Informe Técnico de Inspección")


# -----------------------------
# Helpers
# -----------------------------
def _clean_text(s: str) -> str:
    s = s or ""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _basic_spelling_fix_es(text: str) -> str:
    """
    Corrección MUY básica (sin IA): tildes comunes, mayúsculas iniciales, espacios.
    """
    t = (text or "").strip()
    t = re.sub(r"\s+", " ", t)

    # correcciones típicas
    replacements = {
        "demasciado": "demasiado",
        "profecional": "profesional",
        "inspeccion": "inspección",
        "mecanico": "mecánico",
        "electrico": "eléctrico",
        "conclucion": "conclusión",
        "observacion": "observación",
        "ubicacion": "ubicación",
        "critico": "crítico",
        "tecnico": "técnico",
        "sugerido": "sugerido",
        "plazo": "plazo",
    }
    def repl_word(m):
        w = m.group(0)
        lw = w.lower()
        if lw in replacements:
            # respeta capitalización inicial
            fixed = replacements[lw]
            if w[:1].isupper():
                fixed = fixed[:1].upper() + fixed[1:]
            return fixed
        return w

    t = re.sub(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]+", repl_word, t)

    # mayúscula inicial si corresponde
    if t:
        t = t[0].upper() + t[1:]
    return t


def pil_to_png_bytes(pil_img: PILImage.Image) -> bytes:
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()


def read_uploaded_image(upload) -> PILImage.Image:
    # Acepta st.file_uploader (UploadedFile)
    img = PILImage.open(upload).convert("RGB")
    return img


def make_thumbnail(img: PILImage.Image, max_px: int = 900) -> PILImage.Image:
    """
    Reduce imágenes grandes para que el PDF no pese mucho.
    """
    out = img.copy()
    out.thumbnail((max_px, max_px))
    return out


# -----------------------------
# PDF Drawing (header/footer)
# -----------------------------
def _draw_header_footer(c: rl_canvas.Canvas, doc, title: str):
    c.saveState()
    w, h = A4

    # Header line
    c.setStrokeColor(colors.HexColor("#999999"))
    c.setLineWidth(0.5)
    c.line(15 * mm, h - 15 * mm, w - 15 * mm, h - 15 * mm)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#111111"))
    c.drawString(15 * mm, h - 12 * mm, _clean_text(title)[:70])

    # Footer
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#555555"))
    c.drawString(15 * mm, 10 * mm, f"Generado: {datetime.now().strftime('%d-%m-%Y %H:%M')}")
    c.drawRightString(w - 15 * mm, 10 * mm, f"Página {doc.page}")

    c.restoreState()


def build_pdf_bytes(
    data: dict,
    include_photos: bool,
    include_signature: bool,
    basic_fix: bool,
    photo_uploads: List,
    signature_upload,
) -> bytes:
    buf = io.BytesIO()

    # Márgenes
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=15 * mm,
        title=_clean_text(data.get("titulo", "Informe")),
        author=_clean_text(data.get("inspector", "")),
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="H",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            spaceAfter=6,
            textColor=colors.HexColor("#111111"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="P",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            spaceAfter=4,
            textColor=colors.HexColor("#111111"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="Small",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            spaceAfter=3,
            textColor=colors.HexColor("#111111"),
        )
    )

    def P(text: str) -> Paragraph:
        t = text or ""
        if basic_fix:
            t = _basic_spelling_fix_es(t)
        # escape mínimo para reportlab Paragraph
        t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        t = t.replace("\n", "<br/>")
        return Paragraph(t, styles["P"])

    story = []

    # Encabezado / resumen
    story.append(Paragraph("Datos del informe", styles["H"]))

    info_rows = [
        ["Fecha", data.get("fecha", "")],
        ["Título", data.get("titulo", "")],
        ["Disciplina", data.get("disciplina", "")],
        ["Equipo / Área inspeccionada", data.get("equipo", "")],
        ["Ubicación", data.get("ubicacion", "")],
        ["Inspector", data.get("inspector", "")],
        ["Cargo", data.get("cargo", "")],
        ["N° Registro / OT", data.get("ot", "")],
        ["Nivel de riesgo", data.get("riesgo", "")],
    ]
    # Limpieza
    info_rows = [[_clean_text(a), _clean_text(b)] for a, b in info_rows]

    t = Table(info_rows, colWidths=[45 * mm, 125 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111111")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                ("ROWBACKGROUNDS", (1, 0), (1, -1), [colors.white, colors.HexColor("#fbfbfb")]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 6 * mm))

    # Hallazgos
    story.append(Paragraph("Hallazgos", styles["H"]))
    hallazgos = data.get("hallazgos", [])
    if hallazgos:
        story.append(P("• " + "\n• ".join([_clean_text(x) for x in hallazgos])))
    else:
        story.append(P("Sin hallazgos marcados."))
    story.append(Spacer(1, 4 * mm))

    # Observaciones técnicas
    story.append(Paragraph("Observaciones técnicas", styles["H"]))
    obs = data.get("observaciones", "").strip()
    if obs:
        story.append(P(obs))
    else:
        story.append(P("Sin observaciones registradas."))
    story.append(Spacer(1, 4 * mm))

    # Conclusión (más corta)
    story.append(Paragraph("Conclusión", styles["H"]))
    concl = data.get("conclusion", "").strip()
    if concl:
        story.append(P(concl))
    else:
        story.append(P("Conclusión no registrada."))
    story.append(Spacer(1, 6 * mm))

    # -----------------------------
    # Fotos (hasta 3) + Firma al final
    # Requisito: firma DESPUÉS de las imágenes y solo pasar a 2da hoja si es necesario.
    # Solución: KeepTogether con bloque (fotos + firma). Si no cabe, salta todo junto.
    # -----------------------------
    end_block = []

    if include_photos:
        end_block.append(Paragraph("Registro fotográfico", styles["H"]))

        uploads = photo_uploads[:3] if photo_uploads else []
        if uploads:
            # Querías la imagen a 1/4 aprox del tamaño anterior:
            # usamos miniaturas y un ancho fijo pequeño.
            max_w = 55 * mm  # pequeño; caben hasta 3
            max_h = 55 * mm

            imgs = []
            for up in uploads:
                pil = make_thumbnail(read_uploaded_image(up), max_px=900)
                png = pil_to_png_bytes(pil)
                rl_img = RLImage(io.BytesIO(png))
                rl_img._restrictSize(max_w, max_h)
                imgs.append(rl_img)

            # Tabla 1 fila, hasta 3 columnas
            row = imgs + [""] * (3 - len(imgs))
            photos_tbl = Table([row], colWidths=[60 * mm, 60 * mm, 60 * mm])
            photos_tbl.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dddddd")),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            end_block.append(photos_tbl)
            end_block.append(Spacer(1, 6 * mm))
        else:
            end_block.append(P("Sin fotografías adjuntas."))
            end_block.append(Spacer(1, 6 * mm))

    if include_signature:
        end_block.append(Paragraph("Firma", styles["H"]))
        if signature_upload is not None:
            sig_pil = make_thumbnail(read_uploaded_image(signature_upload), max_px=700)
            sig_png = pil_to_png_bytes(sig_pil)

            sig_img = RLImage(io.BytesIO(sig_png))
            sig_img._restrictSize(70 * mm, 35 * mm)
            end_block.append(sig_img)
            end_block.append(Spacer(1, 2 * mm))
        else:
            end_block.append(P("Firma no adjunta."))
            end_block.append(Spacer(1, 2 * mm))

        # Texto firma (siempre al final)
        firma_text = data.get("firma_texto", "").strip()
        if firma_text:
            end_block.append(Paragraph(firma_text.replace("\n", "<br/>"), styles["Small"]))

    if end_block:
        story.append(KeepTogether(end_block))

    doc.build(
        story,
        onFirstPage=lambda c, d: _draw_header_footer(c, d, data.get("titulo", "Informe Técnico de Inspección")),
        onLaterPages=lambda c, d: _draw_header_footer(c, d, data.get("titulo", "Informe Técnico de Inspección")),
    )

    return buf.getvalue()


# -----------------------------
# UI
# -----------------------------
st.subheader("Configuración del informe")

c1, c2, c3 = st.columns(3)
with c1:
    include_signature = st.checkbox("Incluir firma", value=True)
with c2:
    include_photos = st.checkbox("Incluir fotos", value=True)
with c3:
    basic_fix = st.checkbox("Mostrar corrección básica", value=True)

st.divider()

fecha = st.date_input("Fecha", value=date.today(), format="DD-MM-YYYY")
titulo = st.text_input("Título del informe", value="Informe Técnico de Inspección")

disciplina = st.selectbox("Disciplina", options=["Eléctrica", "Mecánica", "Instrumentación", "Otro"], index=0)

equipo = st.text_input("Equipo / área inspeccionada", value="")
ubicacion = st.text_input("Ubicación", value="")

inspector = st.text_input("Inspector", value="JORGE CAMPOS AGUIRRE")
cargo = st.text_input("Cargo", value="Especialista eléctrico")

ot = st.text_input("N° Registro / OT", value="")
riesgo = st.selectbox("Nivel de riesgo", options=["Bajo", "Medio", "Alto", "Crítico"], index=1)

hallazgos_opts = [
    "Riesgo eléctrico",
    "Riesgo mecánico",
    "Protecciones / guardas",
    "Orden y limpieza",
    "Etiquetado / identificación",
    "EPP",
    "Bloqueo y consignación (LOTO)",
    "Iluminación",
    "Señalización",
    "Instrumentación / medición",
]
hallazgos = st.multiselect("Hallazgos (marca lo que aplique)", options=hallazgos_opts, default=[])

observaciones = st.text_area(
    "Observaciones técnicas",
    value="",
    height=140,
    placeholder="Describe condición encontrada, evidencia, medición (si aplica), y recomendación técnica puntual.",
)

# ✅ Esto lo quitamos: NO más “Plazo sugerido: 7–14 días...”
# Y acortamos conclusión: por defecto viene corta y tú la editas.
conclusion_default = (
    "Se recomienda ejecutar acciones correctivas según criticidad y controlar la efectividad mediante verificación posterior."
)
conclusion = st.text_area(
    "Conclusión (mantenerla breve y técnica)",
    value=conclusion_default,
    height=100,
)

# Opcional: limitar extensión (para que no se dispare)
max_chars = 420
if len(conclusion) > max_chars:
    st.warning(f"La conclusión está muy extensa. Máximo sugerido: {max_chars} caracteres.")
    conclusion = conclusion[:max_chars]

st.divider()

photo_uploads = []
signature_upload = None

if include_photos:
    photos = st.file_uploader(
        "Cargar hasta 3 fotos (JPG/PNG)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )
    if photos:
        if len(photos) > 3:
            st.warning("Máximo 3 imágenes. Se usarán solo las primeras 3.")
        photo_uploads = photos[:3]

        st.caption("Vista previa (miniaturas):")
        cols = st.columns(3)
        for i, up in enumerate(photo_uploads):
            with cols[i]:
                img = make_thumbnail(read_uploaded_image(up), max_px=700)
                st.image(img, use_container_width=True)

if include_signature:
    signature_upload = st.file_uploader(
        "Cargar firma (JPG/PNG)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=False,
    )
    st.caption("La firma se insertará AL FINAL del PDF (después de las fotos).")
    if signature_upload is not None:
        sig_img = make_thumbnail(read_uploaded_image(signature_upload), max_px=700)
        st.image(sig_img, caption="Vista previa firma", use_container_width=True)

# Texto final firma (fijo, editable si quieres)
firma_texto = st.text_area(
    "Bloque de firma (texto)",
    value="Jorge Campos Aguirre\nEspecialista Eléctrico\nCodelco División Andina",
    height=70,
)

st.divider()

data = {
    "fecha": fecha.strftime("%d-%m-%Y"),
    "titulo": titulo,
    "disciplina": disciplina,
    "equipo": equipo,
    "ubicacion": ubicacion,
    "inspector": inspector,
    "cargo": cargo,
    "ot": ot,
    "riesgo": riesgo,
    "hallazgos": hallazgos,
    "observaciones": observaciones,
    "conclusion": conclusion,
    "firma_texto": firma_texto,
}

col_a, col_b = st.columns([1, 1])
with col_a:
    if st.button("📄 Generar PDF", use_container_width=True):
        try:
            pdf_bytes = build_pdf_bytes(
                data=data,
                include_photos=include_photos,
                include_signature=include_signature,
                basic_fix=basic_fix,
                photo_uploads=photo_uploads,
                signature_upload=signature_upload,
            )
            st.success("PDF generado ✅")
            st.download_button(
                "⬇️ Descargar PDF",
                data=pdf_bytes,
                file_name=f"Informe_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Error al generar PDF: {e}")

with col_b:
    st.caption("Tip: si quieres que NO venga nada por defecto, deja value='' en los campos que quieras vacíos 😉")

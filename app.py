# app.py
import io
import re
from datetime import datetime, date
from typing import List

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


# -----------------------------
# UI Config
# -----------------------------
st.set_page_config(page_title="jcamp029.pro", page_icon="🧾", layout="centered")

# ✅ CSS oscuro (labels bien visibles + widgets)
st.markdown(
    """
<style>
/* Fondo */
.stApp {
  background: radial-gradient(1200px 600px at 20% 0%, #0b1a33 0%, #05070d 55%, #000 100%);
}

/* ✅ Títulos */
h1, h2, h3, h4, h5, h6 {
  color: #ffffff !important;
  font-weight: 800 !important;
  text-shadow: 0 0 10px rgba(255,255,255,0.18);
}

/* ✅ Labels (lo que te sale débil en la imagen) */
div[data-testid="stWidgetLabel"] > label,
div[data-testid="stWidgetLabel"] label,
label {
  color: #ffffff !important;
  font-weight: 800 !important;
  font-size: 0.95rem !important;
  letter-spacing: .2px !important;
  text-shadow: 0 0 10px rgba(255,255,255,0.22);
  opacity: 1 !important;
}

/* Texto general */
.stMarkdown, .stText, .stCaption, p, span {
  color: #f2f2f2 !important;
}

/* Inputs */
div[data-baseweb="input"] input {
  background-color: rgba(5,7,13,0.9) !important;
  color: #ffffff !important;
  border: 1px solid rgba(255,255,255,0.22) !important;
}

/* Textarea */
div[data-baseweb="textarea"] textarea {
  background-color: rgba(5,7,13,0.9) !important;
  color: #ffffff !important;
  border: 1px solid rgba(255,255,255,0.22) !important;
}

/* Select */
div[data-baseweb="select"] > div {
  background-color: rgba(5,7,13,0.9) !important;
  color: #ffffff !important;
  border: 1px solid rgba(255,255,255,0.22) !important;
}

/* Checkboxes text */
div[data-testid="stCheckbox"] label {
  color: #ffffff !important;
  font-weight: 700 !important;
  text-shadow: 0 0 10px rgba(255,255,255,0.18);
}

/* Botones */
.stButton button {
  border-radius: 12px;
  padding: 0.6rem 1.0rem;
  border: 1px solid rgba(255,255,255,0.22);
}
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
    t = (text or "").strip()
    t = re.sub(r"\s+", " ", t)

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
    }

    def repl_word(m):
        w = m.group(0)
        lw = w.lower()
        if lw in replacements:
            fixed = replacements[lw]
            if w[:1].isupper():
                fixed = fixed[:1].upper() + fixed[1:]
            return fixed
        return w

    t = re.sub(r"[A-Za-zÁÉÍÓÚáéíóúÑñ]+", repl_word, t)

    if t:
        t = t[0].upper() + t[1:]
    return t


def pil_to_png_bytes(pil_img: PILImage.Image) -> bytes:
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()


def read_uploaded_image(upload) -> PILImage.Image:
    img = PILImage.open(upload).convert("RGB")
    return img


def make_thumbnail(img: PILImage.Image, max_px: int = 900) -> PILImage.Image:
    out = img.copy()
    out.thumbnail((max_px, max_px))
    return out


# -----------------------------
# PDF Header/Footer
# -----------------------------
def _draw_header_footer(c: rl_canvas.Canvas, doc, title: str):
    c.saveState()
    w, h = A4

    c.setStrokeColor(colors.HexColor("#999999"))
    c.setLineWidth(0.5)
    c.line(15 * mm, h - 15 * mm, w - 15 * mm, h - 15 * mm)

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#111111"))
    c.drawString(15 * mm, h - 12 * mm, _clean_text(title)[:70])

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
        t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        t = t.replace("\n", "<br/>")
        return Paragraph(t, styles["P"])

    story = []

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
    info_rows = [[_clean_text(a), _clean_text(b)] for a, b in info_rows]

    t = Table(info_rows, colWidths=[45 * mm, 125 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111111")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
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

    story.append(Paragraph("Hallazgos", styles["H"]))
    hallazgos = data.get("hallazgos", [])
    if hallazgos:
        story.append(P("• " + "\n• ".join([_clean_text(x) for x in hallazgos])))
    else:
        story.append(P("Sin hallazgos marcados."))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Observaciones técnicas", styles["H"]))
    obs = (data.get("observaciones", "") or "").strip()
    story.append(P(obs if obs else "Sin observaciones registradas."))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Conclusión", styles["H"]))
    concl = (data.get("conclusion", "") or "").strip()
    story.append(P(concl if concl else "Conclusión no registrada."))
    story.append(Spacer(1, 6 * mm))

    # Bloque final (fotos + firma), juntos: si no cabe, salta a otra hoja completo
    end_block = []

    if include_photos:
        end_block.append(Paragraph("Registro fotográfico", styles["H"]))
        uploads = photo_uploads[:3] if photo_uploads else []
        if uploads:
            max_w = 55 * mm
            max_h = 55 * mm

            imgs = []
            for up in uploads:
                pil = make_thumbnail(read_uploaded_image(up), max_px=900)
                png = pil_to_png_bytes(pil)
                rl_img = RLImage(io.BytesIO(png))
                rl_img._restrictSize(max_w, max_h)
                imgs.append(rl_img)

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

        firma_text = (data.get("firma_texto", "") or "").strip()
        if firma_text:
            firma_text = firma_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
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
# Session State (para botón LIMPIAR)
# -----------------------------
FIELD_KEYS = {
    "fecha": "fecha",
    "titulo": "titulo",
    "disciplina": "disciplina",
    "equipo": "equipo",
    "ubicacion": "ubicacion",
    "inspector": "inspector",
    "cargo": "cargo",
    "ot": "ot",
    "riesgo": "riesgo",
    "hallazgos": "hallazgos",
    "observaciones": "observaciones",
    "conclusion": "conclusion",
    "firma_texto": "firma_texto",
    "include_signature": "include_signature",
    "include_photos": "include_photos",
    "basic_fix": "basic_fix",
}

def reset_form():
    st.session_state[FIELD_KEYS["fecha"]] = date.today()
    st.session_state[FIELD_KEYS["titulo"]] = "Informe Técnico de Inspección"
    st.session_state[FIELD_KEYS["disciplina"]] = "Eléctrica"
    st.session_state[FIELD_KEYS["equipo"]] = ""
    st.session_state[FIELD_KEYS["ubicacion"]] = ""
    st.session_state[FIELD_KEYS["inspector"]] = ""
    st.session_state[FIELD_KEYS["cargo"]] = ""
    st.session_state[FIELD_KEYS["ot"]] = ""
    st.session_state[FIELD_KEYS["riesgo"]] = "Medio"
    st.session_state[FIELD_KEYS["hallazgos"]] = []
    st.session_state[FIELD_KEYS["observaciones"]] = ""
    st.session_state[FIELD_KEYS["conclusion"]] = "Se recomienda ejecutar acciones correctivas según criticidad y controlar la efectividad mediante verificación posterior."
    st.session_state[FIELD_KEYS["firma_texto"]] = "Jorge Campos Aguirre\nEspecialista Eléctrico\nCodelco División Andina"
    st.session_state[FIELD_KEYS["include_signature"]] = True
    st.session_state[FIELD_KEYS["include_photos"]] = True
    st.session_state[FIELD_KEYS["basic_fix"]] = True
    # limpiar uploads (no siempre se puede “vaciar” el uploader, pero limpiamos referencias)
    st.session_state["__photos__"] = []
    st.session_state["__signature__"] = None


# -----------------------------
# UI
# -----------------------------
st.subheader("Configuración del informe")

top_a, top_b = st.columns([1, 1])
with top_a:
    c1, c2, c3 = st.columns(3)
    with c1:
        include_signature = st.checkbox("Incluir firma", key=FIELD_KEYS["include_signature"], value=True)
    with c2:
        include_photos = st.checkbox("Incluir fotos", key=FIELD_KEYS["include_photos"], value=True)
    with c3:
        basic_fix = st.checkbox("Mostrar corrección básica", key=FIELD_KEYS["basic_fix"], value=True)

with top_b:
    st.write("")  # espacio
    if st.button("🧹 Limpiar formulario", use_container_width=True):
        reset_form()
        st.rerun()

st.divider()

fecha = st.date_input("Fecha", key=FIELD_KEYS["fecha"], value=st.session_state.get(FIELD_KEYS["fecha"], date.today()), format="DD-MM-YYYY")
titulo = st.text_input("Título del informe", key=FIELD_KEYS["titulo"], value=st.session_state.get(FIELD_KEYS["titulo"], "Informe Técnico de Inspección"))

disciplina = st.selectbox(
    "Disciplina",
    options=["Eléctrica", "Mecánica", "Instrumentación", "Otro"],
    key=FIELD_KEYS["disciplina"],
    index=["Eléctrica", "Mecánica", "Instrumentación", "Otro"].index(st.session_state.get(FIELD_KEYS["disciplina"], "Eléctrica")),
)

equipo = st.text_input("Equipo / área inspeccionada", key=FIELD_KEYS["equipo"], value=st.session_state.get(FIELD_KEYS["equipo"], ""))
ubicacion = st.text_input("Ubicación", key=FIELD_KEYS["ubicacion"], value=st.session_state.get(FIELD_KEYS["ubicacion"], ""))

inspector = st.text_input("Inspector", key=FIELD_KEYS["inspector"], value=st.session_state.get(FIELD_KEYS["inspector"], ""))
cargo = st.text_input("Cargo", key=FIELD_KEYS["cargo"], value=st.session_state.get(FIELD_KEYS["cargo"], ""))

ot = st.text_input("N° Registro / OT", key=FIELD_KEYS["ot"], value=st.session_state.get(FIELD_KEYS["ot"], ""))

riesgo = st.selectbox(
    "Nivel de riesgo",
    options=["Bajo", "Medio", "Alto", "Crítico"],
    key=FIELD_KEYS["riesgo"],
    index=["Bajo", "Medio", "Alto", "Crítico"].index(st.session_state.get(FIELD_KEYS["riesgo"], "Medio")),
)

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
hallazgos = st.multiselect(
    "Hallazgos (marca lo que aplique)",
    options=hallazgos_opts,
    default=st.session_state.get(FIELD_KEYS["hallazgos"], []),
    key=FIELD_KEYS["hallazgos"],
)

observaciones = st.text_area(
    "Observaciones técnicas",
    key=FIELD_KEYS["observaciones"],
    value=st.session_state.get(FIELD_KEYS["observaciones"], ""),
    height=140,
    placeholder="Describe condición encontrada, evidencia, medición (si aplica), y recomendación técnica puntual.",
)

conclusion = st.text_area(
    "Conclusión (mantenerla breve y técnica)",
    key=FIELD_KEYS["conclusion"],
    value=st.session_state.get(
        FIELD_KEYS["conclusion"],
        "Se recomienda ejecutar acciones correctivas según criticidad y controlar la efectividad mediante verificación posterior.",
    ),
    height=100,
)

# limitar extensión
max_chars = 420
if len(conclusion) > max_chars:
    st.warning(f"La conclusión está muy extensa. Máximo sugerido: {max_chars} caracteres.")
    conclusion = conclusion[:max_chars]
    st.session_state[FIELD_KEYS["conclusion"]] = conclusion

st.divider()

photo_uploads = []
signature_upload = None

if include_photos:
    photos = st.file_uploader(
        "Cargar hasta 3 fotos (JPG/PNG)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="photos_uploader",
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
        key="signature_uploader",
    )
    st.caption("La firma se insertará AL FINAL del PDF (después de las fotos).")
    if signature_upload is not None:
        sig_img = make_thumbnail(read_uploaded_image(signature_upload), max_px=700)
        st.image(sig_img, caption="Vista previa firma", use_container_width=True)

firma_texto = st.text_area(
    "Bloque de firma (texto)",
    key=FIELD_KEYS["firma_texto"],
    value=st.session_state.get(FIELD_KEYS["firma_texto"], "Jorge Campos Aguirre\nEspecialista Eléctrico\nCodelco División Andina"),
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
    st.caption("Si algo queda “guardado”, usa 🧹 Limpiar formulario 😎")

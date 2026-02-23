import io
import re
import unicodedata
import base64
from collections import Counter
from datetime import datetime
from typing import List, Tuple, Optional

import streamlit as st
import streamlit.components.v1 as components
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, PageBreak

from PIL import Image, ImageOps
from xml.sax.saxutils import escape


# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="jcamp029.pro", page_icon="🧾", layout="centered")
APP_TITLE = "jcamp029.pro"
APP_SUBTITLE = "Generador profesional de informes de inspección técnica (PDF)."
TZ_CL = ZoneInfo("America/Santiago")

UP_NONCE = "__uploader_nonce__"

# ✅ Reglas Multimedia
# - Bloque total de imágenes (1,2,3) NO supera 15x6 cm
TOTAL_IMG_W_MM = 150
TOTAL_IMG_H_MM = 60

# - Firma fija 3x3 cm
SIGN_W_MM = 30
SIGN_H_MM = 30


# -----------------------------
# Keys + Defaults
# -----------------------------
FIELD_KEYS = {
    "theme": "theme",
    "theme_initialized": "theme_initialized",

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

    "last_pdf_bytes": "last_pdf_bytes",
    "last_pdf_name": "last_pdf_name",
    "last_pdf_token": "last_pdf_token",
}


def get_defaults() -> dict:
    return {
        FIELD_KEYS["theme"]: "Claro",
        FIELD_KEYS["theme_initialized"]: False,

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

        FIELD_KEYS["last_pdf_bytes"]: None,
        FIELD_KEYS["last_pdf_name"]: "",
        FIELD_KEYS["last_pdf_token"]: "",
    }


def init_state():
    if UP_NONCE not in st.session_state:
        st.session_state[UP_NONCE] = 0

    defaults = get_defaults()

    # abrir siempre en CLARO al inicio de la sesión, permitir cambiar luego
    if not st.session_state.get(FIELD_KEYS["theme_initialized"], False):
        st.session_state[FIELD_KEYS["theme"]] = "Claro"
        st.session_state[FIELD_KEYS["theme_initialized"]] = True

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def hard_reset_now():
    """Reset definitivo del formulario preservando el tema actual."""
    current_theme = st.session_state.get(FIELD_KEYS["theme"], "Claro")

    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.session_state[UP_NONCE] = 1

    defaults = get_defaults()
    for k, v in defaults.items():
        st.session_state[k] = v

    st.session_state[FIELD_KEYS["theme"]] = current_theme
    st.session_state[FIELD_KEYS["theme_initialized"]] = True
    st.rerun()


init_state()


# -----------------------------
# CSS Dinámico
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

        btn_bg = "#0B1220"
        btn_border = "#2A3A58"
        btn_text = "#FFFFFF"
        btn_hover = "#101A2E"
    else:
        bg = "#FFFFFF"
        fg = "#0F172A"
        muted = "#334155"
        card = "#F8FAFC"
        border = "#E2E8F0"
        input_bg = "#FFFFFF"
        placeholder = "#64748B"
        focus = "#2563EB"

        btn_bg = "#FFFFFF"
        btn_border = "#CBD5E1"
        btn_text = "#0F172A"
        btn_hover = "#F1F5F9"

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

        /* Botones */
        div[data-testid="stButton"] button,
        div[data-testid="stDownloadButton"] button,
        div[data-testid="stFormSubmitButton"] button {{
            background: {btn_bg} !important;
            border: 1px solid {btn_border} !important;
            color: {btn_text} !important;
            border-radius: 12px !important;
            font-weight: 800 !important;
        }}
        div[data-testid="stButton"] button:hover,
        div[data-testid="stDownloadButton"] button:hover,
        div[data-testid="stFormSubmitButton"] button:hover {{
            background: {btn_hover} !important;
            color: {btn_text} !important;
            border-color: {btn_border} !important;
        }}
        div[data-testid="stButton"] button *,
        div[data-testid="stDownloadButton"] button *,
        div[data-testid="stFormSubmitButton"] button * {{
            color: {btn_text} !important;
        }}

        /* File Uploader */
        div[data-testid="stFileUploader"] {{ color: {fg} !important; }}
        div[data-testid="stFileUploader"] * {{ color: {fg} !important; }}
        div[data-testid="stFileUploader"] section {{
            background: {card} !important;
            border: 1px solid {border} !important;
            border-radius: 14px !important;
        }}
        div[data-testid="stFileUploader"] button {{
            background: {btn_bg} !important;
            border: 1px solid {btn_border} !important;
            color: {btn_text} !important;
            font-weight: 800 !important;
            border-radius: 12px !important;
        }}
        div[data-testid="stFileUploader"] button * {{ color: {btn_text} !important; }}

        div[role="radiogroup"] * {{ color: {fg} !important; }}

        /* Evitar “botón vacío raro” (espacios extra) */
        div[data-testid="stButton"] {{ margin-top: 0.25rem; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------
# Recomendación NO bloqueante para Nombres (Inspector)
# -----------------------------
def _recommended_title_name(name: str) -> str:
    s = (name or "").strip()
    s = re.sub(r"\s+", " ", s)
    parts = re.split(r"([ \-’'`])", s)
    out = []
    for p in parts:
        if p in {" ", "-", "’", "'", "`"} or p == "":
            out.append(p)
            continue
        out.append(p[:1].upper() + p[1:].lower() if p.isalpha() else p)
    return "".join(out).strip()


def _has_obvious_caps_issue(name: str) -> bool:
    s = (name or "").strip()
    if not s:
        return False

    letters = [ch for ch in s if ch.isalpha()]
    if not letters:
        return False

    if all(ch.islower() for ch in letters):
        return True
    if all(ch.isupper() for ch in letters):
        return True

    words = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", s)
    for w in words:
        if len(w) >= 2 and w[0].isupper():
            if any(ch.isupper() for ch in w[1:]) and not w.isupper():
                return True
    return False


# -----------------------------
# Corrección técnica (A) - solo Observaciones
# -----------------------------
def normalize_spaces(text: str) -> str:
    text = text or ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


def match_case(original: str, replacement: str) -> str:
    if original.isupper():
        return replacement.upper()
    if len(original) > 1 and original[0].isupper() and original[1:].islower():
        return replacement[:1].upper() + replacement[1:].lower()
    return replacement


TECH_WORDS = {
    "aseo": "aseo",
    "area": "área",
    "tecnico": "técnico",
    "tecnica": "técnica",
    "inspeccion": "inspección",
    "ubicacion": "ubicación",
    "conclusion": "conclusión",
    "observacion": "observación",
    "iluminacion": "iluminación",
    "condicion": "condición",
    "revision": "revisión",
    "operacion": "operación",
    "senalizacion": "señalización",
    "proteccion": "protección",
    "mantenimiento": "mantenimiento",
    "electrico": "eléctrico",
    "electrica": "eléctrica",
    "electricos": "eléctricos",
    "electricas": "eléctricas",
    "mecanico": "mecánico",
    "mecanica": "mecánica",
    "instrumentacion": "instrumentación",
    "medicion": "medición",   # ✅ tu caso
    "epp": "EPP",
}
TECH_MAP = {strip_accents(k).lower(): v for k, v in TECH_WORDS.items()}


def technical_spanish_fixes(text: str):
    t = normalize_spaces(text or "")
    changes_counter = Counter()
    word_re = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")

    def repl(m: re.Match) -> str:
        w = m.group(0)
        if any(ch.isdigit() for ch in w):
            return w
        key = strip_accents(w).lower()
        if key in TECH_MAP:
            new_word = match_case(w, TECH_MAP[key])
            if new_word != w:
                changes_counter[f"{w} → {new_word}"] += 1
            return new_word
        return w

    t2 = word_re.sub(repl, t)

    logs = []
    if t2 and t2[0].islower():
        t2 = t2[0].upper() + t2[1:]
        changes_counter["Capitalización inicial"] += 1

    for k, n in changes_counter.most_common():
        logs.append(f"{k} ({n})")

    return t2, logs


def apply_obs_fix():
    st.session_state[FIELD_KEYS["observaciones_raw"]] = st.session_state.get(FIELD_KEYS["obs_fixed_preview"], "")
    st.rerun()


# -----------------------------
# Auto-conclusión (compacta)
# -----------------------------
def compute_auto_hash() -> str:
    d = st.session_state.get(FIELD_KEYS["disciplina"], "")
    r = st.session_state.get(FIELD_KEYS["nivel_riesgo"], "")
    h = ",".join(st.session_state.get(FIELD_KEYS["hallazgos"], []) or [])
    o = st.session_state.get(FIELD_KEYS["observaciones_raw"], "")
    return f"{d}|{r}|{h}|{o}"


def _contains_any(text: str, words: List[str]) -> bool:
    t = strip_accents((text or "").lower())
    return any(strip_accents(w.lower()) in t for w in words)


def generate_conclusion_compact(disciplina: str, nivel_riesgo: str, hallazgos: List[str], observaciones: str) -> str:
    disc = (disciplina or "Otra").strip()
    obs = observaciones or ""
    hall = hallazgos or []

    causas = []

    if disc.lower().startswith("eléctr") or disc.lower().startswith("electr"):
        if _contains_any(obs, ["tablero", "tableros", "gabinete", "panel"]):
            causas.append("condición deficiente en tableros/gabinetes")
        if _contains_any(obs, ["loto", "bloqueo", "etiquetado"]):
            causas.append("ausencia o debilidad de control LOTO")
        if _contains_any(obs, ["polvo conductor", "polvo", "suciedad"]):
            causas.append("acumulación de polvo")
        if not causas and hall:
            causas.append("condiciones observadas en terreno")

        accion = "Corregir según prioridad"
        if _contains_any(obs, ["polvo conductor", "polvo", "suciedad", "aseo", "limpieza"]) or ("Orden y limpieza" in hall):
            accion = "Realizar limpieza y control de polvo conductor"
        if _contains_any(obs, ["loto", "bloqueo", "etiquetado"]) or ("LOTO" in hall):
            accion = accion + " y asegurar aplicación LOTO"
        if _contains_any(obs, ["tablero", "tableros", "gabinete", "panel"]) or ("Tableros" in hall):
            accion = accion + " en tableros/gabinetes"

    elif disc.lower().startswith("mec"):
        if _contains_any(obs, ["guardas", "proteccion", "protección"]):
            causas.append("protecciones/guardas deficientes")
        if _contains_any(obs, ["fuga", "aceite", "lubric"]):
            causas.append("fugas o lubricación deficiente")
        if not causas and hall:
            causas.append("condiciones mecánicas observadas")
        accion = "Corregir según prioridad"

    elif disc.lower().startswith("instr"):
        if _contains_any(obs, ["medicion", "medición", "calibr", "señal", "sensor"]):
            causas.append("condición de medición/control a verificar")
        if not causas and hall:
            causas.append("condiciones de instrumentación observadas")
        accion = "Verificar y corregir según prioridad"

    else:
        if not causas and hall:
            causas.append("condiciones observadas")
        accion = "Corregir según prioridad"

    causa_txt = " y ".join(causas) if causas else "condiciones observadas"
    frase1 = f"Se identifican {causa_txt}."
    frase2 = f"{accion}."

    out = f"{frase1} {frase2}"
    out = re.sub(r"\s+", " ", out).strip()
    if len(out) > 260:
        out = out[:257].rstrip() + "..."
    return out


def sync_auto_conclusion_if_needed():
    if not st.session_state.get(FIELD_KEYS["auto_conclusion"], True):
        return
    if st.session_state.get(FIELD_KEYS["conclusion_locked"], False):
        return

    current_hash = compute_auto_hash()
    last_hash = st.session_state.get(FIELD_KEYS["last_auto_hash"], "")

    if current_hash != last_hash or not (st.session_state.get(FIELD_KEYS["conclusion"], "").strip()):
        st.session_state[FIELD_KEYS["conclusion"]] = generate_conclusion_compact(
            st.session_state.get(FIELD_KEYS["disciplina"], "Otra"),
            st.session_state.get(FIELD_KEYS["nivel_riesgo"], "Medio"),
            st.session_state.get(FIELD_KEYS["hallazgos"], []),
            st.session_state.get(FIELD_KEYS["observaciones_raw"], ""),
        )
        st.session_state[FIELD_KEYS["last_auto_hash"]] = current_hash


# -----------------------------
# Imágenes (COVER) + utilidades
# -----------------------------
def _safe_filename(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s\-\.]", "", s, flags=re.UNICODE)
    s = s.replace(" ", "_")
    return s[:80] if s else "informe"


def _mm_to_px(mm_value: float, dpi: int = 300) -> int:
    return max(1, int(round((mm_value / 25.4) * dpi)))


def _img_cover(file_bytes: bytes, w_mm: float, h_mm: float) -> RLImage:
    """
    Genera una imagen “cover” (recorte centrado) para llenar exactamente w_mm × h_mm.
    Retorna RLImage listo para ReportLab.
    """
    if not file_bytes:
        raise ValueError("Imagen vacía")

    with Image.open(io.BytesIO(file_bytes)) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        target_w_px = _mm_to_px(w_mm, dpi=300)
        target_h_px = _mm_to_px(h_mm, dpi=300)
        fitted = ImageOps.fit(im, (target_w_px, target_h_px), method=Image.LANCZOS, centering=(0.5, 0.5))

        bio = io.BytesIO()
        fitted.save(bio, format="JPEG", quality=88, optimize=True)
        bio.seek(0)

    rl = RLImage(bio, width=w_mm * mm, height=h_mm * mm)
    return rl


def _safe_paragraph(text: str) -> Paragraph:
    text = normalize_spaces(text or "")
    text = escape(text).replace("\n", "<br/>")
    styles = getSampleStyleSheet()
    p = Paragraph(text if text else "&nbsp;", styles["BodyText"])
    return p


def _section_title(text: str) -> Paragraph:
    styles = getSampleStyleSheet()
    t = escape((text or "").strip())
    return Paragraph(f"<b>{t}</b>", styles["Heading4"])


def _kv_table(rows: List[Tuple[str, str]]) -> Table:
    data = []
    for k, v in rows:
        data.append([f"<b>{escape(k)}</b>", escape(v or "")])
    styles = getSampleStyleSheet()
    t = Table(
        [[Paragraph(a, styles["BodyText"]), Paragraph(b, styles["BodyText"])] for a, b in data],
        colWidths=[45 * mm, 135 * mm],
    )
    t.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _chips_table(title: str, items: List[str]) -> Optional[Table]:
    items = [x.strip() for x in (items or []) if x and x.strip()]
    if not items:
        return None

    styles = getSampleStyleSheet()
    chips = []
    for it in items:
        chips.append(Paragraph(f"• {escape(it)}", styles["BodyText"]))

    t = Table([[Paragraph(f"<b>{escape(title)}</b>", styles["BodyText"])], chips], colWidths=[180 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def build_pdf(
    *,
    titulo: str,
    fecha: str,
    disciplina: str,
    equipo: str,
    ubicacion: str,
    inspector: str,
    cargo: str,
    registro_ot: str,
    nivel_riesgo: str,
    hallazgos: List[str],
    observaciones: str,
    conclusion: str,
    photos: List[bytes],
    signature: Optional[bytes],
) -> bytes:
    buff = io.BytesIO()
    doc = SimpleDocTemplate(
        buff,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=titulo or "Informe",
        author=inspector or "",
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>{escape(titulo or 'Informe Técnico de Inspección')}</b>", styles["Title"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"<i>Fecha:</i> {escape(fecha or '')}", styles["BodyText"]))
    story.append(Spacer(1, 3 * mm))

    info = _kv_table(
        [
            ("Disciplina", disciplina or ""),
            ("Equipo", equipo or ""),
            ("Ubicación", ubicacion or ""),
            ("Inspector", inspector or ""),
            ("Cargo", cargo or ""),
            ("Registro OT", registro_ot or ""),
            ("Nivel de riesgo", nivel_riesgo or ""),
        ]
    )
    story.append(info)
    story.append(Spacer(1, 4 * mm))

    ht = _chips_table("Hallazgos", hallazgos or [])
    if ht is not None:
        story.append(ht)
        story.append(Spacer(1, 4 * mm))

    story.append(_section_title("Observaciones"))
    story.append(Spacer(1, 2 * mm))
    story.append(_safe_paragraph(observaciones or ""))
    story.append(Spacer(1, 4 * mm))

    story.append(_section_title("Conclusión"))
    story.append(Spacer(1, 2 * mm))
    story.append(_safe_paragraph(conclusion or ""))
    story.append(Spacer(1, 5 * mm))

    # --- Multimedia al final: fotos (bloque total 15x6 cm) + firma (3x3 cm)
    media_parts = []

    n = len([p for p in (photos or []) if p])
    if n > 0:
        # Distribuir ancho total entre N fotos, altura total fija
        per_w = TOTAL_IMG_W_MM / n
        per_h = TOTAL_IMG_H_MM

        imgs = []
        for p in photos[:3]:
            if not p:
                continue
            imgs.append(_img_cover(p, per_w, per_h))

        if imgs:
            row = imgs
            t = Table([row], colWidths=[per_w * mm] * len(row), rowHeights=[per_h * mm])
            t.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                        ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                    ]
                )
            )
            media_parts.append(_section_title("Registro fotográfico"))
            media_parts.append(Spacer(1, 2 * mm))
            media_parts.append(t)
            media_parts.append(Spacer(1, 3 * mm))

    if signature:
        sig = _img_cover(signature, SIGN_W_MM, SIGN_H_MM)
        sig_tbl = Table([[sig]], colWidths=[SIGN_W_MM * mm], rowHeights=[SIGN_H_MM * mm])
        sig_tbl.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                ]
            )
        )
        media_parts.append(_section_title("Firma"))
        media_parts.append(Spacer(1, 2 * mm))
        media_parts.append(sig_tbl)

    if media_parts:
        story.append(Spacer(1, 2 * mm))
        story.extend(media_parts)

    doc.build(story)
    pdf_bytes = buff.getvalue()
    buff.close()
    return pdf_bytes


# -----------------------------
# UI
# -----------------------------
apply_theme_css(st.session_state.get(FIELD_KEYS["theme"], "Claro"))

st.markdown(f"<div class='app-card'><h2 style='margin:0'>{APP_TITLE}</h2><div class='muted'>{APP_SUBTITLE}</div></div>", unsafe_allow_html=True)

# Header controls
c1, c2, c3 = st.columns([1.2, 1.0, 1.1])
with c1:
    theme = st.selectbox(
        "Tema",
        ["Claro", "Oscuro"],
        index=0 if st.session_state[FIELD_KEYS["theme"]] == "Claro" else 1,
        key=FIELD_KEYS["theme"],
    )
with c2:
    st.toggle("Auto-conclusión", key=FIELD_KEYS["auto_conclusion"])
with c3:
    st.toggle("Mostrar corrección", key=FIELD_KEYS["show_correccion"])

apply_theme_css(st.session_state.get(FIELD_KEYS["theme"], "Claro"))

# Acciones rápidas
a1, a2, a3 = st.columns([1.2, 1.0, 1.0])
with a1:
    st.toggle("Incluir fotos", key=FIELD_KEYS["include_photos"])
with a2:
    st.toggle("Incluir firma", key=FIELD_KEYS["include_signature"])
with a3:
    if st.button("Limpiar formulario", use_container_width=True):
        hard_reset_now()

st.markdown("<div class='app-card'>", unsafe_allow_html=True)

# Datos
d1, d2 = st.columns([1, 1])
with d1:
    st.text_input("Fecha", key=FIELD_KEYS["fecha"])
    st.text_input("Título", key=FIELD_KEYS["titulo"])
    st.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Instrumentación", "Civil", "Otra"], key=FIELD_KEYS["disciplina"])
with d2:
    st.text_input("Equipo", key=FIELD_KEYS["equipo"])
    st.text_input("Ubicación", key=FIELD_KEYS["ubicacion"])
    st.text_input("Registro OT", key=FIELD_KEYS["registro_ot"])

d3, d4 = st.columns([1, 1])
with d3:
    st.text_input("Inspector", key=FIELD_KEYS["inspector"])
    if _has_obvious_caps_issue(st.session_state.get(FIELD_KEYS["inspector"], "")):
        rec = _recommended_title_name(st.session_state.get(FIELD_KEYS["inspector"], ""))
        st.caption(f"Sugerencia (no obliga): {rec}")
with d4:
    st.text_input("Cargo", key=FIELD_KEYS["cargo"])
    st.selectbox("Nivel de riesgo", ["Bajo", "Medio", "Alto", "Crítico"], key=FIELD_KEYS["nivel_riesgo"])

# Hallazgos
st.multiselect(
    "Hallazgos (selecciona lo que aplique)",
    ["Orden y limpieza", "Tableros", "LOTO", "Protecciones", "Señalización", "Iluminación", "Instrumentación", "EPP", "Otros"],
    key=FIELD_KEYS["hallazgos"],
)

# Observaciones + corrección
st.text_area("Observaciones", key=FIELD_KEYS["observaciones_raw"], height=170, placeholder="Describe hallazgos, condición, ubicación exacta, etc.")

if st.session_state.get(FIELD_KEYS["show_correccion"], True):
    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("Corrección técnica (solo Observaciones)", use_container_width=True):
            fixed, logs = technical_spanish_fixes(st.session_state.get(FIELD_KEYS["observaciones_raw"], ""))
            st.session_state[FIELD_KEYS["obs_fixed_preview"]] = fixed
            if logs:
                st.caption("Cambios: " + " | ".join(logs))
            else:
                st.caption("Sin cambios detectados.")
    with b2:
        if st.button("Aplicar corrección", use_container_width=True):
            apply_obs_fix()

   if st.session_state.get(FIELD_KEYS["show_correccion"], True):
    b1, b2 = st.columns([1, 1])

    with b1:
        if st.button("Corrección técnica (solo Observaciones)", use_container_width=True):
            fixed, logs = technical_spanish_fixes(st.session_state.get(FIELD_KEYS["observaciones_raw"], ""))
            st.session_state[FIELD_KEYS["obs_fixed_preview"]] = fixed
            if logs:
                st.caption("Cambios: " + " | ".join(logs))
            else:
                st.caption("Sin cambios detectados.")

    with b2:
        if st.button("Aplicar corrección", use_container_width=True):
            apply_obs_fix()

    if (st.session_state.get(FIELD_KEYS["obs_fixed_preview"], "") or "").strip():
        st.text_area(
            "Vista previa corregida",
            key=FIELD_KEYS["obs_fixed_preview"],
            height=170
        )

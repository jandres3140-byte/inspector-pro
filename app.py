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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage

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
    "theme_initialized": "theme_initialized",  # fuerza claro SOLO 1 vez por sesión

    "include_signature": "include_signature",
    "include_photos": "include_photos",
    "show_correccion": "show_correccion",
    "auto_conclusion": "auto_conclusion",

    "auto_started": "auto_started",  # ✅ NO autogenerar hasta que el usuario lo pida

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

    # PDF generado (para descargar/compartir sin perderlo en reruns)
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

        FIELD_KEYS["auto_started"]: False,

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

    # ✅ abrir siempre en CLARO al inicio de la sesión,
    # pero permitir cambiar a Oscuro después (no se pisa en reruns).
    if not st.session_state.get(FIELD_KEYS["theme_initialized"], False):
        st.session_state[FIELD_KEYS["theme"]] = "Claro"
        st.session_state[FIELD_KEYS["theme_initialized"]] = True

    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def hard_reset_now():
    """
    Reset definitivo del formulario preservando el tema actual.
    """
    current_theme = st.session_state.get(FIELD_KEYS["theme"], "Claro")

    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.session_state[UP_NONCE] = 1

    defaults = get_defaults()
    for k, v in defaults.items():
        st.session_state[k] = v

    st.session_state[FIELD_KEYS["theme"]] = current_theme
    st.session_state[FIELD_KEYS["theme_initialized"]] = True  # no volver a forzar
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
        .app-card:empty {{
            display: none !important;
            padding: 0 !important;
            margin: 0 !important;
            border: 0 !important;
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

        /* File Uploader (Browse files visible en claro) */
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
    """
    Detecta SOLO problemas reales:
    - todo en minúsculas
    - mezcla rara tipo "JOrGe"
    IMPORTANTE: MAYÚSCULAS completas ya NO se consideran problema (en informes es común).
    """
    s = (name or "").strip()
    if not s:
        return False

    letters = [ch for ch in s if ch.isalpha()]
    if not letters:
        return False

    if all(ch.islower() for ch in letters):
        return True

    # ✅ ya NO marcamos "todo en MAYÚSCULAS" como problema
    # if all(ch.isupper() for ch in letters):
    #     return True

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
    "medicion": "medición",
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
# Auto-conclusión (prioriza Observaciones por FRASES EXACTAS)
# -----------------------------
def _normalize_for_exact_phrase_match(s: str) -> str:
    s = normalize_spaces(s or "").lower()
    s = strip_accents(s)
    return s


PHRASE_RULES = [
    {
        "phrase": "luminaria suelta",
        "disc": ["Eléctrica", "Otra"],
        "cause": "sujeción deficiente en elemento de iluminación",
        "action": "asegurar fijación del punto de iluminación",
        "priority": 10,
    },
    {
        "phrase": "polvo conductor",
        "disc": ["Eléctrica", "Otra"],
        "cause": "presencia de contaminación conductiva en el área",
        "action": "ejecutar limpieza y control de contaminación conductiva",
        "priority": 9,
    },
    {
        "phrase": "tablero sin tapa",
        "disc": ["Eléctrica", "Otra"],
        "cause": "gabinete eléctrico con barreras de protección incompletas",
        "action": "normalizar gabinete y restituir barreras de protección",
        "priority": 10,
    },
    {
        "phrase": "cable expuesto",
        "disc": ["Eléctrica", "Instrumental", "Otra"],
        "cause": "conductor/cableado sin protección adecuada",
        "action": "aislar, encauzar y proteger cableado según estándar",
        "priority": 10,
    },
    {
        "phrase": "sin loto",
        "disc": ["Eléctrica", "Mecánica", "Instrumental", "Civil", "Otra"],
        "cause": "ausencia de control de energías previo a intervención",
        "action": "implementar y verificar control LOTO antes de intervenir",
        "priority": 11,
    },
    {
        "phrase": "falta loto",
        "disc": ["Eléctrica", "Mecánica", "Instrumental", "Civil", "Otra"],
        "cause": "ausencia de control de energías previo a intervención",
        "action": "implementar y verificar control LOTO antes de intervenir",
        "priority": 11,
    },
    {
        "phrase": "fuga de aceite",
        "disc": ["Mecánica", "Otra"],
        "cause": "pérdida de fluido por condición de estanqueidad deficiente",
        "action": "corregir estanqueidad y verificar ausencia de fugas",
        "priority": 10,
    },
    {
        "phrase": "guarda faltante",
        "disc": ["Mecánica", "Otra"],
        "cause": "resguardo de partes móviles incompleto",
        "action": "restituir resguardo y asegurar integridad de protecciones",
        "priority": 10,
    },
    {
        "phrase": "señal inestable",
        "disc": ["Instrumental", "Otra"],
        "cause": "variación anómala de señal por condición de conexión/calibración",
        "action": "verificar conexiones, calibrar y normalizar señal de proceso",
        "priority": 9,
    },
    {
        "phrase": "baranda suelta",
        "disc": ["Civil", "Otra"],
        "cause": "elemento de protección colectiva con fijación deficiente",
        "action": "asegurar y reforzar fijación de protección colectiva",
        "priority": 10,
    },
    {
        "phrase": "piso resbaladizo",
        "disc": ["Civil", "Otra"],
        "cause": "superficie con condición que favorece deslizamiento",
        "action": "normalizar condición de piso y señalizar hasta corregir",
        "priority": 9,
    },
]


def _match_phrases_from_observations(obs_text: str, disciplina: str) -> List[dict]:
    obs_n = _normalize_for_exact_phrase_match(obs_text)
    d = (disciplina or "Otra").strip()

    hits = []
    for r in PHRASE_RULES:
        phrase_n = _normalize_for_exact_phrase_match(r["phrase"])
        if phrase_n and phrase_n in obs_n:
            if d in r.get("disc", ["Otra"]) or "Otra" in r.get("disc", []):
                hits.append(r)

    hits.sort(key=lambda x: int(x.get("priority", 0)), reverse=True)
    return hits


def _risk_text(disciplina: str, nivel: str) -> str:
    d = (disciplina or "Otra").strip()
    r = (nivel or "Medio").strip()
    nivel_txt = {"Bajo": "bajo", "Medio": "medio", "Alto": "alto"}.get(r, "medio")

    adj = {
        "Eléctrica": "eléctrico",
        "Mecánica": "mecánico",
        "Instrumental": "instrumental",
        "Civil": "civil",
        "Otra": "",
    }.get(d, "")

    return f"riesgo {adj} {nivel_txt}".strip()


def _prevent_text(nivel: str) -> str:
    r = (nivel or "Medio").strip()
    return {
        "Alto": "para prevenir accidentes y daño a equipos",
        "Medio": "para prevenir contacto accidental y fallas operacionales",
        "Bajo": "para mantener condiciones seguras de operación",
    }.get(r, "para prevenir contacto accidental y fallas operacionales")


def _fallback_conclusion_by_hallazgos(disciplina: str, nivel_riesgo: str, hallazgos: List[str]) -> str:
    d = (disciplina or "Otra").strip()
    r = (nivel_riesgo or "Medio").strip()
    hs = [h.strip() for h in (hallazgos or []) if (h or "").strip()]

    riesgo_txt = _risk_text(d, r)
    prevent_txt = _prevent_text(r)

    priority = ["LOTO", "Tableros", "Condición insegura", "Orden y limpieza", "Otros"]
    rule = {
        "LOTO": ("ausencia de control de energías previo a intervención", "implementar y verificar control LOTO antes de intervenir"),
        "Tableros": ("condición deficiente en tableros/protecciones", "normalizar tableros y asegurar protecciones/rotulación"),
        "Condición insegura": ("condición insegura presente en el área/equipo", "corregir condición insegura y asegurar control de riesgos"),
        "Orden y limpieza": ("condiciones deficientes de orden y limpieza", "ejecutar limpieza y control de material/polvo"),
        "Otros": ("hallazgos relevantes detectados", "corregir hallazgos según criticidad"),
    }

    base_by_disc = {
        "Eléctrica": ("condición deficiente en instalaciones eléctricas", "normalizar instalaciones y ejecutar limpieza/control del área"),
        "Mecánica": ("condición deficiente en elementos mecánicos", "normalizar resguardos y corregir condición mecánica"),
        "Instrumental": ("condición deficiente en instrumentación/señales", "verificar, calibrar y normalizar instrumentación/señales"),
        "Civil": ("condición deficiente en infraestructura", "reparar/asegurar infraestructura y mejorar condición del área"),
        "Otra": ("condiciones deficientes detectadas", "corregir condiciones detectadas y normalizar el área"),
    }

    if not hs:
        cause, action = base_by_disc.get(d, base_by_disc["Otra"])
        return f"Se determina {riesgo_txt} debido a {cause}. Se requiere {action} {prevent_txt}."

    selected_causes, selected_actions = [], []
    hs_set = set(hs)

    for p in priority:
        if p in hs_set:
            c, a = rule[p]
            if c not in selected_causes:
                selected_causes.append(c)
            if a not in selected_actions:
                selected_actions.append(a)
        if len(selected_causes) >= 2 and len(selected_actions) >= 2:
            break

    if not selected_causes:
        selected_causes = [base_by_disc.get(d, base_by_disc["Otra"])[0]]
    if not selected_actions:
        selected_actions = [base_by_disc.get(d, base_by_disc["Otra"])[1]]

    cause_txt = " y ".join(selected_causes[:2])
    action_txt = " y ".join(selected_actions[:2])
    return f"Se determina {riesgo_txt} debido a {cause_txt}. Se requiere {action_txt} {prevent_txt}."


def generate_conclusion_short(disciplina: str, nivel_riesgo: str, hallazgos: List[str], observaciones: str) -> str:
    d = (disciplina or "Otra").strip()
    r = (nivel_riesgo or "Medio").strip()
    obs = (observaciones or "").strip()

    riesgo_txt = _risk_text(d, r)
    prevent_txt = _prevent_text(r)

    if obs:
        hits = _match_phrases_from_observations(obs, d)
        if hits:
            causes, actions = [], []
            for h in hits:
                c = (h.get("cause") or "").strip()
                a = (h.get("action") or "").strip()
                if c and c not in causes:
                    causes.append(c)
                if a and a not in actions:
                    actions.append(a)
                if len(causes) >= 2 and len(actions) >= 2:
                    break

            if not causes or not actions:
                return _fallback_conclusion_by_hallazgos(d, r, hallazgos)

            cause_txt = " y ".join(causes[:2])
            action_txt = " y ".join(actions[:2])

            return f"Se determina {riesgo_txt} debido a {cause_txt}. Se requiere {action_txt} {prevent_txt}."

    return _fallback_conclusion_by_hallazgos(d, r, hallazgos)


def compute_auto_hash() -> str:
    d = st.session_state.get(FIELD_KEYS["disciplina"], "")
    r = st.session_state.get(FIELD_KEYS["nivel_riesgo"], "")
    h = ",".join(st.session_state.get(FIELD_KEYS["hallazgos"], []) or [])
    o = normalize_spaces(st.session_state.get(FIELD_KEYS["observaciones_raw"], "") or "")
    return f"{d}|{r}|{h}|{o}"


def sync_auto_conclusion_force():
    if not st.session_state.get(FIELD_KEYS["auto_conclusion"], True):
        return
    if st.session_state.get(FIELD_KEYS["conclusion_locked"], False):
        return

    st.session_state[FIELD_KEYS["conclusion"]] = generate_conclusion_short(
        st.session_state.get(FIELD_KEYS["disciplina"], "Otra"),
        st.session_state.get(FIELD_KEYS["nivel_riesgo"], "Medio"),
        st.session_state.get(FIELD_KEYS["hallazgos"], []),
        st.session_state.get(FIELD_KEYS["observaciones_raw"], ""),
    )
    st.session_state[FIELD_KEYS["last_auto_hash"]] = compute_auto_hash()


# -----------------------------
# Imágenes (COVER)
# -----------------------------
def _img_cover(file_bytes: bytes, w_mm: float, h_mm: float) -> io.BytesIO:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(file_bytes)).convert("RGB"))
    box_px_w = 1500
    box_px_h = max(1, int(box_px_w * (h_mm / w_mm)))

    scale = max(box_px_w / img.width, box_px_h / img.height)
    img = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)

    left = (img.width - box_px_w) // 2
    top = (img.height - box_px_h) // 2
    img = img.crop((left, top, left + box_px_w, top + box_px_h))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return buf


# -----------------------------
# PDF
# -----------------------------
def build_pdf(
    data_dict: dict,
    fotos: List[Tuple[str, bytes]],
    firma_img: Optional[Tuple[str, bytes]],
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, margin=15 * mm)
    styles = getSampleStyleSheet()

    story = [
        Paragraph("INFORME TÉCNICO DE INSPECCIÓN", styles["Heading1"]),
        Spacer(1, 8),
    ]

    table_data = [
        ["Fecha", data_dict["fecha"]],
        ["Título", data_dict["titulo"]],
        ["Disciplina", data_dict["disciplina"]],
        ["Riesgo", data_dict["nivel_riesgo"]],
        ["Equipo/Área", data_dict["equipo"] or "—"],
        ["Ubicación", data_dict["ubicacion"] or "—"],
        ["Inspector", data_dict["inspector"]],
        ["Cargo", data_dict["cargo"]],
        ["OT/Registro", data_dict["registro_ot"] or "—"],
    ]

    t = Table(table_data, colWidths=[42 * mm, 138 * mm])
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.extend([t, Spacer(1, 10)])

    story.append(Paragraph("Observaciones", styles["Heading2"]))
    story.append(Paragraph(escape(data_dict["observaciones"]).replace("\n", "<br/>"), styles["BodyText"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Conclusión", styles["Heading2"]))
    story.append(Paragraph(escape(data_dict["conclusion"]).replace("\n", "<br/>"), styles["BodyText"]))
    story.append(Spacer(1, 8))

    if fotos:
        story.append(Paragraph("Imágenes", styles["Heading2"]))
        use = fotos[:3]
        n = len(use)

        img_w_mm = TOTAL_IMG_W_MM / n
        img_h_mm = TOTAL_IMG_H_MM

        imgs = [
            RLImage(_img_cover(b, img_w_mm, img_h_mm), width=img_w_mm * mm, height=img_h_mm * mm)
            for _, b in use
        ]

        img_table = Table([imgs], colWidths=[img_w_mm * mm] * n)
        img_table.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(img_table)

    if firma_img:
        story.append(Spacer(1, 8))
        sig = RLImage(_img_cover(firma_img[1], SIGN_W_MM, SIGN_H_MM), width=SIGN_W_MM * mm, height=SIGN_H_MM * mm)
        story.append(sig)

    doc.build(story)
    return buffer.getvalue()


# -----------------------------
# Compartir (Web Share API) para móvil
# -----------------------------
def render_share_button(pdf_bytes: bytes, filename: str, token: str) -> None:
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    safe_name = (filename or "informe.pdf").replace('"', "").replace("'", "")

    html = f"""
    <div style="width:100%; margin-top: 10px;">
      <button id="shareBtn_{token}"
        style="
          width:100%;
          padding: 0.6rem 0.9rem;
          border-radius: 12px;
          border: 1px solid #CBD5E1;
          background: white;
          font-weight: 800;
          cursor: pointer;">
        📤 Compartir PDF
      </button>
      <div id="shareMsg_{token}" style="margin-top:8px; font-size: 0.9rem;"></div>
    </div>

    <script>
      (function() {{
        const btn = document.getElementById("shareBtn_{token}");
        const msg = document.getElementById("shareMsg_{token}");
        const b64 = "{b64}";
        const filename = "{safe_name}";

        function b64ToUint8Array(base64) {{
          const binary_string = atob(base64);
          const len = binary_string.length;
          const bytes = new Uint8Array(len);
          for (let i = 0; i < len; i++) {{
            bytes[i] = binary_string.charCodeAt(i);
          }}
          return bytes;
        }}

        async function sharePdf() {{
          try {{
            if (!navigator.share) {{
              msg.innerHTML = "⚠️ Tu navegador no permite compartir directo. Usa 'Descargar Informe'.";
              return;
            }}
            const bytes = b64ToUint8Array(b64);
            const blob = new Blob([bytes], {{ type: "application/pdf" }});
            const file = new File([blob], filename, {{ type: "application/pdf" }});

            const data = {{
              title: "Informe PDF",
              text: "Informe generado en jcamp029.pro",
              files: [file]
            }};

            if (navigator.canShare && !navigator.canShare(data)) {{
              msg.innerHTML = "⚠️ No se puede compartir archivo aquí. Descarga el PDF y compártelo manual.";
              return;
            }}

            await navigator.share(data);
            msg.innerHTML = "✅ Compartido.";
          }} catch (e) {{
            msg.innerHTML = "⚠️ Compartir cancelado o no disponible.";
          }}
        }}

        btn.addEventListener("click", sharePdf);
      }})();
    </script>
    """
    components.html(html, height=120)


# -----------------------------
# UI
# -----------------------------
apply_theme_css(st.session_state[FIELD_KEYS["theme"]])

st.markdown(f"<h1><i>{APP_TITLE}</i></h1><p class='muted'>{APP_SUBTITLE}</p>", unsafe_allow_html=True)

st.radio("Tema", ["Claro", "Oscuro"], horizontal=True, key=FIELD_KEYS["theme"])
apply_theme_css(st.session_state[FIELD_KEYS["theme"]])

# Configuración + Limpieza
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns([1, 1, 1, 1.4])
with c1:
    st.checkbox("Firma", key=FIELD_KEYS["include_signature"])
with c2:
    st.checkbox("Fotos", key=FIELD_KEYS["include_photos"])
with c3:
    st.checkbox("Corrección", key=FIELD_KEYS["show_correccion"])
with c4:
    if st.button("Limpiar formulario", use_container_width=True):
        hard_reset_now()
st.markdown("</div>", unsafe_allow_html=True)

# Formulario
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
cL, cR = st.columns(2)
with cL:
    st.text_input("Fecha", key=FIELD_KEYS["fecha"])
with cR:
    st.text_input("Título", key=FIELD_KEYS["titulo"])

cA, cB = st.columns(2)
with cA:
    st.selectbox("Disciplina", ["Eléctrica", "Mecánica", "Instrumental", "Civil", "Otra"], key=FIELD_KEYS["disciplina"])
    st.text_input("Equipo/Área", key=FIELD_KEYS["equipo"])
    st.text_input("Inspector", key=FIELD_KEYS["inspector"])
with cB:
    st.selectbox("Riesgo", ["Bajo", "Medio", "Alto"], key=FIELD_KEYS["nivel_riesgo"])
    st.text_input("Ubicación", key=FIELD_KEYS["ubicacion"])
    st.text_input("Cargo", key=FIELD_KEYS["cargo"])

# ✅ Sugerencia discreta (sin caja amarilla grande)
_ins = st.session_state.get(FIELD_KEYS["inspector"], "")
if _has_obvious_caps_issue(_ins):
    sugg = _recommended_title_name(_ins)
    if sugg and sugg != _ins.strip():
        st.caption(f"⚠️ Sugerido: {sugg}")

st.text_input("N° Registro/OT", key=FIELD_KEYS["registro_ot"])

# Hallazgos
try:
    st.multiselect(
        "Hallazgos",
        ["Condición insegura", "Orden y limpieza", "LOTO", "Tableros", "Otros"],
        key=FIELD_KEYS["hallazgos"],
        placeholder="Seleccione opciones",
    )
except TypeError:
    st.multiselect(
        "Hallazgos",
        ["Condición insegura", "Orden y limpieza", "LOTO", "Tableros", "Otros"],
        key=FIELD_KEYS["hallazgos"],
    )

st.text_area("Observaciones", height=120, key=FIELD_KEYS["observaciones_raw"])

# Corrección (técnica A)
if st.session_state[FIELD_KEYS["show_correccion"]]:
    if st.button("Sugerir correcciones"):
        fixed, changes = technical_spanish_fixes(st.session_state[FIELD_KEYS["observaciones_raw"]])
        st.session_state[FIELD_KEYS["obs_fixed_preview"]] = fixed
        if changes:
            st.info("Cambios: " + " | ".join(changes))
            st.info("Tip: para que se aplique en el PDF, presiona “Aplicar sugerencias”.")
        else:
            st.info("Sin cambios detectados.")
    if st.session_state.get(FIELD_KEYS["obs_fixed_preview"], "").strip():
        st.text_area("Sugerencia", key=FIELD_KEYS["obs_fixed_preview"], height=90)
        st.button("Aplicar sugerencias", on_click=apply_obs_fix)

# Auto / Manual
st.checkbox("Auto", key=FIELD_KEYS["auto_conclusion"])

cX, cY = st.columns(2)
with cX:
    if st.button("🔁 Auto", use_container_width=True):
        st.session_state[FIELD_KEYS["auto_started"]] = True
        st.session_state[FIELD_KEYS["conclusion_locked"]] = False
        sync_auto_conclusion_force()
        st.rerun()
with cY:
    if st.button("✍️ Manual", use_container_width=True):
        st.session_state[FIELD_KEYS["conclusion_locked"]] = True
        st.rerun()

st.text_area("Conclusión", height=120, key=FIELD_KEYS["conclusion"])
st.markdown("</div>", unsafe_allow_html=True)

# Multimedia
st.markdown("<div class='app-card'>", unsafe_allow_html=True)
st.subheader("Multimedia")
nonce = st.session_state[UP_NONCE]

fotos_files = (
    st.file_uploader("Fotos (Máx 3)", type=["jpg", "png", "jpeg"], accept_multiple_files=True, key=f"f_{nonce}")
    if st.session_state[FIELD_KEYS["include_photos"]]
    else None
)
firma_file = (
    st.file_uploader("Firma", type=["jpg", "png", "jpeg"], key=f"s_{nonce}")
    if st.session_state[FIELD_KEYS["include_signature"]]
    else None
)
st.markdown("</div>", unsafe_allow_html=True)

# Generación
if st.button("Generar PDF Profesional ✅", use_container_width=True):
    fotos = [(f.name, f.read()) for f in (fotos_files or [])[:3]]
    firma = (firma_file.name, firma_file.read()) if firma_file else None

    if st.session_state.get(FIELD_KEYS["auto_conclusion"], True) and not st.session_state.get(FIELD_KEYS["conclusion_locked"], False):
        if not (st.session_state.get(FIELD_KEYS["conclusion"], "").strip()):
            sync_auto_conclusion_force()

    datos = {
        "titulo": st.session_state[FIELD_KEYS["titulo"]],
        "fecha": st.session_state[FIELD_KEYS["fecha"]],
        "disciplina": st.session_state[FIELD_KEYS["disciplina"]],
        "equipo": st.session_state[FIELD_KEYS["equipo"]],
        "ubicacion": st.session_state[FIELD_KEYS["ubicacion"]],
        "inspector": st.session_state[FIELD_KEYS["inspector"]],
        "cargo": st.session_state[FIELD_KEYS["cargo"]],
        "registro_ot": st.session_state[FIELD_KEYS["registro_ot"]],
        "nivel_riesgo": st.session_state[FIELD_KEYS["nivel_riesgo"]],
        "observaciones": st.session_state[FIELD_KEYS["observaciones_raw"]],
        "conclusion": st.session_state[FIELD_KEYS["conclusion"]],
    }

    pdf_output = build_pdf(datos, fotos, firma)
    fname = f"informe_{datetime.now(TZ_CL).strftime('%H%M%S')}.pdf"

    st.session_state[FIELD_KEYS["last_pdf_bytes"]] = pdf_output
    st.session_state[FIELD_KEYS["last_pdf_name"]] = fname
    st.session_state[FIELD_KEYS["last_pdf_token"]] = datetime.now(TZ_CL).strftime("%Y%m%d%H%M%S%f")

    st.success("PDF generado ✅ (ya puedes descargar o compartir).")

# Acciones (descargar + compartir) usando el último PDF generado
last_pdf = st.session_state.get(FIELD_KEYS["last_pdf_bytes"], None)
last_name = st.session_state.get(FIELD_KEYS["last_pdf_name"], "")
last_token = st.session_state.get(FIELD_KEYS["last_pdf_token"], "")

if last_pdf:
    st.download_button(
        "Descargar Informe",
        data=last_pdf,
        file_name=last_name or f"informe_{datetime.now(TZ_CL).strftime('%H%M%S')}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    render_share_button(last_pdf, last_name or "informe.pdf", last_token or "share")

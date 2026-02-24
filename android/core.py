import io
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import List, Tuple, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage

from PIL import Image, ImageOps
from xml.sax.saxutils import escape


# ✅ Reglas Multimedia
TOTAL_IMG_W_MM = 150
TOTAL_IMG_H_MM = 60
SIGN_W_MM = 30
SIGN_H_MM = 30


@dataclass
class ReportData:
    titulo: str
    fecha: str
    disciplina: str
    equipo: str
    ubicacion: str
    inspector: str
    cargo: str
    registro_ot: str
    nivel_riesgo: str
    hallazgos: List[str]
    observaciones: str
    conclusion: str


# -----------------------------
# Texto / Corrección técnica (solo Observaciones)
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


# -----------------------------
# Auto-conclusión (frases exactas)
# -----------------------------
def _normalize_for_exact_phrase_match(s: str) -> str:
    s = normalize_spaces(s or "").lower()
    s = strip_accents(s)
    return s


PHRASE_RULES = [
    {"phrase": "luminaria suelta", "disc": ["Eléctrica", "Otra"], "cause": "sujeción deficiente en elemento de iluminación", "action": "asegurar fijación del punto de iluminación", "priority": 10},
    {"phrase": "polvo conductor", "disc": ["Eléctrica", "Otra"], "cause": "presencia de contaminación conductiva en el área", "action": "ejecutar limpieza y control de contaminación conductiva", "priority": 9},
    {"phrase": "tablero sin tapa", "disc": ["Eléctrica", "Otra"], "cause": "gabinete eléctrico con barreras de protección incompletas", "action": "normalizar gabinete y restituir barreras de protección", "priority": 10},
    {"phrase": "cable expuesto", "disc": ["Eléctrica", "Instrumental", "Otra"], "cause": "conductor/cableado sin protección adecuada", "action": "aislar, encauzar y proteger cableado según estándar", "priority": 10},
    {"phrase": "sin loto", "disc": ["Eléctrica", "Mecánica", "Instrumental", "Civil", "Otra"], "cause": "ausencia de control de energías previo a intervención", "action": "implementar y verificar control LOTO antes de intervenir", "priority": 11},
    {"phrase": "falta loto", "disc": ["Eléctrica", "Mecánica", "Instrumental", "Civil", "Otra"], "cause": "ausencia de control de energías previo a intervención", "action": "implementar y verificar control LOTO antes de intervenir", "priority": 11},
    {"phrase": "fuga de aceite", "disc": ["Mecánica", "Otra"], "cause": "pérdida de fluido por condición de estanqueidad deficiente", "action": "corregir estanqueidad y verificar ausencia de fugas", "priority": 10},
    {"phrase": "guarda faltante", "disc": ["Mecánica", "Otra"], "cause": "resguardo de partes móviles incompleto", "action": "restituir resguardo y asegurar integridad de protecciones", "priority": 10},
    {"phrase": "señal inestable", "disc": ["Instrumental", "Otra"], "cause": "variación anómala de señal por condición de conexión/calibración", "action": "verificar conexiones, calibrar y normalizar señal de proceso", "priority": 9},
    {"phrase": "baranda suelta", "disc": ["Civil", "Otra"], "cause": "elemento de protección colectiva con fijación deficiente", "action": "asegurar y reforzar fijación de protección colectiva", "priority": 10},
    {"phrase": "piso resbaladizo", "disc": ["Civil", "Otra"], "cause": "superficie con condición que favorece deslizamiento", "action": "normalizar condición de piso y señalizar hasta corregir", "priority": 9},
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

    adj = {"Eléctrica": "eléctrico", "Mecánica": "mecánico", "Instrumental": "instrumental", "Civil": "civil", "Otra": ""}.get(d, "")
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


# -----------------------------
# Imágenes (cover 15x6 total)
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


def build_pdf(
    data: ReportData,
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
        ["Fecha", data.fecha],
        ["Título", data.titulo],
        ["Disciplina", data.disciplina],
        ["Riesgo", data.nivel_riesgo],
        ["Equipo/Área", data.equipo or "—"],
        ["Ubicación", data.ubicacion or "—"],
        ["Inspector", data.inspector],
        ["Cargo", data.cargo],
        ["OT/Registro", data.registro_ot or "—"],
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
    story.append(Paragraph(escape(data.observaciones).replace("\n", "<br/>"), styles["BodyText"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Conclusión", styles["Heading2"]))
    story.append(Paragraph(escape(data.conclusion).replace("\n", "<br/>"), styles["BodyText"]))
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

import io
import os
import re
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Tuple

from PIL import Image as PILImage, ImageOps
from fpdf import FPDF


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


_COMMON_FIXES = [
    (r"\bq\b", "que"),
    (r"\bxq\b", "porque"),
    (r"\bporq\b", "porque"),
    (r"\bde el\b", "del"),
    (r"\ba el\b", "al"),
]


def _clean_spaces(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def technical_spanish_fixes(text: str):
    original = text or ""
    out = original
    changes = []

    out2 = _clean_spaces(out)
    if out2 != out:
        changes.append("Espacios/formatos normalizados")
        out = out2

    for pat, rep in _COMMON_FIXES:
        new = re.sub(pat, rep, out, flags=re.IGNORECASE)
        if new != out:
            changes.append(f"Reemplazo '{pat}'")
            out = new

    if out and out[0].islower():
        out = out[0].upper() + out[1:]
        changes.append("Mayúscula inicial")

    return out, changes


def generate_conclusion_short(disciplina: str, riesgo: str, hallazgos: List[str], observaciones: str) -> str:
    d = (disciplina or "").strip()
    r = (riesgo or "").strip()
    h = [x.strip() for x in (hallazgos or []) if x.strip()]

    if h:
        h_txt = ", ".join(h[:4]) + ("…" if len(h) > 4 else "")
        base = f"Se determina riesgo {r.lower()} en disciplina {d.lower()} por hallazgos: {h_txt}."
    else:
        base = f"Se determina riesgo {r.lower()} en disciplina {d.lower()} según condición observada."

    rec = "Se requieren acciones correctivas y verificación en próxima inspección."
    return f"{base} {rec}".strip()


# Regla multimedia: bloque total fotos 150x60 mm (15x6 cm)
TOTAL_IMG_W_MM = 150
TOTAL_IMG_H_MM = 60

# Firma 3x3 cm
SIGN_W_MM = 30
SIGN_H_MM = 30


def _tmp_write_image(img_bytes: bytes, suggested_name: str = "img") -> str:
    ext = ".jpg"
    name_lower = (suggested_name or "").lower()
    if name_lower.endswith(".png"):
        ext = ".png"
    elif name_lower.endswith(".jpeg"):
        ext = ".jpeg"
    elif name_lower.endswith(".jpg"):
        ext = ".jpg"

    fd, path = tempfile.mkstemp(prefix="jcamp029_", suffix=ext)
    os.close(fd)
    with open(path, "wb") as f:
        f.write(img_bytes)
    return path


def _img_size_px(img_bytes: bytes) -> Tuple[int, int]:
    with io.BytesIO(img_bytes) as bio:
        im = PILImage.open(bio)
        im = ImageOps.exif_transpose(im)
        return im.size


def _fit_box(orig_w: float, orig_h: float, box_w: float, box_h: float) -> Tuple[float, float]:
    if orig_w <= 0 or orig_h <= 0:
        return box_w, box_h
    scale = min(box_w / orig_w, box_h / orig_h)
    return orig_w * scale, orig_h * scale


class _PDF(FPDF):
    pass


def build_pdf(
    data: ReportData,
    fotos: List[Tuple[str, bytes]],
    firma: Optional[Tuple[str, bytes]],
) -> bytes:
    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 8, data.titulo or "Informe")
    pdf.ln(1)

    pdf.set_font("Helvetica", "", 10)

    def row(label: str, value: str):
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(40, 6, f"{label}:", 0, 0)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, value or "-")

    row("Fecha", data.fecha)
    row("Disciplina", data.disciplina)
    row("Riesgo", data.nivel_riesgo)
    row("Equipo/Área", data.equipo)
    row("Ubicación", data.ubicacion)
    row("Inspector", data.inspector)
    row("Cargo", data.cargo)
    row("N° Registro/OT", data.registro_ot)
    row("Hallazgos", ", ".join(data.hallazgos) if data.hallazgos else "-")

    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Observaciones", 0, 1)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5.5, data.observaciones or "-")
    pdf.ln(1)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, "Conclusión", 0, 1)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5.5, data.conclusion or "-")
    pdf.ln(2)

    fotos = (fotos or [])[:3]
    if fotos:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Registro fotográfico", 0, 1)

        x0 = pdf.get_x()
        y0 = pdf.get_y()

        if y0 + TOTAL_IMG_H_MM + 10 > (pdf.h - pdf.b_margin):
            pdf.add_page()
            x0 = pdf.get_x()
            y0 = pdf.get_y()

        n = len(fotos)
        slot_w = TOTAL_IMG_W_MM / n
        slot_h = TOTAL_IMG_H_MM

        for i, (name, bts) in enumerate(fotos):
            try:
                iw, ih = _img_size_px(bts)
                draw_w, draw_h = _fit_box(iw, ih, slot_w, slot_h)

                sx = x0 + i * slot_w
                sy = y0
                px = sx + (slot_w - draw_w) / 2
                py = sy + (slot_h - draw_h) / 2

                tmp = _tmp_write_image(bts, name)
                pdf.image(tmp, x=px, y=py, w=draw_w, h=draw_h)
                try:
                    os.remove(tmp)
                except Exception:
                    pass
            except Exception:
                continue

        pdf.set_y(y0 + TOTAL_IMG_H_MM + 3)

    if firma:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "Firma", 0, 1)

        y = pdf.get_y()
        if y + SIGN_H_MM + 12 > (pdf.h - pdf.b_margin):
            pdf.add_page()

        name, bts = firma
        try:
            iw, ih = _img_size_px(bts)
            draw_w, draw_h = _fit_box(iw, ih, SIGN_W_MM, SIGN_H_MM)

            x = pdf.get_x()
            y = pdf.get_y()

            px = x + (SIGN_W_MM - draw_w) / 2
            py = y + (SIGN_H_MM - draw_h) / 2

            tmp = _tmp_write_image(bts, name)
            pdf.image(tmp, x=px, y=py, w=draw_w, h=draw_h)
            try:
                os.remove(tmp)
            except Exception:
                pass

            pdf.set_y(y + SIGN_H_MM + 2)
        except Exception:
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 6, "Firma cargada, pero no se pudo insertar como imagen.")

    out = pdf.output(dest="S")
    return out.encode("latin-1") if isinstance(out, str) else bytes(out)

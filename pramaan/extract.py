"""Document understanding, LITE providers: PDF text layer, anchor extractor, keyword classifier, QR reader.
Models are named by role. Scanned pages with no text layer go to manual review (no OCR/Handwriting Model on serverless)."""
import io
import re
from datetime import datetime

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from PIL import Image

PROVIDERS = {"ocr": "PDF text layer (LITE)", "classifier": "Keyword classifier (LITE)",
             "extractor": "Anchor/regex extractor (LITE)", "handwriting": "not available in LITE"}

DATE_FORMATS = ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%d.%m.%Y"]


def norm_date(s):
    s = s.strip().rstrip(".")
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s, f).date().isoformat()
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})(?!\d)", s)
    if m and s.strip() != m.group(0):
        return norm_date(m.group(0))
    return None


def norm_number(s):
    m = re.search(r"[\d,]+(\.\d+)?", s)
    return float(m.group(0).replace(",", "")) if m else None


def open_pdf(data):
    return pdfium.PdfDocument(data)


def pdf_text(pdf):
    pages = []
    for i in range(len(pdf)):
        tp = pdf[i].get_textpage()
        pages.append(tp.get_text_bounded())
    return pages


def render_page(pdf, i, scale=1.5):
    return pdf[i].render(scale=scale).to_pil().convert("RGB")


def page_images(pdf, i):
    out = []
    for obj in pdf[i].get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE]):
        try:
            out.append(obj.get_bitmap(render=False).to_pil().convert("RGB"))
        except Exception:
            pass
    return out


def find_bbox(pdf, page_i, text):
    """Return [x, y, w, h] as fractions of the page, top-left origin."""
    page = pdf[page_i]
    w, h = page.get_size()
    tp = page.get_textpage()
    s = tp.search(text, match_case=True)
    occ = s.get_next()
    if not occ:
        return None
    idx, n = occ
    boxes = [tp.get_charbox(idx + k) for k in range(n)]
    l, b = min(x[0] for x in boxes), min(x[1] for x in boxes)
    r, t = max(x[2] for x in boxes), max(x[3] for x in boxes)
    return [round(l / w, 4), round((h - t) / h, 4), round((r - l) / w, 4), round((t - b) / h, 4)]


def classify(text, taxonomy):
    low = text.lower()
    best, score = None, 0
    for t, spec in taxonomy.items():
        kws = spec.get("keywords") or []
        hits = sum(1 for k in kws if k in low)
        if kws and hits / len(kws) > score:
            best, score = t, hits / len(kws)
    return best, round(score, 2)


def extract_fields(pdf, pages, spec):
    """Anchor 'Label: value' lines. Returns {field: {value, raw, page, bbox, conf}}."""
    out = {}
    for fname, fs in (spec.get("fields") or {}).items():
        anchor = re.escape(fs["anchor"])
        for pi, txt in enumerate(pages):
            m = re.search(anchor + r"\s*:\s*(.+)", txt)
            if not m:
                continue
            raw = m.group(1).strip()
            if fs.get("type") == "date":
                val = norm_date(raw)
            elif fs.get("type") == "number":
                val = norm_number(raw)
            else:
                val = raw
            out[fname] = {"value": val, "raw": raw, "page": pi, "bbox": find_bbox(pdf, pi, raw),
                          "conf": 0.99 if val is not None else 0.4}
            break
    return out


def read_qr(pdf):
    import zxingcpp
    for i in range(len(pdf)):
        img = render_page(pdf, i, scale=3)
        for r in zxingcpp.read_barcodes(img):
            if r.format == zxingcpp.BarcodeFormat.QRCode:
                p = r.position
                xs = [p.top_left.x, p.top_right.x, p.bottom_left.x, p.bottom_right.x]
                ys = [p.top_left.y, p.top_right.y, p.bottom_left.y, p.bottom_right.y]
                w, h = img.size
                bbox = [min(xs) / w, min(ys) / h, (max(xs) - min(xs)) / w, (max(ys) - min(ys)) / h]
                return {"payload": r.text, "page": i, "bbox": [round(v, 4) for v in bbox]}
    return None


INJECTION = [r"ignore (all |any )?(previous|prior|above) instructions", r"system prompt", r"you are now",
             r"mark (this|the) application as (approved|verified|clean)", r"disregard .{0,30}rules"]


def injection_hits(text):
    low = text.lower()
    return [p for p in INJECTION if re.search(p, low)]


def to_png(img, max_w=1100):
    if img.width > max_w:
        img = img.resize((max_w, int(img.height * max_w / img.width)))
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=82)
    return b.getvalue()


def load_image(data):
    return Image.open(io.BytesIO(data))

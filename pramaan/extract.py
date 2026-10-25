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


DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def norm_date(s):
    s = s.translate(DEV_DIGITS).strip().rstrip(".")
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
    s = s.translate(DEV_DIGITS)
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


def find_bbox(pdf, page_i, text, label=None):
    """Return [x, y, w, h] as fractions of the page, top-left origin. With `label`, the value is found right after
    'label: ' so a value that also appears elsewhere (an issuer name in the letterhead) is boxed in the right place."""
    page = pdf[page_i]
    w, h = page.get_size()
    tp = page.get_textpage()
    occ, skip = None, 0
    if label:
        for sep in (": ", ":", " : "):
            occ = tp.search(label + sep + text, match_case=True).get_next()
            if occ:
                skip = len(label + sep)
                break
    if not occ:
        occ = tp.search(text, match_case=True).get_next()
        skip = 0
    if not occ:
        return None
    idx, n = occ[0] + skip, occ[1] - skip
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
        for pi, txt in enumerate(pages):
            m = None
            for anc in [fs["anchor"]] + list(fs.get("alt_anchors") or []):  # English label first, then Hindi labels
                m = re.search(re.escape(anc) + r"\s*:\s*(.+)", txt)
                if m:
                    break
            if not m:
                continue
            raw = m.group(1).strip()
            if fs.get("type") == "date":
                val = norm_date(raw)
            elif fs.get("type") == "number":
                val = norm_number(raw)
            else:
                val = raw
            out[fname] = {"value": val, "raw": raw, "page": pi, "bbox": find_bbox(pdf, pi, raw, anc),
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
             r"mark (this|the) (application|document) (as )?(approved|verified|clean|genuine)", r"disregard .{0,30}rules",
             r"(^|\n)\s*system\s*:"]


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


# ---------------- tables (FR-DOC-06), digital PDFs
def extract_tables(data):
    """Tables from the text layer: [{page, rows: [[cell, ...], ...]}]."""
    import pdfplumber
    out = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for i, page in enumerate(pdf.pages):
            for t in page.extract_tables():
                rows = [[(c or "").strip() for c in r] for r in t if any((c or "").strip() for c in r)]
                if len(rows) >= 2:
                    out.append({"page": i, "rows": rows})
    return out


# ---------------- floor plans (FR-INF-06), vector PDFs
def floor_plan(data):
    """Rooms from a vector floor plan: rectangles with a label inside, sized with the printed 'Scale 1:N'.
    Returns None for raster plans (scans or photos), which go to manual review."""
    import pdfplumber
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        page = pdf.pages[0]
        text = page.extract_text() or ""
        m = re.search(r"Scale\s*:?\s*1\s*:\s*(\d+)", text, re.I)
        rects = [r for r in page.rects if r["width"] > 20 and r["height"] > 20]
        if not m or not rects:
            return None
        k = 0.3528 / 1000 * int(m.group(1))  # metres per PDF point at this scale
        words = page.extract_words()
        rooms = []
        for r in rects:
            # a label belongs to the room it starts in (long labels may run past a small room's wall)
            inside = [w["text"] for w in words if r["x0"] < w["x0"] < r["x1"] and r["top"] < w["top"] and w["bottom"] < r["bottom"]]
            label = next((w for w in inside if re.match(r"^[A-Z]+(_[A-Z]+)*_\d+$", w)), None)
            if label:
                W, H = page.width, page.height
                rooms.append({"label": label, "area_sqm": round(r["width"] * k * r["height"] * k, 1),
                              "bbox": [round(r["x0"] / W, 4), round(r["top"] / H, 4), round(r["width"] / W, 4), round(r["height"] / H, 4)]})
        return {"scale": f"1:{m.group(1)}", "rooms": rooms}


# ---------------- video (FR-DOC-12): sample frames, drop near-duplicates
def video_frames(data, fps=1, max_frames=8):
    import os
    import subprocess
    import tempfile

    try:
        import imageio_ffmpeg
    except ImportError:  # hosted build ships without ffmpeg
        return None
    from PIL import Image
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "in.mp4")
        open(src, "wb").write(data)
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-i", src, "-vf", f"fps={fps}", "-frames:v", str(max_frames),
                        os.path.join(d, "f%02d.png")], check=True, timeout=60)
        frames = [Image.open(os.path.join(d, f)).convert("RGB") for f in sorted(os.listdir(d)) if f.endswith(".png")]
    from .forensics import dhash, hamming
    keep, hashes = [], []
    for f in frames:
        h = dhash(f)
        if all(hamming(h, x) > 6 for x in hashes):
            keep.append(f)
            hashes.append(h)
    return keep


# ---------------- raster floor plans (scans, photos, exported images)
def _morph(mask, r, grow):
    """Square dilation (grow=True) or erosion (grow=False) of a boolean mask by r pixels."""
    import numpy as np
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            sh = np.roll(np.roll(mask, dy, 0), dx, 1)
            out = (out | sh) if grow else (out & sh)
    return out


def floor_plan_raster(img, wall_thresh=120, thick=0, door=3, min_room_frac=0.004):  # tuned on 20 CubiCasa5K plans
    """Rooms as enclosed white regions between walls. Thin lines (furniture, text, door swings) are dropped by keeping only
    wall strokes thicker than 2*thick px, and doorways are closed by growing walls `door` px. Areas are relative (pixels):
    a raster plan has no reliable scale. Returns [{bbox, area_px}] with bbox in page fractions."""
    import numpy as np
    from .forensics import label
    g = np.asarray(img.convert("L"), dtype=np.uint8)
    H, W = g.shape
    k = max(1, max(H, W) // 800)
    small = g[::k, ::k]
    walls = small < wall_thresh
    if thick:
        walls = _morph(_morph(walls, thick, False), thick, True)  # opening keeps thick strokes only
    sealed = _morph(walls, door, True)
    h, w = small.shape
    rooms = []
    for area, x, y, bw, bh in label(~sealed):
        if x == 0 or y == 0 or x + bw >= w or y + bh >= h or area < min_room_frac * h * w:
            continue
        x0, y0 = max(0, x - door), max(0, y - door)  # undo the wall growth on the box
        x1, y1 = min(w, x + bw + door), min(h, y + bh + door)
        rooms.append({"bbox": [round(x0 / w, 4), round(y0 / h, 4), round((x1 - x0) / w, 4), round((y1 - y0) / h, 4)], "area_px": int(area * k * k)})
    return sorted(rooms, key=lambda r: -r["area_px"])

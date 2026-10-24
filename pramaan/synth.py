"""Synthetic documents, photos and ground truth. Fictional issuers and institutions only; every issuer is marked (mock)."""
import base64
import io
import json
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

W, H = A4


def b64u(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def qr_payload(issuer_id, priv, fields):
    body = json.dumps({"iss": issuer_id, **fields}, separators=(",", ":")).encode()
    return f"PRM1.{b64u(body)}.{b64u(priv.sign(body))}"


def pdf_doc(title, issuer, lines, qr=None, extra=None, creation=None):
    """lines: list of (label, value). Returns PDF bytes."""
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4, invariant=1)
    c.setTitle(title)
    c.setAuthor(issuer)
    c.setProducer("PRAMAAN synthetic generator")
    c.setFillColorRGB(0.12, 0.22, 0.4)
    c.rect(0, H - 70, W, 70, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(40, H - 42, issuer)
    c.setFont("Helvetica", 9)
    c.drawString(40, H - 58, "Fictional issuer for prototype testing. Not a government document.")
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(40, H - 115, title)
    c.setFont("Helvetica", 11)
    y = H - 160
    for label, value in lines:
        c.drawString(40, y, f"{label}: {value}")
        y -= 24
    for t in extra or []:
        c.drawString(40, y, t)
        y -= 18
    # stamp + signature
    c.setStrokeColorRGB(0.2, 0.3, 0.7)
    c.setLineWidth(2)
    c.circle(W - 130, 150, 45)
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0.2, 0.3, 0.7)
    c.drawCentredString(W - 130, 152, issuer[:28])
    c.drawCentredString(W - 130, 142, "(mock seal)")
    c.setStrokeColorRGB(0, 0, 0)
    p = c.beginPath()
    p.moveTo(60, 140)
    for k in range(12):
        p.curveTo(70 + k * 12, 160, 76 + k * 12, 120, 84 + k * 12, 140)
    c.drawPath(p)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 9)
    c.drawString(60, 115, "Authorised signatory")
    if qr:
        import qrcode
        img = qrcode.make(qr, box_size=4, border=2).convert("RGB")
        c.drawImage(ImageReader(img), W - 190, H - 290, 150, 150)
        c.setFont("Helvetica", 7)
        c.drawString(W - 190, H - 300, "Scan to verify (signed by issuer)")
    c.showPage()
    c.save()
    return b.getvalue()


def _font(size, hand=False):
    for p in (["C:/Windows/Fonts/Inkfree.ttf"] if hand else []) + ["C:/Windows/Fonts/arial.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def scanned_affidavit(lines_printed, hand_fields, tamper=None, seed=1):
    """A noisy 'scan' with handwritten fills. tamper=(field_index, new_text) pastes a clean patch over a value."""
    rnd = random.Random(seed)
    img = Image.new("L", (1240, 1754), 245)
    d = ImageDraw.Draw(img)
    d.text((90, 90), "GENERAL AFFIDAVIT", font=_font(44), fill=20)
    d.text((90, 150), "Before the Notary (mock) - fictional, for prototype testing", font=_font(22), fill=60)
    y = 240
    for t in lines_printed:
        d.text((90, y), t, font=_font(28), fill=25)
        y += 50
    pos = []
    for label, val in hand_fields:
        d.text((90, y), label + ":", font=_font(28), fill=25)
        x = 420
        for ch in val:
            d.text((x, y - 6 + rnd.randint(-3, 3)), ch, font=_font(34, True), fill=rnd.randint(30, 70))
            x += int(_font(34, True).getlength(ch)) + rnd.randint(0, 3)
        pos.append((420, y - 10, x + 10, y + 44))
        y += 70
    d.ellipse((900, 1450, 1110, 1660), outline=90, width=5)
    arr = np.array(img.rotate(0.6, fillcolor=245).filter(ImageFilter.GaussianBlur(0.6)), dtype=np.float32)
    arr += np.random.default_rng(seed).normal(0, 7, arr.shape)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    if tamper:
        i, new = tamper
        x0, y0, x1, y1 = pos[i]
        patch = Image.new("L", (x1 - x0 + 160, y1 - y0), 245)
        ImageDraw.Draw(patch).text((0, 6), new, font=_font(34, True), fill=40)
        img.paste(patch, (x0, y0))
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=93)
    pdf = io.BytesIO()
    c = canvas.Canvas(pdf, pagesize=A4, invariant=1)
    c.drawImage(ImageReader(io.BytesIO(b.getvalue())), 0, 0, W, H)
    c.showPage()
    c.save()
    return pdf.getvalue()


def lab_photo(monitors, seed=1, wall=(214, 218, 210)):
    rnd = random.Random(seed)
    img = Image.new("RGB", (1024, 768), wall)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 520, 1024, 768), fill=(170, 160, 140))
    bx = rnd.randint(20, 600)
    d.rectangle((bx, 40 + rnd.randint(0, 40), bx + rnd.randint(200, 380), 200), fill=(240, 240, 235), outline=(120, 120, 120), width=4)
    for _ in range(rnd.randint(1, 3)):
        wx = rnd.randint(0, 900)
        d.rectangle((wx, 20, wx + rnd.randint(60, 140), 120 + rnd.randint(0, 80)), fill=tuple(rnd.randint(150, 255) for _ in range(3)))
    per_row = rnd.randint(7, 8)
    rows = (monitors + per_row - 1) // per_row
    k = 0
    for r in range(rows):
        y = 250 + rnd.randint(0, 30) + r * 120
        d.rectangle((40, y + 50, 984, y + 70), fill=(150, 110, 70))
        for cidx in range(per_row):
            if k >= monitors:
                break
            x = 50 + rnd.randint(0, 40) + cidx * 115 + rnd.randint(-4, 4)
            d.rectangle((x, y, x + 70, y + 42), fill=(25, 28, 32))
            d.rectangle((x + 30, y + 44, x + 40, y + 50), fill=(110, 110, 110))
            k += 1
    arr = np.array(img, dtype=np.float32) + np.random.default_rng(seed).normal(0, 4, (768, 1024, 3))
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _dms(v):
    v = abs(v)
    dd = int(v)
    mm = int((v - dd) * 60)
    ss = round(((v - dd) * 60 - mm) * 60, 2)
    return (float(dd), float(mm), float(ss))


def jpeg_with_exif(img, lat=None, lon=None, taken="2026:09:20 10:30:00", quality=88):
    ex = Image.Exif()
    ex[306] = taken
    if lat is not None:
        from PIL import TiffImagePlugin
        ex[0x8825] = {1: "N" if lat >= 0 else "S", 2: tuple(TiffImagePlugin.IFDRational(x) for x in _dms(lat)),
                      3: "E" if lon >= 0 else "W", 4: tuple(TiffImagePlugin.IFDRational(x) for x in _dms(lon))}
    b = io.BytesIO()
    img.save(b, "JPEG", quality=quality, exif=ex)
    return b.getvalue()

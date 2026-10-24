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


def scanned_affidavit(lines_printed, hand_fields, tamper=None, seed=1, damage=True):
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
    base = img.rotate(0.6, fillcolor=245).filter(ImageFilter.GaussianBlur(0.6))
    if damage:
        base = degrade(base, seed=seed)
    arr = np.array(base, dtype=np.float32)
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


# ---------------- demo PKI: deterministic CA and issuer certificates, pyHanko-signed PDFs
def _ec_key(label):
    import hashlib
    from cryptography.hazmat.primitives.asymmetric import ec
    n = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
    v = int.from_bytes(hashlib.sha256((os.environ.get("ISSUER_KEY_SEED", "pramaan-demo-issuers") + label).encode()).digest(), "big") % (n - 1) + 1
    return ec.derive_private_key(v, ec.SECP256R1())


def _cert(subject_cn, key, issuer_cn, issuer_key, ca, serial):
    from datetime import datetime, timezone
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.x509.oid import NameOID
    name = lambda cn: x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn), x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PRAMAAN demo PKI (mock)")])
    b = (x509.CertificateBuilder().subject_name(name(subject_cn)).issuer_name(name(issuer_cn)).public_key(key.public_key())
         .serial_number(serial).not_valid_before(datetime(2020, 1, 1, tzinfo=timezone.utc)).not_valid_after(datetime(2036, 1, 1, tzinfo=timezone.utc))
         .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
         .add_extension(x509.KeyUsage(digital_signature=not ca, content_commitment=not ca, key_encipherment=False, data_encipherment=False,
                                      key_agreement=False, key_cert_sign=ca, crl_sign=ca, encipher_only=False, decipher_only=False), critical=True))
    return b.sign(issuer_key, hashes.SHA256())


CA_CN = "PRAMAAN Demo Issuer Root CA (mock)"


def demo_ca():
    k = _ec_key("CA")
    return k, _cert(CA_CN, k, CA_CN, k, True, 1000)


def issuer_cert(iid, name, ca_key):
    k = _ec_key("SIG" + iid)
    return k, _cert(name, k, CA_CN, ca_key, False, 2000 + sum(map(ord, iid)))


def sign_pdf(pdf, key, cert, ca_cert):
    from asn1crypto import keys as ak, x509 as ax
    from cryptography.hazmat.primitives import serialization as ser
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers
    from pyhanko_certvalidator.registry import SimpleCertificateStore
    sk = ak.PrivateKeyInfo.load(key.private_bytes(ser.Encoding.DER, ser.PrivateFormat.PKCS8, ser.NoEncryption()))
    c = ax.Certificate.load(cert.public_bytes(ser.Encoding.DER))
    ca = ax.Certificate.load(ca_cert.public_bytes(ser.Encoding.DER))
    signer = signers.SimpleSigner(signing_cert=c, signing_key=sk, cert_registry=SimpleCertificateStore.from_certs([ca]))
    out = signers.sign_pdf(IncrementalPdfFileWriter(io.BytesIO(pdf), strict=False), signers.PdfSignatureMetadata(field_name="IssuerSignature"), signer=signer)
    return out.getvalue()


def edit_after_signing(pdf, text="Valid until: 31-03-2060"):
    """Forgery: an incremental update that adds visible text after the signature."""
    from pyhanko.pdf_utils import generic
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    w = IncrementalPdfFileWriter(io.BytesIO(pdf), strict=False)
    page = w.root["/Pages"]["/Kids"][0].get_object()
    stream = generic.StreamObject(stream_data=f"BT /F1 11 Tf 40 300 Td ({text}) Tj ET".encode())
    ref = w.add_object(stream)
    contents = page["/Contents"]
    arr = contents if isinstance(contents, generic.ArrayObject) else generic.ArrayObject([page.raw_get("/Contents")])
    arr.append(ref)
    page["/Contents"] = arr
    w.update_container(page)
    b = io.BytesIO()
    w.write(b)
    return b.getvalue()


def degrade(img, seed=1, folds=True, stain=True, low_dpi=True):
    """Scan damage: low DPI resample, a fold line and a tea stain (FR-SYN-02)."""
    rnd = random.Random(seed)
    if low_dpi:
        w, h = img.size
        img = img.resize((int(w * 0.6), int(h * 0.6))).resize((w, h))
    a = np.array(img, dtype=np.float32)
    if folds:
        y = rnd.randint(a.shape[0] // 3, 2 * a.shape[0] // 3)
        a[y - 2:y + 2] *= 0.82
        a[y + 2:y + 14] *= 1.04
    if stain:
        cy, cx, r = rnd.randint(200, a.shape[0] - 200), rnd.randint(200, a.shape[1] - 200), rnd.randint(60, 120)
        yy, xx = np.ogrid[: a.shape[0], : a.shape[1]]
        m = np.exp(-(((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * r * r)))
        tint = np.array([0.92, 0.85, 0.72]) if a.ndim == 3 else 0.85
        a = a * (1 - m[..., None] * (1 - tint)) if a.ndim == 3 else a * (1 - m * (1 - tint))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def table_pdf(title, issuer, lines, header, rows, total_row=None, extra=None):
    """A document with labelled fields and a ruled table (fee receipts, faculty lists)."""
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4, invariant=1)
    c.setTitle(title)
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
    y = H - 150
    for label, value in lines:
        c.drawString(40, y, f"{label}: {value}")
        y -= 22
    data = [header] + rows + ([total_row] if total_row else [])
    t = Table(data, colWidths=[(W - 80) / len(header)] * len(header), rowHeights=14)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.6, colors.black), ("FONTSIZE", (0, 0), (-1, -1), 9),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)]))
    tw, th = t.wrapOn(c, W - 80, y)
    t.drawOn(c, 40, y - th - 10)
    y = y - th - 40
    for line in extra or []:
        c.drawString(40, y, line)
        y -= 16
    c.setStrokeColorRGB(0.2, 0.3, 0.7)
    c.setLineWidth(2)
    c.circle(W - 130, 110, 40)
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0.2, 0.3, 0.7)
    c.drawCentredString(W - 130, 110, "(mock seal)")
    c.setStrokeColorRGB(0, 0, 0)
    p = c.beginPath()
    p.moveTo(60, 110)
    for k in range(10):
        p.curveTo(70 + k * 12, 130, 76 + k * 12, 90, 84 + k * 12, 110)
    c.drawPath(p)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 9)
    c.drawString(60, 85, "Authorised signatory")
    c.showPage()
    c.save()
    return b.getvalue()


def floor_plan_pdf(rooms, scale=100, institution="Demo Institute"):
    """Vector floor plan: one rectangle per room (label inside), drawn to the printed scale. rooms: [(label, w_m, h_m)]."""
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4, invariant=1)
    c.setTitle("Floor Plan")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, H - 60, "Floor Plan - Ground Floor")
    c.setFont("Helvetica", 10)
    c.drawString(40, H - 78, f"Institution: {institution}")
    c.drawString(40, H - 94, f"Scale 1:{scale}   (all dimensions in metres)   Prepared by: Fictional Architects (mock)")
    pt = 1000 / 0.3528 / scale  # PDF points per metre
    x, y = 50, H - 140
    for label, wm, hm in rooms:
        w, h = wm * pt, hm * pt
        if x + w > W - 40:
            x, y = 50, y - h - 30
        c.setLineWidth(2)
        c.rect(x, y - h, w, h)
        c.setFont("Helvetica", 9)
        c.drawString(x + 6, y - 16, label)
        c.drawString(x + 6, y - 28, f"{wm} m x {hm} m")
        x += w + 20
    c.showPage()
    c.save()
    return b.getvalue()


def lab_video(monitors, seed=1, seconds=4, fps=2):
    """A short walkthrough: the camera pans across one lab. Returns MP4 bytes."""
    import os
    import tempfile

    import imageio_ffmpeg
    wide = lab_photo(monitors, seed=seed).resize((1280, 768))
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "v.mp4")
        w = imageio_ffmpeg.write_frames(out, (1024, 768), fps=fps, macro_block_size=16, quality=7)
        w.send(None)
        n = seconds * fps
        for i in range(n):
            x = int(256 * i / max(1, n - 1))
            w.send(np.ascontiguousarray(np.array(wide.crop((x, 0, x + 1024, 768)))))
        w.close()
        return open(out, "rb").read()

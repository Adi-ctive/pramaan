"""Classical tamper indicators: noise-residual inconsistency, ELA, copy-move, PDF structure, perceptual hash.
Results are indicators that require verification, never proof."""
import io
import re

import cv2
import numpy as np
from PIL import Image

VERSION = "1.0.0"


def _gray(img):
    return np.array(img.convert("L"), dtype=np.float32)


def noise_map(img, block=16):
    """Block std-dev of the high-pass residual, relative to the image median. Pasted clean patches stand out."""
    g = _gray(img)
    res = g - cv2.medianBlur(g.astype(np.uint8), 3).astype(np.float32)
    h, w = (g.shape[0] // block) * block, (g.shape[1] // block) * block
    r = res[:h, :w].reshape(h // block, block, w // block, block)
    std = r.std(axis=(1, 3))
    med = float(np.median(std)) or 1e-3
    return std / med, block


def noise_check(img, threshold=0.65):
    ratio, block = noise_map(img)
    mask = ((ratio < 0.35) | (ratio > 3.0)).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    best = None
    for i in range(1, n):
        if best is None or stats[i, cv2.CC_STAT_AREA] > stats[best, cv2.CC_STAT_AREA]:
            best = i
    area = int(stats[best, cv2.CC_STAT_AREA]) if best else 0
    score = round(min(1.0, area / 12), 3)
    region = None
    if best:
        x, y, w, h = stats[best, :4]
        H, W = ratio.shape
        region = [round(x / W, 4), round(y / H, 4), round(w / W, 4), round(h / H, 4)]
    return {"score": score, "suspicious": score >= threshold, "region": region, "blocks": area}


def heatmap_png(img):
    ratio, block = noise_map(img)
    dev = np.clip(np.abs(np.log(np.maximum(ratio, 1e-3))) / 2.0, 0, 1)
    hm = cv2.applyColorMap((dev * 255).astype(np.uint8), cv2.COLORMAP_JET)
    hm = cv2.resize(hm, (img.width, img.height), interpolation=cv2.INTER_NEAREST)
    base = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    out = cv2.addWeighted(base, 0.55, hm, 0.45, 0)
    if out.shape[1] > 1100:
        out = cv2.resize(out, (1100, int(out.shape[0] * 1100 / out.shape[1])))
    ok, buf = cv2.imencode(".png", out)
    return buf.tobytes()


def ela_score(img, q=90):
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=q)
    re_img = Image.open(io.BytesIO(b.getvalue()))
    d = np.abs(np.array(img.convert("RGB"), dtype=np.float32) - np.array(re_img, dtype=np.float32)).mean(axis=2)
    h, w = (d.shape[0] // 16) * 16, (d.shape[1] // 16) * 16
    blocks = d[:h, :w].reshape(h // 16, 16, w // 16, 16).mean(axis=(1, 3))
    med = float(np.median(blocks)) or 1e-3
    return round(float(np.percentile(blocks, 99.5) / med), 3)


def copy_move(img, min_shift=40):
    """Self-matching ORB keypoints displaced by a consistent vector suggest a cloned region."""
    g = np.array(img.convert("L"))
    orb = cv2.ORB_create(3000)
    kp, des = orb.detectAndCompute(g, None)
    if des is None or len(kp) < 10:
        return {"pairs": 0, "suspicious": False}
    m = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(des, des, k=3)
    vecs = []
    for cand in m:
        for c in cand[1:]:
            if c.distance < 20:
                p, q = np.array(kp[c.queryIdx].pt), np.array(kp[c.trainIdx].pt)
                if np.linalg.norm(p - q) > min_shift:
                    v = q - p if (q - p)[0] >= 0 else p - q
                    vecs.append(tuple((v / 4).round()))
    if not vecs:
        return {"pairs": 0, "suspicious": False}
    vals, counts = np.unique(np.array(vecs), axis=0, return_counts=True)
    top = int(counts.max())
    return {"pairs": top, "suspicious": top >= 12}


def pdf_structure(data, meta):
    findings = []
    revs = data.count(b"%%EOF")
    if revs > 1:
        findings.append({"key": "incremental_revisions", "value": revs,
                         "reason": f"PDF has {revs} revisions (content added after the first save)"})
    c, m = meta.get("CreationDate", ""), meta.get("ModDate", "")
    cd, md = re.sub(r"\D", "", c)[:8], re.sub(r"\D", "", m)[:8]
    if cd and md and cd != md:
        findings.append({"key": "mod_vs_creation", "value": f"{cd} vs {md}",
                         "reason": "Modification date differs from creation date"})
    return findings


def dhash(img, size=8):
    g = np.array(img.convert("L").resize((size + 1, size), Image.LANCZOS), dtype=np.int16)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return "".join("1" if b else "0" for b in bits)


def hamming(a, b):
    return sum(x != y for x, y in zip(a, b))

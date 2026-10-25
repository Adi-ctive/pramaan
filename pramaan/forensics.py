"""Classical tamper indicators: noise-residual inconsistency, ELA, copy-move, PDF structure, perceptual hash.
Results are indicators that require verification, never proof."""
import io
import re

import numpy as np
from PIL import Image

VERSION = "1.1.0"
MAX_PIXELS = 6_000_000  # 600-dpi scans are downscaled first: the 3x3 median of a 35 MP page needs over 1 GB
MIN_DIFF = 2.0  # grey levels. Real scanners clip paper to white, so noise ratios over a near-zero median mean nothing


def _cap(img):
    n = img.width * img.height
    if n <= MAX_PIXELS:
        return img
    k = (MAX_PIXELS / n) ** 0.5
    return img.resize((int(img.width * k), int(img.height * k)))


def _gray(img):
    return np.array(img.convert("L"), dtype=np.float32)


def _median3(g):
    p = np.pad(g, 1, mode="edge")
    h, w = g.shape
    return np.median(np.stack([p[i:i + h, j:j + w] for i in range(3) for j in range(3)]), axis=0)


def label(mask):
    """4-connected components of a small boolean grid. Returns list of (area, x, y, w, h)."""
    seen = np.zeros_like(mask, dtype=bool)
    H, W = mask.shape
    out = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        stack, seen[y0, x0] = [(y0, x0)], True
        ys, xs = [], []
        while stack:
            y, x = stack.pop()
            ys.append(y)
            xs.append(x)
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        out.append((len(ys), min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1))
    return out


def noise_map(img, block=16):
    """Block std-dev of the high-pass residual, relative to the image median. Pasted clean patches stand out.
    Returns (ratio, block, std, med)."""
    g = _gray(_cap(img))
    res = g - _median3(g)
    h, w = (g.shape[0] // block) * block, (g.shape[1] // block) * block
    # measure noise on paper only: ink edges would hide a pasted patch that contains writing
    ink = g < 200
    near = np.zeros_like(ink)
    for dy in range(-2, 3):  # keep 2 px away from strokes: anti-aliased edges are not paper
        for dx in range(-2, 3):
            near |= np.roll(np.roll(ink, dy, 0), dx, 1)
    paper = (~near[:h, :w]).reshape(h // block, block, w // block, block)
    r = res[:h, :w].reshape(h // block, block, w // block, block)
    cnt = paper.sum(axis=(1, 3))
    mean = (r * paper).sum(axis=(1, 3)) / np.maximum(cnt, 1)
    var = ((r ** 2) * paper).sum(axis=(1, 3)) / np.maximum(cnt, 1) - mean ** 2
    std = np.sqrt(np.maximum(var, 0))
    ok = cnt >= block * block // 4
    med = float(np.median(std[ok])) if ok.any() else 1e-3
    ratio = np.where(ok, std / (med or 1e-3), 1.0)  # mostly-ink blocks are neutral
    return ratio, block, np.where(ok, std, med), med


def noise_check(img, threshold=0.65):
    ratio, block, std, med = noise_map(img)
    # a block is odd only if its noise differs from the page both in ratio and by a visible amount
    comps = label(((ratio < 0.35) | (ratio > 3.0)) & (np.abs(std - med) > MIN_DIFF))
    best = max(comps, default=None)
    area = best[0] if best else 0
    score = round(min(1.0, area / 12), 3)
    region = None
    if best:
        H, W = ratio.shape
        _, x, y, w, h = best
        region = [round(float(x) / W, 4), round(float(y) / H, 4), round(float(w) / W, 4), round(float(h) / H, 4)]
    return {"score": score, "suspicious": score >= threshold, "region": region, "blocks": int(area)}


def _jet(v):
    r = np.clip(1.5 - np.abs(4 * v - 3), 0, 1)
    g = np.clip(1.5 - np.abs(4 * v - 2), 0, 1)
    b = np.clip(1.5 - np.abs(4 * v - 1), 0, 1)
    return (np.stack([r, g, b], -1) * 255).astype(np.uint8)


def heatmap_png(img):
    ratio, block, _, _ = noise_map(img)
    dev = np.clip(np.abs(np.log(np.maximum(ratio, 1e-3))) / 2.0, 0, 1)
    hm = Image.fromarray(_jet(dev)).resize((img.width, img.height), Image.NEAREST)
    out = Image.blend(img.convert("RGB"), hm, 0.45)
    if out.width > 1100:
        out = out.resize((1100, int(out.height * 1100 / out.width)))
    b = io.BytesIO()
    out.save(b, "PNG")
    return b.getvalue()


def ela_score(img, q=90):
    img = _cap(img)
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=q)
    re_img = Image.open(io.BytesIO(b.getvalue()))
    d = np.abs(np.array(img.convert("RGB"), dtype=np.float32) - np.array(re_img, dtype=np.float32)).mean(axis=2)
    h, w = (d.shape[0] // 16) * 16, (d.shape[1] // 16) * 16
    blocks = d[:h, :w].reshape(h // 16, 16, w // 16, 16).mean(axis=(1, 3))
    med = float(np.median(blocks)) or 1e-3
    return round(float(np.percentile(blocks, 99.5) / med), 3)


def copy_move(img, block=16, step=2, min_shift=40, quant=6, min_pairs=500):
    """Overlapping-block matching: identical textured blocks repeated at one consistent offset suggest a cloned region."""
    g = _gray(_cap(img)).astype(np.float64)
    ii = np.pad(g, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    ii2 = np.pad(g * g, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    ys = np.arange(0, g.shape[0] - block, step)
    xs = np.arange(0, g.shape[1] - block, step)
    Y, X = np.meshgrid(ys, xs, indexing="ij")
    Y, X = Y.ravel(), X.ravel()

    def box(I, y, x, s):
        return I[y + s, x + s] - I[y, x + s] - I[y + s, x] + I[y, x]
    hb = block // 2
    q = np.stack([box(ii, Y + dy, X + dx, hb) for dy in (0, hb) for dx in (0, hb)], 1) / (hb * hb)
    var = box(ii2, Y, X, block) / block ** 2 - (box(ii, Y, X, block) / block ** 2) ** 2
    keep = var > 300
    if keep.sum() < 10:
        return {"pairs": 0, "suspicious": False}
    feat = np.round(q[keep] / quant)
    Yk, Xk = Y[keep], X[keep]
    order = np.lexsort(feat.T[::-1])
    f, Ys, Xs = feat[order], Yk[order], Xk[order]
    same = np.all(f[1:] == f[:-1], axis=1)
    dy, dx = (Ys[1:] - Ys[:-1])[same], (Xs[1:] - Xs[:-1])[same]
    far = np.hypot(dy, dx) > min_shift
    if not far.any():
        return {"pairs": 0, "suspicious": False}
    sgn = np.where(dy[far] < 0, -1, 1)
    vecs = np.stack([dy[far] * sgn, dx[far] * sgn], 1)
    _, counts = np.unique(vecs, axis=0, return_counts=True)
    top = int(counts.max())
    return {"pairs": top, "suspicious": top >= min_pairs}


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

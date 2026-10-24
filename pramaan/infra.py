"""Infrastructure evidence: EXIF location/time, object counting.
Object Detector: a vision model through Groq when GROQ_KEY is set, else a classical contour counter
(works on the schematic synthetic photos only; real photos route to manual review)."""
import base64
import io
import json
import math
import os
import re
from datetime import datetime

import httpx
import numpy as np


def exif(img):
    ex = img.getexif()
    out = {}
    dt = ex.get(306) or ex.get_ifd(0x8769).get(36867)
    if dt:
        try:
            out["taken_at"] = datetime.strptime(str(dt), "%Y:%m:%d %H:%M:%S").date().isoformat()
        except ValueError:
            pass
    gps = ex.get_ifd(0x8825)
    if gps and 2 in gps and 4 in gps:
        def deg(v):
            return float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
        lat, lon = deg(gps[2]), deg(gps[4])
        if gps.get(1) == "S":
            lat = -lat
        if gps.get(3) == "W":
            lon = -lon
        out["lat"], out["lon"] = round(lat, 6), round(lon, 6)
    return out


def km(a_lat, a_lon, b_lat, b_lon):
    r = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(h)), 2)


def classical_count(img):
    from .forensics import label
    small = img.convert("L").resize((img.width // 2, img.height // 2))
    g = np.array(small)
    area = g.shape[0] * g.shape[1]
    n = 0
    for a, x, y, w, h in label(g < 60):
        if 0.0008 * area < w * h < 0.03 * area and 1.1 < w / max(h, 1) < 2.2 and a > 0.8 * w * h:
            n += 1
    return n


def vlm_count(img, obj):
    key = os.environ.get("GROQ_KEY")
    if not key:
        return None
    b = io.BytesIO()
    img.convert("RGB").save(b, "JPEG", quality=85)
    url = "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
    body = {"model": os.environ.get("VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"), "temperature": 0,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": f'Count every {obj} visible in this photo. Reply only JSON: {{"count": <int>, "room_type": "<short label>"}}'},
                {"type": "image_url", "image_url": {"url": url}}]}]}
    try:
        r = httpx.post("https://api.groq.com/openai/v1/chat/completions", json=body,
                       headers={"Authorization": f"Bearer {key}"}, timeout=25)
        r.raise_for_status()
        txt = r.json()["choices"][0]["message"]["content"]
        j = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
        return {"count": int(j["count"]), "room_type": j.get("room_type"), "detector": "Object Detector (vision model)"}
    except Exception as e:
        return {"error": str(e)[:200]}


def count_objects(img, obj):
    v = vlm_count(img, obj)
    if v and "count" in v:
        return {**v, "conf": 0.8}
    n = classical_count(img)
    return {"count": n, "room_type": None, "conf": 0.6, "detector": "Classical counter (LITE, synthetic-grade)",
            "note": (v or {}).get("error")}

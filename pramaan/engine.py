"""Deterministic validation pipeline (02_ARCHITECTURE.md §5). Every finding becomes a Flag (§9) with evidence;
severity comes only from the rule pack. A crashing check yields a CHECK_ERROR flag, never a failed report."""
import json
import os
import re
import time
from datetime import date, timedelta

import httpx
from bson import Binary
from rapidfuzz import fuzz

from . import extract, forensics, infra, providers, rulepack, verify
from .audit import record as audit
from .db import get_db, new_id, now
from .security import hmac_sign

MODE = providers.MODE
VIDEO = (".mp4", ".mov")
ADVISORY = "Preliminary indicator; requires official verification."


# ---------- storage helpers
def put_blob(data, kind="bin"):
    bid = new_id("BLB")
    get_db().blobs.insert_one({"_id": bid, "kind": kind, "data": Binary(data)})
    return bid


def get_blob(bid):
    b = get_db().blobs.find_one({"_id": bid})
    return bytes(b["data"]) if b else None


def active_pack(key):
    p = get_db().rule_packs.find_one({"key": key, "status": "ACTIVE"})
    pack, errs = rulepack.parse(p["yaml"])
    return pack, p["version"]


# ---------- per-document processing (stages B1-B12)
def process_doc(doc, pack, app):
    data = get_blob(doc["blob_id"])
    th = pack.get("thresholds", {})
    res = {"stages": [], "pages": [], "fields": {}, "images": [], "flags_raw": []}

    def stage(name, fn):
        t = time.perf_counter()
        try:
            out = fn()
            res["stages"].append({"stage": name, "ms": round((time.perf_counter() - t) * 1000), "status": "ok"})
            return out
        except Exception as e:
            res["stages"].append({"stage": name, "ms": round((time.perf_counter() - t) * 1000), "status": "error", "error": str(e)[:200]})
            res["flags_raw"].append({"code": "CHECK_ERROR", "category": "EXTRACTION", "title": f"Check '{name}' failed",
                                     "reason": f"{type(e).__name__}: {str(e)[:150]}. Routed to manual review.", "evidence": []})
            return None

    is_pdf = doc["filename"].lower().endswith(".pdf")
    if doc["filename"].lower().endswith(VIDEO):
        res.update(type=doc["slot"], type_conf=0, scanned=False, media="video")
        frames = stage("video_frames", lambda: extract.video_frames(data)) if doc["slot"] == "INFRA_PHOTOS" else None
        if not frames:
            return res
        res["frames"] = len(frames)
        spec = (pack.get("infrastructure", {}).get("facilities", {}) or {}).get((doc.get("facility") or "").rsplit("_", 1)[0])
        for k, im in enumerate(frames):
            res["pages"].append(put_blob(extract.to_png(im), "jpeg"))
            entry = {"hash": forensics.dhash(im), "frame": k}
            if spec:
                entry["count"] = stage("object_count", lambda: providers.detector.count(im, spec["count_object"]))
            res["images"].append(entry)
        return res
    if is_pdf:
        pdf = stage("render", lambda: extract.open_pdf(data))
        if pdf is None:
            return res
        texts = stage("read_text", lambda: extract.pdf_text(pdf)) or []
        full = "\n".join(texts)
        res["text_chars"] = len(full.strip())
        for i in range(len(pdf)):
            res["pages"].append(put_blob(extract.to_png(extract.render_page(pdf, i)), "jpeg"))
        scanned = res["text_chars"] < th.get("min_text_chars", 40)
        res["scanned"] = scanned
        if not scanned:
            t, conf = stage("classify", lambda: extract.classify(full, pack["taxonomy"])) or (None, 0)
            res["type"], res["type_conf"] = t, conf
            spec = pack["taxonomy"].get(doc["slot"]) or {}
            res["fields"] = stage("extract", lambda: extract.extract_fields(pdf, texts, spec)) or {}
            hits = extract.injection_hits(full)
            if hits:
                res["injection"] = hits
        else:
            res["type"], res["type_conf"] = None, 0
            img0 = (extract.page_images(pdf, 0) or [extract.render_page(pdf, 0, 2)])[0]
            o = stage("ocr_htr", lambda: read_scanned(img0, pack, doc["slot"], th))
            if o:
                res.update(o)
                hits = extract.injection_hits(o.get("text", ""))
                if hits:
                    res["injection"] = hits
        if not scanned:
            res["regions"] = stage("regions", lambda: detect_regions(pdf, res.get("qr")))
            if (pack["taxonomy"].get(doc["slot"]) or {}).get("tables"):
                res["tables"] = stage("tables", lambda: extract.extract_tables(data)) or []
            if (pack["taxonomy"].get(doc["slot"]) or {}).get("kind") == "floor_plan":
                res["floor_plan"] = stage("floor_plan", lambda: extract.floor_plan(data))
        if b"/ByteRange" in data or "pdf_sig" in (pack["taxonomy"].get(doc["slot"]) or {}).get("verification", []):
            res["pdf_sig"] = stage("pdf_signature", lambda: verify.check_pdf_sig(data))
        if "qr" in (pack["taxonomy"].get(doc["slot"]) or {}).get("verification", []):
            res["qr"] = stage("qr", lambda: extract.read_qr(pdf))
        meta = pdf.get_metadata_dict()
        res["pdf_findings"] = stage("pdf_forensics", lambda: forensics.pdf_structure(data, meta)) or []
        if (res.get("pdf_sig") or {}).get("status") in ("VERIFIED", "MODIFIED_AFTER_SIGNING"):
            res["pdf_findings"] = []  # revisions are explained by the signature check itself
        imgs = [extract.render_page(pdf, i, 2) for i in range(len(pdf))] if scanned else []
        if scanned:
            emb = extract.page_images(pdf, 0)
            if emb:
                imgs = emb
    else:
        img = extract.load_image(data)
        img.load()
        res["pages"].append(put_blob(extract.to_png(img.convert("RGB")), "jpeg"))
        res["exif"] = stage("exif", lambda: infra.exif(img))
        res["type"], res["type_conf"], res["scanned"] = ("INFRA_PHOTOS" if doc["slot"] == "INFRA_PHOTOS" else None), 1.0, doc["slot"] != "INFRA_PHOTOS"
        imgs = [img.convert("RGB")]

    for k, im in enumerate(imgs[:2]):
        entry = {"hash": forensics.dhash(im)}
        if doc["slot"] != "INFRA_PHOTOS":
            nc = stage("noise_residual", lambda: forensics.noise_check(im, th.get("noise_suspicion", 0.65)))
            entry["noise"] = nc
            # escalation: deeper checks only when the cheap one is borderline or worse
            if nc and nc["score"] >= th.get("noise_suspicion", 0.65) / 2:
                entry["ela"] = stage("ela", lambda: forensics.ela_score(im))
                entry["copy_move"] = stage("copy_move", lambda: forensics.copy_move(im))
                res["stages"].append({"stage": "escalate", "ms": 0, "status": "ok",
                                      "note": f"noise score {nc['score']} >= {th.get('noise_suspicion', 0.65) / 2} -> ran ELA and copy-move"})
            if nc and nc["suspicious"]:
                entry["heatmap"] = put_blob(forensics.heatmap_png(im), "png")
        else:
            fac = doc.get("facility")
            spec = (pack.get("infrastructure", {}).get("facilities", {}) or {}).get((fac or "").rsplit("_", 1)[0])
            if spec:
                entry["count"] = stage("object_count", lambda: providers.detector.count(im, spec["count_object"]))
                labels = spec.get("room_labels", []) + ["classroom", "library", "office", "corridor", "washroom"]
                entry["room"] = stage("room_type", lambda: providers.scene.classify(im, labels))
            entry["emb"] = providers.scene.embed(im) if providers.MODE == "FULL" else None
        res["images"].append(entry)
    if doc["slot"] != "INFRA_PHOTOS":
        res["htr_needed"] = bool(res.get("scanned"))
    return res


def _deskew(img):
    """Projection-profile deskew in +-3 degrees (scan pre-processing)."""
    import numpy as np
    g = img.convert("L").resize((img.width // 4, img.height // 4))
    best, ang = -1, 0
    for a in [x / 2 for x in range(-6, 7)]:
        prof = (np.array(g.rotate(a, fillcolor=255)) < 128).sum(1).astype(float)
        sc = float(np.var(prof))
        if sc > best:
            best, ang = sc, a
    return img.rotate(ang, fillcolor="white", expand=False) if ang else img, ang


def read_scanned(img, pack, slot, th):
    """OCR Model on the page, Handwriting Model on field values the OCR Model reads poorly. None in LITE."""
    img, angle = _deskew(img.convert("RGB"))
    lines = providers.ocr.read(img)
    if lines is None:
        return None
    spec0 = pack["taxonomy"].get(slot) or {}
    hindi_labels = [a for f in (spec0.get("fields") or {}).values() for a in f.get("alt_anchors") or [] if re.search(r"[ऀ-ॿ]", a)]
    english_found = any(f["anchor"].lower() in " ".join(l["text"].lower() for l in lines) for f in (spec0.get("fields") or {}).values())
    if hindi_labels and not english_found:
        hl = providers.ocr.read_hindi(img)
        if hl:
            lines = hl
    text = "\n".join(l["text"] for l in lines)
    t, conf = extract.classify(text, pack["taxonomy"])
    spec = pack["taxonomy"].get(slot) or {}
    fields, htr = {}, []
    W, H = img.size
    for fname, fs in (spec.get("fields") or {}).items():
        ln = None
        for anc in [fs["anchor"].lower()] + [x.lower() for x in fs.get("alt_anchors") or []]:
            ln = next((l for l in lines if l["text"].lower().startswith(anc) or anc + ":" in l["text"].lower()), None) or                 next((l for l in lines if anc in l["text"].lower()), None)
            if ln:
                break
        if not ln:
            continue
        hit = next(a for a in [fs["anchor"]] + list(fs.get("alt_anchors") or []) if a.lower() in ln["text"].lower())
        raw = re.split(re.escape(hit) + r"\s*[:ः]?", ln["text"], flags=re.I)[-1].strip().lstrip(":ः ").strip()
        c, band = ln["conf"], ln["bbox"]
        if not raw:
            # value written beside the label: nearest OCR line to the right that overlaps vertically
            y0, y1 = ln["bbox"][1] - ln["bbox"][3], ln["bbox"][1] + 2 * ln["bbox"][3]
            cands = [l for l in lines if l is not ln and l["bbox"][0] > ln["bbox"][0] + ln["bbox"][2] - 0.01 and y0 <= l["bbox"][1] <= y1]
            nb = min(cands, key=lambda l: abs(l["bbox"][1] - ln["bbox"][1]) + l["bbox"][0], default=None)
            if nb:
                raw, c, band = nb["text"], nb["conf"], nb["bbox"]
        if band is not ln["bbox"] and c < th.get("ocr_min_conf", 0.8):
            pad = 0.004
            crop = img.crop((int(max(0, band[0] - pad) * W), int(max(0, band[1] - pad) * H), int(min(1, band[0] + band[2] + pad) * W),
                             int(min(1, band[1] + band[3] + pad) * H)))
            h = providers.htr.read(crop)

            def parses(t):
                return fs.get("type") not in ("date", "number") or (extract.norm_date(t) if fs["type"] == "date" else extract.norm_number(t)) is not None
            if h and (parses(h["text"]), h["conf"]) > (parses(raw), c):
                raw, c = h["text"], h["conf"]
            htr.append({"field": fname, "text": raw, "conf": c, "bbox": band})
        val = extract.norm_date(raw) if fs.get("type") == "date" else extract.norm_number(raw) if fs.get("type") == "number" else raw
        fields[fname] = {"value": val, "raw": raw, "page": 0, "bbox": [round(float(v), 4) for v in band], "conf": round(c if val is not None else min(c, 0.4), 3)}
    return {"fields": fields, "htr": htr, "ocr_lines": len(lines), "text": text, "type": t, "type_conf": conf,
            "deskew_deg": angle, "ocr_used": True}


def detect_regions(pdf, qr=None):
    """Stamp/seal (coloured ink) and signature (ink strokes outside the text layer) presence with boxes."""
    import numpy as np
    page = pdf[0]
    img = extract.render_page(pdf, 0, 2)
    a = np.asarray(img, dtype=np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    W, H = img.size
    out = {}
    ink = ((b - r > 50) & (b > 100)) | ((r - b > 60) & (r > 120) & (g < 120))
    ink[: int(H * 0.12)] = False  # letterhead band is printed colour, not a stamp

    def box(ys, xs):
        return [round(float(xs.min()) / W, 4), round(float(ys.min()) / H, 4), round(float(xs.max() - xs.min()) / W, 4), round(float(ys.max() - ys.min()) / H, 4)]
    if ink.sum() > 0.0008 * W * H:
        out["stamp"] = box(*np.nonzero(ink))
    dark = (a.max(axis=2) < 150)
    dark[: int(H * 0.12)] = False  # header band
    tp = page.get_textpage()
    pw, ph = page.get_size()
    for i in range(tp.count_chars()):
        l, bb, rr, t = tp.get_charbox(i)
        dark[max(0, int((ph - t) * H / ph) - 2): int((ph - bb) * H / ph) + 2, max(0, int(l * W / pw) - 2): int(rr * W / pw) + 2] = False
    if qr:
        x, y, w, h = qr["bbox"]
        dark[int(y * H) - 4: int((y + h) * H) + 4, int(x * W) - 4: int((x + w) * W) + 4] = False
    if "stamp" in out:
        x, y, w, h = out["stamp"]
        dark[int(y * H): int((y + h) * H), int(x * W): int((x + w) * W)] = False
    if dark.sum() > 0.00015 * W * H:
        out["signature"] = box(*np.nonzero(dark))
    return out


def doc_stage(d, pack, app, ref, route=None, trace=None):
    """Per-document tools in order: process, then verification routes. `route` lets the Verification Agent pick methods."""
    db = get_db()
    app_id = app["id"]
    r = process_doc(d, pack, app)
    tax = pack["taxonomy"].get(d["slot"], {})
    methods = route(r) if callable(route) else route if route is not None else tax.get("verification", [])
    vids = []
    cf = None if r.get("scanned") and not r.get("ocr_used") else verify.carry_forward(d, app)
    if cf:
        vids.append(cf["id"])
    else:
        if "pdf_sig" in methods and r.get("pdf_sig"):
            vids.append(verify.record_pdf_sig(d["id"], app_id, r["pdf_sig"])["id"])
        if "qr" in methods:
            if r.get("qr"):
                vids.append(verify.verify_qr(d["id"], app_id, r["qr"], r["fields"])["id"])
            elif not r.get("scanned"):
                vids.append(verify._record(d["id"], app_id, "qr", None, "MANUAL_REVIEW", {"reason": "No QR code found on the document"})["id"])
        if "ref_lookup" in methods and (not r.get("scanned") or r.get("ocr_used")):
            v = verify.verify_ref(d["id"], app_id, d["slot"], r["fields"], retries=1 if route is not None else 0)
            vids.append(v["id"])
            if trace and v["status"] == "SOURCE_UNAVAILABLE":
                trace("Verification Agent", "issuer_lookup", {"doc": d["id"]}, "source unavailable after retry; routed to manual confirmation")
    r["verification_ids"] = vids
    db.documents.update_one({"id": d["id"]}, {"$set": {"result": r, "pack_ref": ref}})
    d["result"] = r
    return r


# ---------- flag factory
class Flags:
    def __init__(self, pack, pack_ref, app_id):
        self.pack, self.ref, self.app_id, self.items = pack, pack_ref, app_id, []
        self.src = {r["id"]: r.get("source_ref") for r in pack["rules"] + pack.get("plausibility", [])}

    def add(self, code, category, title, reason, evidence, rule_id=None, doc_id=None, key=None, expected=None,
            observed=None, action=None, conf=0.95, detector="rules-engine"):
        sev = self.pack["severity"].get(code, "MEDIUM")
        ev = list(evidence)
        if rule_id:
            ev.append({"type": "rule", "rule_id": rule_id, "pack": self.ref, "source_ref": self.src.get(rule_id, self.pack.get("default_source_ref"))})
        self.items.append({
            "code": code, "category": category, "severity": sev, "title": title, "reason": reason, "evidence": ev,
            "expected": expected, "observed": observed, "detector": detector, "detector_version": forensics.VERSION,
            "confidence": conf, "recommended_action": action, "doc_id": doc_id, "rule_id": rule_id,
            "institution_visible": code in self.pack.get("institution_visible", []),
            "advisory_note": ADVISORY, "fingerprint": f"{code}|{rule_id}|{doc_id}|{key}"})


def _translit(s):
    if re.search(r"[\u0900-\u097F]", s):
        from indic_transliteration import sanscript
        s = sanscript.transliterate(s, sanscript.DEVANAGARI, sanscript.ITRANS)
    return s


def _skeleton(s):
    """Consonant skeleton, so 'narmadA vidyA TrasTa' and 'Narmada Vidya Trust' compare equal."""
    return " ".join(re.sub(r"[aeiou]", "", w) or w for w in _norm_name(s).split())


def _norm_name(s):
    s = _translit(s).lower().replace("&", " and ")
    s = re.sub(r"\b(the|of)\b", " ", s)
    return re.sub(r"[^a-z0-9 ]", " ", s)


def _fe(doc, fname, f):
    return {"type": "field", "document_id": doc["id"], "slot": doc["slot"], "page": f.get("page", 0),
            "bbox": f.get("bbox"), "key": fname, "value": f.get("value"), "conf": f.get("conf")}


# ---------- application-level validation
def use_agents():
    return os.environ.get("AGENTS", "auto") == "on" or (os.environ.get("AGENTS", "auto") == "auto" and MODE == "FULL")


def run(app_id, changed=None, actor="system", pack_override=None, dry=False, agents_on=None):
    db = get_db()
    t0 = time.perf_counter()
    app = db.applications.find_one({"id": app_id})
    pack, ver = pack_override or active_pack(app["pack_key"])
    ref = f"{pack['key']}@{ver}"
    timeline = []
    docs = list(db.documents.find({"app_id": app_id, "superseded": {"$ne": True}}))
    rec = db.records.find_one({"aicte_id": app["institution_id"]}) or {}
    rec = {k: v for k, v in rec.items() if k != "_id"}
    timeline.append({"stage": "records_fetch", "status": "ok" if rec else "missing", "ms": 0})

    # B: per-document stages, reusing cached results for unchanged documents
    agent = None
    if not dry and (use_agents() if agents_on is None else agents_on):
        from . import agents
        agent = agents.Run(app, pack, ref, timeline)
    for d in docs:
        if d.get("result") and (dry or ((changed is None or d["id"] not in changed) and d.get("pack_ref") == ref)):
            timeline.append({"stage": f"doc:{d['slot']}", "status": "reused", "doc_id": d["id"], "ms": 0})
            continue
        t = time.perf_counter()
        try:
            r = agent.process(d) if agent else doc_stage(d, pack, app, ref)
        except Exception as e:  # any agent failure: deterministic pipeline completes the stage
            timeline.append({"stage": "agent_fallback", "status": "error", "note": f"{type(e).__name__}: {str(e)[:120]} -> DAG"})
            agent = None
            r = doc_stage(d, pack, app, ref)
        timeline.append({"stage": f"doc:{d['slot']}", "status": "ran", "doc_id": d["id"],
                         "ms": round((time.perf_counter() - t) * 1000), "substages": r["stages"]})

    F = Flags(pack, ref, app_id)
    by_slot = {}
    for d in docs:
        by_slot.setdefault(d["slot"], []).append(d)
    a = dict(app["form"])
    a["submitted_on"] = app.get("submitted_on") or date.today().isoformat()
    ctx = {"app": a, "records": rec}
    for s, ds in by_slot.items():
        if s != "INFRA_PHOTOS":
            ctx[s] = {k: v["value"] for k, v in ds[0]["result"].get("fields", {}).items()}

    def check(name, fn):
        t = time.perf_counter()
        try:
            fn()
            timeline.append({"stage": name, "status": "ok", "ms": round((time.perf_counter() - t) * 1000)})
        except Exception as e:
            timeline.append({"stage": name, "status": "error", "error": str(e)[:200]})
            F.add("CHECK_ERROR", "VALIDITY", f"Check '{name}' failed", f"{type(e).__name__}: {str(e)[:150]}. Manual review.", [])

    # C2 completeness + document type + required fields
    def c_complete():
        cat = pack["categories"][app["category"]]
        req = list(cat["required_slots"])
        for cond in cat.get("conditional_slots", []):
            try:
                if not rulepack.evaluate(cond["when"], ctx) and cond["slot"] in req:
                    req.remove(cond["slot"])
            except rulepack.Missing:
                pass
        for s in req:
            if s not in by_slot:
                lbl = pack["taxonomy"][s]["label"]
                F.add("DOC_MISSING", "COMPLETENESS", f"{lbl} not uploaded", f"Category {app['category']} requires slot {s}.",
                      [], rule_id=f"{app['category']}.required_slots", key=s, expected="document present", observed="missing",
                      action=f"Upload the {lbl}")
        for v in docs:
            if v["result"].get("media") == "video" and not v["result"].get("frames"):
                F.add("MEDIA_NOT_ANALYSED", "EXTRACTION", f"{v['filename']}: video not analysed automatically",
                      "Video frame sampling needs ffmpeg, which this deployment does not include (local builds analyse videos). An officer should view the video.",
                      [{"type": "metadata", "document_id": v["id"], "key": "file", "value": v["filename"]}], doc_id=v["id"], conf=0.0)
        for s, ds in by_slot.items():
            d = ds[0]
            r = d["result"]
            spec = pack["taxonomy"].get(s, {})
            if r.get("media") == "video":
                continue
            if r.get("ocr_used"):
                for fname, f in r.get("fields", {}).items():
                    if f.get("conf", 1) < pack["thresholds"].get("htr_min_conf", 0.7):
                        F.add("HTR_LOW_CONFIDENCE", "EXTRACTION", f"{spec.get('label', s)}: '{fname.replace('_', ' ')}' read with low confidence",
                              f"Read as '{f.get('raw')}' with confidence {f.get('conf')} (threshold {pack['thresholds'].get('htr_min_conf')}). Routed to manual review.",
                              [_fe(d, fname, f)], doc_id=d["id"], key=fname, expected=f">= {pack['thresholds'].get('htr_min_conf')}",
                              observed=f.get("conf"), conf=f.get("conf"), action="Officer to read this field", detector="Handwriting Model")
            elif r.get("scanned"):
                F.add("HTR_LOW_CONFIDENCE", "EXTRACTION", f"{spec.get('label', s)}: scanned or handwritten, not machine-readable",
                      "No text layer. Handwriting Model is not available in LITE mode, so fields could not be read with confidence. Routed to manual review.",
                      [{"type": "region", "document_id": d["id"], "page": 0, "bbox": [0, 0, 1, 1]}], doc_id=d["id"],
                      expected=f"confidence >= {pack['thresholds'].get('htr_min_conf')}", observed="0.0", conf=0.0,
                      action="Officer to read the document", detector="Handwriting Model")
                continue
            if spec.get("kind") == "floor_plan" and not r.get("floor_plan"):
                F.add("FLOOR_PLAN_NOT_MEASURED", "INFRASTRUCTURE", "Floor plan could not be measured",
                      "Areas are measured from vector floor plans with a printed scale. This one is an image or has no scale. Officer to review.",
                      [{"type": "region", "document_id": d["id"], "page": 0, "bbox": [0, 0, 1, 1]}], doc_id=d["id"], conf=0.0, detector="Floor-plan reader")
            for reg in (spec.get("requires_regions") or []) if "regions" in r else []:
                if reg not in (r.get("regions") or {}):
                    F.add("REQUIRED_REGION_MISSING", "COMPLETENESS", f"{spec.get('label', s)}: no {reg} found",
                          f"The rule pack requires a {reg} on this document type and none was detected.",
                          [{"type": "region", "document_id": d["id"], "page": 0, "bbox": [0, 0, 1, 1]}], doc_id=d["id"], key=reg,
                          expected=f"{reg} present", observed="not detected", action=f"Upload a copy that shows the issuer's {reg}",
                          conf=0.7, detector="Region detector")
            if s != "INFRA_PHOTOS" and r.get("type") and r["type"] != s:
                F.add("WRONG_DOC_TYPE", "COMPLETENESS", f"Wrong document in slot {spec.get('label', s)}",
                      f"Document looks like {pack['taxonomy'][r['type']]['label']} (score {r['type_conf']}).",
                      [{"type": "metadata", "document_id": d["id"], "key": "classified_as", "value": r["type"]}],
                      doc_id=d["id"], expected=s, observed=r["type"], action=f"Upload the {spec.get('label', s)} in this slot",
                      conf=r["type_conf"], detector="Document Classifier")
                continue
            for fname, fs in (spec.get("fields") or {}).items():
                f = r["fields"].get(fname)
                low = f and f.get("conf", 1) < pack["thresholds"].get("htr_min_conf", 0.7)
                if fs.get("required") and (not f or (f.get("value") is None and not low)):
                    F.add("FIELD_MISSING", "COMPLETENESS", f"{spec['label']}: '{fs['anchor']}' not found",
                          "Required field is missing or unreadable.", [], doc_id=d["id"], key=fname,
                          action=f"Upload a copy that shows '{fs['anchor']}'")
                elif f and fs.get("pattern") and not re.match(fs["pattern"], str(f["value"])):
                    F.add("FORMAT_INVALID", "VALIDITY", f"{spec['label']}: '{fs['anchor']}' has an unexpected format",
                          f"Value does not match the issuer's reference format.", [_fe(d, fname, f)], doc_id=d["id"], key=fname,
                          expected=fs["pattern"], observed=f["value"], action="Check the reference number")
            if r.get("injection"):
                F.add("INJECTION_INDICATOR", "ANOMALY", f"{spec.get('label', s)} contains instruction-like text",
                      "Text addressed to an automated system was found. It was treated as data and never executed.",
                      [{"type": "metadata", "document_id": d["id"], "key": "patterns", "value": r["injection"]}], doc_id=d["id"],
                      detector="Injection screen")
    check("completeness", c_complete)

    # C2/C3/C4 rule pack rules
    def c_rules():
        for rule in pack["rules"]:
            k = rule["kind"]
            if k == "expiry":
                d = (by_slot.get(rule["applies_to"]) or [None])[0]
                f = d and d["result"].get("fields", {}).get(rule["field"])
                if f and f.get("value") and f["value"] < a["submitted_on"]:
                    lbl = pack["taxonomy"][rule["applies_to"]]["label"]
                    F.add(rule["code"], "VALIDITY", f"{lbl} has expired",
                          f"Valid-to date {f['value']} is before the submission date {a['submitted_on']} (rule {rule['id']}).",
                          [_fe(d, rule["field"], f)], rule_id=rule["id"], doc_id=d["id"], expected="valid_to >= submission date",
                          observed=f["value"], action=rule.get("action"), conf=f.get("conf", 0.9))
            elif k == "table_sum":
                d = (by_slot.get(rule["applies_to"]) or [None])[0]
                if not d or not d["result"].get("tables"):
                    continue
                rows = d["result"]["tables"][0]["rows"]
                nums = [(r_[0], extract.norm_number(r_[-1])) for r_ in rows[1:] if extract.norm_number(r_[-1] or "") is not None]
                items = [v for lbl, v in nums if "total" not in lbl.lower()]
                total = next((v for lbl, v in nums if "total" in lbl.lower()), None)
                stated = (d["result"]["fields"].get(rule["field"]) or {}).get("value")
                s_items = round(sum(items), 2)
                if items and ((total is not None and abs(s_items - total) > 0.5) or (stated is not None and abs(s_items - stated) > 0.5)):
                    F.add(rule["code"], "CONSISTENCY", f"{pack['taxonomy'][rule['applies_to']]['label']}: line items do not add up",
                          f"Items sum to {s_items:,.0f}; table total {total if total is None else f'{total:,.0f}'}; stated amount {stated if stated is None else f'{stated:,.0f}'}.",
                          [{"type": "table", "document_id": d["id"], "rows": rows}], rule_id=rule["id"], doc_id=d["id"],
                          expected=f"sum of items = {stated}", observed=s_items, action=rule.get("action"), detector="Table reader")
            elif k == "table_count":
                d = (by_slot.get(rule["applies_to"]) or [None])[0]
                want = rec.get(rule["record_field"])
                if not d or not d["result"].get("tables") or want is None:
                    continue
                n = sum(len(t["rows"]) - 1 for t in d["result"]["tables"])
                if abs(n - want) > want * rule.get("tolerance_pct", 0) / 100:
                    F.add(rule["code"], "CONSISTENCY", f"{pack['taxonomy'][rule['applies_to']]['label']}: {n} listed, AICTE records show {want}",
                          f"Rows in the faculty table ({n}) do not match the faculty count in records ({want}).",
                          [{"type": "table", "document_id": d["id"], "rows": d["result"]["tables"][0]["rows"][:4]},
                           {"type": "record", "adapter": "records", "key": rule["record_field"], "value": want}],
                          rule_id=rule["id"], doc_id=d["id"], expected=want, observed=n, action=rule.get("action"), detector="Table reader")
            elif k == "area_vs_claim":
                d = (by_slot.get(rule["applies_to"]) or [None])[0]
                plan = d and d["result"].get("floor_plan")
                if not plan:
                    continue
                rooms = {x["label"]: x for x in plan["rooms"]}
                for fac in a.get("facilities", []):
                    claimed, room = fac.get(rule["claim_field"]), rooms.get(fac["id"])
                    if claimed and room and room["area_sqm"] < claimed * (1 - rule.get("tolerance_pct", 10) / 100):
                        F.add(rule["code"], "INFRASTRUCTURE", f"{fac['id']}: {room['area_sqm']} sq m on the floor plan, {claimed} claimed",
                              f"Measured from the floor plan at scale {plan['scale']}. Advisory only.",
                              [{"type": "region", "document_id": d["id"], "page": 0, "bbox": room["bbox"]}], rule_id=rule["id"], doc_id=d["id"],
                              key=fac["id"], expected=claimed, observed=room["area_sqm"], action=rule.get("action"), detector="Floor-plan reader")
            elif k == "entity_match":
                lv = rulepack.lookup(ctx, rule["left"])
                if not lv:
                    continue
                for rpath in rule["right"]:
                    rv = rulepack.lookup(ctx, rpath)
                    if not rv:
                        continue
                    score = fuzz.token_set_ratio(_norm_name(lv), _norm_name(rv)) / 100
                    if re.search(r"[\u0900-\u097F]", lv + rv):  # one side in Devanagari: also compare consonant skeletons
                        score = max(score, fuzz.token_set_ratio(_skeleton(lv), _skeleton(rv)) / 100)
                    if score < rule.get("threshold", 0.88):
                        ev = []
                        for path, val in ((rule["left"], lv), (rpath, rv)):
                            slot, fld = path.split(".", 1)
                            if slot in by_slot:
                                ev.append(_fe(by_slot[slot][0], fld, by_slot[slot][0]["result"]["fields"].get(fld, {})))
                            else:
                                ev.append({"type": "record" if slot == "records" else "field", "key": path, "value": val})
                        F.add(rule["code"], "CONSISTENCY", f"Name mismatch: {rule['left']} vs {rpath}",
                              f"'{lv}' vs '{rv}' similarity {score:.2f} below {rule.get('threshold')}.", ev,
                              rule_id=rule["id"], key=rpath, expected=lv, observed=rv, action=rule.get("action"), conf=round(1 - score, 2))
            elif k == "expr":
                try:
                    ok = rulepack.evaluate(rule["expr"], ctx)
                except rulepack.Missing as m:
                    timeline.append({"stage": f"rule:{rule['id']}", "status": "skipped", "note": f"missing {m}"})
                    continue
                if not ok:
                    obs = rulepack.lookup(ctx, rule.get("observed_var", ""))
                    ev = [{"type": "record", "adapter": "records", "key": "approved_intake", "value": rec.get("approved_intake")}] if "records" in json.dumps(rule["expr"]) else []
                    F.add(rule["code"], "CONSISTENCY", rule.get("expected", rule["id"]) + " - not met",
                          f"Rule {rule['id']} failed.", ev, rule_id=rule["id"], expected=rule.get("expected"),
                          observed=obs, action=rule.get("action"))
    check("rules", c_rules)

    def c_plaus():
        for rule in pack.get("plausibility", []):
            for s, ds in by_slot.items():
                d = ds[0]
                flds = d["result"].get("fields", {})
                if rule["kind"] == "max_validity":
                    mx = pack["taxonomy"].get(s, {}).get("issuer_max_validity_days")
                    i, v = flds.get("issued_on", {}).get("value"), flds.get("valid_to", {}).get("value")
                    if mx and i and v and (date.fromisoformat(v) - date.fromisoformat(i)).days > mx:
                        F.add(rule["code"], "VALIDITY", f"{pack['taxonomy'][s]['label']}: validity longer than issuer maximum",
                              f"{i} to {v} exceeds {mx} days.", [_fe(d, "valid_to", flds["valid_to"])], rule_id=rule["id"],
                              doc_id=d["id"], expected=f"<= {mx} days", observed=v)
                    continue
                c2 = dict(ctx, doc={k: v["value"] for k, v in flds.items()})
                try:
                    if not rulepack.evaluate(rule["expr"], c2):
                        F.add(rule["code"], "VALIDITY", f"{pack['taxonomy'][s]['label']}: implausible date",
                              f"{rule.get('expected')} (rule {rule['id']}).", [_fe(d, "issued_on", flds["issued_on"])],
                              rule_id=rule["id"], doc_id=d["id"], key=rule["id"], expected=rule.get("expected"),
                              observed=flds["issued_on"]["value"], action="Check the issue date on the document")
                except rulepack.Missing:
                    pass
    check("plausibility", c_plaus)

    # B11 forensics flags
    def c_forensics():
        for d in docs:
            r = d["result"]
            lbl = pack["taxonomy"].get(d["slot"], {}).get("label", d["slot"])
            for im in r.get("images", []):
                nc = im.get("noise")
                if nc and nc["suspicious"]:
                    F.add("TAMPER_INDICATOR", "ANOMALY", f"{lbl}: possible local alteration - indicator, requires verification",
                          f"Noise pattern in one region is inconsistent with the rest of the page (score {nc['score']}).",
                          [{"type": "heatmap", "document_id": d["id"], "image_key": im.get("heatmap"), "regions": [nc["region"]]},
                           {"type": "region", "document_id": d["id"], "page": 0, "bbox": nc["region"]}],
                          doc_id=d["id"], key="noise", conf=nc["score"], detector="Tamper Localiser (noise residual)",
                          expected="uniform noise", observed=f"score {nc['score']}")
                cm = im.get("copy_move")
                if cm and cm.get("suspicious"):
                    F.add("TAMPER_INDICATOR", "ANOMALY", f"{lbl}: repeated region - indicator, requires verification",
                          f"{cm['pairs']} keypoint pairs share one displacement (possible copy-move).",
                          [{"type": "metadata", "document_id": d["id"], "key": "copy_move_pairs", "value": cm["pairs"]}],
                          doc_id=d["id"], key="copymove", detector="Tamper Localiser (copy-move)")
            for pf in r.get("pdf_findings", []):
                F.add("PDF_EDIT_INDICATOR", "ANOMALY", f"{lbl}: PDF changed after creation - indicator, requires verification",
                      pf["reason"], [{"type": "metadata", "document_id": d["id"], "key": pf["key"], "value": pf["value"]}],
                      doc_id=d["id"], key=pf["key"], detector="PDF forensics")
    check("forensics", c_forensics)

    # C5 duplicates across applications
    def c_dupes():
        thr = pack["thresholds"].get("duplicate_hash_hamming", 6)
        others = list(db.documents.find({"app_id": {"$ne": app_id}, "superseded": {"$ne": True}, "result.images": {"$exists": True}},
                                        {"id": 1, "app_id": 1, "result.images.hash": 1, "slot": 1}))
        app_inst = {x["id"]: x["institution_id"] for x in db.applications.find({}, {"id": 1, "institution_id": 1})}
        seen = {}
        for d in docs:
            for im in d["result"].get("images", []):
                h = im["hash"]
                for o in others:
                    for oi in o.get("result", {}).get("images", []):
                        dist = forensics.hamming(h, oi["hash"])
                        if dist <= thr and app_inst.get(o["app_id"]) != app["institution_id"]:
                            F.add("DUPLICATE_ACROSS_INSTITUTIONS", "ANOMALY", "Image matches a document from another institution",
                                  f"Perceptual hash distance {dist} <= {thr}. Same photo/scan may be reused.",
                                  [{"type": "duplicate", "document_id": d["id"], "other_document_id": o["id"],
                                    "other_application_id": o["app_id"], "similarity": round(1 - dist / 64, 3)}],
                                  doc_id=d["id"], key=o["id"], conf=round(1 - dist / 64, 3), detector="Duplicate detector (pHash)")
                for k, (od, oh) in seen.items():
                    if forensics.hamming(h, oh) <= thr and od != d["id"]:
                        F.add("DUPLICATE_WITHIN_APPLICATION", "ANOMALY", "Same image uploaded twice in this application",
                              "Counted once.", [{"type": "duplicate", "document_id": d["id"], "other_document_id": od}],
                              doc_id=d["id"], key=od, detector="Duplicate detector (pHash)")
                seen[f"{d['id']}:{h}"] = (d["id"], h)
                if im.get("emb"):
                    import numpy as np
                    cos_th = pack["thresholds"].get("duplicate_embed_cos", 0.95)
                    for o in db.documents.find({"app_id": {"$ne": app_id}, "superseded": {"$ne": True}, "result.images.emb": {"$ne": None}},
                                               {"id": 1, "app_id": 1, "result.images.emb": 1, "result.images.hash": 1}):
                        for oi in o["result"]["images"]:
                            if oi.get("emb") and app_inst.get(o["app_id"]) != app["institution_id"]:
                                cos = float(np.dot(im["emb"], oi["emb"]))
                                if cos >= cos_th and forensics.hamming(h, oi["hash"]) <= 20:
                                    F.add("DUPLICATE_ACROSS_INSTITUTIONS", "ANOMALY", "Image matches a document from another institution",
                                          f"Image-embedding similarity {cos:.3f} >= {cos_th}.",
                                          [{"type": "duplicate", "document_id": d["id"], "other_document_id": o["id"],
                                            "other_application_id": o["app_id"], "similarity": round(cos, 3)}],
                                          doc_id=d["id"], key=o["id"], conf=round(cos, 3), detector="Duplicate detector (image embeddings)")
    check("duplicates", c_dupes)

    # B12 verification flags
    vmap = {("qr", "MISMATCH"): "QR_MISMATCH", ("qr", "SIGNATURE_INVALID"): "QR_SIGNATURE_INVALID",
            ("ref_lookup", "MISMATCH"): "REF_MISMATCH", ("ref_lookup", "NOT_FOUND"): "REF_NOT_FOUND",
            ("ref_lookup", "SOURCE_UNAVAILABLE"): "VERIFICATION_SOURCE_UNAVAILABLE",
            ("pdf_sig", "SIGNATURE_INVALID"): "PDF_SIGNATURE_INVALID", ("pdf_sig", "MODIFIED_AFTER_SIGNING"): "PDF_MODIFIED_AFTER_SIGNING"}
    vids = [v for d in docs for v in d["result"].get("verification_ids", [])]
    vers = list(db.verifications.find({"id": {"$in": vids}}))

    def c_verify():
        for v in vers:
            code = vmap.get((v["method"], v["status"]))
            if code:
                d = next(x for x in docs if x["id"] == v["doc_id"])
                lbl = pack["taxonomy"].get(d["slot"], {}).get("label")
                diffs = v["details"].get("diffs", [])
                F.add(code, "VERIFICATION", f"{lbl}: {v['method']} {v['status'].replace('_', ' ').lower()}",
                      v["details"].get("reason") or "; ".join(f"{x['field']}: source '{x['source']}' vs document '{x['document']}'" for x in diffs),
                      [{"type": "verification", "verification_id": v["id"], "source": v["source"], "status": v["status"]}],
                      doc_id=d["id"], key=v["method"], detector=f"Verification adapter ({v['method']})",
                      action="Officer to confirm with the issuing authority" if code == "VERIFICATION_SOURCE_UNAVAILABLE" else None)
    check("verification", c_verify)

    # C6 infrastructure
    def c_infra():
        facs = pack.get("infrastructure", {}).get("facilities", {}) or {}
        ex = pack.get("infrastructure", {}).get("exif", {})
        photos = by_slot.get("INFRA_PHOTOS", [])
        for rule in pack["rules"]:
            if rule["kind"] == "count_vs_claim":
                spec = facs[rule["facility_type"]]
                for fac in [x for x in a.get("facilities", []) if x["type"] == rule["facility_type"]]:
                    ph = [p for p in photos if p.get("facility") == fac["id"]]
                    claimed = fac.get(spec["claim_field"])
                    if not ph:
                        continue
                    counted, hashes = 0, []
                    for p in ph:
                        if not p["result"].get("images"):
                            continue
                        im = max(p["result"]["images"], key=lambda x: (x.get("count") or {}).get("count", 0))  # a video counts its best frame
                        if any(forensics.hamming(im["hash"], h) <= 6 for h in hashes):
                            continue
                        hashes.append(im["hash"])
                        counted += (im.get("count") or {}).get("count", 0)
                    for p in ph:
                        room = p["result"]["images"][0].get("room") if p["result"].get("images") else None
                        if room and room["conf"] >= 0.5 and room["label"] not in spec.get("room_labels", []):
                            F.add("ROOM_TYPE_MISMATCH", "INFRASTRUCTURE", f"{fac['id']}: photo looks like a {room['label']}",
                                  f"Scene Classifier: '{room['label']}' ({room['conf']}), expected one of {spec.get('room_labels')}.",
                                  [{"type": "region", "document_id": p["id"], "page": 0, "bbox": [0, 0, 1, 1]}], rule_id=rule["id"],
                                  doc_id=p["id"], key="room", conf=room["conf"], detector="Scene Classifier", action="Provide a photo of the claimed facility")
                    if claimed and counted < claimed * (1 - spec.get("tolerance_pct", 15) / 100):
                        F.add(rule["code"], "INFRASTRUCTURE", f"{fac['id']}: {spec['count_object']}s {counted} detected / {claimed} claimed",
                              f"Detected count is below claim minus {spec.get('tolerance_pct')}% tolerance. Advisory only.",
                              [{"type": "region", "document_id": p["id"], "page": 0, "bbox": [0, 0, 1, 1]} for p in ph],
                              rule_id=rule["id"], key=fac["id"], expected=claimed, observed=counted, action=rule.get("action"),
                              conf=(((ph[0]["result"].get("images") or [{}])[0]).get("count") or {}).get("conf", 0.6), detector="Object Detector")
            if rule["kind"] == "exif_geo" and photos:
                window = ex.get("capture_window_days", 180)
                for p in photos:
                    e = p["result"].get("exif") or {}
                    if "lat" not in e:
                        F.add("EXIF_MISSING", "INFRASTRUCTURE", f"Photo {p['filename']} has no location data", "Cannot confirm it was taken on campus.",
                              [{"type": "metadata", "document_id": p["id"], "key": "exif", "value": e}], doc_id=p["id"], rule_id=rule["id"],
                              action=rule.get("action"))
                        continue
                    dist = infra.km(e["lat"], e["lon"], rec.get("lat", 0), rec.get("lon", 0))
                    old = e.get("taken_at") and e["taken_at"] < (date.fromisoformat(a["submitted_on"]) - timedelta(days=window)).isoformat()
                    if dist > ex.get("max_distance_km", 2) or old:
                        F.add(rule["code"], "INFRASTRUCTURE", f"Photo {p['filename']}: taken {dist} km from campus" if dist > ex.get("max_distance_km", 2) else f"Photo {p['filename']}: older than {window} days",
                              f"Distance {dist} km (max {ex.get('max_distance_km')}), taken {e.get('taken_at')}.",
                              [{"type": "metadata", "document_id": p["id"], "key": "gps", "value": [e["lat"], e["lon"]]},
                               {"type": "record", "adapter": "records", "key": "campus", "value": [rec.get("lat"), rec.get("lon")]}],
                              doc_id=p["id"], rule_id=rule["id"], expected=f"<= {ex.get('max_distance_km')} km", observed=f"{dist} km",
                              action=rule.get("action"))
    check("infrastructure", c_infra)

    if dry:
        return F.items
    # persist flags, carry dispositions forward
    prev = {f["fingerprint"]: f for f in db.flags.find({"app_id": app_id, "current": True})}
    db.flags.update_many({"app_id": app_id}, {"$set": {"current": False}})
    version = app.get("report_version", 0) + 1
    out = []
    seenfp = set()
    for f in F.items:
        if f["fingerprint"] in seenfp:
            continue
        seenfp.add(f["fingerprint"])
        p = prev.get(f["fingerprint"])
        f.update({"id": p["id"] if p else new_id("FLG"), "app_id": app_id, "report_version": version, "current": True,
                  "status": p["status"] if p else "OPEN", "disposition": p.get("disposition") if p else None,
                  "first_seen": p.get("first_seen", version) if p else version})
        out.append(f)
    if out:
        db.flags.insert_many([dict(x) for x in out])
    resolved = [p["id"] for fp, p in prev.items() if fp not in seenfp]

    w = pack["risk_weights"]
    open_f = [f for f in out if f["status"] in ("OPEN", "ESCALATED", "CONFIRMED")]
    risk = min(100, sum(w[f["severity"]] for f in open_f))
    counts = {s: sum(1 for f in open_f if f["severity"] == s) for s in ("HIGH", "MEDIUM", "LOW")}
    vstat = {"verified": sum(1 for v in vers if v["status"] == "VERIFIED"), "total": len(vers)}
    diff = records_diff(a, rec, ctx)
    summary = None
    if agent:
        try:
            summary = agent.summarize(out)
        except Exception as e:
            timeline.append({"stage": "case_writer", "status": "error", "note": f"{str(e)[:100]} -> template"})
    summary = summary or case_summary(out, pack)
    elapsed = round((time.perf_counter() - t0) * 1000)
    rep = {"id": new_id("RPT"), "app_id": app_id, "version": version, "created": now().isoformat(), "mode": MODE, "pack": ref,
           "flag_ids": [f["id"] for f in out], "resolved_flag_ids": resolved, "timeline": timeline, "records_diff": diff,
           "summary": summary, "risk": risk, "counts": counts, "verification": vstat, "elapsed_ms": elapsed,
           "changed": changed, "agents": bool(agent), "providers": providers.status()}
    db.reports.insert_one(dict(rep))
    status = "READY_FOR_REVIEW"
    db.applications.update_one({"id": app_id}, {"$set": {"report_version": version, "risk": risk, "counts": counts,
                                                         "verification": vstat, "status": status, "validated_at": now().isoformat(),
                                                         "elapsed_ms": elapsed}})
    if agent:
        agent.save_traces(rep["id"])
    raise_alerts(app, pack, out)
    audit(actor, "validation.run", app_id, {"version": version, "flags": len(out), "risk": risk, "changed": changed})
    send_webhook(app, "validation.updated" if version > 1 else "validation.completed", version)
    return rep


def records_diff(a, rec, ctx):
    rows = [("Institution name", a.get("institution_name"), rec.get("name"), (ctx.get("ACCREDITATION") or {}).get("institution")),
            ("Society name", a.get("society_name"), rec.get("society_name"), (ctx.get("SOCIETY_REG") or {}).get("society_name")),
            ("Current intake", a.get("current_intake"), rec.get("approved_intake"), None),
            ("Region", None, rec.get("region"), None),
            ("Established on", None, rec.get("established_on"), (ctx.get("SOCIETY_REG") or {}).get("issued_on"))]
    out = []
    for label, claim, record_v, docv in rows:
        vals = [str(x).lower() for x in (claim, record_v) if x is not None]
        out.append({"item": label, "application": claim, "records": record_v, "document": docv,
                    "mismatch": len(set(vals)) > 1})
    return out


def case_summary(flags, pack):
    """Case Writer (template). Each sentence cites flag IDs; no independent claims."""
    open_f = [f for f in flags if f["status"] != "DISMISSED"]
    if not open_f:
        return [{"text": "All configured checks passed. No open findings.", "flags": []}]
    out = []
    for sev in ("HIGH", "MEDIUM", "LOW"):
        fs = [f for f in open_f if f["severity"] == sev]
        if fs:
            cats = sorted({f["category"].lower() for f in fs})
            out.append({"text": f"{len(fs)} {sev.lower()}-severity finding(s) in {', '.join(cats)}: " +
                        "; ".join(f["title"] for f in fs[:4]) + ("." if len(fs) <= 4 else "; and more."),
                        "flags": [f["id"] for f in fs]})
    out.append({"text": "Findings are decision-support only. Final scrutiny and decisions remain with the competent authority.", "flags": []})
    return out


def raise_alerts(app, pack, flags):
    db = get_db()
    for rule in pack.get("alerts", []):
        codes = rule.get("on_codes")
        if not codes:
            continue
        hit = [f for f in flags if f["code"] in codes and f["status"] == "OPEN"]
        key = {"app_id": app["id"], "type": rule["type"]}
        if hit and not db.alerts.find_one({**key, "status": "OPEN"}):
            sev = "HIGH" if any(f["severity"] == "HIGH" for f in hit) else "MEDIUM"
            cond_at = now()
            db.alerts.insert_one({**key, "id": new_id("ALR"), "severity": sev, "status": "OPEN", "notify": rule["notify"],
                                  "channel": ["in-app", "webhook"], "flag_ids": [f["id"] for f in hit],
                                  "created": now().isoformat(), "condition_at": cond_at.isoformat(),
                                  "due": (cond_at + timedelta(days=2)).isoformat(), "institution": app["form"].get("institution_name")})
            notify_alert(app, rule["type"], sev, [f["title"] for f in hit])


def notify_alert(app, kind, sev, titles):
    """Email via SMTP_HOST when configured (e.g. Mailpit), otherwise kept in the outbox collection; plus host webhook."""
    db = get_db()
    msg = {"id": new_id("MAIL"), "ts": now().isoformat(), "to": "scrutiny-officers@pramaan.local", "app_id": app["id"],
           "subject": f"[PRAMAAN] {sev} {kind}: {app['form'].get('institution_name')}", "body": "\n".join(titles), "channel": "outbox"}
    host = os.environ.get("SMTP_HOST")
    if host:
        try:
            import smtplib
            from email.message import EmailMessage
            em = EmailMessage()
            em["From"], em["To"], em["Subject"] = "pramaan@pramaan.local", msg["to"], msg["subject"]
            em.set_content(msg["body"])
            with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "1025")), timeout=5) as sm:
                sm.send_message(em)
            msg["channel"] = "smtp"
        except Exception as e:
            msg["error"] = str(e)[:120]
    db.outbox.insert_one(msg)
    send_webhook(app, "alert.raised", app.get("report_version", 0), extra={"alert": kind, "severity": sev})


def send_webhook(app, event, version, extra=None):
    db = get_db()
    host = db.hosts.find_one({"id": app["host_id"]})
    if not host or not host.get("webhook_url"):
        return
    body = json.dumps({"event": event, "external_ref": app.get("external_ref"), "application_id": app["id"],
                       "report_version": version, "ts": now().isoformat(), **(extra or {})}).encode()
    stamp = str(int(time.time()))
    sig = hmac_sign(host["webhook_secret"], stamp.encode() + b"." + body)
    entry = {"id": new_id("WH"), "host_id": host["id"], "event": event, "app_id": app["id"], "ts": now().isoformat()}
    url = host["webhook_url"]
    if url.startswith("/"):
        prod = os.environ.get("VERCEL_PROJECT_PRODUCTION_URL")
        url = os.environ.get("PUBLIC_URL", f"https://{prod}" if prod else "http://127.0.0.1:8010") + url
    for attempt in range(2):
        try:
            r = httpx.post(url, content=body, headers={"X-Pramaan-Signature": sig, "X-Pramaan-Timestamp": stamp,
                                                       "X-Pramaan-Delivery": entry["id"], "Content-Type": "application/json"},
                           timeout=httpx.Timeout(6, connect=2))
            entry.update(status=r.status_code, attempts=attempt + 1)
            if r.status_code < 500:
                break
        except Exception as e:
            entry.update(status="error", error=str(e)[:120], attempts=attempt + 1)
    db.webhook_deliveries.insert_one(entry)

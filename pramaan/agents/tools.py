"""Typed, read-only tools for the agents (02_ARCHITECTURE.md §6.3). Every tool wraps an existing pipeline function.
Agents cannot write records, rule packs, dispositions or decisions. The only flags agents can cause come from deterministic
checks inside these tools, and emit_flag() looks severity up in the rule pack; nothing the LLM says sets a severity or status."""
import time
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from .. import engine, extract, forensics, providers, verify
from ..db import get_db

ReadMode = Literal["native", "ocr", "manual"]


class NoArgs(BaseModel):
    pass


class DocArgs(BaseModel):
    doc_id: str


class PlanDoc(BaseModel):
    doc_id: str
    read: ReadMode = "native"
    forensics: Literal["skip", "check"] = "check"
    verify: list[Literal["qr", "pdf_sig", "ref_lookup"]] = []


class PlanArgs(BaseModel):
    docs: list[PlanDoc]
    notes: str = Field("", max_length=400)


class ReadArgs(BaseModel):
    mode: Literal["ocr", "manual"]


class FieldArgs(BaseModel):
    field: str


class LookupArgs(BaseModel):
    retries: int = Field(1, ge=0, le=3)


class PairArgs(BaseModel):
    left: str = Field(..., description="field path like SOCIETY_REG.society_name or records.society_name")
    right: str


class CountArgs(BaseModel):
    doc_id: str
    label: str = Field(..., max_length=40, description="object to count, e.g. 'computer monitor'")


class FinishArgs(BaseModel):
    reason: str = Field("", max_length=300)


class Tool:
    def __init__(self, name, desc, args, fn, untrusted=False):
        self.name, self.desc, self.args, self.fn, self.untrusted = name, desc, args, fn, untrusted

    def schema(self):
        js = self.args.model_json_schema()
        js.pop("title", None)
        return {"type": "function", "function": {"name": self.name, "description": self.desc, "parameters": js}}

    def call(self, ctx, raw):
        try:
            a = self.args.model_validate(raw or {})
        except ValidationError as e:
            return {"error": f"invalid arguments: {e.errors()[:2]}"}
        try:
            return self.fn(ctx, a)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {str(e)[:160]}"}


# ---------------- emit guard
def emit_flag(ctx, code, category, title, reason, evidence, **kw):
    """Schema-checked flag from an agent-run check. Severity comes from the rule pack inside Flags.add; evidence is required."""
    if code not in ctx.pack["severity"]:
        raise ValueError(f"unknown flag code {code}")
    if not evidence:
        ctx.trace("Critic", "reject_flag", {"code": code}, f"dropped {code}: no evidence")
        return False
    ctx.extra_flags.append(dict(code=code, category=category, title=title, reason=reason, evidence=evidence, **kw))
    return True


# ---------------- Orchestrator
def get_manifest(ctx, a):
    cat = ctx.pack["categories"][ctx.app["category"]]
    present = {d["slot"] for d in ctx.docs}
    return {"category": ctx.app["category"], "required": cat["required_slots"], "optional": cat.get("optional_slots", []),
            "missing": [s for s in cat["required_slots"] if s not in present],
            "documents": [{"doc_id": d["id"], "slot": d["slot"], "file": d["filename"], "kind": d["filename"].rsplit(".", 1)[-1].lower(),
                           "taxonomy_verification": (ctx.pack["taxonomy"].get(d["slot"]) or {}).get("verification", [])} for d in ctx.docs]}


def peek_document(ctx, a):
    """Cheap look before reading: page count, how much text the PDF carries, whether it is digitally signed."""
    d = ctx.doc(a.doc_id)
    data = engine.get_blob(d["blob_id"])
    if not d["filename"].lower().endswith(".pdf"):
        return {"doc_id": d["id"], "type": "image or video", "text_chars": 0}
    pdf = extract.open_pdf(data)
    chars = len("".join(extract.pdf_text(pdf)).strip())
    return {"doc_id": d["id"], "pages": len(pdf), "text_chars": chars, "has_text_layer": chars >= ctx.th.get("min_text_chars", 40),
            "digitally_signed": b"/ByteRange" in data}


def submit_plan(ctx, a):
    ids = {d["id"] for d in ctx.docs}
    unknown = [p.doc_id for p in a.docs if p.doc_id not in ids]
    if unknown:
        return {"error": f"unknown doc ids {unknown}"}
    missing = ids - {p.doc_id for p in a.docs}
    if missing:
        return {"error": f"plan must cover every document; missing {sorted(missing)}"}
    problems = []
    for p in a.docs:
        d = ctx.doc(p.doc_id)
        media = d["slot"] == "INFRA_PHOTOS" or d["filename"].lower().endswith(engine.VIDEO)
        if p.forensics == "skip" and not media:
            problems.append(f"{d['filename']}: forensics can only be skipped for photos and videos")
        if d["filename"].lower().endswith(".pdf"):
            has_text = peek_document(ctx, DocArgs(doc_id=d["id"]))["text_chars"] >= ctx.th.get("min_text_chars", 40)
            if p.read == "native" and not has_text:
                problems.append(f"{d['filename']}: has no text layer, use 'ocr' or 'manual'")
            if p.read == "ocr" and has_text:
                problems.append(f"{d['filename']}: has a text layer, use 'native'")
    if problems:
        return {"error": "fix the plan: " + "; ".join(problems)}
    ctx.plan = {p.doc_id: p.model_dump() for p in a.docs}
    ctx.plan_notes = a.notes
    return {"ok": True}


# ---------------- Document Agent
def read_document(ctx, a):
    d = ctx.current
    ctx.read_mode[d["id"]] = a.mode
    return {"ok": True, "mode": a.mode}


def compare_readers(ctx, a):
    """OCR Model value vs Handwriting Model value for one field at normal resolution."""
    return _readers(ctx, a.field, 1)


def reread_crop_2x(ctx, a):
    """Re-reads the field's crop at 2x with both readers. If they still disagree, records an EXTRACTION_CONFLICT."""
    out = _readers(ctx, a.field, 2)
    if "error" not in out and not out["agree"]:
        r = ctx.result(ctx.current["id"])
        r.setdefault("conflicts", []).append({"field": a.field, "ocr": out["ocr"], "htr": out["htr"], "bbox": out["bbox"]})
    return out


def _readers(ctx, field, scale):
    r = ctx.result(ctx.current["id"])
    f = (r.get("fields") or {}).get(field)
    imgs = engine.IMG_CACHE.get(ctx.current["id"]) or []
    if not f or not imgs:
        return {"error": "field not read or no page image"}
    img = imgs[0]
    W, H = img.size
    b = f["bbox"]
    crop = img.crop((int(b[0] * W), int(b[1] * H), int((b[0] + b[2]) * W), int((b[1] + b[3]) * H)))
    if scale != 1:
        crop = crop.resize((crop.width * scale, crop.height * scale))
    lines = providers.ocr.read(crop) or []
    ocr = " ".join(l["text"] for l in lines).strip() or (f.get("raw") or "")
    htr = (providers.htr.read(crop) or {}).get("text", "")
    norm = lambda s: "".join(ch for ch in str(s).lower() if ch.isalnum())
    return {"field": field, "ocr": ocr, "htr": htr, "agree": bool(norm(ocr)) and norm(ocr) == norm(htr), "scale": scale, "bbox": b}


def field_confidence(ctx, a):
    r = ctx.result(ctx.current["id"])
    return {"fields": {k: {"value": v.get("raw"), "conf": v.get("conf")} for k, v in (r.get("fields") or {}).items()}}


# ---------------- Forensics Agent
def forensics_cheap(ctx, a):
    d = ctx.current
    r = ctx.result(d["id"])
    out = {"thresholds": {"ela_suspicion": ctx.th.get("ela_suspicion", 1.5), "noise_suspicion": ctx.th.get("noise_suspicion", 0.65)},
           "pdf_metadata_findings": [f["reason"] for f in r.get("pdf_findings", [])],
           "images": engine.forensics_tier(d["id"], r, ctx.th, "cheap")}
    ctx.signals[d["id"]] = out
    return out


def forensics_deep(ctx, a):
    d = ctx.current
    r = ctx.result(d["id"])
    out = engine.forensics_tier(d["id"], r, ctx.th, "deep")
    ctx.deep_done.add(d["id"])
    return {"images": out}


def text_level_forensics(ctx, a):
    d = ctx.current
    if not d["filename"].lower().endswith(".pdf") or ctx.result(d["id"]).get("scanned"):
        return {"error": "text-level forensics needs a digital PDF"}
    return {"outliers": engine.text_forensics(d, ctx.result(d["id"]))}


# ---------------- Verification Agent
def available_evidence(ctx, a):
    d = ctx.current
    r = ctx.result(d["id"])
    flds = r.get("fields") or {}
    return {"has_qr": bool(r.get("qr")), "digitally_signed": (r.get("pdf_sig") or {}).get("status") not in (None, "NOT_SIGNED"),
            "reference_number": bool(flds.get("ref_no") or flds.get("reg_no")), "issuer_named": bool(flds.get("issuer")),
            "rule_pack_methods": (ctx.pack["taxonomy"].get(d["slot"]) or {}).get("verification", []), "already_done": ctx.methods_done(d["id"])}


def qr_verify(ctx, a):
    d, r = ctx.current, ctx.result(ctx.current["id"])
    if not r.get("qr"):
        return {"error": "no QR code on this document"}
    v = verify.verify_qr(d["id"], ctx.app["id"], r["qr"], r.get("fields") or {})
    ctx.add_verification(d["id"], v)
    return {"status": v["status"], "source": v["source"]}


def pdf_sig_verify(ctx, a):
    d, r = ctx.current, ctx.result(ctx.current["id"])
    if not r.get("pdf_sig"):
        return {"error": "not a PDF"}
    v = verify.record_pdf_sig(d["id"], ctx.app["id"], r["pdf_sig"])
    ctx.add_verification(d["id"], v)
    return {"status": v["status"], "source": v["source"]}


def issuer_lookup(ctx, a):
    d, r = ctx.current, ctx.result(ctx.current["id"])
    v = verify.verify_ref(d["id"], ctx.app["id"], d["slot"], r.get("fields") or {}, retries=a.retries)
    ctx.add_verification(d["id"], v)
    return {"status": v["status"], "source": v["source"], "attempts": (v["details"] or {}).get("attempts", 1)}


# ---------------- Consistency Agent
def list_fields(ctx, a):
    out = {}
    for d in ctx.docs:
        r = ctx.result(d["id"]) or {}
        for k, v in (r.get("fields") or {}).items():
            if v.get("value") is not None:
                out[f"{d['slot']}.{k}"] = v.get("raw")
    for k in ("institution_name", "society_name"):
        if ctx.app["form"].get(k):
            out[f"app.{k}"] = ctx.app["form"][k]
    for k in ("name", "society_name"):
        if ctx.records.get(k):
            out[f"records.{k}"] = ctx.records[k]
    return {"fields": {k: {"value": v, "entity": entity_role(ctx, k)} for k, v in out.items() if entity_role(ctx, k)},
            "already_compared_by_rules": ctx.rule_pairs}


def entity_role(ctx, path):
    """'society' or 'institution' for a name field (rule pack taxonomy), so only like is compared with like."""
    slot, _, name = path.partition(".")
    if slot == "records":
        return {"society_name": "society", "name": "institution"}.get(name)
    if slot == "app":
        return {"society_name": "society", "institution_name": "institution"}.get(name)
    return ((ctx.pack["taxonomy"].get(slot) or {}).get("fields", {}).get(name) or {}).get("entity")


def compare_entities(ctx, a):
    vals = list_fields(ctx, a)["fields"]
    if a.left not in vals or a.right not in vals:
        return {"error": "unknown field path; use list_fields"}
    rl, rr = entity_role(ctx, a.left), entity_role(ctx, a.right)
    if not rl or rl != rr:
        return {"error": f"not comparable: {a.left} names a {rl or 'non-organisation'}, {a.right} names a {rr or 'non-organisation'}"}
    from rapidfuzz import fuzz
    lv, rv = vals[a.left]["value"], vals[a.right]["value"]
    score = fuzz.token_set_ratio(engine._norm_name(lv), engine._norm_name(rv)) / 100
    if any(ord(ch) > 0x900 for ch in lv + rv):
        score = max(score, fuzz.token_set_ratio(engine._skeleton(lv), engine._skeleton(rv)) / 100)
    th = ctx.th.get("name_match", 0.88)
    pair = tuple(sorted([a.left, a.right]))
    covered = any(tuple(sorted(p)) == pair for p in ctx.rule_pairs)
    if score < th and not covered:
        ev = [{"type": "field", "key": a.left, "value": lv}, {"type": "field", "key": a.right, "value": rv}]
        emit_flag(ctx, "NAME_MISMATCH", "CONSISTENCY", f"Name mismatch: {a.left} vs {a.right}",
                  f"'{lv}' vs '{rv}' similarity {score:.2f} below {th} (pair chosen by the Consistency Agent).", ev,
                  rule_id=f"AGENT.entity:{a.left}|{a.right}", key=a.right, expected=lv, observed=rv, detector="Consistency Agent")
    return {"score": round(score, 3), "threshold": th, "below_threshold": score < th, "covered_by_rule_pack": covered}


# ---------------- Infrastructure Agent
def map_facility_photos(ctx, a):
    photos = [d for d in ctx.docs if d["slot"] == "INFRA_PHOTOS"]
    return {"facilities": [{"id": f["id"], "type": f["type"], "claims": {k: v for k, v in f.items() if k.startswith("claimed")},
                            "photos": [p["id"] for p in photos if p.get("facility") == f["id"]]} for f in ctx.app["form"].get("facilities", [])],
            "unassigned_photos": [p["id"] for p in photos if not p.get("facility")]}


def count_objects(ctx, a):
    d = ctx.doc(a.doc_id)
    imgs = engine.IMG_CACHE.get(d["id"]) or []
    if not imgs:
        return {"error": "no image for this document"}
    c = providers.detector.count(imgs[0], a.label)
    r = ctx.result(d["id"])
    if r.get("images"):
        r["images"][0].setdefault("agent_counts", {})[a.label] = c["count"]
    return {"doc_id": d["id"], "label": a.label, "count": c["count"], "detector": c["detector"]}


def finish(ctx, a):
    return {"ok": True, "reason": a.reason}


T = Tool
REGISTRY = {
    "Orchestrator": [T("get_manifest", "Lists uploaded documents, required and missing slots.", NoArgs, get_manifest),
                     T("peek_document", "Cheap check of one document: pages, text layer, digital signature.", DocArgs, peek_document),
                     T("submit_plan", "Submit the per-document plan: read mode, forensics, verification methods. Must cover every document.", PlanArgs, submit_plan)],
    "Document Agent": [T("read_document", "Choose how to read this scanned page: 'ocr' (OCR + Handwriting Models) or 'manual' (leave to a person).", ReadArgs, read_document),
                       T("field_confidence", "Values and confidence of the fields read so far.", NoArgs, field_confidence, untrusted=True),
                       T("compare_readers", "OCR Model vs Handwriting Model reading of one field.", FieldArgs, compare_readers, untrusted=True),
                       T("reread_crop_2x", "Re-read one field crop at 2x with both readers; records a conflict if they still disagree.", FieldArgs, reread_crop_2x, untrusted=True),
                       T("finish", "Done with this document.", FinishArgs, finish)],
    "Forensics Agent": [T("forensics_cheap", "Cheap checks: ELA and noise residual per image, PDF metadata findings, with thresholds.", NoArgs, forensics_cheap),
                        T("forensics_deep", "Deeper checks: copy-move search and the edit heatmap. Use when a cheap signal crosses its threshold.", NoArgs, forensics_deep),
                        T("text_level_forensics", "Font and size outliers inside field values (digital PDFs only).", NoArgs, text_level_forensics),
                        T("finish", "Done with this document.", FinishArgs, finish)],
    "Verification Agent": [T("available_evidence", "What this document carries for verification and what is already done.", NoArgs, available_evidence),
                           T("qr_verify", "Verify the signed QR code against the issuer key.", NoArgs, qr_verify),
                           T("pdf_sig_verify", "Validate the PDF digital signature against the trusted issuer CA.", NoArgs, pdf_sig_verify),
                           T("issuer_lookup", "Look up the reference number with the issuing office; retries with back-off if it is down.", LookupArgs, issuer_lookup),
                           T("finish", "Done with this document.", FinishArgs, finish)],
    "Consistency Agent": [T("list_fields", "All extracted name fields, form claims and records, plus pairs the rule pack already compares.", NoArgs, list_fields, untrusted=True),
                          T("compare_entities", "Compare two name fields (fuzzy, transliteration-aware).", PairArgs, compare_entities, untrusted=True),
                          T("finish", "Done.", FinishArgs, finish)],
    "Infrastructure Agent": [T("map_facility_photos", "Claimed facilities with their photos and claims.", NoArgs, map_facility_photos),
                             T("count_objects", "Count one kind of object in a photo with the Object Detector.", CountArgs, count_objects),
                             T("finish", "Done.", FinishArgs, finish)],
}

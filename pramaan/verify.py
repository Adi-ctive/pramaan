"""Source verification adapters: signed QR (Ed25519) and issuer reference lookup (mock issuer)."""
import base64
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from rapidfuzz import fuzz

from .db import get_db, new_id, now
from .security import sha256

COMPARE = ["ref_no", "valid_to", "issued_on", "addressee", "institution", "programme", "lessee", "owner"]


def _b64d(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _record(doc_id, app_id, method, source, status, details):
    from .audit import record as audit
    v = {"id": new_id("VER"), "doc_id": doc_id, "app_id": app_id, "method": method, "source": source,
         "status": status, "ts": now().isoformat(), "details": details,
         "response_digest": sha256(json.dumps(details, sort_keys=True, default=str).encode())[:16]}
    v["request_digest"] = sha256(f"{method}|{doc_id}|{source}".encode())[:16]
    get_db().verifications.insert_one(dict(v))
    audit("verifier", f"verification.{method}", doc_id, {"status": status, "source": source, "response_digest": v["response_digest"]})
    return v


def _compare(claimed, fields):
    diffs = []
    for k in COMPARE:
        if k in claimed and k in fields and fields[k].get("value") is not None:
            a, b = str(claimed[k]), str(fields[k]["value"])
            if a != b and fuzz.token_set_ratio(a.lower(), b.lower()) < 95:
                diffs.append({"field": k, "source": a, "document": b})
    return diffs


def check_qr(payload, get_pub, fields):
    """Pure check. Returns (status, issuer_id, details)."""
    try:
        tag, body, sig = payload.split(".")
        assert tag == "PRM1"
        claimed = json.loads(_b64d(body))
    except Exception:
        return "MANUAL_REVIEW", None, {"reason": "QR is not a recognised signed payload"}
    pub = get_pub(claimed.get("iss"))
    if not pub:
        return "MANUAL_REVIEW", claimed.get("iss"), {"reason": "Unknown issuer key"}
    try:
        Ed25519PublicKey.from_public_bytes(_b64d(pub)).verify(_b64d(sig), _b64d(body))
    except InvalidSignature:
        return "SIGNATURE_INVALID", claimed.get("iss"), {"reason": "QR signature does not verify with the issuer key"}
    diffs = _compare(claimed, fields)
    return ("MISMATCH" if diffs else "VERIFIED"), claimed.get("iss"), {"diffs": diffs, "claimed": claimed}


def verify_qr(doc_id, app_id, qr, fields):
    db = get_db()
    names = {}

    def pub(iid):
        i = db.issuers.find_one({"id": iid})
        if i:
            names[iid] = i["name"]
        return i and i["public_key"]
    status, iid, det = check_qr(qr["payload"], pub, fields)
    return _record(doc_id, app_id, "qr", names.get(iid, iid), status, det)


def verify_ref(doc_id, app_id, doc_type, fields, retries=0):
    db = get_db()
    name = (fields.get("issuer") or {}).get("value")
    ref = (fields.get("ref_no") or fields.get("reg_no") or {}).get("value")
    if not ref:
        return _record(doc_id, app_id, "ref_lookup", name, "MANUAL_REVIEW", {"reason": "No reference number extracted"})
    issuer, best = None, 89
    for i in db.issuers.find({"doc_types": doc_type}):
        sc = fuzz.ratio(i["name"].lower(), (name or "").lower())
        if sc > best:
            issuer, best = i, sc
    if not issuer:
        return _record(doc_id, app_id, "ref_lookup", name, "MANUAL_REVIEW", {"reason": "No authorised source registered for this issuer"})
    import time
    for attempt in range(retries + 1):
        if issuer.get("latency_ms"):
            time.sleep(min(issuer["latency_ms"], 3000) / 1000)
        if not issuer.get("down"):
            break
        if attempt < retries:
            time.sleep(0.2 * (2 ** attempt))
    if issuer.get("down"):
        return _record(doc_id, app_id, "ref_lookup", issuer["name"], "SOURCE_UNAVAILABLE",
                       {"reason": "Issuer service did not respond", "attempts": retries + 1})
    rec = db.issuer_records.find_one({"issuer_id": issuer["id"], "ref_no": ref})
    if not rec:
        return _record(doc_id, app_id, "ref_lookup", issuer["name"], "NOT_FOUND", {"ref_no": ref})
    diffs = _compare(rec["fields"], fields)
    if issuer.get("force_mismatch"):
        diffs.append({"field": "forced", "source": "toggle", "document": "-"})
    return _record(doc_id, app_id, "ref_lookup", issuer["name"], "MISMATCH" if diffs else "VERIFIED", {"diffs": diffs})


# ---------------- PDF digital signatures (pyHanko) against the demo issuer CA
def trust_roots():
    from asn1crypto import pem, x509
    out = []
    for t in get_db().trust_roots.find():
        _, _, der = pem.unarmor(t["pem"].encode())
        out.append(x509.Certificate.load(der))
    return out


def check_pdf_sig(data):
    import logging
    logging.getLogger("pyhanko").setLevel(logging.CRITICAL)
    logging.getLogger("pyhanko_certvalidator").setLevel(logging.CRITICAL)
    """Pure check: {status, signer, intact, valid, trusted, coverage, modification}. Status is VERIFIED,
    SIGNATURE_INVALID, MODIFIED_AFTER_SIGNING or NOT_SIGNED."""
    import io
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext
    r = PdfFileReader(io.BytesIO(data), strict=False)
    if not r.embedded_signatures:
        return {"status": "NOT_SIGNED"}
    sig = r.embedded_signatures[0]
    st = validate_pdf_signature(sig, ValidationContext(trust_roots=trust_roots(), allow_fetching=False, revocation_mode="soft-fail"))
    cov = str(getattr(st.coverage, "name", st.coverage))
    mod = str(getattr(st.modification_level, "name", st.modification_level))
    out = {"signer": st.signing_cert.subject.human_friendly, "intact": bool(st.intact), "valid": bool(st.valid),
           "trusted": bool(st.trusted), "coverage": cov, "modification": mod}
    if not (st.intact and st.valid and st.trusted):
        out["status"] = "SIGNATURE_INVALID"
    elif cov != "ENTIRE_FILE" and mod not in ("NONE", "LTA_UPDATES"):
        out["status"] = "MODIFIED_AFTER_SIGNING"
    else:
        out["status"] = "VERIFIED"
    return out


def record_pdf_sig(doc_id, app_id, res):
    status = res["status"] if res["status"] != "NOT_SIGNED" else "MANUAL_REVIEW"
    reason = {"NOT_SIGNED": "Document carries no digital signature", "SIGNATURE_INVALID": "Signature does not validate against a trusted issuer certificate",
              "MODIFIED_AFTER_SIGNING": "Content was changed after the issuer signed it"}.get(res["status"])
    return _record(doc_id, app_id, "pdf_sig", res.get("signer"), status, {**res, **({"reason": reason} if reason else {})})


def carry_forward(doc, app):
    """FR-REC-02: identical file already verified for this institution -> VERIFIED (carried forward)."""
    db = get_db()
    same = [x["id"] for x in db.documents.find({"sha256": doc.get("sha256"), "id": {"$ne": doc["id"]}}, {"id": 1, "app_id": 1})
            if (db.applications.find_one({"id": x["app_id"]}, {"institution_id": 1}) or {}).get("institution_id") == app["institution_id"]]
    for sid in same:
        prev = list(db.verifications.find({"doc_id": sid}).sort("ts", 1))
        latest = {}
        for v in prev:
            latest[v["method"]] = v
        # only when every method on that identical file passed; a single mismatch means re-verify from scratch
        if latest and all(v["status"] == "VERIFIED" for v in latest.values()):
            return [_record(doc["id"], app["id"], v["method"], v["source"], "VERIFIED",
                            {"carried_forward_from": v["id"], "original_ts": v["ts"], "reason": "Identical file verified earlier (carried forward)"})
                    for v in latest.values()]
    return None

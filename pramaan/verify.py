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
    v = {"id": new_id("VER"), "doc_id": doc_id, "app_id": app_id, "method": method, "source": source,
         "status": status, "ts": now().isoformat(), "details": details,
         "response_digest": sha256(json.dumps(details, sort_keys=True, default=str).encode())[:16]}
    get_db().verifications.insert_one(dict(v))
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


def verify_ref(doc_id, app_id, doc_type, fields):
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
    if issuer.get("down"):
        return _record(doc_id, app_id, "ref_lookup", issuer["name"], "SOURCE_UNAVAILABLE", {"reason": "Issuer service did not respond"})
    rec = db.issuer_records.find_one({"issuer_id": issuer["id"], "ref_no": ref})
    if not rec:
        return _record(doc_id, app_id, "ref_lookup", issuer["name"], "NOT_FOUND", {"ref_no": ref})
    diffs = _compare(rec["fields"], fields)
    if issuer.get("force_mismatch"):
        diffs.append({"field": "forced", "source": "toggle", "document": "-"})
    return _record(doc_id, app_id, "ref_lookup", issuer["name"], "MISMATCH" if diffs else "VERIFIED", {"diffs": diffs})

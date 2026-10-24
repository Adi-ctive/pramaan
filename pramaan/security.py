"""Passwords, tokens, RBAC, field encryption and upload safety (05_SECURITY.md)."""
import base64
import hashlib
import hmac
import io
import os
import time

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Depends, HTTPException, Request

from .db import get_db

_ph = PasswordHasher()
ROLES = ["INSTITUTION", "SCRUTINY_OFFICER", "SENIOR_OFFICER", "RULE_ADMIN", "INTEGRATION_ADMIN", "AUDITOR"]

# capability -> roles (05_SECURITY.md §4)
MATRIX = {
    "upload_own": ["INSTITUTION"],
    "view_queue": ["SCRUTINY_OFFICER", "SENIOR_OFFICER", "AUDITOR"],
    "view_forensics": ["SCRUTINY_OFFICER", "SENIOR_OFFICER", "AUDITOR"],
    "dispose_flags": ["SCRUTINY_OFFICER", "SENIOR_OFFICER"],
    "decision_note": ["SENIOR_OFFICER"],
    "edit_rules": ["RULE_ADMIN"],
    "manage_hosts": ["INTEGRATION_ADMIN"],
    "audit": ["SENIOR_OFFICER", "AUDITOR"],
    "run_eval": ["RULE_ADMIN"],
}


def _secret():
    s = os.environ.get("SESSION_SECRET")
    if not s:
        s = os.environ.setdefault("SESSION_SECRET", base64.b64encode(os.urandom(32)).decode())
    return s


def hash_password(pw):
    return _ph.hash(pw)


def check_password(h, pw):
    try:
        return _ph.verify(h, pw)
    except VerifyMismatchError:
        return False


def make_token(user, minutes=480):
    payload = {"sub": user["username"], "role": user["role"], "region": user.get("region", "ALL"),
               "exp": int(time.time()) + minutes * 60}
    return jwt.encode(payload, _secret(), algorithm="HS256")


def current_user(request: Request):
    tok = request.cookies.get("pramaan_session") or request.headers.get("authorization", "").removeprefix("Bearer ")
    if not tok:
        raise HTTPException(401, "Sign in required")
    try:
        return jwt.decode(tok, _secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired")


def require(cap):
    def dep(user=Depends(current_user)):
        if user["role"] not in MATRIX[cap]:
            raise HTTPException(403, f"Role {user['role']} lacks {cap}")
        return user
    return dep


def can(user, cap):
    return user["role"] in MATRIX[cap]


def _key():
    raw = os.environ.get("FIELD_KEY")
    return base64.b64decode(raw) if raw else hashlib.sha256(_secret().encode()).digest()


def encrypt(text):
    if text is None:
        return None
    nonce = os.urandom(12)
    return base64.b64encode(nonce + AESGCM(_key()).encrypt(nonce, text.encode(), None)).decode()


def decrypt(blob):
    if not blob:
        return None
    raw = base64.b64decode(blob)
    return AESGCM(_key()).decrypt(raw[:12], raw[12:], None).decode()


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def hmac_sign(secret, body: bytes):
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def hmac_ok(secret, body, sig):
    return hmac.compare_digest(hmac_sign(secret, body), sig or "")


# ---- upload safety (§8). No ClamAV on serverless: signature scan + structure checks.
MAX_BYTES = 4 * 1024 * 1024
ALLOWED = {".pdf": b"%PDF", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".png": b"\x89PNG"}
EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!"


def check_upload(name, data):
    ext = os.path.splitext(name.lower())[1]
    if len(data) > MAX_BYTES:
        return "File is larger than 4 MB"
    if ext not in ALLOWED:
        return "Only PDF, JPG and PNG files are accepted"
    if EICAR in data:
        return "File rejected by malware scan (test signature EICAR)"
    if not data.startswith(ALLOWED[ext]):
        return "File content does not match its extension"
    if ext == ".pdf":
        if b"/JavaScript" in data or b"/Launch" in data or b"/EmbeddedFile" in data:
            return "PDF contains active content and was rejected"
    else:
        from PIL import Image
        try:
            Image.open(io.BytesIO(data)).verify()
        except Exception:
            return "Image could not be decoded"
    return None


def rate_limit(key, limit=20, window=300):
    db = get_db()
    t = int(time.time()) // window
    r = db.rate.find_one_and_update({"_id": f"{key}:{t}"}, {"$inc": {"n": 1}}, upsert=True, return_document=True)
    if r and r.get("n", 0) > limit:
        raise HTTPException(429, "Too many attempts, try again later")

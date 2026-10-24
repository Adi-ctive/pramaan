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


ACCESS_MIN, REFRESH_H = 15, 8


def make_token(user, minutes=ACCESS_MIN, kind="access", jti=None):
    payload = {"sub": user["username"], "role": user["role"], "region": user.get("region", "ALL"), "typ": kind,
               "exp": int(time.time()) + minutes * 60}
    if jti:
        payload["jti"] = jti
    return jwt.encode(payload, _secret(), algorithm="HS256")


def issue_session(response, user):
    """15-minute access cookie plus an 8-hour rotating refresh cookie (SameSite=Strict, refresh path only)."""
    import secrets as _s
    jti = _s.token_urlsafe(16)
    get_db().refresh_tokens.insert_one({"jti": jti, "user": user["username"], "exp": int(time.time()) + REFRESH_H * 3600, "used": False})
    secure = os.environ.get("VERCEL") == "1"
    response.set_cookie("pramaan_session", make_token(user), httponly=True, samesite="lax", secure=secure, max_age=ACCESS_MIN * 60)
    response.set_cookie("pramaan_refresh", make_token(user, REFRESH_H * 60, "refresh", jti), httponly=True, samesite="strict",
                        secure=secure, max_age=REFRESH_H * 3600, path="/api/auth")


def decode(tok):
    return jwt.decode(tok, _secret(), algorithms=["HS256"])


def current_user(request: Request):
    tok = request.cookies.get("pramaan_session") or request.headers.get("authorization", "").removeprefix("Bearer ")
    if not tok:
        raise HTTPException(401, "Sign in required")
    try:
        claims = decode(tok)
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired")
    if claims.get("typ", "access") != "access":
        raise HTTPException(401, "Wrong token type")
    return claims


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
MAX_BYTES = int(float(os.environ.get("MAX_UPLOAD_MB", "4")) * 1024 * 1024)  # Vercel request cap; 25 MB locally
ALLOWED = {".pdf": b"%PDF", ".jpg": b"\xff\xd8\xff", ".jpeg": b"\xff\xd8\xff", ".png": b"\x89PNG", ".tif": (b"II*\x00", b"MM\x00*"),
           ".tiff": (b"II*\x00", b"MM\x00*"), ".mp4": None, ".mov": None}
MAX_PDF_PAGES = 300


def clamd_scan(data):
    """ClamAV INSTREAM when CLAMD_HOST is set. Returns a virus name, None if clean, or 'unavailable'."""
    import socket
    import struct
    host = os.environ.get("CLAMD_HOST")
    if not host:
        return "unavailable"
    try:
        with socket.create_connection((host, int(os.environ.get("CLAMD_PORT", "3310"))), timeout=10) as sk:
            sk.sendall(b"zINSTREAM\0")
            for i in range(0, len(data), 8192):
                chunk = data[i:i + 8192]
                sk.sendall(struct.pack("!L", len(chunk)) + chunk)
            sk.sendall(struct.pack("!L", 0))
            reply = sk.recv(4096).decode(errors="ignore")
        return reply.split("FOUND")[0].split(":")[-1].strip() if "FOUND" in reply else None
    except OSError:
        return "unavailable"
EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!"


def check_upload(name, data):
    ext = os.path.splitext(name.lower())[1]
    if len(data) > MAX_BYTES:
        return f"File is larger than {MAX_BYTES // (1024 * 1024)} MB"
    if ext not in ALLOWED:
        return "Only PDF, JPG, PNG, TIFF, MP4 and MOV files are accepted"
    if data[:4] in (b"PK\x03\x04", b"Rar!") or data[:2] == b"\x1f\x8b":
        return "Archives are not accepted"
    virus = clamd_scan(data)
    if virus not in (None, "unavailable"):
        return f"File rejected by malware scan ({virus})"
    if virus == "unavailable" and EICAR in data:  # signature fallback when no ClamAV daemon is reachable
        return "File rejected by malware scan (test signature EICAR)"
    magic = ALLOWED[ext]
    if ext in (".mp4", ".mov"):
        if data[4:8] not in (b"ftyp", b"moov", b"mdat", b"wide"):
            return "File content does not match its extension"
        return None
    if not data.startswith(magic if isinstance(magic, tuple) else (magic,)):
        return "File content does not match its extension"
    if ext == ".pdf":
        import re
        dicts = re.sub(rb"stream\r?\n.*?endstream", b"", data, flags=re.S)  # look at object dictionaries, not binary streams
        hit = re.search(rb"/(JavaScript|JS|Launch|EmbeddedFile|OpenAction)(?=[\s/<\[(>])", dicts)
        if hit:
            return f"PDF contains active content (/{hit.group(1).decode()}) and was rejected"
        if data.count(b"/Type /Page") - data.count(b"/Type /Pages") > MAX_PDF_PAGES:
            return f"PDF has more than {MAX_PDF_PAGES} pages"
    else:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = 60_000_000  # decompression-bomb guard
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

"""PRAMAAN API: host integration, widget, officer console, admin, audit, evaluation."""
import csv
import io
import json
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Body, Depends, FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse

from . import audit, engine, extract, rulepack
from .db import clean, get_db, new_id, now
from .security import (can, check_password, check_upload, current_user, hash_password, hmac_ok, make_token,
                       rate_limit, require)

app = FastAPI(title="PRAMAAN", docs_url="/api/docs", openapi_url="/api/openapi.json")
DEMO = os.environ.get("DEMO", "true") == "true"


@app.middleware("http")
async def headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    return resp


@app.on_event("startup")
def autoseed():
    if not os.environ.get("MONGODB_URI") and not os.environ.get("VERCEL") and not get_db().users.find_one():
        from .seed import reset
        reset(password=os.environ.get("DEMO_PASSWORD", "demo-local"))


def access_log(user, what, obj):
    get_db().access_log.insert_one({"ts": now().isoformat(), "user": user["sub"], "role": user["role"], "what": what, "object": obj})


# ---------------- health + auth
@app.get("/api/health")
def health():
    try:
        get_db().command("ping")
        dbs = "ok"
    except Exception as e:
        dbs = f"error: {str(e)[:80]}"
    return {"db": dbs, "mode": engine.MODE, "providers": extract.PROVIDERS,
            "object_detector": "vision model" if os.environ.get("GROQ_KEY") else "classical counter (LITE)",
            "store": "atlas" if os.environ.get("MONGODB_URI") else "in-memory"}


@app.get("/api/demo-users")
def demo_users():
    if not DEMO:
        return []
    return [{"username": u["username"], "role": u["role"], "name": u["name"]} for u in get_db().users.find({}, {"pw": 0})]


@app.post("/api/auth/login")
def login(response: Response, request: Request, body: dict = Body(...)):
    rate_limit("login:" + (request.client.host if request.client else "x"), 15)
    u = get_db().users.find_one({"username": body.get("username", "")})
    if not u or u.get("locked_until", "") > now().isoformat() or not check_password(u["pw"], body.get("password", "")):
        if u:
            n = u.get("fails", 0) + 1
            upd = {"fails": n}
            if n >= 5:
                upd = {"fails": 0, "locked_until": (now() + timedelta(minutes=10)).isoformat()}
            get_db().users.update_one({"username": u["username"]}, {"$set": upd})
        audit.record(body.get("username", "?"), "auth.login_failed", "user")
        raise HTTPException(401, "Wrong username or password")
    get_db().users.update_one({"username": u["username"]}, {"$set": {"fails": 0}})
    tok = make_token(u)
    response.set_cookie("pramaan_session", tok, httponly=True, samesite="lax", secure=os.environ.get("VERCEL") == "1", max_age=8 * 3600)
    audit.record(u["username"], "auth.login", "user")
    return {"username": u["username"], "role": u["role"], "name": u["name"], "region": u["region"]}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("pramaan_session")
    return {"ok": True}


@app.get("/api/me")
def me(user=Depends(current_user)):
    from .security import MATRIX
    return {**user, "caps": [c for c in MATRIX if can(user, c)]}


# ---------------- host API (server-to-server)
def host_from_key(key):
    from .security import check_password as chk
    for h in get_db().hosts.find():
        if key and key.startswith(h["key_prefix"]) and chk(h["api_key_hash"], key):
            return h
    raise HTTPException(401, "Invalid API key")


def create_app_for_host(h, body):
    from .seed import create_application
    rec = get_db().records.find_one({"aicte_id": body.get("institution_id")})
    if not rec:
        raise HTTPException(404, "Unknown institution id in records")
    form = body.get("form") or {}
    form.setdefault("institution_name", rec["name"])
    form.setdefault("society_name", rec["society_name"])
    form.setdefault("facilities", [])
    app_id = create_application(h["id"], body.get("external_ref") or new_id("REF"), rec["aicte_id"], h["category"], form, h["pack_key"], rec["region"])
    return app_id


def new_session(app_id):
    tok = secrets.token_urlsafe(24)
    get_db().upload_sessions.insert_one({"token": tok, "app_id": app_id, "expires": (now() + timedelta(hours=6)).isoformat()})
    return tok


@app.post("/api/v1/applications", status_code=201)
def api_create(body: dict = Body(...), x_api_key: str = Header(None)):
    h = host_from_key(x_api_key)
    return {"application_id": create_app_for_host(h, body)}


@app.post("/api/v1/applications/{app_id}/upload-sessions", status_code=201)
def api_session(app_id: str, x_api_key: str = Header(None)):
    h = host_from_key(x_api_key)
    a = get_db().applications.find_one({"id": app_id, "host_id": h["id"]})
    if not a:
        raise HTTPException(404)
    return {"token": new_session(app_id), "widget": "/widget/v1/pramaan.js"}


@app.get("/api/v1/applications/{app_id}/status")
def api_status(app_id: str, x_api_key: str = Header(None)):
    h = host_from_key(x_api_key)
    a = get_db().applications.find_one({"id": app_id, "host_id": h["id"]})
    if not a:
        raise HTTPException(404)
    return {"status": a["status"], "report_version": a.get("report_version"), "deficiencies": deficiencies(a)}


# ---------------- widget (upload-session token)
def session_app(token):
    s = get_db().upload_sessions.find_one({"token": token or ""})
    if not s or s["expires"] < now().isoformat():
        raise HTTPException(401, "Upload session expired")
    return get_db().applications.find_one({"id": s["app_id"]})


@app.get("/api/widget/session")
def w_session(x_session: str = Header(None)):
    a = session_app(x_session)
    h = get_db().hosts.find_one({"id": a["host_id"]})
    pack, _ = engine.active_pack(a["pack_key"])
    docs = list(get_db().documents.find({"app_id": a["id"], "superseded": {"$ne": True}}, {"result": 0, "_id": 0}))
    return {"application_id": a["id"], "status": a["status"], "host": h["name"],
            "slots": [{"slot": s, "label": l, "canonical": c, "required": c in pack["categories"][a["category"]]["required_slots"],
                       "multiple": c == "INFRA_PHOTOS", "accept": ".jpg,.jpeg,.png" if c == "INFRA_PHOTOS" else ".pdf,.jpg,.jpeg,.png",
                       "files": [d["filename"] for d in docs if d["slot"] == c]} for s, l, c in h["slots"]],
            "facilities": a["form"].get("facilities", [])}


def quick_check(doc_id, pack, slot):
    from .engine import get_blob
    d = get_db().documents.find_one({"id": doc_id})
    data = get_blob(d["blob_id"])
    tax = pack["taxonomy"]
    if d["filename"].lower().endswith(".pdf"):
        pdf = extract.open_pdf(data)
        texts = extract.pdf_text(pdf)
        full = "\n".join(texts)
        if len(full.strip()) < 40:
            return {"level": "warn", "text": "Scanned document. It will be read by an officer."}
        t, conf = extract.classify(full, tax)
        if t and t != slot:
            return {"level": "error", "text": f"This looks like a {tax[t]['label']}, not a {tax[slot]['label']}"}
        f = extract.extract_fields(pdf, texts, tax[slot])
        vt = (f.get("valid_to") or {}).get("value")
        if vt and vt < now().date().isoformat():
            return {"level": "warn", "text": f"Looks like a {tax[slot]['label']} - valid until {vt} - expired"}
        return {"level": "ok", "text": f"Looks like a {tax[slot]['label']}" + (f" - valid until {vt}" if vt else "")}
    import cv2
    import numpy as np
    img = extract.load_image(data).convert("L")
    if img.width < 640:
        return {"level": "warn", "text": "Image resolution is low - please upload a clearer photo"}
    var = cv2.Laplacian(np.array(img), cv2.CV_64F).var()
    if var < 20:
        return {"level": "warn", "text": "Image is blurry - please upload a clearer photo"}
    return {"level": "ok", "text": "Photo received"}


@app.post("/api/widget/upload")
async def w_upload(slot: str = Form(...), file: UploadFile = File(...), facility: str = Form(None), x_session: str = Header(None)):
    from .seed import add_document
    a = session_app(x_session)
    h = get_db().hosts.find_one({"id": a["host_id"]})
    canon = next((c for s, l, c in h["slots"] if s == slot), None)
    if not canon:
        raise HTTPException(400, "Unknown slot")
    data = await file.read()
    err = check_upload(file.filename, data)
    if err:
        audit.record("institution", "upload.rejected", a["id"], {"reason": err, "file": file.filename})
        return JSONResponse({"level": "error", "text": err}, status_code=422)
    pack, _ = engine.active_pack(a["pack_key"])
    if canon == "INFRA_PHOTOS" and not facility:
        import re
        hit = re.search(r"([A-Z]+_[A-Z]+_\d+)__", file.filename)
        facility = hit.group(1) if hit else None
    doc_id = add_document(a["id"], canon, file.filename, data, facility)
    resub = a["status"] not in ("DRAFT",)
    if resub:
        engine.run(a["id"], changed=[doc_id], actor="institution")
    qc = quick_check(doc_id, pack, canon)
    return {"doc_id": doc_id, **qc, "rerun": resub}


@app.post("/api/widget/submit", status_code=202)
def w_submit(x_session: str = Header(None)):
    a = session_app(x_session)
    get_db().applications.update_one({"id": a["id"]}, {"$set": {"status": "SUBMITTED", "submitted_on": now().date().isoformat(),
                                                               "submitted_at": now().isoformat()}})
    audit.record("institution", "application.submit", a["id"])
    rep = engine.run(a["id"], actor="institution")
    return {"accepted": True, "report_version": rep["version"]}


def deficiencies(a):
    fl = list(get_db().flags.find({"app_id": a["id"], "current": True, "status": {"$ne": "DISMISSED"}}))
    vis = [{"id": f["id"], "title": f["title"], "action": f.get("recommended_action") or "Please review this item",
            "slot": next((e.get("slot") for e in f["evidence"] if e.get("slot")), None), "severity": f["severity"]}
           for f in fl if f["institution_visible"]]
    hidden = sum(1 for f in fl if not f["institution_visible"] and f["severity"] in ("HIGH", "MEDIUM"))
    return {"items": vis, "pending_authority_verification": hidden}


@app.get("/api/widget/deficiencies")
def w_def(x_session: str = Header(None)):
    a = session_app(x_session)
    return {"status": a["status"], "report_version": a.get("report_version"), **deficiencies(a)}


# ---------------- mock host back-ends (they hold their own API key, call the engine server-side)
def mock_host(h):
    hid = {"a": "HOST-A", "b": "HOST-B"}.get(h)
    if not hid:
        raise HTTPException(404)
    cfg = get_db().mock_host_config.find_one({"host_id": hid})
    return host_from_key(cfg["api_key"])


@app.post("/api/mock-hosts/{h}/start")
def mh_start(h: str, body: dict = Body(...)):
    host = mock_host(h)
    app_id = create_app_for_host(host, body)
    return {"application_id": app_id, "token": new_session(app_id)}


@app.get("/api/mock-hosts/{h}/institutions")
def mh_inst(h: str):
    return [{"id": r["aicte_id"], "name": r["name"]} for r in get_db().records.find({}, {"aicte_id": 1, "name": 1}).sort("aicte_id")]


@app.post("/api/mock-hosts/{h}/webhook")
async def mh_webhook(h: str, request: Request):
    host = mock_host(h)
    body = await request.body()
    ok = hmac_ok(host["webhook_secret"], body, request.headers.get("X-Pramaan-Signature"))
    if not ok:
        raise HTTPException(401, "Bad signature")
    get_db().mock_host_inbox.insert_one({"host": h, "ts": now().isoformat(), "payload": json.loads(body), "signature_ok": ok})
    return {"ok": True}


@app.get("/api/mock-hosts/{h}/inbox")
def mh_inbox(h: str, app_id: str):
    return [clean(x) for x in get_db().mock_host_inbox.find({"host": h, "payload.application_id": app_id}).sort("ts", -1).limit(10)]


# ---------------- officer console
def scoped(user, q=None):
    q = dict(q or {})
    q["status"] = {"$ne": "DRAFT"}
    if user["role"] == "SCRUTINY_OFFICER" and user.get("region", "ALL") != "ALL":
        q["region"] = user["region"]
    return q


def sla(a, pack_days=10):
    if not a.get("submitted_at"):
        return None
    age = (now() - datetime.fromisoformat(a["submitted_at"])).days
    return {"age_days": age, "breached": age > pack_days and a.get("counts", {}).get("HIGH", 0) > 0}


@app.get("/api/queue")
def queue(user=Depends(require("view_queue"))):
    apps = list(get_db().applications.find(scoped(user)).sort("risk", -1))
    hosts = {h["id"]: h["name"] for h in get_db().hosts.find()}
    return [{"id": a["id"], "institution": a["form"]["institution_name"], "institution_id": a["institution_id"], "category": a["category"],
             "host": hosts.get(a["host_id"]), "region": a["region"], "submitted": a.get("submitted_on"), "risk": a.get("risk", 0),
             "counts": a.get("counts", {}), "verification": a.get("verification", {}), "status": a["status"],
             "external_ref": a.get("external_ref"), "sla": sla(a), "decided": bool(a.get("decision"))} for a in apps]


def get_app(user, app_id):
    a = get_db().applications.find_one(scoped(user, {"id": app_id}))
    if not a:
        raise HTTPException(404, "Not found or outside your region")
    return a


@app.get("/api/applications/{app_id}")
def app_detail(app_id: str, user=Depends(require("view_queue"))):
    db = get_db()
    a = get_app(user, app_id)
    access_log(user, "application.view", app_id)
    rep = clean(db.reports.find_one({"app_id": app_id}, sort=[("version", -1)]))
    flags = [clean(f) for f in db.flags.find({"app_id": app_id, "current": True})]
    for f in flags:
        for e in f["evidence"]:
            if e.get("type") == "duplicate" and e.get("other_document_id"):
                o = db.documents.find_one({"id": e["other_document_id"]}, {"result.pages": 1, "app_id": 1, "filename": 1})
                if o:
                    oa = db.applications.find_one({"id": o["app_id"]}, {"form.institution_name": 1})
                    e["other_pages"] = (o.get("result") or {}).get("pages", [])
                    e["other_label"] = f"{o['filename']} - {oa['form']['institution_name'] if oa else o['app_id']}"
    docs = []
    for d in db.documents.find({"app_id": app_id}).sort("uploaded_at", 1):
        r = d.get("result") or {}
        docs.append({"id": d["id"], "slot": d["slot"], "filename": d["filename"], "facility": d.get("facility"), "superseded": d.get("superseded"),
                     "uploaded_at": d["uploaded_at"], "pages": r.get("pages", []), "type": r.get("type"), "type_conf": r.get("type_conf"),
                     "fields": r.get("fields", {}), "qr": r.get("qr"), "exif": r.get("exif"), "scanned": r.get("scanned"),
                     "images": r.get("images", []), "stages": r.get("stages", [])})
    vers = [clean(v) for v in db.verifications.find({"app_id": app_id}).sort("ts", -1)]
    pack, ver = engine.active_pack(a["pack_key"])
    rec = clean(db.records.find_one({"aicte_id": a["institution_id"]}))
    rec.pop("contact_phone_enc", None)
    reports = [{"version": r["version"], "created": r["created"], "changed": r.get("changed"), "elapsed_ms": r.get("elapsed_ms")}
               for r in db.reports.find({"app_id": app_id}).sort("version", 1)]
    host = db.hosts.find_one({"id": a["host_id"]})
    return {"application": clean(a), "report": rep, "reports": reports, "flags": flags, "documents": docs, "verifications": vers,
            "records": rec, "host": host["name"], "pack": f"{pack['key']}@{ver}",
            "taxonomy": {k: v["label"] for k, v in pack["taxonomy"].items()},
            "required_slots": pack["categories"][a["category"]]["required_slots"],
            "institution_view": deficiencies(a)}


@app.get("/api/blobs/{bid}")
def blob(bid: str, user=Depends(require("view_queue"))):
    b = get_db().blobs.find_one({"_id": bid, "kind": {"$in": ["png", "jpeg"]}})
    if b is None:
        raise HTTPException(404)
    access_log(user, "blob.view", bid)
    return Response(bytes(b["data"]), media_type=f"image/{b['kind']}", headers={"Cache-Control": "private, max-age=3600"})


@app.post("/api/flags/{flag_id}/dispose")
def dispose(flag_id: str, body: dict = Body(...), user=Depends(require("dispose_flags"))):
    action = body.get("action")
    reason = (body.get("reason") or "").strip()
    if action not in ("CONFIRM", "DISMISS", "ESCALATE") or len(reason) < 3:
        raise HTTPException(400, "Action and a reason are required")
    db = get_db()
    f = db.flags.find_one({"id": flag_id, "current": True})
    if not f:
        raise HTTPException(404)
    get_app(user, f["app_id"])
    status = {"CONFIRM": "CONFIRMED", "DISMISS": "DISMISSED", "ESCALATE": "ESCALATED"}[action]
    disp = {"by": user["sub"], "reason": reason, "ts": now().isoformat(), "action": action}
    db.flags.update_one({"id": flag_id, "current": True}, {"$set": {"status": status, "disposition": disp}})
    _recount(f["app_id"])
    audit.record(user["sub"], f"flag.{action.lower()}", flag_id, {"app_id": f["app_id"], "reason": reason})
    return {"ok": True, "status": status}


def _recount(app_id):
    db = get_db()
    a = db.applications.find_one({"id": app_id})
    pack, _ = engine.active_pack(a["pack_key"])
    fl = list(db.flags.find({"app_id": app_id, "current": True, "status": {"$in": ["OPEN", "ESCALATED", "CONFIRMED"]}}))
    w = pack["risk_weights"]
    db.applications.update_one({"id": app_id}, {"$set": {"risk": min(100, sum(w[f["severity"]] for f in fl)),
                                                         "counts": {s: sum(1 for f in fl if f["severity"] == s) for s in ("HIGH", "MEDIUM", "LOW")}}})


@app.post("/api/applications/{app_id}/observations")
def observe(app_id: str, body: dict = Body(...), user=Depends(require("dispose_flags"))):
    get_app(user, app_id)
    o = {"by": user["sub"], "text": body.get("text", "")[:2000], "ts": now().isoformat()}
    get_db().applications.update_one({"id": app_id}, {"$push": {"observations": o}})
    audit.record(user["sub"], "observation.add", app_id)
    return o


@app.post("/api/applications/{app_id}/decision")
def decision(app_id: str, body: dict = Body(...), user=Depends(require("decision_note"))):
    get_app(user, app_id)
    open_high = [f["id"] for f in get_db().flags.find({"app_id": app_id, "current": True, "severity": "HIGH", "status": "OPEN"})]
    if open_high:
        return JSONResponse({"detail": "HIGH-severity flags must be disposed first", "open_high": open_high}, status_code=409)
    note = {"by": user["sub"], "text": body.get("text", "")[:4000], "ts": now().isoformat()}
    get_db().applications.update_one({"id": app_id}, {"$set": {"decision": note, "status": "DECISION_RECORDED"}})
    audit.record(user["sub"], "decision.record", app_id)
    return note


@app.post("/api/applications/{app_id}/rerun")
def rerun(app_id: str, user=Depends(require("dispose_flags"))):
    get_app(user, app_id)
    ids = [d["id"] for d in get_db().documents.find({"app_id": app_id, "superseded": {"$ne": True}})]
    rep = engine.run(app_id, changed=ids, actor=user["sub"])
    return {"version": rep["version"]}


@app.get("/api/dashboard")
def dashboard(user=Depends(require("view_queue"))):
    db = get_db()
    apps = list(db.applications.find(scoped(user)))
    ids = [a["id"] for a in apps]
    flags = list(db.flags.find({"app_id": {"$in": ids}, "current": True}))
    vers = list(db.verifications.find({"app_id": {"$in": ids}}))

    def tally(xs):
        out = {}
        for x in xs:
            out[x] = out.get(x, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))
    times = [a.get("elapsed_ms", 0) for a in apps if a.get("elapsed_ms")]
    return {"kpi": {"in_queue": len(apps), "ready": sum(1 for a in apps if a["status"] == "READY_FOR_REVIEW"),
                    "sla_breaches": sum(1 for a in apps if (sla(a) or {}).get("breached")),
                    "pending_verifications": sum(1 for v in vers if v["status"] in ("SOURCE_UNAVAILABLE", "MANUAL_REVIEW", "PENDING")),
                    "avg_processing_ms": round(sum(times) / len(times)) if times else 0,
                    "flags_per_app": round(len(flags) / len(apps), 1) if apps else 0},
            "by_category": tally(f["category"] for f in flags), "top_codes": dict(list(tally(f["code"] for f in flags).items())[:8]),
            "verification": tally(f"{v['method']}:{v['status']}" for v in vers), "by_region": tally(a["region"] for a in apps),
            "processing": [{"id": a["id"], "ms": a.get("elapsed_ms")} for a in apps]}


@app.get("/api/alerts")
def alerts(user=Depends(require("view_queue"))):
    ids = [a["id"] for a in get_db().applications.find(scoped(user), {"id": 1})]
    return [clean(x) for x in get_db().alerts.find({"app_id": {"$in": ids}}).sort("created", -1)]


@app.post("/api/alerts/{aid}/ack")
def ack(aid: str, user=Depends(require("dispose_flags"))):
    get_db().alerts.update_one({"id": aid}, {"$set": {"status": "ACKNOWLEDGED", "ack_by": user["sub"]}})
    audit.record(user["sub"], "alert.ack", aid)
    return {"ok": True}


# ---------------- rule packs
@app.get("/api/rulepacks")
def packs(user=Depends(current_user)):
    return [clean(p) for p in get_db().rule_packs.find().sort([("key", 1), ("created", -1)])]


@app.get("/api/rulepacks/sample-apps")
def pack_samples(user=Depends(current_user)):
    if not can(user, "edit_rules"):
        return []
    return [{"id": a["id"], "external_ref": a.get("external_ref"), "institution": a["form"]["institution_name"]}
            for a in get_db().applications.find({"status": {"$ne": "DRAFT"}})]


@app.post("/api/rulepacks/validate")
def pack_validate(body: dict = Body(...), user=Depends(require("edit_rules"))):
    p, errs = rulepack.parse(body.get("yaml", ""))
    return {"ok": not errs, "errors": errs, "version": p and p["version"]}


@app.post("/api/rulepacks/dryrun")
def pack_dryrun(body: dict = Body(...), user=Depends(require("edit_rules"))):
    p, errs = rulepack.parse(body.get("yaml", ""))
    if errs:
        return {"ok": False, "errors": errs}
    app_id = body["app_id"]
    cur = {f["fingerprint"]: f for f in get_db().flags.find({"app_id": app_id, "current": True})}
    new = {f["fingerprint"]: f for f in engine.run(app_id, pack_override=(p, p["version"] + "-draft"), dry=True)}
    added = [{"code": f["code"], "title": f["title"], "severity": f["severity"]} for k, f in new.items() if k not in cur]
    removed = [{"code": f["code"], "title": f["title"], "severity": f["severity"]} for k, f in cur.items() if k not in new]
    changed = [{"code": f["code"], "title": f["title"], "from": cur[k]["severity"], "to": f["severity"]}
               for k, f in new.items() if k in cur and cur[k]["severity"] != f["severity"]]
    return {"ok": True, "added": added, "removed": removed, "severity_changed": changed}


@app.post("/api/rulepacks/activate")
def pack_activate(body: dict = Body(...), user=Depends(require("edit_rules"))):
    p, errs = rulepack.parse(body.get("yaml", ""))
    if errs:
        raise HTTPException(400, "; ".join(errs))
    db = get_db()
    if db.rule_packs.find_one({"key": p["key"], "version": p["version"]}):
        raise HTTPException(409, "This version already exists - bump the version")
    db.rule_packs.update_many({"key": p["key"], "status": "ACTIVE"}, {"$set": {"status": "ARCHIVED"}})
    db.rule_packs.insert_one({"key": p["key"], "version": p["version"], "status": "ACTIVE", "yaml": body["yaml"],
                              "created": now().isoformat(), "by": user["sub"]})
    audit.record(user["sub"], "rulepack.activate", f"{p['key']}@{p['version']}")
    return {"ok": True}


# ---------------- hosts
@app.get("/api/hosts")
def hosts(user=Depends(require("manage_hosts"))):
    db = get_db()
    return [{**{k: v for k, v in clean(h).items() if k not in ("api_key_hash", "webhook_secret")},
             "deliveries": [clean(d) for d in db.webhook_deliveries.find({"host_id": h["id"]}).sort("ts", -1).limit(15)]}
            for h in db.hosts.find()]


@app.post("/api/hosts/{hid}/rotate")
def rotate(hid: str, user=Depends(require("manage_hosts"))):
    key = "pk_" + secrets.token_urlsafe(24)
    db = get_db()
    db.hosts.update_one({"id": hid}, {"$set": {"api_key_hash": hash_password(key), "key_prefix": key[:8]}})
    db.mock_host_config.update_one({"host_id": hid}, {"$set": {"api_key": key}})
    audit.record(user["sub"], "host.rotate_key", hid)
    return {"api_key": key, "note": "Shown once. The mock host back-end was updated with it."}


@app.post("/api/hosts/{hid}/test-webhook")
def test_webhook(hid: str, user=Depends(require("manage_hosts"))):
    a = get_db().applications.find_one({"host_id": hid})
    if a:
        engine.send_webhook(a, "test.ping", a.get("report_version", 0))
    return {"ok": bool(a)}


@app.put("/api/hosts/{hid}/slots")
def set_slots(hid: str, body: dict = Body(...), user=Depends(require("manage_hosts"))):
    slots = body.get("slots", [])
    if not all(len(s) == 3 for s in slots):
        raise HTTPException(400, "Each slot is [host_slot, label, canonical]")
    get_db().hosts.update_one({"id": hid}, {"$set": {"slots": slots}})
    audit.record(user["sub"], "host.slots", hid)
    return {"ok": True}


# ---------------- audit
@app.get("/api/audit")
def audit_list(user=Depends(require("audit")), actor: str = None, action: str = None):
    q = {}
    if actor:
        q["actor"] = actor
    if action:
        q["action"] = {"$regex": "^" + action.replace(".", r"\.")}
    return [clean(e) for e in get_db().audit_log.find(q).sort("seq", -1).limit(300)]


@app.get("/api/audit/verify")
def audit_verify(user=Depends(require("audit"))):
    r = audit.verify()
    audit.record(user["sub"], "audit.verify", "chain", r)
    return r


@app.get("/api/audit/export")
def audit_export(user=Depends(require("audit"))):
    b = io.StringIO()
    w = csv.writer(b)
    w.writerow(["seq", "ts", "actor", "action", "object", "hash", "prev_hash"])
    for e in get_db().audit_log.find().sort("seq", 1):
        w.writerow([e["seq"], e["ts"], e["actor"], e["action"], e["object"], e["hash"], e["prev_hash"]])
    return Response(b.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=audit.csv"})


# ---------------- evaluation
@app.get("/api/eval/runs")
def eval_runs(user=Depends(current_user)):
    return [clean(r) for r in get_db().eval_runs.find().sort("created", -1).limit(10)]


@app.post("/api/eval/run")
def eval_run(user=Depends(require("run_eval"))):
    from .evaluate import run_eval
    r = run_eval()
    audit.record(user["sub"], "eval.run", r["id"])
    return r


# ---------------- admin (token-gated, for demo resets)
def seed_ok(tok):
    want = os.environ.get("SEED_TOKEN")
    if not want or not secrets.compare_digest(want, tok or ""):
        raise HTTPException(403, "Seed token required")


@app.post("/api/admin/seed")
def admin_seed(x_seed_token: str = Header(None)):
    seed_ok(x_seed_token)
    from .seed import reset
    r = reset(password=os.environ.get("DEMO_PASSWORD"))
    r.pop("password", None)
    return r


@app.post("/api/admin/tamper-demo")
def tamper(x_seed_token: str = Header(None)):
    """Demo only: edits one audit row in place to show the chain check catches it."""
    seed_ok(x_seed_token)
    e = get_db().audit_log.find_one({"seq": 3})
    get_db().audit_log.update_one({"seq": 3}, {"$set": {"actor": e["actor"] + "-edited"}})
    return {"tampered_seq": 3}

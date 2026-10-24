"""Scheduled jobs (Vercel Cron in the hosted build, `python tasks.py cron` locally)."""
from datetime import datetime, timedelta

from . import audit, engine
from .db import get_db, new_id, now


def sla_alerts():
    """SLA_BREACH alerts for applications older than the pack's sla_days with HIGH flags still open."""
    db = get_db()
    raised = 0
    for a in db.applications.find({"submitted_at": {"$exists": True}, "decision": {"$exists": False}}):
        pack, _ = engine.active_pack(a["pack_key"])
        rule = next((r for r in pack.get("alerts", []) if r["type"] == "SLA_BREACH"), None)
        if not rule:
            continue
        age = (now() - datetime.fromisoformat(a["submitted_at"])).days
        open_high = db.flags.count_documents({"app_id": a["id"], "current": True, "severity": "HIGH", "status": "OPEN"})
        if age > rule.get("sla_days", 10) and open_high and not db.alerts.find_one({"app_id": a["id"], "type": "SLA_BREACH", "status": "OPEN"}):
            db.alerts.insert_one({"id": new_id("ALR"), "app_id": a["id"], "type": "SLA_BREACH", "severity": "HIGH", "status": "OPEN",
                                  "notify": rule["notify"], "channel": ["in-app", "email", "webhook"], "flag_ids": [], "created": now().isoformat(),
                                  "condition_at": (datetime.fromisoformat(a["submitted_at"]) + timedelta(days=rule.get("sla_days", 10))).isoformat(),
                                  "due": now().isoformat(), "institution": a["form"].get("institution_name")})
            engine.notify_alert(a, "SLA_BREACH", "HIGH", [f"{open_high} HIGH findings open after {age} days"])
            raised += 1
    return raised


def retention_purge():
    """Deletes raw files and derived images past the per-type retention_days; keeps hashes, flags and audit entries."""
    db = get_db()
    purged = 0
    for a in db.applications.find({"legal_hold": {"$ne": True}}):
        pack, _ = engine.active_pack(a["pack_key"])
        for d in db.documents.find({"app_id": a["id"], "purged": {"$ne": True}}):
            days = (pack["taxonomy"].get(d["slot"]) or {}).get("retention_days")
            if days and datetime.fromisoformat(d["uploaded_at"]) < now() - timedelta(days=days):
                ids = [d["blob_id"]] + (d.get("result") or {}).get("pages", []) + [i.get("heatmap") for i in (d.get("result") or {}).get("images", []) if i.get("heatmap")]
                db.blobs.delete_many({"_id": {"$in": ids}})
                db.documents.update_one({"id": d["id"]}, {"$set": {"purged": True, "purged_at": now().isoformat()}})
                purged += 1
    db.retention_jobs.insert_one({"id": new_id("RET"), "ts": now().isoformat(), "purged": purged})
    audit.record("system", "retention.purge", "documents", {"purged": purged})
    return purged


def anchor_audit():
    """Writes the current audit head hash to a separate collection as an external anchor."""
    db = get_db()
    head = db.audit_log.find_one(sort=[("seq", -1)])
    if not head:
        return None
    db.audit_anchors.insert_one({"ts": now().isoformat(), "seq": head["seq"], "hash": head["hash"]})
    return head["seq"]

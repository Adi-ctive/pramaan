"""Hash-chained, append-only audit log (05_SECURITY.md §6)."""
import hashlib
import json

from pymongo import ReturnDocument

from .db import get_db, now


def _digest(entry, prev):
    body = json.dumps({k: entry[k] for k in ("seq", "ts", "actor", "action", "object", "data")},
                      sort_keys=True, default=str)
    return hashlib.sha256((prev + body).encode()).hexdigest()


def record(actor, action, obj, data=None):
    db = get_db()
    seq = db.counters.find_one_and_update({"_id": "audit"}, {"$inc": {"n": 1}}, upsert=True,
                                          return_document=ReturnDocument.AFTER)["n"]
    prev = db.audit_log.find_one({"seq": seq - 1})
    entry = {"seq": seq, "ts": now().isoformat(), "actor": actor, "action": action, "object": obj, "data": data or {}}
    entry["prev_hash"] = prev["hash"] if prev else "GENESIS"
    entry["hash"] = _digest(entry, entry["prev_hash"])
    db.audit_log.insert_one(entry)
    return seq


def verify():
    prev_hash, last = "GENESIS", 0
    for e in get_db().audit_log.find({}, sort=[("seq", 1)]):
        if e["seq"] != last + 1 or e["prev_hash"] != prev_hash or _digest(e, prev_hash) != e["hash"]:
            return {"ok": False, "broken_at": e["seq"], "last_verified": last}
        prev_hash, last = e["hash"], e["seq"]
    return {"ok": True, "last_verified": last}

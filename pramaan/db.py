"""MongoDB access. Uses MONGODB_URI (Atlas) or an in-memory mongomock store for tests and local runs."""
import os
import secrets
from datetime import datetime, timezone

_db = None


def get_db():
    global _db
    if _db is None:
        uri = os.environ.get("MONGODB_URI")
        name = os.environ.get("MONGODB_DB", "pramaan")
        if uri:
            import pymongo
            _db = pymongo.MongoClient(uri, serverSelectionTimeoutMS=8000)[name]
        else:
            import mongomock
            _db = mongomock.MongoClient()[name]
    return _db


def set_db(db):
    global _db
    _db = db


def now():
    return datetime.now(timezone.utc)


def new_id(prefix):
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def clean(doc):
    """Strip Mongo's _id so a document can be returned as JSON."""
    if doc is None:
        return None
    doc = dict(doc)
    doc.pop("_id", None)
    return doc

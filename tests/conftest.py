import os
import sys

import mongomock
import pytest

sys.path.insert(0, os.path.dirname(__file__))
os.environ.pop("MONGODB_URI", None)
os.environ["PUBLIC_URL"] = "http://127.0.0.1:9"
os.environ["SEED_TOKEN"] = "t"
os.environ.setdefault("MODE", "LITE")

PW = "test-pass-123"


@pytest.fixture(scope="session")
def seeded():
    from pramaan import db
    from pramaan.seed import reset
    db.set_db(mongomock.MongoClient()["t"])
    return reset(password=PW)

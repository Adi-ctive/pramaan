"""Local AI worker: runs on a machine with a GPU and Ollama, next to the hosted site's database.
It posts a heartbeat, picks up applications an officer sent to "local AI", re-checks them in FULL mode with the agents,
and writes the new report back. No port is opened on the machine; it only talks outward to MongoDB and to local Ollama.
Usage: MONGODB_URI=... python -m pramaan.worker   (or: python tasks.py worker, reading .env.worker)"""
import os
import socket
import time

os.environ["MODE"] = "FULL"
os.environ.setdefault("AGENT_MODE", "on")
os.environ.setdefault("PUBLIC_URL", "https://pramaan-sih26.vercel.app")

from . import engine  # noqa: E402
from .agents import llm  # noqa: E402
from .db import get_db, now  # noqa: E402


def beat(db, busy=None):
    db.workers.update_one({"_id": "local"}, {"$set": {"ts": now().isoformat(), "host": socket.gethostname(), "mode": "FULL",
                                                      "model": llm.MODEL, "llm_ok": llm.reachable(), "busy": busy}}, upsert=True)


def main(once=False):
    if not os.environ.get("MONGODB_URI"):
        raise SystemExit("Set MONGODB_URI (the hosted site's database) in .env.worker")
    db = get_db()
    print(f"local AI worker up: model {llm.MODEL}, Ollama reachable: {llm.reachable()}")
    while True:
        beat(db)
        job = db.applications.find_one_and_update({"agent_request.status": "pending"}, {"$set": {"agent_request.status": "running",
                                                                                                "agent_request.started": now().isoformat()}})
        if job:
            beat(db, busy=job["id"])
            print("re-checking", job["id"], job["form"].get("institution_name"))
            try:
                ids = [d["id"] for d in db.documents.find({"app_id": job["id"], "superseded": {"$ne": True}})]
                rep = engine.run(job["id"], changed=ids, actor="local-ai-worker", agents_on=(job["agent_request"].get("agents", True) and llm.reachable()))
                db.applications.update_one({"id": job["id"]}, {"$set": {"agent_request.status": "done", "agent_request.finished": now().isoformat(),
                                                                       "agent_request.report_version": rep["version"], "agent_request.agents": rep["agents"]}})
                print("done", job["id"], "report v", rep["version"], "agents", rep["agents"], rep.get("agent_usage"))
            except Exception as e:
                db.applications.update_one({"id": job["id"]}, {"$set": {"agent_request.status": "failed", "agent_request.error": str(e)[:200]}})
                print("failed", job["id"], e)
        if once:
            return
        time.sleep(5)


if __name__ == "__main__":
    import sys
    main(once="--once" in sys.argv)

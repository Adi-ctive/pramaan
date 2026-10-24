import pyotp
from fastapi.testclient import TestClient

from conftest import PW
from pramaan import db, engine, extract, infra, synth
from pramaan.main import app


def test_tables_and_fee_total():
    ok = synth.table_pdf("Fee Receipt", "Gateway (mock)", [("Amount (INR)", "1,50,000")], ["Item", "Amount (INR)"],
                         [["Processing fee", "1,20,000"], ["Inspection fee", "30,000"]], ["Total", "1,50,000"])
    rows = extract.extract_tables(ok)[0]["rows"]
    assert rows[0] == ["Item", "Amount (INR)"] and rows[-1] == ["Total", "1,50,000"]


def test_floor_plan_areas():
    plan = extract.floor_plan(synth.floor_plan_pdf([("COMPUTER_LAB_1", 11, 6), ("CLASSROOM_1", 9, 7)]))
    areas = {r["label"]: r["area_sqm"] for r in plan["rooms"]}
    assert plan["scale"] == "1:100" and areas == {"COMPUTER_LAB_1": 66.0, "CLASSROOM_1": 63.0}
    assert extract.floor_plan(synth.pdf_doc("Not a plan", "x", [("A", "b")])) is None


def test_carry_forward_skips_files_with_a_mismatch(seeded):
    from pramaan import verify
    d = db.get_db()
    acc = d.documents.find_one({"app_id": seeded["apps"]["PROBLEM-A"], "slot": "ACCREDITATION"})  # QR mismatch on this file
    a = d.applications.find_one({"id": seeded["apps"]["PROBLEM-A"]})
    clone = {k: v for k, v in acc.items() if k != "_id"}
    clone.update(id="DOC-CLONE-ACC", app_id="APP-OTHER-ACC")
    d.documents.insert_one(clone)
    assert verify.carry_forward(clone, {**a, "id": "APP-OTHER-ACC"}) is None


def test_video_frames_count():
    frames = extract.video_frames(synth.lab_video(15, seed=3))
    assert 2 <= len(frames) <= 8 and max(infra.classical_count(f) for f in frames) == 15


def test_transliterated_names_and_digits():
    assert engine._skeleton("नर्मदा विद्या ट्रस्ट") == engine._skeleton("Narmada Vidya Trust")
    assert extract.norm_date("0२-१0-२०२६") == "2026-10-02"


def test_seeded_addons(seeded):
    d = db.get_db()
    pa = seeded["apps"]["PROBLEM-A"]
    assert "AREA_SHORTFALL" in {f["code"] for f in d.flags.find({"app_id": pa, "current": True})}
    ga = d.documents.find_one({"app_id": seeded["apps"]["GOLDEN-A"], "slot": "AFFIDAVIT_GENERAL"})
    assert ga["result"]["fields"]["society_name"]["value"] == "Shivalik Education Society"  # read through the Hindi label
    v = d.documents.find_one({"filename": "COMPUTER_LAB_1__walkthrough.mp4"})
    assert v["result"]["frames"] >= 2


def test_totp_screen_endpoints(seeded):
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"username": "ruleadmin", "password": PW}).status_code == 200
    s = c.post("/api/auth/totp/setup").json()
    assert s["qr"].startswith("data:image/png;base64,")
    assert c.post("/api/auth/totp/enable", json={"code": pyotp.TOTP(s["secret"]).now()}).status_code == 200
    assert c.get("/api/me").json()["mfa"] is True
    assert c.post("/api/auth/totp/disable", json={"code": pyotp.TOTP(s["secret"]).now()}).status_code == 200
    assert c.get("/api/me").json()["mfa"] is False

import os

import pytest
from fastapi.testclient import TestClient

from conftest import PW
from pramaan import audit, db, security
from pramaan.main import app


def login(c, user):
    r = c.post("/api/auth/login", json={"username": user, "password": PW})
    assert r.status_code == 200, r.text
    return c


def codes(app_id):
    return {f["code"] for f in db.get_db().flags.find({"app_id": app_id, "current": True})}


def test_golden_has_no_high_or_medium(seeded):
    for k in ("GOLDEN-A", "GOLDEN-B"):
        hi = [f for f in db.get_db().flags.find({"app_id": seeded["apps"][k], "current": True}) if f["severity"] in ("HIGH", "MEDIUM")]
        assert hi == [], hi


def test_problem_a_surfaces_every_expected_flag(seeded):
    want = {"DOC_MISSING", "DOC_EXPIRED", "NAME_MISMATCH", "INTAKE_MISMATCH_RECORDS", "TAMPER_INDICATOR", "DUPLICATE_ACROSS_INSTITUTIONS",
            "QR_MISMATCH", "HTR_LOW_CONFIDENCE", "INFRA_SHORTFALL", "EXIF_LOCATION_MISMATCH", "INJECTION_INDICATOR"}
    assert want <= codes(seeded["apps"]["PROBLEM-A"])


def test_problem_b(seeded):
    assert {"WRONG_DOC_TYPE", "DATE_IMPLAUSIBLE", "VERIFICATION_SOURCE_UNAVAILABLE"} <= codes(seeded["apps"]["PROBLEM-B"])


def test_flags_have_evidence_and_advisory_wording(seeded):
    for f in db.get_db().flags.find({"current": True}):
        assert f["advisory_note"] and f["severity"] in ("HIGH", "MEDIUM", "LOW", "INFO")
        if f["category"] == "ANOMALY":
            assert "forged" not in f["title"].lower() and "fake" not in f["title"].lower()
            assert f["evidence"]


def test_rbac_matrix(seeded):
    c = TestClient(app)
    login(c, "auditor")
    assert c.get("/api/queue").status_code == 200
    assert c.post("/api/flags/x/dispose", json={"action": "DISMISS", "reason": "abc"}).status_code == 403
    assert c.post("/api/rulepacks/validate", json={"yaml": ""}).status_code == 403
    login(c, "integration")
    assert c.get("/api/queue").status_code == 403
    assert c.get("/api/hosts").status_code == 200
    login(c, "inst.narmada")
    assert c.get("/api/queue").status_code == 403
    login(c, "officer.north")
    assert c.get(f"/api/applications/{seeded['apps']['PROBLEM-A']}").status_code == 404  # region scoping


def test_decision_gate_and_dispose(seeded):
    c = login(TestClient(app), "senior")
    aid = seeded["apps"]["PROBLEM-A"]
    assert c.post(f"/api/applications/{aid}/decision", json={"text": "x"}).status_code == 409
    for f in db.get_db().flags.find({"app_id": aid, "current": True, "severity": "HIGH"}):
        assert c.post(f"/api/flags/{f['id']}/dispose", json={"action": "CONFIRM", "reason": "checked"}).status_code == 200
    assert c.post(f"/api/applications/{aid}/decision", json={"text": "Deficiency letter"}).status_code == 200


def test_audit_chain_and_tamper(seeded):
    assert audit.verify()["ok"]
    c = TestClient(app)
    c.post("/api/admin/tamper-demo", headers={"X-Seed-Token": "t"})
    r = audit.verify()
    assert not r["ok"] and r["broken_at"] == 3


def test_widget_flow_eicar_and_rectification(seeded):
    c = TestClient(app)
    s = c.post("/api/mock-hosts/a/start", json={"institution_id": "INST-011", "external_ref": "T-1"}).json()
    h = {"X-Session": s["token"]}
    assert c.get("/api/widget/session", headers=h).json()["slots"][0]["slot"] == "society_certificate"
    eicar = security.EICAR + b"\n"
    r = c.post("/api/widget/upload", headers=h, data={"slot": "fire_noc"}, files={"file": ("x.pdf", b"%PDF" + eicar)})
    assert r.status_code == 422 and "EICAR" in r.json()["text"]
    d = "public/samples/PROBLEM-A"
    if not os.path.isdir(d):
        pytest.skip("samples not generated")
    r = c.post("/api/widget/upload", headers=h, data={"slot": "fire_noc"}, files={"file": ("fire.pdf", open(f"{d}/FIRE_NOC__fire_noc.pdf", "rb").read())})
    assert r.json()["level"] == "warn" and "expired" in r.json()["text"]
    assert c.post("/api/widget/submit", headers=h).status_code == 202
    defs = c.get("/api/widget/deficiencies", headers=h).json()
    assert any("Fire" in i["title"] for i in defs["items"])
    assert all("noise" not in i["title"].lower() for i in defs["items"])
    r = c.post("/api/widget/upload", headers=h, data={"slot": "fire_noc"},
               files={"file": ("renewed.pdf", open(f"{d}/FIRE_NOC__fire_noc_renewed.pdf", "rb").read())})
    assert r.json()["rerun"]
    rep = db.get_db().reports.find_one({"app_id": s["application_id"]}, sort=[("version", -1)])
    ran = [t for t in rep["timeline"] if t["stage"].startswith("doc:") and t["status"] == "ran"]
    assert len(ran) == 1 and ran[0]["stage"] == "doc:FIRE_NOC"
    assert "DOC_EXPIRED" not in codes(s["application_id"])


def test_rulepack_validation():
    from pramaan import rulepack
    p, errs = rulepack.parse(rulepack.load_file("aicte-demo-2026-27.yaml"))
    assert not errs
    _, errs = rulepack.parse("key: x\nversion: 1\ntaxonomy: {}\ncategories: {}\nrules: [{id: a, kind: nope}]\nseverity: {}")
    assert errs

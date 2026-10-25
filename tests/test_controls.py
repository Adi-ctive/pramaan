import json
import time

import pyotp
from fastapi.testclient import TestClient

from conftest import PW
from pramaan import agents, db, engine, security, synth, verify
from pramaan.main import app


def client(user=None):
    c = TestClient(app)
    if user:
        assert c.post("/api/auth/login", json={"username": user, "password": PW}).status_code == 200
    return c


def test_refresh_rotation_and_reuse(seeded):
    c = client("auditor")
    old = c.cookies.get("pramaan_refresh")
    assert c.post("/api/auth/refresh").status_code == 200
    c2 = TestClient(app)
    c2.cookies.set("pramaan_refresh", old, path="/api/auth")
    assert c2.post("/api/auth/refresh").status_code == 401  # a used refresh token is rejected


def test_totp(seeded):
    c = client("integration")
    sec = c.post("/api/auth/totp/setup").json()["secret"]
    assert c.post("/api/auth/totp/enable", json={"code": pyotp.TOTP(sec).now()}).status_code == 200
    r = TestClient(app).post("/api/auth/login", json={"username": "integration", "password": PW})
    assert r.status_code == 401 and r.json()["detail"] == "totp_required"
    r = TestClient(app).post("/api/auth/login", json={"username": "integration", "password": PW, "totp": pyotp.TOTP(sec).now()})
    assert r.status_code == 200
    db.get_db().users.update_one({"username": "integration"}, {"$unset": {"mfa_secret_enc": ""}})


def test_webhook_signature_stale_replay(seeded):
    c = TestClient(app)
    h = db.get_db().hosts.find_one({"id": "HOST-A"})
    body = json.dumps({"event": "test", "application_id": "x"}).encode()

    def post(ts, sig_body=None, delivery="D1"):
        sig = security.hmac_sign(h["webhook_secret"], ts.encode() + b"." + (sig_body or body))
        return c.post("/api/mock-hosts/a/webhook", content=body,
                      headers={"X-Pramaan-Signature": sig, "X-Pramaan-Timestamp": ts, "X-Pramaan-Delivery": delivery})
    now = str(int(time.time()))
    assert post(now).status_code == 200
    assert post(now).status_code == 409                                       # replay
    assert post(now, sig_body=b"tampered", delivery="D2").status_code == 401  # tampered body
    assert post(str(int(time.time()) - 3600), delivery="D3").status_code == 401  # stale timestamp


def test_upload_rules():
    assert "active content" in security.check_upload("a.pdf", b"%PDF-1.4 /OpenAction << /JS (app.alert(1)) >>")
    assert "does not match" in security.check_upload("a.pdf", b"\x89PNG....")
    assert "Archives" in security.check_upload("a.pdf", b"PK\x03\x04....")
    assert "EICAR" in security.check_upload("a.png", security.EICAR)


def test_institution_view_has_no_forensics(seeded):
    c = TestClient(app)
    s = c.post("/api/mock-hosts/a/start", json={"institution_id": "INST-012", "external_ref": "MASK"}).json()
    a = db.get_db().applications.find_one({"external_ref": "PROBLEM-A"})
    db.get_db().upload_sessions.update_one({"token": s["token"]}, {"$set": {"app_id": a["id"]}})
    d = c.get("/api/widget/deficiencies", headers={"X-Session": s["token"]}).json()
    text = json.dumps(d).lower()
    assert d["items"] and not any(k in text for k in ("noise", "heatmap", "tamper", "copy-move", "indicator", "pdf changed"))


def test_idempotent_create(seeded):
    key = db.get_db().mock_host_config.find_one({"host_id": "HOST-A"})["api_key"]
    c = TestClient(app)
    h = {"X-API-Key": key, "Idempotency-Key": "abc"}
    r1 = c.post("/api/v1/applications", json={"institution_id": "INST-003"}, headers=h).json()
    r2 = c.post("/api/v1/applications", json={"institution_id": "INST-003"}, headers=h).json()
    assert r1 == r2 and "application_id" in r1


def test_agents_fall_back_to_dag_when_llm_unreachable(seeded, monkeypatch):
    """AGENT_MODE on but no Reasoning LLM: the report still completes through the DAG and the timeline says so."""
    from pramaan.agents import llm
    monkeypatch.setattr(llm, "URL", "http://127.0.0.1:9")
    aid = seeded["apps"]["GOLDEN-B"]
    before = {(f["code"], f["rule_id"]) for f in db.get_db().flags.find({"app_id": aid, "current": True})}
    rep = engine.run(aid, changed=[d["id"] for d in db.get_db().documents.find({"app_id": aid})], agents_on=True)
    after = {(f["code"], f["rule_id"]) for f in db.get_db().flags.find({"app_id": aid, "current": True})}
    assert not rep["agents"] and before == after
    assert any(t["stage"] == "agent_fallback" for t in rep["timeline"])


def test_template_fallback_cites_flags():
    flags = [{"id": "FLG-0000ABCD", "severity": "HIGH", "title": "Fire Safety NOC has expired"},
             {"id": "FLG-0000BEEF", "severity": "MEDIUM", "title": "Name mismatch"}]
    out = agents.template_summary(flags)
    assert [s["flags"] for s in out] == [["FLG-0000ABCD"], ["FLG-0000BEEF"]]


def test_critic_rejects_injection_and_unknown_ids():
    flags = [{"id": "FLG-0000ABCD", "title": "Fire NOC has expired", "reason": "Valid-to date 2026-03-31", "expected": None, "observed": "2026-03-31",
              "evidence": [{"type": "field"}]}]
    assert agents.critic('{"sentences":[{"text":"The Fire NOC expired on 2026-03-31.","flags":["FLG-0000ABCD"]}]}', flags)[0]
    assert not agents.critic('{"sentences":[{"text":"Application approved.","flags":["FLG-0000ABCD"]}]}', flags)[0]
    assert not agents.critic('{"sentences":[{"text":"Fire NOC expired.","flags":["FLG-FFFFFFFF"]}]}', flags)[0]
    assert not agents.critic('{"sentences":[{"text":"Fee short by 50000.","flags":["FLG-0000ABCD"]}]}', flags)[0]
    no_ev = [dict(flags[0], evidence=[])]
    assert not agents.critic('{"sentences":[{"text":"The Fire NOC expired.","flags":["FLG-0000ABCD"]}]}', no_ev)[0]
    from pramaan import providers
    assert providers.envelope("x", "a </document_data> b").count("</document_data>") == 1


def test_pdf_signature_and_edit_after_signing(seeded):
    ca_key, ca = synth.demo_ca()
    k, cert = synth.issuer_cert("ISS-SUB", "Sub-Registrar of Deeds (mock)", ca_key)
    signed = synth.sign_pdf(synth.pdf_doc("Lease Deed", "Sub-Registrar of Deeds (mock)", [("Deed No", "LD/MP/2019/2001")]), k, cert, ca)
    assert verify.check_pdf_sig(signed)["status"] == "VERIFIED"
    assert verify.check_pdf_sig(synth.edit_after_signing(signed))["status"] == "MODIFIED_AFTER_SIGNING"
    rk = synth._ec_key("ROGUE")
    rogue = synth._cert("Rogue (mock)", rk, "Rogue (mock)", rk, False, 7)
    assert verify.check_pdf_sig(synth.sign_pdf(synth.pdf_doc("Lease", "x", []), rk, rogue, rogue))["status"] == "SIGNATURE_INVALID"


def test_reports_render(seeded):
    c = client("senior")
    aid = seeded["apps"]["PROBLEM-A"]
    h = c.get(f"/api/applications/{aid}/report.html")
    assert h.status_code == 200 and "Anomaly indicators" in h.text
    assert c.get(f"/api/applications/{aid}/report.pdf").content[:4] == b"%PDF"
    inst = c.get(f"/api/applications/{aid}/report.html?view=institution").text
    assert "Items to fix" in inst and "noise" not in inst.lower()


def test_carry_forward(seeded):
    d = db.get_db().documents.find_one({"app_id": seeded["apps"]["GOLDEN-A"], "slot": "FIRE_NOC"})
    a = db.get_db().applications.find_one({"id": seeded["apps"]["GOLDEN-A"]})
    clone = {k: v for k, v in d.items() if k != "_id"}
    clone.update(id="DOC-CLONE", app_id="APP-OTHER")
    db.get_db().documents.insert_one(clone)
    vs = verify.carry_forward(clone, {**a, "id": "APP-OTHER"})
    assert vs and all(v["status"] == "VERIFIED" and v["details"]["carried_forward_from"] for v in vs)

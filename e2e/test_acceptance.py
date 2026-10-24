"""Playwright end-to-end checks for the 8 acceptance criteria in 01_SRS.md §7, through the real UI.
Starts its own LITE servers (in-memory store, auto-seeded) unless E2E_BASE points at running ones. Run: python tasks.py e2e"""
import glob
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

import pytest
from playwright.sync_api import expect, sync_playwright

expect.set_options(timeout=20_000)  # cold starts on the hosted build

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get("E2E_BASE", "http://localhost:5180")
API = os.environ.get("E2E_API", "http://127.0.0.1:8010")
SEED_TOKEN = os.environ.get("SEED_TOKEN", "e2e-token")
SAMPLES = os.path.join(ROOT, "public", "samples")
HOST_A = ["SOCIETY_REG", "LAND_LEASE", "FIRE_NOC", "BUILDING_COMPLETION", "AFFIDAVIT_GENERAL", "ACCREDITATION", "FEE_RECEIPT", "FACULTY_LIST",
          "INFRA_PHOTOS", "FLOOR_PLAN"]


def _up(url):
    try:
        urllib.request.urlopen(url, timeout=3)
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def servers():
    procs = []
    if not _up(API + "/api/health"):
        env = dict(os.environ, MODE="LITE", SEED_TOKEN=SEED_TOKEN, PUBLIC_URL=API, DEMO="true", MAX_UPLOAD_MB="25")
        env.pop("MONGODB_URI", None)
        procs.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "pramaan.main:app", "--port", "8010"], cwd=ROOT, env=env,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    if not _up(BASE):
        procs.append(subprocess.Popen(["npm.cmd" if os.name == "nt" else "npm", "run", "dev", "--", "--port", "5180", "--strictPort"], cwd=ROOT,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    for _ in range(240):
        if _up(API + "/api/health") and _up(BASE):
            break
        time.sleep(1)
    yield
    for p in procs:  # close everything this fixture launched
        if os.name == "nt":
            subprocess.call(["taskkill", "/F", "/T", "/PID", str(p.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            p.terminate()


@pytest.fixture(scope="session")
def browser(servers):
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
    pg = ctx.new_page()
    pg.set_default_timeout(60_000)
    yield pg
    ctx.close()


def officer(page, role_button):
    page.goto(BASE + "/")
    page.get_by_text(role_button, exact=True).click()
    expect(page.get_by_text("Viewing as")).to_be_visible()


def api(page, method, path, data=None):
    r = page.request.fetch(BASE + "/api" + path, method=method, data=json.dumps(data) if data is not None else None,
                           headers={"Content-Type": "application/json"} if data is not None else None)
    return r.json()


def open_app(page, ext_ref):
    q = api(page, "GET", "/queue")
    aid = next(a["id"] for a in q if a["external_ref"] == ext_ref)
    page.goto(f"{BASE}/app/{aid}")
    return aid


def host_a_upload(page, sample, inst, intake, lab2=0):
    page.goto(BASE + "/host-a/")
    page.select_option("#inst", inst)
    page.get_by_role("button", name="Next").click()
    page.fill("#intake", str(intake))
    page.fill("#lab2", str(lab2))
    page.get_by_role("button", name="Create application and continue").click()
    w = page.locator("#pramaan-uploader")
    expect(w.get_by_text("Fire NOC", exact=True)).to_be_visible()
    inputs = w.locator("input[type=file]")
    for i, slot in enumerate(HOST_A):
        files = sorted(glob.glob(os.path.join(SAMPLES, sample, f"{slot}__*")))
        files = [f for f in files if "renewed" not in f]
        if slot == "INFRA_PHOTOS":
            for f in files:
                fac = re.search(r"(COMPUTER_LAB_\d)", f).group(1)
                w.locator("select").select_option(fac)
                w.locator("input[type=file]").nth(i).set_input_files(f)
                expect(w.get_by_text(os.path.basename(f)[len("INFRA_PHOTOS__"):], exact=False).first).to_be_visible()
        elif files:
            inputs.nth(i).set_input_files(files[0])
            expect(w.get_by_text(os.path.basename(files[0])[len(slot) + 2:], exact=False).first).to_be_visible()
    return page.locator("#ref").inner_text()


# 1. Same engine, two portals, different rule packs, live
def test_1_two_portals(page):
    host_a_upload(page, "GOLDEN-A", "INST-011", 120)
    page.goto(BASE + "/host-b/")
    page.get_by_role("button", name="Begin affiliation application").click()
    w = page.locator("#pramaan-uploader")
    expect(w.get_by_text("Fire Clearance Certificate")).to_be_visible()
    expect(w.get_by_text("University Affiliation Portal (mock)", exact=False)).to_be_visible()


# 2. Golden application: all checks green, all documents verified
def test_2_golden_all_green(page):
    ref = host_a_upload(page, "GOLDEN-A", "INST-011", 120)
    page.locator("#pramaan-uploader").get_by_role("button", name="Submit for validation").click()
    expect(page.locator("#pramaan-uploader").get_by_text("No items to fix", exact=False)).to_be_visible(timeout=120_000)
    expect(page.locator("#status")).to_contain_text("validation.completed", timeout=30_000)
    officer(page, "Enter as Senior Officer")
    aid = open_app(page, ref)
    expect(page.get_by_text("All checks passed")).to_be_visible()
    expect(page.get_by_text("confirmed with the issuing office", exact=False)).to_be_visible()
    vers = api(page, "GET", f"/applications/{aid}")["verifications"]
    assert vers and all(v["status"] == "VERIFIED" for v in vers), [(v["method"], v["status"], v["details"].get("reason")) for v in vers]


# 3. Problem application surfaces every seeded problem with evidence
def test_3_problem_findings(page):
    officer(page, "Enter as Senior Officer")
    open_app(page, "PROBLEM-A")
    for text in ["Building Completion Certificate not uploaded", "Fire Safety NOC has expired", "Name mismatch",
                 "Claimed intake equals approved intake", "possible local alteration", "Image matches a document from another institution",
                 "qr mismatch", "scanned or handwritten", "computer monitors 12 detected / 30 claimed", "instruction-like text"]:
        expect(page.get_by_text(text, exact=False).first).to_be_visible()
    page.get_by_role("button", name=re.compile("General Affidavit")).first.click()
    expect(page.get_by_text("Show edit heatmap", exact=False)).to_be_visible()
    page.get_by_text("Compare with matching image", exact=False).first.click()
    expect(page.get_by_text("Same photo found in another college", exact=False)).to_be_visible()


# 4. Institution sees only the rectification list; re-upload re-runs only affected checks
def test_4_rectification(page):
    ref = host_a_upload(page, "PROBLEM-A", "INST-012", 180, lab2=15)
    w = page.locator("#pramaan-uploader")
    w.get_by_role("button", name="Submit for validation").click()
    expect(w.get_by_text("Items to fix")).to_be_visible(timeout=120_000)
    expect(w.get_by_text("Fire Safety NOC has expired", exact=False)).to_be_visible()
    for hidden in ("noise", "alteration", "heatmap", "copy-move"):
        expect(w.get_by_text(hidden, exact=False)).to_have_count(0)
    w.locator("input[type=file]").nth(2).set_input_files(os.path.join(SAMPLES, "PROBLEM-A", "FIRE_NOC__fire_noc_renewed.pdf"))
    expect(w.get_by_text("Fire Safety NOC has expired", exact=False)).to_have_count(0, timeout=120_000)
    officer(page, "Enter as Senior Officer")
    aid = open_app(page, ref)
    rep = api(page, "GET", f"/applications/{aid}")["report"]
    ran = [t["stage"] for t in rep["timeline"] if t["stage"].startswith("doc:") and t["status"] == "ran"]
    assert ran == ["doc:FIRE_NOC"], ran
    page.get_by_role("button", name="How it was processed").click()
    expect(page.get_by_text("after re-upload", exact=False)).to_be_visible()


# 5. Officer dismisses a flag with a reason; the decision gate blocks until HIGH flags are disposed
def test_5_dispose_and_gate(page):
    officer(page, "Enter as Senior Officer")
    aid = open_app(page, "PROBLEM-A")
    expect(page.get_by_role("button", name="Record decision note")).to_be_disabled()
    card = page.locator("[id^=FLG-]").filter(has_text="Serious").first
    card.get_by_role("button", name="Review").click()
    card.get_by_placeholder("Why?", exact=False).fill("Checked with the issuer by phone (demo)")
    card.get_by_role("button", name="Dismiss").click()
    expect(page.get_by_text("dismissed", exact=False).first).to_be_visible()
    assert page.request.post(f"{BASE}/api/applications/{aid}/decision", data=json.dumps({"text": "x"}),
                             headers={"Content-Type": "application/json"}).status == 409
    for f in api(page, "GET", f"/applications/{aid}")["flags"]:
        if f["severity"] == "HIGH" and f["status"] == "OPEN":
            api(page, "POST", f"/flags/{f['id']}/dispose", {"action": "CONFIRM", "reason": "Confirmed in review (demo)"})
    page.reload()
    page.get_by_placeholder("e.g. Issue deficiency letter", exact=False).fill("Issue deficiency letter for the confirmed items")
    page.get_by_role("button", name="Record decision note").click()
    expect(page.get_by_text("Issue deficiency letter for the confirmed items")).to_be_visible()


# 7. Evaluation page shows the PS metrics
def test_7_evaluation_page(page):
    officer(page, "Enter as Rule Admin")
    page.goto(BASE + "/evaluation")
    page.get_by_role("button", name="Run quick evaluation").click()
    for m in ("Field exact match", "Discrepancy recall", "Source verification success", "Avg time / application", "Alert timeliness",
              "Est. manual effort saved", "Anomaly detection per forgery type"):
        expect(page.get_by_text(m, exact=False).first).to_be_visible(timeout=240_000)


# 8. Runs in LITE mode on CPU and still produces a report
def test_8_lite_mode(page):
    h = json.loads(urllib.request.urlopen(API + "/api/health").read())
    assert h["mode"] == "LITE"
    officer(page, "Enter as Senior Officer")
    aid = open_app(page, "GOLDEN-B")
    r = page.request.get(f"{BASE}/api/applications/{aid}/report.pdf")
    assert r.ok and r.body()[:4] == b"%PDF"


# 6. Audit chain verifies; tampering one row breaks it (runs last: it damages the chain)
def test_9_audit_chain(page):
    officer(page, "Enter as Auditor")
    page.goto(BASE + "/audit")
    page.get_by_role("button", name="Verify chain").click()
    expect(page.get_by_text("Chain intact", exact=False)).to_be_visible()
    urllib.request.urlopen(urllib.request.Request(API + "/api/admin/tamper-demo", method="POST", headers={"X-Seed-Token": SEED_TOKEN}))
    page.get_by_role("button", name="Verify chain").click()
    expect(page.get_by_text("Chain BROKEN at sequence #3", exact=False)).to_be_visible()

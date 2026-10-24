"""Scores PRAMAAN against real, permitted files in realdata/ and the hand-written truth sheet realdata/truth.csv.
Runs offline: in-memory store, no Atlas, no hosted LLM/vision calls. Separate from the synthetic evaluation.
Usage: python -m pramaan.evaluate_real   (MODE=FULL adds the OCR, handwriting and detector models)"""
import csv
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL = os.path.join(ROOT, "realdata")
for k in ("MONGODB_URI", "GROQ_KEY", "SMTP_HOST"):  # keep real files on this machine
    os.environ.pop(k, None)

from . import engine, extract, rulepack  # noqa: E402
from .db import get_db  # noqa: E402
from .evaluate import cer  # noqa: E402

PII = [(r"\b\d{4}\s?\d{4}\s?\d{4}\b", "12-digit number (Aadhaar-like)"), (r"\b[A-Z]{5}\d{4}[A-Z]\b", "PAN-like ID"),
       (r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)", "mobile number")]


def norm(field, v):
    v = str(v or "").strip()
    if field in ("issued_on", "valid_to", "paid_on", "as_on"):
        return extract.norm_date(v) or v
    if field == "amount":
        n = extract.norm_number(v)
        return f"{n:.0f}" if n is not None else v
    return re.sub(r"\s+", " ", v).casefold()


def main():
    truth_path = os.path.join(REAL, "truth.csv")
    if not os.path.exists(truth_path):
        print("No realdata/truth.csv yet. Copy realdata/truth.example.csv, add your files and rows, then run again.")
        return 1
    rows = list(csv.DictReader(open(truth_path, encoding="utf-8-sig")))
    pack, ver = rulepack.parse(rulepack.load_file("aicte-demo-2026-27.yaml"))[0], "real"
    app = {"id": "REAL", "form": {}, "institution_id": "REAL"}
    results, warnings, cache = [], [], {}
    t0 = time.perf_counter()
    for r in rows:
        f, slot, field, want = r["file"].strip(), r["doc_type"].strip(), r["field"].strip(), r["expected"].strip()
        path = os.path.join(REAL, f)
        if not os.path.exists(path):
            results.append({**r, "got": "file not found", "ok": False})
            continue
        if f not in cache:
            data = open(path, "rb").read()
            if f.lower().endswith(".pdf"):
                txt = "\n".join(extract.pdf_text(extract.open_pdf(data)))
                for pat, what in PII:
                    if re.search(pat, txt):
                        warnings.append(f"{f}: text layer contains a {what}. Mask it before sharing any output.")
            fac = re.search(r"(COMPUTER_LAB_\d+|lab(\d+))", f, re.I)
            doc = {"id": f"REAL-{len(cache)}", "slot": slot, "filename": f, "blob_id": engine.put_blob(data),
                   "facility": f"COMPUTER_LAB_{fac.group(2) or 1}" if slot == "INFRA_PHOTOS" else None}
            t = time.perf_counter()
            res = engine.process_doc(doc, pack, app)
            res["ms"] = round((time.perf_counter() - t) * 1000)
            if field == "expect_flag" or any(x["file"] == f and x["field"] == "expect_flag" for x in rows):
                get_db().documents.insert_one({**doc, "app_id": "REAL", "result": res, "pack_ref": f"{pack['key']}@{ver}", "uploaded_at": "2026-10-24T00:00:00"})
            cache[f] = res
        res = cache[f]
        if field == "doc_type":
            got = res.get("type") or ("unreadable scan" if res.get("scanned") else "unknown")
            ok = got == want
        elif field == "computer_count":
            counts = [(i.get("count") or {}).get("count") for i in res.get("images", [])]
            got = max([c for c in counts if c is not None], default=None)
            ok = got is not None and abs(got - int(want)) <= max(1, round(0.1 * int(want)))
        elif field.startswith("area:"):
            room = field.split(":", 1)[1]
            plan = res.get("floor_plan") or {}
            got = next((x["area_sqm"] for x in plan.get("rooms", []) if x["label"].upper() == room.upper()), None)
            if got is None and not plan:
                got = "plan not measured (raster or no printed scale)"
            ok = isinstance(got, (int, float)) and abs(got - float(want)) <= 0.05 * float(want)
        elif field == "expect_flag":
            got = None
            ok = None  # filled after the application-level run below
        else:
            fv = (res.get("fields") or {}).get(field) or {}
            got = fv.get("raw")
            ok = norm(field, got) == norm(field, want)
            r["cer"] = round(cer(norm(field, got), norm(field, want)), 3)
            r["conf"] = fv.get("conf")
        results.append({**r, "got": got, "ok": ok})
    if any(r["field"] == "expect_flag" for r in rows):
        get_db().applications.insert_one({"id": "REAL", "host_id": "-", "institution_id": "REAL", "category": "EOA", "pack_key": pack["key"],
                                          "region": "-", "form": {}, "report_version": 0, "submitted_on": time.strftime("%Y-%m-%d")})
        get_db().rule_packs.insert_one({"key": pack["key"], "version": ver, "status": "ACTIVE", "yaml": rulepack.load_file("aicte-demo-2026-27.yaml")})
        engine.send_webhook = lambda *a, **k: None
        engine.run("REAL", actor="eval-real", agents_on=False)
        flags = list(get_db().flags.find({"app_id": "REAL", "current": True}))
        for x in results:
            if x["field"] == "expect_flag":
                did = next((d["id"] for d in get_db().documents.find({"app_id": "REAL", "filename": x["file"]})), None)
                hits = [fl["code"] for fl in flags if fl.get("doc_id") == did]
                x["got"], x["ok"] = ", ".join(sorted(set(hits))) or "no findings", x["expected"] in hits
    write_report(results, warnings, time.perf_counter() - t0, cache)
    return 0


def write_report(results, warnings, secs, cache):
    by = {}
    for r in results:
        k = "fields" if r["field"] not in ("doc_type", "computer_count", "expect_flag") and not r["field"].startswith("area:") else r["field"].split(":")[0]
        by.setdefault(k, []).append(r)
    pct = lambda rs: f"{100 * sum(1 for r in rs if r['ok']) / len(rs):.0f}% ({sum(1 for r in rs if r['ok'])}/{len(rs)})" if rs else "n/a"
    L = [f"# Real-data evaluation ({engine.MODE} mode)", "", f"{len(cache)} files, {len(results)} truth rows, {secs:.1f} s. Private: do not commit or share.", "",
         "| Check | Correct |", "|---|---|"]
    names = {"doc_type": "Document type recognised", "fields": "Field values read exactly", "computer_count": "Computer count within 10%",
             "area": "Room area within 5%", "expect_flag": "Expected findings raised"}
    for k, rs in by.items():
        L.append(f"| {names.get(k, k)} | {pct(rs)} |")
    cers = [r["cer"] for r in results if "cer" in r]
    if cers:
        L.append(f"| Field character error rate | {100 * sum(cers) / len(cers):.1f}% |")
    if warnings:
        L += ["", "## Masking warnings", ""] + [f"- {w}" for w in warnings]
    L += ["", "## Every row", "", "| File | Field | Expected | PRAMAAN got | OK |", "|---|---|---|---|---|"]
    L += [f"| {r['file']} | {r['field']} | {r['expected']} | {r['got']} | {'yes' if r['ok'] else 'no'} |" for r in results]
    out = os.path.join(ROOT, "docs", "EVAL-REAL.md")
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L[:12 + len(by)]))
    print("\nFull report:", out)


if __name__ == "__main__":
    sys.exit(main())

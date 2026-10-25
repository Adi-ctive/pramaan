"""Large public-dataset evaluation: thousands of real documents and photos fetched by scripts/fetch_public_data.py.
Runs the same tamper rule as the engine (noise residual flag, ELA + copy-move when the noise score is borderline) on real
genuine and real tampered files, plus OCR, room type and floor plans in FULL mode. Offline: no Atlas, no hosted AI.
Writes docs/EVAL-LARGE.md and docs/EVAL-LARGE.json. Usage: [MODE=FULL] python -m pramaan.evaluate_large [part ...]"""
import csv
import glob
import io
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

for k in ("MONGODB_URI", "GROQ_KEY"):
    os.environ.pop(k, None)

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from . import extract, forensics, providers  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(ROOT, "realdata", "public")
NOISE_TH = 0.65  # rulepacks: noise_suspicion
WORKERS = min(6, os.cpu_count() or 2)
Image.MAX_IMAGE_PIXELS = 60_000_000


def tamper(img):
    """The engine's DAG rule for an uploaded image: TAMPER_INDICATOR if the noise residual or copy-move is suspicious."""
    im = img.convert("RGB")
    nc = forensics.noise_check(im, NOISE_TH)
    out = {"noise": nc["score"], "region": nc["region"], "flag": nc["suspicious"], "escalated": False}
    if nc["score"] >= NOISE_TH / 2:
        out["escalated"] = True
        out["ela"] = forensics.ela_score(im)
        cm = forensics.copy_move(im)
        out["copy_move"] = cm["pairs"]
        out["flag"] = out["flag"] or cm["suspicious"]
    return out


def _job(item):
    """Worker: item = (key, path or bytes, mask path or None). Returns (key, result, ms)."""
    key, src, mask = item
    t = time.perf_counter()
    try:
        img = Image.open(io.BytesIO(src) if isinstance(src, bytes) else src)
        r = tamper(img)
        if mask and r["flag"] and r["region"]:
            m = np.asarray(Image.open(mask).convert("L").resize(img.size)) > 127
            x, y, w, h = r["region"]
            H, W = m.shape
            box = m[int(y * H):int((y + h) * H) + 1, int(x * W):int((x + w) * W) + 1]
            r["hit_mask"] = bool(box.size and box.mean() > 0.05)
    except Exception as e:
        r = {"error": f"{type(e).__name__}: {str(e)[:80]}"}
    return key, r, (time.perf_counter() - t) * 1000


def run_tamper(items):
    out, ms = {}, []
    with ProcessPoolExecutor(WORKERS) as ex:
        for k, r, t in ex.map(_job, items, chunksize=8):
            out[k] = r
            ms.append(t)
    return out, ms


def rate(n, d):
    return round(n / d, 4) if d else None


def scores(flags):
    """flags: list of (truth_tampered, flagged). Precision, recall, F1, false-alarm rate."""
    tp = sum(1 for t, f in flags if t and f)
    fp = sum(1 for t, f in flags if not t and f)
    fn = sum(1 for t, f in flags if t and not f)
    tn = sum(1 for t, f in flags if not t and not f)
    p, r = rate(tp, tp + fp), rate(tp, tp + fn)
    return {"tampered": tp + fn, "genuine": fp + tn, "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": p, "recall": r,
            "f1": round(2 * p * r / (p + r), 4) if p and r else 0.0, "false_alarm_rate": rate(fp, fp + tn)}


# ---------------- RVL-CDIP: real genuine scans, 16 document types
def rvl():
    import pyarrow.parquet as pq
    files = sorted(glob.glob(os.path.join(PUB, "rvl_cdip", "sample", "*.parquet")))
    if not files:
        return None
    items, labels = [], {}
    for f in files:
        t = pq.read_table(f)
        for i, row in enumerate(t.to_pylist()):
            k = f"{os.path.basename(f)}:{i}"
            items.append((k, row["image"]["bytes"], None))
            labels[k] = row["label"]
    res, ms = run_tamper(items)
    errs = sum(1 for r in res.values() if "error" in r)
    per = defaultdict(lambda: [0, 0])
    for k, r in res.items():
        if "error" not in r:
            per[labels[k]][0] += 1
            per[labels[k]][1] += r["flag"]
    cls = ["advertisement", "budget", "email", "file folder", "form", "handwritten", "invoice", "letter", "memo", "news article",
           "presentation", "questionnaire", "resume", "scientific publication", "scientific report", "specification"]
    ok = [r for r in res.values() if "error" not in r]
    out = {"documents": len(ok), "errors": errs, "flagged": sum(r["flag"] for r in ok), "false_alarm_rate": rate(sum(r["flag"] for r in ok), len(ok)),
           "escalated": sum(r["escalated"] for r in ok), "ms_per_doc": round(float(np.mean(ms)), 1), "workers": WORKERS,
           "per_class": {cls[c]: {"docs": n, "flagged": f, "rate": rate(f, n)} for c, (n, f) in sorted(per.items())}}
    if providers.MODE == "FULL":
        out["ocr"] = rvl_ocr(items[:int(os.environ.get("RVL_OCR", 1000))])
    return out


def rvl_ocr(items):
    """OCR throughput and coverage on real scans (no ground-truth text in RVL-CDIP, so no accuracy number)."""
    ms, words, empty = [], [], 0
    for _, b, _ in items:
        t = time.perf_counter()
        lines = providers.ocr.read(Image.open(io.BytesIO(b))) or []
        ms.append((time.perf_counter() - t) * 1000)
        n = sum(len(l["text"].split()) for l in lines)
        words.append(n)
        empty += n == 0
    return {"pages": len(items), "ms_per_page": round(float(np.mean(ms)), 1), "words_per_page": round(float(np.mean(words)), 1), "pages_no_text": empty}


# ---------------- SROIE (genuine receipts) and T-SROIE (same receipts with tampered text)
def _sroie_truth():
    truth = {}
    for p in glob.glob(os.path.join(PUB, "sroie", "**", "*.txt"), recursive=True):
        try:
            j = json.load(open(p, encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        if isinstance(j, dict) and "total" in j:
            truth[os.path.splitext(os.path.basename(p))[0]] = j
    return truth


def sroie():
    gen = {os.path.splitext(os.path.basename(p))[0]: p for p in glob.glob(os.path.join(PUB, "sroie", "**", "*.jpg"), recursive=True)}
    tam = {os.path.splitext(os.path.basename(p))[0]: p for p in glob.glob(os.path.join(PUB, "tsroie", "**", "*.jpg"), recursive=True)}
    if not gen and not tam:
        return None
    items = [("g:" + k, p, None) for k, p in gen.items()] + [("t:" + k, p, None) for k, p in tam.items()]
    res, ms = run_tamper(items)
    ok = {k: r for k, r in res.items() if "error" not in r}
    out = {"genuine_receipts": len(gen), "tampered_receipts": len(tam), "errors": len(res) - len(ok), "ms_per_doc": round(float(np.mean(ms)), 1),
           "tamper": scores([(k.startswith("t:"), r["flag"]) for k, r in ok.items()])}
    truth = _sroie_truth()
    out["dates_parsed"] = {"receipts": len(truth), "parsed": sum(1 for j in truth.values() if extract.norm_date(j.get("date", "")))}
    if providers.MODE == "FULL" and truth:
        out["ocr"] = sroie_ocr(gen, truth)
    return out


def _norm(s):
    return re.sub(r"[^0-9a-z.]", "", str(s).lower())


def sroie_ocr(gen, truth, limit=None):
    """Does the OCR Model read each receipt's total and date (as printed) and the company name (CER)?"""
    from .evaluate import cer
    keys = [k for k in gen if k in truth][:limit]
    tot = dat = 0
    errs, ms = [], []
    for k in keys:
        t = time.perf_counter()
        lines = providers.ocr.read(Image.open(gen[k])) or []
        ms.append((time.perf_counter() - t) * 1000)
        text = _norm(" ".join(l["text"] for l in lines))
        j = truth[k]
        tot += bool(_norm(j["total"])) and _norm(j["total"]) in text
        dat += bool(_norm(j.get("date", ""))) and _norm(j.get("date", "")) in text
        comp = _norm(j.get("company", ""))
        if comp:
            best = min((cer(_norm(l["text"]), comp) for l in lines), default=1.0)
            errs.append(min(best, 1.0))
    return {"receipts": len(keys), "total_read": rate(tot, len(keys)), "date_read": rate(dat, len(keys)),
            "company_cer": round(float(np.mean(errs)), 4) if errs else None, "ms_per_page": round(float(np.mean(ms)), 1) if ms else None}


# ---------------- SIFTA: real and forged document images
def sifta():
    import pyarrow.parquet as pq
    files = glob.glob(os.path.join(PUB, "sifta", "**", "*.parquet"), recursive=True)
    if not files:
        return None
    items, truth = [], {}
    for f in files:
        for i, row in enumerate(pq.read_table(f).to_pylist()):
            k = f"{os.path.basename(f)}:{i}"
            items.append((k, row["image"]["bytes"], None))
            truth[k] = row["label"] == 1
    res, ms = run_tamper(items)
    ok = {k: r for k, r in res.items() if "error" not in r}
    return {"documents": len(ok), "errors": len(res) - len(ok), "ms_per_doc": round(float(np.mean(ms)), 1),
            "tamper": scores([(truth[k], r["flag"]) for k, r in ok.items()])}


# ---------------- photo forgery: CASIA, COCO, Paris; splicing, copy-move, editing, inpainting
def forgery():
    lab = os.path.join(PUB, "forgery", "labels.csv")
    if not os.path.exists(lab):
        return None
    rows = list(csv.DictReader(open(lab)))
    d = os.path.join(PUB, "forgery")
    items = [(r["image"], os.path.join(d, r["image"]), os.path.join(d, r["mask"]) if r["mask"] else None) for r in rows
             if os.path.exists(os.path.join(d, r["image"]))]
    op = {r["image"]: r["operation"] for r in rows}
    res, ms = run_tamper(items)
    ok = {k: r for k, r in res.items() if "error" not in r}
    per = {}
    for o in sorted(set(op.values())):
        rs = [r for k, r in ok.items() if op[k] == o]
        per[o] = {"images": len(rs), "flagged": sum(r["flag"] for r in rs), "rate": rate(sum(r["flag"] for r in rs), len(rs))}
        if o != "authentic":
            hits = [r.get("hit_mask") for r in rs if r["flag"] and "hit_mask" in r]
            per[o]["flag_region_on_tampered_pixels"] = rate(sum(hits), len(hits))
    return {"images": len(ok), "errors": len(res) - len(ok), "ms_per_image": round(float(np.mean(ms)), 1),
            "tamper": scores([(op[k] != "authentic", r["flag"]) for k, r in ok.items()]), "per_operation": per}


# ---------------- MIT Indoor 67, all 15,620 photos, production label set for a computer lab
LAB_LABELS = ["computer lab", "computer laboratory", "classroom", "library", "office", "corridor", "washroom"]
MIT_MAP = {"computerroom": "computer lab", "classroom": "classroom", "library": "library", "office": "office", "corridor": "corridor"}


def mit_full():
    lab = os.path.join(PUB, "mit_indoor", "labels_full.csv")
    if not os.path.exists(lab) or providers.MODE != "FULL":
        return None
    rows = list(csv.DictReader(open(lab)))
    conf, tp, fp, fn, ok5, n5, ms = Counter(), 0, 0, 0, 0, 0, []
    fp_by = Counter()
    for r in rows:
        t = time.perf_counter()
        got = providers.scene.classify(Image.open(os.path.join(PUB, "mit_indoor", r["file"])), LAB_LABELS)["label"]
        ms.append((time.perf_counter() - t) * 1000)
        got = "computer lab" if got.startswith("computer") else got
        want = MIT_MAP.get(r["room"])
        lab_true, lab_pred = r["room"] == "computerroom", got == "computer lab"
        tp += lab_true and lab_pred
        fn += lab_true and not lab_pred
        if lab_pred and not lab_true:
            fp += 1
            fp_by[r["room"]] += 1
        if want:
            n5 += 1
            ok5 += got == want
            conf[(want, got)] += 1
    return {"photos": len(rows), "room_types": len({r["room"] for r in rows}), "ms_per_photo": round(float(np.mean(ms)), 1),
            "five_room_accuracy": rate(ok5, n5), "five_room_photos": n5, "computer_lab": {"true": tp + fn, "tp": tp, "fp": fp, "fn": fn,
            "precision": rate(tp, tp + fp), "recall": rate(tp, tp + fn)}, "lab_false_positives_by_room": dict(fp_by.most_common(8))}


# ---------------- CubiCasa5K and IIIT-HW-Dev reuse the small-set scorers
def cubicasa():
    from .evaluate_public import cubicasa as c
    t = time.perf_counter()
    r = c()
    if r:
        r["seconds"] = round(time.perf_counter() - t, 1)
    return r


def iiit():
    from .evaluate_public import iiit as h
    return h(limit=int(os.environ.get("IIIT_LIMIT", 3000)))


PARTS = {"rvl": rvl, "sroie": sroie, "sifta": sifta, "forgery": forgery, "mit_full": mit_full, "cubicasa": cubicasa, "iiit": iiit}


def report(r):
    pct = lambda x: "n/a" if x is None else f"{100 * x:.1f}%"
    L = ["# Large public-dataset evaluation", "",
         f"Mode {r['mode']}, run {r['date']}, {r['total_items']:,} real files in total. Fetched by scripts/fetch_public_data.py, kept in realdata/public/ (gitignored).",
         "Tamper rule is the engine's: TAMPER_INDICATOR when the noise residual is suspicious, ELA and copy-move run when the noise score is borderline.", ""]
    if r.get("rvl"):
        x = r["rvl"]
        L += [f"## RVL-CDIP: {x['documents']:,} real scanned documents, 16 types, none tampered", "",
              f"- Tamper flags raised on genuine scans: {x['flagged']:,} ({pct(x['false_alarm_rate'])} false-alarm rate).",
              f"- Forensics time: {x['ms_per_doc']} ms per document per CPU worker ({x['workers']} workers).", ""]
        L += ["| Type | Docs | Flagged | Rate |", "|---|---|---|---|"] + [f"| {k} | {v['docs']} | {v['flagged']} | {pct(v['rate'])} |" for k, v in x["per_class"].items()]
        if x.get("ocr"):
            o = x["ocr"]
            L += ["", f"OCR Model on {o['pages']:,} pages: {o['ms_per_page']} ms per page, {o['words_per_page']} words per page, {o['pages_no_text']} pages with no text read. RVL-CDIP has no text truth, so this is throughput and coverage only."]
        L.append("")
    for key, title in (("sroie", "SROIE and T-SROIE: real receipts, genuine and with tampered text"), ("sifta", "SIFTA: real and forged document images"),
                       ("forgery", "Photo forgery (CASIA, COCO, Paris): authentic and tampered photos with masks")):
        x = r.get(key)
        if not x:
            continue
        s = x["tamper"]
        L += [f"## {title}", "", f"- Files: {s['genuine']:,} genuine, {s['tampered']:,} tampered.",
              f"- Tamper indicator: precision {pct(s['precision'])}, recall {pct(s['recall'])}, F1 {s['f1']:.3f}, false-alarm rate on genuine {pct(s['false_alarm_rate'])}."]
        if key == "sroie":
            dp = x["dates_parsed"]
            L.append(f"- Receipt dates our date parser understands: {dp['parsed']} of {dp['receipts']}.")
            if x.get("ocr"):
                o = x["ocr"]
                L.append(f"- OCR Model on {o['receipts']} genuine receipts: total read {pct(o['total_read'])}, date read {pct(o['date_read'])}, company name CER {pct(o['company_cer'])}, {o['ms_per_page']} ms per receipt.")
        if key == "forgery":
            L += ["", "| Operation | Images | Flagged | Rate | Flag region on tampered pixels |", "|---|---|---|---|---|"]
            L += [f"| {k} | {v['images']} | {v['flagged']} | {pct(v['rate'])} | {pct(v.get('flag_region_on_tampered_pixels'))} |" for k, v in x["per_operation"].items()]
        L.append("")
    if r.get("mit_full"):
        x = r["mit_full"]
        c = x["computer_lab"]
        L += [f"## MIT Indoor 67: all {x['photos']:,} real photos, {x['room_types']} room types", "",
              f"- Label set is the one the engine uses for a computer-lab photo: {', '.join(LAB_LABELS)}.",
              f"- Accuracy on the 5 room types in that set: {pct(x['five_room_accuracy'])} ({x['five_room_photos']:,} photos).",
              f"- 'Computer lab' accepted: precision {pct(c['precision'])}, recall {pct(c['recall'])} ({c['tp']} right, {c['fp']} other rooms wrongly accepted, {c['fn']} labs missed).",
              f"- Rooms most often mistaken for a computer lab: {', '.join(f'{k} {v}' for k, v in x['lab_false_positives_by_room'].items())}.",
              f"- {x['ms_per_photo']} ms per photo on the GPU.", ""]
    if r.get("cubicasa"):
        x = r["cubicasa"]
        L += [f"## CubiCasa5K: {x['plans']:,} real floor plans", "", f"- Room recall {pct(x['room_recall'])}, precision {pct(x['room_precision'])} ({x['rooms_found']:,} found, {x['rooms_true']:,} true). {x['note']}", ""]
    if r.get("iiit"):
        x = r["iiit"]
        L += [f"## IIIT-HW-Dev: {x['words']:,} handwritten Hindi words", "", f"- CER {pct(x['cer'])}, exact {pct(x['exact'])}. Reader: {x['reader']}.", ""]
    L += ["## Licences", "", "RVL-CDIP (IIT-CDIP / UCSF terms), SROIE (ICDAR 2019), T-SROIE (MIT), SIFTA (Hugging Face, no licence stated), photo forgery set "
          "(Apache-2.0 tag; CASIA, COCO and Paris sources), MIT Indoor 67, CubiCasa5K, IIIT-HW-Dev: research use, cited, never redistributed."]
    return "\n".join(L) + "\n"


def main():
    parts = sys.argv[1:] or list(PARTS)
    path = os.path.join(ROOT, "docs", "EVAL-LARGE.json")
    r = json.load(open(path)) if os.path.exists(path) else {}
    for p in parts:
        t = time.perf_counter()
        print("running", p, flush=True)
        r[p] = PARTS[p]()
        if r[p]:
            r[p]["seconds"] = round(time.perf_counter() - t, 1)
            r[p]["mode"] = providers.MODE
        print(p, json.dumps(r[p], default=str)[:600], flush=True)
        json.dump(r, open(path, "w"), indent=1, default=str)
    r["mode"] = "FULL" if any((r.get(k) or {}).get("mode") == "FULL" for k in PARTS) else providers.MODE
    r["date"] = time.strftime("%d %b %Y")
    counts = {"rvl": ("documents",), "sroie": ("genuine_receipts", "tampered_receipts"), "sifta": ("documents",), "forgery": ("images",),
              "mit_full": ("photos",), "cubicasa": ("plans",), "iiit": ("words",)}
    r["total_items"] = sum((r.get(k) or {}).get(f, 0) for k, fs in counts.items() for f in fs)
    json.dump(r, open(path, "w"), indent=1, default=str)
    open(os.path.join(ROOT, "docs", "EVAL-LARGE.md"), "w", encoding="utf-8").write(report(r))
    print(report(r))


if __name__ == "__main__":
    main()

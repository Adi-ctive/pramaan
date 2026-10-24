"""Scores PRAMAAN's models on public datasets fetched by scripts/fetch_public_data.py (realdata/public/, gitignored).
Offline: no Atlas, no hosted AI. Writes docs/EVAL-PUBLIC.md. Usage: MODE=FULL python -m pramaan.evaluate_public"""
import csv
import glob
import os
import re
import time
from collections import Counter

for k in ("MONGODB_URI", "GROQ_KEY"):
    os.environ.pop(k, None)

from PIL import Image  # noqa: E402

from . import extract, providers  # noqa: E402
from .evaluate import cer  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(ROOT, "realdata", "public")
ROOM_WORDS = {"computerroom": "computer lab", "classroom": "classroom", "library": "library", "office": "office",
              "corridor": "corridor", "meeting_room": "meeting room"}


def mit():
    lab = os.path.join(PUB, "mit_indoor", "labels.csv")
    if not os.path.exists(lab) or providers.MODE != "FULL":
        return None
    rows = list(csv.DictReader(open(lab)))
    labels = list(ROOM_WORDS.values())
    conf, ok = Counter(), 0
    tp = fp = fn = 0
    for r in rows:
        p = os.path.join(PUB, "mit_indoor", r["file"])
        if not os.path.exists(p):
            continue
        got = providers.scene.classify(Image.open(p), labels)["label"]
        want = ROOM_WORDS[r["room"]]
        conf[(want, got)] += 1
        ok += got == want
        tp += want == "computer lab" and got == "computer lab"
        fp += want != "computer lab" and got == "computer lab"
        fn += want == "computer lab" and got != "computer lab"
    n = sum(conf.values())
    return {"images": n, "accuracy": round(ok / n, 3) if n else None,
            "computer_lab_precision": round(tp / (tp + fp), 3) if tp + fp else None,
            "computer_lab_recall": round(tp / (tp + fn), 3) if tp + fn else None,
            "confusion": {f"{a} -> {b}": c for (a, b), c in sorted(conf.items())}}


def _svg_rooms(svg_text):
    """Room polygons from a CubiCasa model.svg: <g class="Space ..."><polygon points="..."/>."""
    rooms = []
    for m in re.finditer(r'<g[^>]*class="Space ([^"]*)"[^>]*>\s*<polygon[^>]*points="([^"]+)"', svg_text):
        pts = [tuple(map(float, p.split(","))) for p in m.group(2).split() if "," in p]
        if len(pts) >= 3:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            rooms.append({"kind": m.group(1).split()[0], "box": (min(xs), min(ys), max(xs), max(ys))})
    return rooms


def _iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u else 0


def cubicasa():
    plans = glob.glob(os.path.join(PUB, "cubicasa5k", "**", "model.svg"), recursive=True)
    if not plans:
        return None
    gt_n = pred_n = matched_gt = matched_pred = 0
    for svg in plans:
        png = os.path.join(os.path.dirname(svg), "F1_scaled.png")
        if not os.path.exists(png):
            continue
        img = Image.open(png)
        W, H = img.size
        gt = _svg_rooms(open(svg, encoding="utf-8", errors="ignore").read())
        pred = [(r["bbox"][0] * W, r["bbox"][1] * H, (r["bbox"][0] + r["bbox"][2]) * W, (r["bbox"][1] + r["bbox"][3]) * H)
                for r in extract.floor_plan_raster(img)]
        gt_n += len(gt)
        pred_n += len(pred)
        matched_gt += sum(1 for g in gt if any(_iou(g["box"], p) >= 0.5 for p in pred))
        matched_pred += sum(1 for p in pred if any(_iou(g["box"], p) >= 0.5 for g in gt))
    return {"plans": len(plans), "rooms_true": gt_n, "rooms_found": pred_n,
            "room_recall": round(matched_gt / gt_n, 3) if gt_n else None, "room_precision": round(matched_pred / pred_n, 3) if pred_n else None,
            "note": "Rooms matched by box overlap (IoU >= 0.5). No scale in these images, so areas in m² are not measured."}


def iiit(limit=500):
    d = os.path.join(PUB, "iiit_hw_dev")
    if not os.path.isdir(d) or providers.MODE != "FULL":
        return None
    truth = {}
    for name in ("test.txt", "val.txt"):  # official split lists: "HindiSeg/<split>/<writer>/<page>/<n>.jpg <word>"
        t = os.path.join(d, name)
        if os.path.exists(t):
            for line in open(t, encoding="utf-8", errors="ignore"):
                parts = line.strip().split(" ", 1)
                if len(parts) == 2:
                    truth[parts[0]] = parts[1].strip()
    imgs = []
    for p in glob.glob(os.path.join(d, "img", "**", "*.jpg"), recursive=True):
        rel = os.path.relpath(p, os.path.join(d, "img")).replace("\\", "/")
        if rel in truth:
            imgs.append((p, truth[rel]))
    imgs = imgs[:limit]
    errs, exact = [], 0
    for p, want in imgs:
        lines = providers.ocr.read_hindi(Image.open(p)) or []
        got = " ".join(l["text"] for l in lines).strip()
        errs.append(cer(got, want))
        exact += got == want
    return {"words": len(imgs), "cer": round(sum(errs) / len(errs), 4) if errs else None, "exact": round(exact / len(imgs), 3) if imgs else None,
            "reader": "Hindi OCR Model (printed-text model, no Hindi handwriting model)"}


def main():
    t = time.perf_counter()
    r = {"mit": mit(), "cubicasa": cubicasa(), "iiit": iiit()}
    pct = lambda x: "n/a" if x is None else f"{100 * x:.1f}%"
    L = [f"# Public-dataset evaluation ({providers.MODE} mode)", "", f"Run took {time.perf_counter() - t:.0f} s. Subsets fetched by scripts/fetch_public_data.py.", "",
         "| Dataset | What it tests | Result |", "|---|---|---|"]
    m, c, h = r["mit"], r["cubicasa"], r["iiit"]
    L.append(f"| MIT Indoor 67 ({m['images'] if m else 0} real photos) | room type from a photo | " +
             (f"{pct(m['accuracy'])} correct over 6 room types; 'computer lab' precision {pct(m['computer_lab_precision'])}, recall {pct(m['computer_lab_recall'])} |" if m else "needs FULL mode |"))
    L.append(f"| CubiCasa5K ({c['plans'] if c else 0} real floor plans) | finding rooms on raster plans | " +
             (f"room recall {pct(c['room_recall'])}, precision {pct(c['room_precision'])} ({c['rooms_found']} found, {c['rooms_true']} true) |" if c else "not fetched |"))
    L.append(f"| IIIT-HW-Dev ({h['words'] if h else 0} handwritten Hindi words) | reading Hindi handwriting | " +
             (f"CER {pct(h['cer'])}, exact {pct(h['exact'])} ({h['reader']}) |" if h else "needs FULL mode or not fetched |"))
    if m:
        L += ["", "## Room-type confusion (true -> predicted)", ""] + [f"- {k}: {v}" for k, v in m["confusion"].items()]
    if c:
        L += ["", c["note"]]
    L += ["", "Licences: MIT Indoor 67 mirror (Voxel51) tagged MIT; CubiCasa5K and IIIT-HW-Dev for research use, cite the papers. Data stays in realdata/public/."]
    out = os.path.join(ROOT, "docs", "EVAL-PUBLIC.md")
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

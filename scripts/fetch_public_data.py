"""Fetches small, research-use subsets of public datasets into realdata/public/ (gitignored). Never downloads more than needed:
- MIT Indoor 67 (Voxel51 mirror, MIT licence): 60 images per room type we care about.
- IIIT-HW-Dev v1 (CVIT, cite Dutta et al. DAS 2018): streams the archive, keeps 1,500 Hindi handwritten word images + labels.
- CubiCasa5K (Zenodo): reads floor plans out of the 5.5 GB zip with HTTP range requests (the zip never touches disk).
Large set (thousands, for capacity and false-alarm numbers):
- mit_full: all 15,620 MIT Indoor 67 photos (6 room types we score, 61 others as negatives).
- rvl: RVL-CDIP test shards (chainyo parquet, 16 document classes, real scans). Licence: IIT-CDIP / UCSF terms, research use.
- sroie: 973 real scanned receipts with key fields (ICDAR 2019). tsroie: 986 of the same receipts with tampered text (MIT licence).
- sifta: 192 real and forged document images.
- forgery: CASIA, COCO and Paris photos, authentic and tampered with masks (splicing, copy-move, editing, inpainting), test split.
Usage: python scripts/fetch_public_data.py [mit|iiit|cubicasa|mit_full|rvl|sroie|tsroie|sifta|forgery ...]"""
import io
import json
import os
import sys
import tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "realdata", "public")
ROOMS = ["computerroom", "classroom", "library", "office", "corridor", "meeting_room"]


def mit(per=60):
    from huggingface_hub import hf_hub_download
    d = os.path.join(OUT, "mit_indoor")
    s = json.load(open(hf_hub_download("Voxel51/IndoorSceneRecognition", "samples.json", repo_type="dataset", local_dir=d)))["samples"]
    rows = []
    for room in ROOMS:
        picks = [x for x in s if x["ground_truth"]["label"] == room][:per]
        for x in picks:
            hf_hub_download("Voxel51/IndoorSceneRecognition", x["filepath"], repo_type="dataset", local_dir=d)
            rows.append(f"{x['filepath']},{room}")
        print("mit", room, len(picks))
    open(os.path.join(d, "labels.csv"), "w").write("file,room\n" + "\n".join(rows) + "\n")


def iiit(keep=1500):
    import httpx
    d = os.path.join(OUT, "iiit_hw_dev")
    os.makedirs(d, exist_ok=True)
    url = "https://cvit.iiit.ac.in/images/Projects/wordlevel-Indicscripts/IIIT-HW-Hindi_v1.tar.gz"
    kept, texts = 0, 0
    with httpx.stream("GET", url, timeout=120, follow_redirects=True) as r:
        r.raise_for_status()

        class Pipe(io.RawIOBase):
            def __init__(self, it):
                self.it, self.buf = it, b""

            def readable(self):
                return True

            def readinto(self, b):
                while not self.buf:
                    try:
                        self.buf = next(self.it)
                    except StopIteration:
                        return 0
                n = min(len(b), len(self.buf))
                b[:n], self.buf = self.buf[:n], self.buf[n:]
                return n
        with tarfile.open(fileobj=io.BufferedReader(Pipe(r.iter_bytes(1 << 16))), mode="r|gz") as tf:
            for m in tf:
                if not m.isfile():
                    continue
                name = m.name.replace("\\", "/")
                if name.endswith(".txt") and "/" not in name.strip("./"):  # only the top-level split lists
                    open(os.path.join(d, name.replace("/", "__")), "wb").write(tf.extractfile(m).read())
                    texts += 1
                elif name.lower().endswith((".jpg", ".png")) and kept < keep and "/test" in name.lower():
                    dest = os.path.join(d, "img", name)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    open(dest, "wb").write(tf.extractfile(m).read())
                    kept += 1
    print("iiit images", kept, "label files", texts)


def mit_full():
    from huggingface_hub import snapshot_download
    d = os.path.join(OUT, "mit_indoor")
    retry(lambda: snapshot_download("Voxel51/IndoorSceneRecognition", repo_type="dataset", local_dir=d, max_workers=2))
    s = json.load(open(os.path.join(d, "samples.json")))["samples"]
    rows = [f"{x['filepath']},{x['ground_truth']['label']}" for x in s if os.path.exists(os.path.join(d, x["filepath"]))]
    open(os.path.join(d, "labels_full.csv"), "w").write("file,room\n" + "\n".join(rows) + "\n")
    print("mit_full", len(rows))


def rvl(per_class=350):
    """All 15 test shards, one at a time: keeps up to per_class documents of each of the 16 types, then deletes the shard."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download
    d = os.path.join(OUT, "rvl_cdip")
    out = os.path.join(d, "sample")
    os.makedirs(out, exist_ok=True)
    have = {}
    for f in glob_rec(out, ".parquet"):
        for lab in pq.read_table(f, columns=["label"]).column("label").to_pylist():
            have[lab] = have.get(lab, 0) + 1
    for i in range(15):
        dest = os.path.join(out, f"test-{i:02d}.parquet")
        if os.path.exists(dest):
            continue
        src = retry(lambda: hf_hub_download("chainyo/rvl-cdip", f"data/test-{i:05d}-of-00015.parquet", repo_type="dataset", local_dir=d))
        t = pq.read_table(src)
        labels = t.column("label").to_pylist()
        keep = []
        for j, lab in enumerate(labels):
            if have.get(lab, 0) < per_class:
                have[lab] = have.get(lab, 0) + 1
                keep.append(j)
        pq.write_table(t.take(pa.array(keep, type=pa.int64())), dest)
        os.remove(src)
        print("rvl shard", i, "kept", len(keep), flush=True)
    print("rvl documents", sum(have.values()), "types", len(have))


def sroie():
    from huggingface_hub import snapshot_download
    d = os.path.join(OUT, "sroie")
    retry(lambda: snapshot_download("ryanznie/SROIE_2019_with_labels", repo_type="dataset", local_dir=d, max_workers=2,
                                    allow_patterns=["*.jpg", "*.txt", "*.json"], ignore_patterns=["*layoutlm*", "*.bin"]))
    print("sroie jpg", len(glob_rec(d, ".jpg")))


def tsroie():
    from huggingface_hub import hf_hub_download
    d = os.path.join(OUT, "tsroie")
    p = hf_hub_download("Kyliroco/T-sroie", "sroie.tar", repo_type="dataset", local_dir=d)
    with tarfile.open(p) as t:
        t.extractall(d, filter="data")
    os.remove(p)
    print("tsroie jpg", len(glob_rec(d, ".jpg")))


def sifta():
    from huggingface_hub import snapshot_download
    snapshot_download("zodumair/sifta-document-forgery-dataset", repo_type="dataset", local_dir=os.path.join(OUT, "sifta"))
    print("sifta done")


def forgery(fakes_per_op=1500, reals=3000):
    """Test split only. Range requests: the 17 GB zip never touches disk."""
    import random
    from concurrent.futures import ThreadPoolExecutor
    from remotezip import RemoteZip
    url = "https://huggingface.co/datasets/RyuMasamichi/Image_Forgery_Localization_Datasets/resolve/main/trainsets.zip"
    d = os.path.join(OUT, "forgery")
    os.makedirs(d, exist_ok=True)
    with retry(lambda: RemoteZip(url)) as z:
        ops = [json.loads(x) for x in z.read("trainsets/fake_by_type/classification_manifest.jsonl").decode().splitlines()]
        man = [json.loads(x) for x in z.read("trainsets/manifest.jsonl").decode().splitlines()]
    rnd = random.Random(7)
    pick = []
    for op in ("splicing", "copy_move", "traditional_editing", "inpainting_removal"):
        rows = [r for r in ops if r["split"] == "test" and r["operation"] == op]
        pick += [(r["original_image_path"], r["original_mask_path"], op) for r in rnd.sample(rows, min(fakes_per_op, len(rows)))]
    real = [r for r in man if r["split"] == "test" and r["manipulation_type"] == "authentic"]
    pick += [(r["image_path"], None, "authentic") for r in rnd.sample(real, min(reals, len(real)))]
    names = [p for a, m, _ in pick for p in (a, m) if p]

    def grab(chunk):
        with retry(lambda: RemoteZip(url)) as zz:
            for n in chunk:
                dest = os.path.join(d, n)
                if not os.path.exists(dest):
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    open(dest, "wb").write(retry(lambda: zz.read("trainsets/" + n)))
    with ThreadPoolExecutor(3) as ex:
        list(ex.map(grab, [names[i::3] for i in range(3)]))
    open(os.path.join(d, "labels.csv"), "w").write("image,mask,operation\n" + "\n".join(f"{a},{m or ''},{o}" for a, m, o in pick) + "\n")
    print("forgery images", len(pick))


def retry(fn, tries=12):
    """Anonymous Hugging Face downloads hit 429 when fast: back off and try again."""
    import time
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            if i == tries - 1 or not any(x in str(e) for x in ("429", "Too Many", "connection", "Connection", "LocalEntryNotFound", "timed out")):
                raise
            time.sleep(min(600, 20 * 2 ** i))


def glob_rec(d, ext):
    return [os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs if f.lower().endswith(ext)]


def cubicasa(n=60):
    from remotezip import RemoteZip
    d = os.path.join(OUT, "cubicasa5k")
    os.makedirs(d, exist_ok=True)
    url = "https://zenodo.org/records/2613548/files/cubicasa5k.zip?download=1"
    with retry(lambda: RemoteZip(url)) as z:
        names = z.namelist()
        plans = sorted({x.rsplit("/", 1)[0] for x in names if x.endswith("/model.svg") and "/high_quality_architectural/" in x})[:n]
        for p in plans:
            for f in ("F1_scaled.png", "model.svg"):
                if f"{p}/{f}" in names and not os.path.exists(os.path.join(d, p, f)):
                    z.extract(f"{p}/{f}", d)
        print("cubicasa plans", len(plans), "of", len({x.rsplit('/', 1)[0] for x in names if x.endswith('/model.svg')}))


if __name__ == "__main__":
    which = sys.argv[1:] or ["mit", "iiit", "cubicasa"]
    for w in which:
        try:
            {"mit": mit, "iiit": iiit, "cubicasa": cubicasa, "mit_full": mit_full, "rvl": rvl, "sroie": sroie, "tsroie": tsroie,
             "sifta": sifta, "forgery": forgery, "cubicasa_1000": lambda: cubicasa(1000)}[w]()
        except Exception as e:
            print(w, "FAILED:", type(e).__name__, str(e)[:300])

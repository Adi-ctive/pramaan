"""Fetches small, research-use subsets of public datasets into realdata/public/ (gitignored). Never downloads more than needed:
- MIT Indoor 67 (Voxel51 mirror, MIT licence): 60 images per room type we care about.
- IIIT-HW-Dev v1 (CVIT, cite Dutta et al. DAS 2018): streams the archive, keeps 1,500 Hindi handwritten word images + labels.
- CubiCasa5K (Zenodo): reads 60 floor plans out of the 5.5 GB zip with HTTP range requests (the zip never touches disk).
Usage: python scripts/fetch_public_data.py [mit|iiit|cubicasa ...]"""
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


def cubicasa(n=60):
    from remotezip import RemoteZip
    d = os.path.join(OUT, "cubicasa5k")
    os.makedirs(d, exist_ok=True)
    url = "https://zenodo.org/records/2613548/files/cubicasa5k.zip?download=1"
    with RemoteZip(url) as z:
        names = z.namelist()
        plans = sorted({x.rsplit("/", 1)[0] for x in names if x.endswith("/model.svg") and "/high_quality_architectural/" in x})[:n]
        for p in plans:
            for f in ("F1_scaled.png", "model.svg"):
                if f"{p}/{f}" in names:
                    z.extract(f"{p}/{f}", d)
        print("cubicasa plans", len(plans), "of", len({x.rsplit('/', 1)[0] for x in names if x.endswith('/model.svg')}))


if __name__ == "__main__":
    which = sys.argv[1:] or ["mit", "iiit", "cubicasa"]
    for w in which:
        try:
            {"mit": mit, "iiit": iiit, "cubicasa": cubicasa}[w]()
        except Exception as e:
            print(w, "FAILED:", type(e).__name__, str(e)[:300])

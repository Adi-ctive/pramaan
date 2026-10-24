"""Model providers by role. MODE=LITE uses CPU-only classical/text-layer providers; MODE=FULL loads local GPU models
lazily (docTR OCR, TrOCR handwriting, Grounding DINO, CLIP, a small instruct LLM). Any provider that fails to load
degrades to its LITE counterpart and says so in `status()`. UI and reports name models by role, never by brand."""
import json
import os
import re
import threading

import numpy as np

MODE = os.environ.get("MODE", "LITE").upper()
_lock = threading.Lock()
_cache, _errors = {}, {}


def _device():
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _load(name, fn):
    if name in _cache or name in _errors:
        return _cache.get(name)
    with _lock:
        if name not in _cache and name not in _errors:
            try:
                _cache[name] = fn()
            except Exception as e:
                _errors[name] = f"{type(e).__name__}: {str(e)[:160]}"
    return _cache.get(name)


# ---------------- OCR Model
class OCRModel:
    role = "OCR Model"

    def read(self, img):
        """Returns lines: [{text, conf, bbox:[x,y,w,h] fractions}] or None when unavailable."""
        if MODE != "FULL":
            return None
        m = _load("doctr", lambda: __import__("doctr.models", fromlist=["ocr_predictor"]).ocr_predictor(
            det_arch="db_resnet50", reco_arch="crnn_vgg16_bn", pretrained=True).to(_device()))
        if m is None:
            return None
        res = m([np.array(img.convert("RGB"))]).export()
        lines = []
        for block in res["pages"][0]["blocks"]:
            for ln in block["lines"]:
                words = ln["words"]
                if not words:
                    continue
                (x0, y0), (x1, y1) = ln["geometry"]
                lines.append({"text": " ".join(w["value"] for w in words), "conf": round(float(np.mean([w["confidence"] for w in words])), 3),
                              "bbox": [round(x0, 4), round(y0, 4), round(x1 - x0, 4), round(y1 - y0, 4)],
                              "words": [{"text": w["value"], "conf": round(float(w["confidence"]), 3), "bbox": [w["geometry"][0][0], w["geometry"][0][1],
                                         w["geometry"][1][0] - w["geometry"][0][0], w["geometry"][1][1] - w["geometry"][0][1]]} for w in words]})
        lines.sort(key=lambda l: (round(l["bbox"][1], 2), l["bbox"][0]))
        return lines


# ---------------- Handwriting Model
class HandwritingModel:
    role = "Handwriting Model"

    def read(self, crop):
        """Returns {text, conf} for one line crop, or None when unavailable."""
        if MODE != "FULL":
            return None

        def mk():
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel
            n = os.environ.get("HTR_MODEL", "microsoft/trocr-base-handwritten")
            return TrOCRProcessor.from_pretrained(n), VisionEncoderDecoderModel.from_pretrained(n).to(_device()).eval()
        m = _load("trocr", mk)
        if m is None:
            return None
        import torch
        proc, model = m
        px = proc(images=crop.convert("RGB"), return_tensors="pt").pixel_values.to(_device())
        with torch.no_grad():
            out = model.generate(px, max_new_tokens=32, output_scores=True, return_dict_in_generate=True)
        text = proc.batch_decode(out.sequences, skip_special_tokens=True)[0].strip()
        probs = [float(torch.softmax(s, -1).max()) for s in out.scores]
        return {"text": text, "conf": round(float(np.exp(np.mean(np.log(np.maximum(probs, 1e-6))))), 3) if probs else 0.0}


# ---------------- Object Detector
class ObjectDetector:
    role = "Object Detector"

    def count(self, img, label):
        if MODE == "FULL":
            def mk():
                from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
                n = os.environ.get("DETECTOR_MODEL", "IDEA-Research/grounding-dino-tiny")
                return AutoProcessor.from_pretrained(n), AutoModelForZeroShotObjectDetection.from_pretrained(n).to(_device()).eval()
            m = _load("gdino", mk)
            if m is not None:
                import torch
                proc, model = m
                inp = proc(images=img.convert("RGB"), text=label.lower() + ".", return_tensors="pt").to(_device())
                with torch.no_grad():
                    out = model(**inp)
                r = proc.post_process_grounded_object_detection(out, inp.input_ids, box_threshold=0.35, text_threshold=0.25,
                                                                target_sizes=[img.size[::-1]])[0]
                boxes = r["boxes"].cpu().numpy().tolist()
                keep = [boxes[i] for i in _nms(boxes, r["scores"].cpu().numpy().tolist())]
                if keep:  # drop boxes far larger than the typical instance (boards, whole rows)
                    med = float(np.median([(b[2] - b[0]) * (b[3] - b[1]) for b in keep]))
                    keep = [b for b in keep if (b[2] - b[0]) * (b[3] - b[1]) <= 4 * med]
                return {"count": len(keep), "conf": 0.75, "detector": self.role, "boxes": [[round(v, 1) for v in b] for b in keep[:60]]}
        from . import infra
        v = infra.vlm_count(img, label)
        if v and "count" in v:
            return {**v, "conf": 0.8, "detector": self.role}
        return {"count": infra.classical_count(img), "conf": 0.6, "detector": f"{self.role} (classical, synthetic-grade)"}


def _nms(boxes, scores, iou=0.5):
    order = np.argsort(scores)[::-1]
    keep = []
    for i in order:
        if all(_iou(boxes[i], boxes[j]) < iou for j in keep):
            keep.append(i)
    return keep


def _iou(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua else 0


# ---------------- Scene Classifier + Image Embeddings
class SceneClassifier:
    role = "Scene Classifier"

    def _m(self):
        if MODE != "FULL":
            return None

        def mk():
            from transformers import CLIPModel, CLIPProcessor
            n = os.environ.get("CLIP_MODEL", "openai/clip-vit-base-patch32")
            return CLIPProcessor.from_pretrained(n), CLIPModel.from_pretrained(n).to(_device()).eval()
        return _load("clip", mk)

    def classify(self, img, labels):
        m = self._m()
        if m is None:
            return None
        import torch
        proc, model = m
        inp = proc(text=[f"a photo of a {l}" for l in labels], images=img.convert("RGB"), return_tensors="pt", padding=True).to(_device())
        with torch.no_grad():
            p = model(**inp).logits_per_image.softmax(-1)[0].cpu().numpy()
        i = int(p.argmax())
        return {"label": labels[i], "conf": round(float(p[i]), 3)}

    def embed(self, img):
        m = self._m()
        if m is None:
            return None
        import torch
        proc, model = m
        with torch.no_grad():
            v = model.get_image_features(**proc(images=img.convert("RGB"), return_tensors="pt").to(_device()))[0]
        v = v / v.norm()
        return [round(float(x), 5) for x in v.cpu().numpy()]


# ---------------- Reasoning LLM
class ReasoningLLM:
    role = "Reasoning LLM"

    def available(self):
        return MODE == "FULL" and self._m() is not None or bool(os.environ.get("GROQ_KEY"))

    def _m(self):
        if MODE != "FULL":
            return None

        def mk():
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            n = os.environ.get("LLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
            return AutoTokenizer.from_pretrained(n), AutoModelForCausalLM.from_pretrained(n, torch_dtype=torch.float16).to(_device()).eval()
        return _load("llm", mk)

    def complete(self, system, user, max_tokens=400):
        """Document-derived text must already be wrapped in <document_data> by the caller."""
        key = os.environ.get("GROQ_KEY")
        if MODE != "FULL" and key:
            import httpx
            r = httpx.post("https://api.groq.com/openai/v1/chat/completions", timeout=30, headers={"Authorization": f"Bearer {key}"},
                           json={"model": os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"), "temperature": 0, "max_tokens": max_tokens,
                                 "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        m = self._m()
        if m is None:
            raise RuntimeError("Reasoning LLM unavailable")
        import torch
        tok, model = m
        ids = tok.apply_chat_template([{"role": "system", "content": system}, {"role": "user", "content": user}],
                                      add_generation_prompt=True, return_tensors="pt").to(_device())
        with torch.no_grad():
            out = model.generate(ids, max_new_tokens=max_tokens, do_sample=False)
        return tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True)


def envelope(doc_id, text):
    text = re.sub(r"</?document_data[^>]*>", "", text)
    return f'<document_data source="doc:{doc_id}">\n{text}\n</document_data>'


ocr, htr, detector, scene, llm = OCRModel(), HandwritingModel(), ObjectDetector(), SceneClassifier(), ReasoningLLM()


def status():
    out = {"mode": MODE, "device": _device() if MODE == "FULL" else "cpu"}
    names = {"OCR Model": "doctr", "Handwriting Model": "trocr", "Object Detector": "gdino", "Scene Classifier": "clip", "Reasoning LLM": "llm"}
    for role, key in names.items():
        if MODE != "FULL":
            lite = {"OCR Model": "PDF text layer only", "Handwriting Model": "off (manual review)", "Object Detector": "classical counter",
                    "Scene Classifier": "off", "Reasoning LLM": "template (NullLLM)" if not os.environ.get("GROQ_KEY") else "hosted LLM"}
            out[role] = lite[role]
        else:
            out[role] = "loaded" if key in _cache else (f"failed: {_errors[key]}" if key in _errors else "loads on first use")
    return out


def warmup():
    """Loads every FULL model once and returns load status (used by the GPU probe)."""
    from PIL import Image
    img = Image.new("RGB", (64, 64), "white")
    for fn in (lambda: ocr.read(img), lambda: htr.read(img), lambda: detector.count(img, "monitor"), lambda: scene.classify(img, ["room", "lab"]),
               lambda: llm.complete("Reply OK.", "ping", 4)):
        try:
            fn()
        except Exception as e:
            _errors.setdefault("warmup", str(e)[:160])
    return status()


def dumps(o):
    return json.dumps(o, default=str)

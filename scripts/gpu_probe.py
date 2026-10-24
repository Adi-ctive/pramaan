"""GPU and model probe. Writes docs/VERSIONS.md with devices, package versions and FULL-mode model load status."""
import importlib.metadata as md
import os
import platform
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PKGS = ["fastapi", "pymongo", "pypdfium2", "pypdf", "pyhanko", "zxing-cpp", "pillow", "numpy", "rapidfuzz", "cryptography", "argon2-cffi",
        "pyjwt", "pyotp", "jinja2", "reportlab", "langgraph", "torch", "torchvision", "transformers", "python-doctr", "playwright"]
MODELS = {"OCR Model": "docTR db_resnet50 + crnn_vgg16_bn", "Handwriting Model": os.environ.get("HTR_MODEL", "microsoft/trocr-base-handwritten"),
          "Object Detector": os.environ.get("DETECTOR_MODEL", "IDEA-Research/grounding-dino-tiny"),
          "Scene Classifier": os.environ.get("CLIP_MODEL", "openai/clip-vit-base-patch32"), "Reasoning LLM": os.environ.get("LLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")}


def main():
    L = ["# Versions and hardware", "", f"Probed {time.strftime('%Y-%m-%d %H:%M')} on {platform.platform()}, Python {platform.python_version()}.", ""]
    try:
        smi = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
    except OSError:
        smi = ""
    L += ["## GPU", "", smi or "No NVIDIA GPU found (LITE mode only).", ""]
    try:
        import torch
        L.append(f"PyTorch {torch.__version__}, CUDA available: {torch.cuda.is_available()}" + (f", device: {torch.cuda.get_device_name(0)}, CUDA {torch.version.cuda}" if torch.cuda.is_available() else ""))
    except ImportError:
        L.append("PyTorch not installed (LITE only). Install requirements-full.txt for FULL mode.")
    L += ["", "PaddleOCR/PaddlePaddle: not used. The OCR Model is docTR (PyTorch), the spec's documented fallback.",
          "Ollama: not installed on this machine. Models run in-process through transformers instead (see DECISIONS.md).", "",
          "## Packages", "", "| Package | Version |", "|---|---|"]
    for p in PKGS:
        try:
            L.append(f"| {p} | {md.version(p)} |")
        except md.PackageNotFoundError:
            L.append(f"| {p} | not installed |")
    L += ["", "## FULL-mode models", "", "| Role | Model | Status |", "|---|---|---|"]
    if "--load" in sys.argv:
        os.environ["MODE"] = "FULL"
        from pramaan import providers
        providers.MODE = "FULL"
        t = time.time()
        st = providers.warmup()
        for role, name in MODELS.items():
            L.append(f"| {role} | {name} | {st.get(role)} |")
        try:
            import torch
            L += ["", f"Peak VRAM with all five loaded: {torch.cuda.max_memory_allocated() / 1e9:.2f} GB; load time {time.time() - t:.0f} s."]
        except Exception:
            pass
    else:
        L += [f"| {r} | {m} | not loaded (run with --load) |" for r, m in MODELS.items()]
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "VERSIONS.md")
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

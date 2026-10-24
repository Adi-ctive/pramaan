# Versions and hardware

Probed 2026-10-24 12:33 on Windows-11-10.0.26300-SP0, Python 3.13.2.

## GPU

NVIDIA GeForce RTX 4050 Laptop GPU, 6141 MiB, 610.74

PyTorch 2.6.0+cu124, CUDA available: True, device: NVIDIA GeForce RTX 4050 Laptop GPU, CUDA 12.4

PaddleOCR/PaddlePaddle: not used. The OCR Model is docTR (PyTorch), the spec's documented fallback.
Ollama: not installed on this machine. Models run in-process through transformers instead (see DECISIONS.md).

## Packages

| Package | Version |
|---|---|
| fastapi | 0.115.6 |
| pymongo | 4.10.1 |
| pypdfium2 | 4.30.0 |
| pypdf | 5.1.0 |
| pyhanko | 0.25.3 |
| zxing-cpp | 3.1.1 |
| pillow | 11.0.0 |
| numpy | 2.1.3 |
| rapidfuzz | 3.10.1 |
| cryptography | 44.0.0 |
| argon2-cffi | 23.1.0 |
| pyjwt | 2.10.1 |
| pyotp | 2.9.0 |
| jinja2 | 3.1.5 |
| reportlab | 4.2.5 |
| langgraph | 0.3.5 |
| torch | 2.6.0+cu124 |
| torchvision | 0.21.0+cu124 |
| transformers | 4.49.0 |
| python-doctr | 0.11.0 |
| playwright | 1.50.0 |

## FULL-mode models

| Role | Model | Status |
|---|---|---|
| OCR Model | docTR db_resnet50 + crnn_vgg16_bn | loaded |
| Handwriting Model | microsoft/trocr-base-handwritten | loaded |
| Object Detector | IDEA-Research/grounding-dino-tiny | loaded |
| Scene Classifier | openai/clip-vit-base-patch32 | loaded |
| Reasoning LLM | Qwen/Qwen2.5-1.5B-Instruct | loaded |

Peak VRAM with all five loaded: 5.92 GB; load time 104 s.

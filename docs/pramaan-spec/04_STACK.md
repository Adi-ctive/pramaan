# 04 — Technology Stack (free, prototype)

Everything below is free and self-hostable. Pin exact versions in `pyproject.toml`, `package.json` and the compose file when scaffolding. Use the latest stable release that installs cleanly; record the chosen versions in `docs/VERSIONS.md`.

## 1. Runtime and infrastructure
| Concern | Choice | Licence | Notes |
|---|---|---|---|
| Containers | Docker Desktop (WSL2) + Compose | — | NVIDIA Container Toolkit for the GPU worker |
| Reverse proxy / TLS | Caddy | Apache-2.0 | `tls internal` for local HTTPS |
| Database | PostgreSQL 16 + pgvector | PostgreSQL | One database, schemas `public`, `records` |
| Queue / cache | Redis 7 | BSD | Celery broker and result backend |
| Object storage | MinIO | AGPL-3.0 | Fine for the prototype; S3-compatible, so it's swappable |
| Malware scan | ClamAV (`clamav/clamav` image) | GPL | Upload scanning via `clamd` |
| Mail (dev) | Mailpit | MIT | Shows alert emails in a web UI |
| LLM/VLM serving | Ollama (native on host) | MIT | `host.docker.internal:11434` |

## 2. Backend
| Concern | Choice |
|---|---|
| Language | Python 3.11 |
| API | FastAPI + Uvicorn, Pydantic v2, pydantic-settings |
| ORM / migrations | SQLAlchemy 2 + Alembic, psycopg 3 |
| Jobs | Celery (queues `cpu`, `gpu`, `agent`) |
| Agents | LangGraph |
| Auth / crypto | `argon2-cffi` (passwords), PyJWT, `pyotp` (TOTP), `cryptography` (AES-GCM field encryption, Ed25519, demo CA) |
| Rate limiting | `slowapi` |
| PDF parsing | `pypdf`, `pdfplumber`, `pikepdf` (structure and incremental updates), `pypdfium2` (rasterise) |
| PDF signatures | `pyHanko` (sign synthetic documents, validate signatures) |
| Images | OpenCV, Pillow, scikit-image |
| QR | OpenCV `QRCodeDetector` (primary), `qrcode` (generation) |
| Metadata | `exiftool` (binary in the image) via `PyExifTool`; Pillow EXIF as a fallback |
| Fuzzy / entity | RapidFuzz, `indic-transliteration`, `unidecode` |
| Dates / holidays | `dateparser`, `holidays` (IN) |
| Hashing / similarity | `imagehash` (pHash), pgvector cosine |
| Anomaly stats | scikit-learn (IsolationForest) |
| Reports | Jinja2 + WeasyPrint (runs in the Linux container) |
| Testing | pytest, pytest-asyncio, httpx, coverage, factory-boy |
| Lint / format | ruff, mypy (core modules) |

## 3. ML models (referenced by role in UI and code)
| Role | Default implementation | Licence | LITE mode |
|---|---|---|---|
| OCR Model | PaddleOCR (PP-OCR, `en` + `hi`) | Apache-2.0 | Tesseract (`eng+hin`) |
| OCR fallback | docTR (PyTorch) | Apache-2.0 | — |
| Handwriting Model | VLM `qwen2.5vl:7b` via Ollama | Apache-2.0 (7B) | TrOCR `microsoft/trocr-base-handwritten` (CPU, English) |
| Document Classifier | VLM zero-shot over the taxonomy labels | — | Keyword/anchor classifier |
| Field Extractor | VLM with JSON-schema prompt + regex validators | — | Anchor/regex extractor |
| Object / Region Detector | Grounding DINO `IDEA-Research/grounding-dino-tiny` (HF transformers) | Apache-2.0 | Disabled → `MANUAL_REVIEW` |
| Scene Classifier | CLIP `openai/clip-vit-base-patch32` | MIT | Same (CPU is fine) |
| Text Embeddings | `intfloat/multilingual-e5-base` (768-d) | MIT | Same |
| Image Embeddings | CLIP image (512-d) | MIT | Same |
| Reasoning LLM | `qwen2.5:7b-instruct` via Ollama (or `llama3.1:8b`) | Apache-2.0 / Llama licence | NullLLM (templates) |
| Tamper Localiser | Classical: ELA, noise residual, SIFT copy-move (OpenCV) | — | Same |
| Signature Similarity (C) | Small Siamese CNN (PyTorch) trained on synthetic signatures | — | Disabled |

**GPU notes:**
- The RTX 5060 Ti (Blackwell, sm_120) needs CUDA 12.8+ builds. PyTorch cu128 wheels support it.
- **Verify that PaddlePaddle's GPU wheel supports sm_120 on day 1.** If it does not, run PaddleOCR on the RTX 2000 Ada (sm_89) or on CPU, or switch the OCR provider to docTR (PyTorch) with `PROVIDER_OCR=doctr`.
- `worker-gpu` runs with concurrency 1 and lazy-loads models. Ollama models load on demand. Keep VRAM under about 12 GB by not keeping the VLM and Grounding DINO hot at the same time (set Ollama `keep_alive` low during infrastructure stages).

## 4. Frontend
| Concern | Choice |
|---|---|
| Console | React 18 + Vite + TypeScript |
| UI kit | Tailwind CSS + shadcn/ui (Radix), lucide-react |
| Data | TanStack Query, TanStack Table, Zustand (UI state) |
| Routing | React Router |
| Charts | Apache ECharts (`echarts-for-react`) |
| Docs viewer | pdf.js (`pdfjs-dist`) + canvas overlay layer |
| YAML editor | Monaco (`@monaco-editor/react`) + JSON-schema validation |
| i18n | i18next (en, hi) |
| Widget | Vanilla TypeScript, Shadow DOM, built with Vite library mode into one `pramaan.js` |
| Mock hosts | Static HTML + small TS, served by `mock-hosts` FastAPI |
| Testing | Vitest + Testing Library; Playwright for the end-to-end demo flow |

## 5. Synthetic data and evaluation
| Concern | Choice |
|---|---|
| Fake entities | Faker (`en_IN`, `hi_IN`) |
| Document rendering | ReportLab (PDF), Jinja2 HTML → WeasyPrint, Pillow for raster |
| Handwriting | OFL fonts from Google Fonts (e.g. Caveat, Kalam for Devanagari), with per-character jitter |
| Stamps / seals | Procedurally drawn SVG/Pillow circular stamps with fictional issuer names |
| Scan realism | Augraphy (MIT) degradation pipelines |
| Forgeries | Custom `synth/forgeries.py` (see 06_BUILD_PLAN.md) |
| Infra photos | Team-captured photos of their own college rooms (with permission), plus openly licensed images; EXIF written with `piexif` for test cases |
| Metrics | scikit-learn metrics, `jiwer` (CER/WER) |

## 6. Dev tooling
- `Makefile` targets: `up`, `up-gpu`, `down`, `seed`, `demo`, `test`, `eval`, `lint`, `lite`.
- pre-commit with ruff, prettier and eslint.
- `.env.example` with every variable documented; secrets never committed.
- `docs/VERSIONS.md` records the pinned versions and model hashes actually used.

## 7. Commercial swap path (for the pitch slide)
Each role maps to an interface, so production can substitute commercial or government services without code changes. For example: the OCR Model becomes a commercial OCR API, the Records Adapter becomes the real AICTE portal API, and the Verification Adapters become DigiLocker, issuer APIs or e-Sign validation.

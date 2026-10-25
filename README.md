# PRAMAAN

AI-assisted validation for AICTE approval applications (Smart India Hackathon 2026, problem statement SIH26261).
Institutions upload documents through their usual portal. PRAMAAN reads them, checks them against a configurable rule pack and AICTE records,
confirms them with the issuing office, looks for signs of editing, checks infrastructure photos, and shows officers what is wrong and where.
Officers make every decision. All institutions, issuers and documents in this repo are fictional.

Live (LITE mode): https://pramaan-sih26.vercel.app

## Quickstart, LITE mode (CPU only)

Needs Python 3.11 or newer and Node 18 or newer.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt pyotp langgraph jinja2 pytest playwright   # Linux/macOS: .venv/bin/python
npm install
.venv/Scripts/python tasks.py secrets
.venv/Scripts/python tasks.py demo
```

Open http://localhost:5180 and click "Enter as Senior Officer". Without `MONGODB_URI` the API uses an in-memory store that seeds itself.
Put `MONGODB_URI=...` in `.env` to use MongoDB instead.

With GNU make: `make secrets && make demo` (set `PY=.venv/Scripts/python` on Windows).

## Quickstart, FULL mode (NVIDIA GPU, 6 GB or more)

```bash
.venv/Scripts/python -m pip install -r requirements-full.txt
.venv/Scripts/python tasks.py probe        # downloads and loads the five models, writes docs/VERSIONS.md
set MODE=FULL                              # PowerShell: $env:MODE="FULL"   bash: export MODE=FULL
.venv/Scripts/python tasks.py demo
```

FULL adds the OCR Model and Handwriting Model for scanned pages, the Object Detector and Scene Classifier for photos, image embeddings for
duplicate search, and the agents. Agents need Ollama with `ollama pull qwen2.5:7b-instruct`. They run in FULL mode
(`AGENT_MODE=on|off`) and fall back to the fixed pipeline if Ollama is not running.

To give the hosted site a local AI backend, put `MONGODB_URI` (the site's database) in `.env.worker` and run
`python tasks.py worker`. The console then shows "Local AI: online", and an officer can press "Re-check with local AI"
on any application. The agent timeline appears under the Timeline tab.

## Other targets

| Command | What it does |
|---|---|
| `python tasks.py test` | unit and integration tests (pytest) |
| `python tasks.py e2e` | Playwright tests for the 8 acceptance criteria (starts its own LITE servers) |
| `python tasks.py eval` | full evaluation, writes docs/EVAL.md (use MODE=FULL for model metrics) |
| `python tasks.py seed` | reload demo data |
| `python tasks.py worker` | local AI worker for the hosted site (FULL mode plus agents) |
| `python scripts/verify_agents.py` | Phase 7 checks against the real local LLM, writes docs/AGENTS-VERIFY.json |
| `python tasks.py cron` | nightly jobs once: SLA alerts, retention purge, audit anchor |
| `python tasks.py down` | stop servers started by `up` or `demo` |

## Layout

| Path | Contents |
|---|---|
| `pramaan/` | API (FastAPI), engine, agents, providers, verification, forensics, seed, evaluation |
| `rulepacks/` | YAML rule packs (all numbers are demo values) |
| `src/` | officer console (React, Vite, Tailwind) |
| `public/widget/v1/pramaan.js` | embeddable upload widget (Shadow DOM, no framework) |
| `public/host-a`, `public/host-b` | two mock portals using the same engine |
| `public/samples/` | synthetic sample files for the demo |
| `tests/`, `e2e/` | pytest and Playwright suites |
| `docs/` | spec, decisions, progress, demo script, evaluation reports |

## Deploy (Vercel)

`vercel deploy --prod`. Environment: `MONGODB_URI`, `SESSION_SECRET`, `FIELD_KEY`, `SEED_TOKEN`, `DEMO_PASSWORD`, `DEMO=true`, `MODE=LITE`,
optional `CRON_SECRET`, `GROQ_KEY`, `SMTP_HOST`. Seed with `POST /api/admin/seed` then `POST /api/admin/seed-next` until it returns done
(header `X-Seed-Token`).

Prototype. Findings are decision support only. Statutory scrutiny, inspections and final decisions stay with the competent authority.
